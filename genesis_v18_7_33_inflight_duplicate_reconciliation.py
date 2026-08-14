# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.33 — reconcile an in-flight duplicate after lock wait.

The first v18.7.31 cross-platform CI run exposed a useful boundary mistake: a
second cooperating caller that observed ``CALL_ENTERING`` immediately classified
the request as UNDETERMINED, even while the first caller still held the canonical
world lock and was about to publish a valid receipt.

That behavior was safe against duplication but unnecessarily pessimistic. v18.7.33
keeps the failed v18.7.31 run as evidence and changes only the observation order:

1. bind/validate the same caller request identity;
2. if already SETTLED, replay immediately;
3. otherwise enter the same canonical world lock;
4. re-read request state after lock acquisition;
5. if the predecessor settled while we waited, replay its receipt;
6. if CALL_ENTERING is still present after the predecessor lock is gone, classify
   the outcome UNDETERMINED and never re-execute automatically.

Therefore an active duplicate can converge to a receipt, while a crash residue
remains fail-closed. Lock waiting is evidence of synchronization, not evidence
that the prior world call completed; the post-lock durable state decides.
"""
from __future__ import annotations

from genesis_v18_7_31_portable_receipt_runtime import (
    PortableCrashPoint,
    PortableReceiptRuntimeAdapter,
    PortableRuntimeControlError,
    PortableRuntimeOutcomeUndetermined,
)

INFLIGHT_DUPLICATE_RECONCILIATION_VERSION = "18.7.33"
INFLIGHT_DUPLICATE_RECONCILIATION_SCHEMA = "janus.genesis.inflight_duplicate_reconciliation.v1"


class ReconciledPortableReceiptRuntimeAdapter(PortableReceiptRuntimeAdapter):
    """Wait for the world lock before deciding whether CALL_ENTERING is stale."""

    def execute(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        action: str,
    ):
        action_text = str(action).strip()
        record = self.store.bind(
            client_id=client_id,
            request_id=request_id,
            actor_id=actor_id,
            action=action_text,
        )
        if record.state == "SETTLED":
            return self._replay(record)
        if record.state not in {"BOUND", "CALL_ENTERING", "UNDETERMINED_EXCEPTION"}:
            raise PortableRuntimeControlError(f"UNKNOWN_REQUEST_STATE:{record.state}")
        if record.state == "BOUND":
            self.crash_injector.hit(PortableCrashPoint.AFTER_BOUND)

        with self.world_lock.exclusive():
            current = self.store.get(client_id=record.client_id, request_id=record.request_id)
            if current is None:
                raise PortableRuntimeControlError("REQUEST_DISAPPEARED")
            if current.state == "SETTLED":
                return self._replay(current)
            if current.state in {"CALL_ENTERING", "UNDETERMINED_EXCEPTION"}:
                raise PortableRuntimeOutcomeUndetermined(
                    f"effect_key={current.effect_key};state={current.state};"
                    "predecessor_lock_released_without_settled_receipt"
                )
            if current.state != "BOUND":
                raise PortableRuntimeControlError(f"UNKNOWN_REQUEST_STATE:{current.state}")

            entering = self.store.transition_call_entering(current)
            self.crash_injector.hit(PortableCrashPoint.AFTER_CALL_ENTERING_BEFORE_WORLD)
            try:
                result = self.world.process_action(entering.actor_id, action_text)
            except BaseException as exc:
                self.store.mark_undetermined_exception(entering, exc)
                raise

            self.crash_injector.hit(PortableCrashPoint.AFTER_WORLD_BEFORE_RECEIPT)
            internal = result.to_dict(internal=True)
            settled = self.store.settle(entering, result_internal=internal)
            self.crash_injector.hit(PortableCrashPoint.AFTER_RECEIPT)
            replayed = self._replay(settled)
            if replayed.to_dict(internal=True) != internal:
                raise PortableRuntimeControlError("POST_SETTLEMENT_REPLAY_DRIFT")
            return result


__all__ = [
    "INFLIGHT_DUPLICATE_RECONCILIATION_VERSION",
    "INFLIGHT_DUPLICATE_RECONCILIATION_SCHEMA",
    "ReconciledPortableReceiptRuntimeAdapter",
]
