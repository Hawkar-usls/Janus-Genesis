#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JANUS Habitat controlled process-death handoff gauntlet v1.

This additive integration witness joins three exact component surfaces:

- Janus_Genesis #158 boot controller @ 9622241625eb6e6ee56f0fe955bdcf5a2a7bc607
- janus-distributed-ai-swarm #6 lease fencing @ 2b72afe83dfb7318858a103657648bbc668ee6c3
- Demi_Head #28 NOHAND peer @ e287e62fc41d473c2add3eded92d3d163365b9dc

The experiment deliberately kills worker-A after a durable checkpoint + NOHAND
handoff, then starts a fresh worker-B process with only durable filesystem state.
The SWARM fence is checked immediately before every controller checkpoint commit
through ``FencedCheckpointStore``.  Worker-B takes over only after worker-A's
lease is stale, resumes the same durable objective/checkpoint, completes it,
and commits one idempotent completion receipt.  A reconstructed stale worker-A
token is then challenged and must fail before the checkpoint delegate is called.

Claim ceiling: this is a controlled cross-process, single-host SQLite integration
witness.  It does not by itself close the full #162 acceptance gauntlet, resident
MODEL.CALL, real 44-source replay, federation finalization, or cross-host shared
filesystem validation.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

GENESIS_ROOT = Path(__file__).resolve().parents[1]
if str(GENESIS_ROOT) not in sys.path:
    sys.path.insert(0, str(GENESIS_ROOT))

BOOT_CONTROLLER_HEAD = "9622241625eb6e6ee56f0fe955bdcf5a2a7bc607"
SWARM_FENCE_HEAD = "2b72afe83dfb7318858a103657648bbc668ee6c3"
DEMIHEAD_NOHAND_HEAD = "e287e62fc41d473c2add3eded92d3d163365b9dc"
DEMIURGE_SUPERVISOR_HEAD = "74c8a9dc090dba4d3bd7d497e1ff75223e6fe6c0"
SCHEMA = "janus.habitat.process_death_gauntlet.v1"
OBJECTIVE_ID = "habitat-g8-g9-g11-001"
WORKER_A_EXIT = 77
A_NOW = 1000.0
A_COMMIT_NOW = 1000.5
A_TTL = 2.0
B_NOW = 1003.0
B_COMMIT_NOW = 1003.5
B_TTL = 5.0
STALE_A_NOW = 1003.75


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_create_only(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(data)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != data:
            raise RuntimeError(f"CREATE_ONLY_COLLISION:{path}")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: expected JSON object")
    return value


def _install_external_paths(swarm_root: Path, demihead_root: Path) -> None:
    for path in (swarm_root / "tools", demihead_root / "tools"):
        text = str(path.resolve())
        if text not in sys.path:
            sys.path.insert(0, text)


def _imports(swarm_root: Path, demihead_root: Path):
    _install_external_paths(swarm_root, demihead_root)
    from habitat_git_swarm_client import Lease
    from habitat_objective_lease_fencing import LeaseFenceLost, ObjectiveLeaseFence
    import nohand_habitat_peer as nohand_core
    import nohand_habitat_peer_v1_4_2 as nohand_v142
    from tools.janus_demiurge_boot_controller import SUPERVISOR_RESULT_SCHEMA, canonical_sha256
    from tools.janus_demiurge_boot_controller_v1_1 import JanusDemiurgeBootControllerV11
    from tools.janus_demiurge_supervisor_checkpoint_journal import (
        CHECKPOINT_SCHEMA,
        PINNED_SUPERVISOR_HEAD,
        JanusDemiurgeSupervisorCheckpointJournal,
    )
    from tools.janus_hippocampus_hdd_buffer import JanusHippocampusBufferedJournal
    return {
        "Lease": Lease,
        "LeaseFenceLost": LeaseFenceLost,
        "ObjectiveLeaseFence": ObjectiveLeaseFence,
        "nohand_core": nohand_core,
        "nohand_v142": nohand_v142,
        "SUPERVISOR_RESULT_SCHEMA": SUPERVISOR_RESULT_SCHEMA,
        "canonical_sha256": canonical_sha256,
        "JanusDemiurgeBootControllerV11": JanusDemiurgeBootControllerV11,
        "CHECKPOINT_SCHEMA": CHECKPOINT_SCHEMA,
        "PINNED_SUPERVISOR_HEAD": PINNED_SUPERVISOR_HEAD,
        "JanusDemiurgeSupervisorCheckpointJournal": JanusDemiurgeSupervisorCheckpointJournal,
        "JanusHippocampusBufferedJournal": JanusHippocampusBufferedJournal,
    }


BOUNDS = {
    "alpha": (0.01, 0.5),
    "gamma": (0.8, 0.999),
    "epsilon": (0.01, 0.9),
}


def _score(config: Mapping[str, float], target: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total = 0.0
    norm = 0.0
    for key, (low, high) in BOUNDS.items():
        delta = (float(config[key]) - float(target[key])) / (high - low)
        total += float(weights[key]) * delta * delta
        norm += float(weights[key])
    return -float(total / norm)


class ScriptedSupervisor:
    """Deterministic injected workload used only to exercise exact controller mechanics."""

    def __init__(self, api: Mapping[str, Any], *, terminal_window: int = 4) -> None:
        self.api = api
        self.terminal_window = terminal_window
        self.run_calls = 0
        self.resume_calls = 0

    def _checkpoint(
        self,
        *,
        objective_id: str,
        config: Mapping[str, float],
        target: Mapping[str, float],
        weights: Mapping[str, float],
        root_seed: int,
        generation_window: int,
        candidate_count: int,
        patience_windows: int,
        min_window_improvement: float,
        next_window_index: int,
        parent: str | None,
        state: str,
    ) -> dict[str, Any]:
        checkpoint = {
            "schema": self.api["CHECKPOINT_SCHEMA"],
            "objective_id": objective_id,
            "resume_config": dict(config),
            "resume_score": _score(config, target, weights),
            "next_window_index": next_window_index,
            "root_seed": root_seed,
            "target_config": dict(target),
            "weights": dict(weights),
            "generation_window": generation_window,
            "candidate_count": candidate_count,
            "patience_windows": patience_windows,
            "min_window_improvement": min_window_improvement,
            "total_generations": next_window_index * generation_window,
            "total_adoptions": 0,
            "state": state,
            "parent_checkpoint_receipt_sha256": parent,
        }
        checkpoint["receipt_sha256"] = self.api["canonical_sha256"](checkpoint)
        return checkpoint

    def _result(
        self,
        *,
        checkpoint: Mapping[str, Any],
        initial_config: Mapping[str, float],
        window_offset: int,
        windows_executed: int,
    ) -> dict[str, Any]:
        result = {
            "schema": self.api["SUPERVISOR_RESULT_SCHEMA"],
            "state": checkpoint["state"],
            "objective_present": True,
            "objective_id": checkpoint["objective_id"],
            "self_generated_objective": False,
            "initial_config": dict(initial_config),
            "final_config": dict(checkpoint["resume_config"]),
            "initial_score": _score(initial_config, checkpoint["target_config"], checkpoint["weights"]),
            "final_score": checkpoint["resume_score"],
            "weights": dict(checkpoint["weights"]),
            "generation_window": checkpoint["generation_window"],
            "window_offset": window_offset,
            "windows_executed": windows_executed,
            "segment_generations": windows_executed * int(checkpoint["generation_window"]),
            "segment_adoptions": 0,
            "cumulative_generations": checkpoint["total_generations"],
            "cumulative_adoptions": checkpoint["total_adoptions"],
            "candidate_count": checkpoint["candidate_count"],
            "patience_windows": checkpoint["patience_windows"],
            "min_window_improvement": checkpoint["min_window_improvement"],
            "windows": [],
            "checkpoint": dict(checkpoint),
            "work_performed": True,
            "simulation_only": True,
            "authorized": False,
            "external_effect": False,
            "source_writeback": False,
            "automatic_merge": False,
        }
        result["receipt_sha256"] = self.api["canonical_sha256"](result)
        return result

    def run_objective(
        self,
        *,
        objective_id: str,
        base_config: Mapping[str, float],
        target_config: Mapping[str, float],
        root_seed: int,
        generation_window: int,
        max_windows: int,
        candidate_count: int,
        patience_windows: int,
        min_window_improvement: float,
        weights: Mapping[str, float],
    ) -> dict[str, Any]:
        self.run_calls += 1
        next_index = max_windows
        state = "WAIT_PLATEAU" if next_index >= self.terminal_window else "BUDGET_EXHAUSTED"
        checkpoint = self._checkpoint(
            objective_id=objective_id,
            config=base_config,
            target=target_config,
            weights=weights,
            root_seed=root_seed,
            generation_window=generation_window,
            candidate_count=candidate_count,
            patience_windows=patience_windows,
            min_window_improvement=min_window_improvement,
            next_window_index=next_index,
            parent=None,
            state=state,
        )
        return self._result(
            checkpoint=checkpoint,
            initial_config=base_config,
            window_offset=0,
            windows_executed=max_windows,
        )

    def resume_from_checkpoint(self, checkpoint: Mapping[str, Any], *, additional_windows: int) -> dict[str, Any]:
        self.resume_calls += 1
        next_index = int(checkpoint["next_window_index"]) + additional_windows
        state = "WAIT_PLATEAU" if next_index >= self.terminal_window else "BUDGET_EXHAUSTED"
        next_checkpoint = self._checkpoint(
            objective_id=str(checkpoint["objective_id"]),
            config=checkpoint["resume_config"],
            target=checkpoint["target_config"],
            weights=checkpoint["weights"],
            root_seed=int(checkpoint["root_seed"]),
            generation_window=int(checkpoint["generation_window"]),
            candidate_count=int(checkpoint["candidate_count"]),
            patience_windows=int(checkpoint["patience_windows"]),
            min_window_improvement=float(checkpoint["min_window_improvement"]),
            next_window_index=next_index,
            parent=str(checkpoint["receipt_sha256"]),
            state=state,
        )
        return self._result(
            checkpoint=next_checkpoint,
            initial_config=checkpoint["resume_config"],
            window_offset=int(checkpoint["next_window_index"]),
            windows_executed=additional_windows,
        )


class FencedCheckpointStore:
    """Fence check occurs immediately before the durable checkpoint delegate."""

    def __init__(self, inner: Any, fence: Any, lease: Any, *, commit_now: float) -> None:
        self.inner = inner
        self.fence = fence
        self.lease = lease
        self.commit_now = commit_now
        self.persist_attempts = 0
        self.persist_delegations = 0

    async def recover_latest(self, *args, **kwargs):
        return await self.inner.recover_latest(*args, **kwargs)

    async def persist_checkpoint(self, *args, **kwargs):
        self.persist_attempts += 1
        self.fence.assert_current(self.lease, now=self.commit_now)
        self.persist_delegations += 1
        return await self.inner.persist_checkpoint(*args, **kwargs)


def _lease_json(lease: Any) -> dict[str, Any]:
    return {
        "lease_id": lease.lease_id,
        "task_id": lease.task_id,
        "holder_id": lease.holder_id,
        "source_pins": dict(lease.source_pins),
        "expires_at": lease.expires_at,
    }


def _lease_from_json(api: Mapping[str, Any], value: Mapping[str, Any]):
    return api["Lease"](
        lease_id=str(value["lease_id"]),
        task_id=str(value["task_id"]),
        holder_id=str(value["holder_id"]),
        source_pins={str(k): str(v) for k, v in dict(value["source_pins"]).items()},
        expires_at=float(value["expires_at"]),
    )


def _configure_nohand_env() -> None:
    os.environ.pop("GITHUB_ACTIONS", None)
    os.environ.pop("GITHUB_SHA", None)
    os.environ["JANUS_PEER_SOURCE_REVISION"] = DEMIHEAD_NOHAND_HEAD


def _build_nohand_request(api: Mapping[str, Any], checkpoint_receipt: str) -> dict[str, Any]:
    core = api["nohand_core"]
    v142 = api["nohand_v142"]
    request_id = f"G8G9G11-{checkpoint_receipt[:20]}"
    request: dict[str, Any] = {
        "schema": core.REQUEST_SCHEMA,
        "request_id": request_id,
        "action": "LOCAL_TO_GIT",
        "context_sha256": checkpoint_receipt,
        "goldprompt_version": core.GOLDPROMPT_VERSION,
        "goldprompt_contract_digest": core.GOLDPROMPT_CONTRACT_DIGEST,
        "goldprompt_working_faces_bundle_v1_1": v142.EXPECTED_GOLDPROMPT_BUNDLE_V1_1,
        "expected_demihead_parent_main_revision": v142.EXPECTED_DEMIHEAD_PARENT_MAIN_REVISION,
        "authority_requested": False,
        "secret_like": False,
        "terminal_script_sha256": v142.EXPECTED_TERMINAL_SCRIPT_SHA256,
        "local_sha256": v142.EXPECTED_TERMINAL_SCRIPT_SHA256,
        "git_sha256": None,
        "path_sha256": None,
        "predictor_forecast_receipt_sha256": sha256({"objective_id": OBJECTIVE_ID, "checkpoint": checkpoint_receipt}),
        "guard": {
            "no_delete": True,
            "no_move": True,
            "no_rename": True,
            "guardian_of_guardian_ok": True,
            "preservation_sentinel_ok": True,
            "verified_preimage_backup_required": False,
            "safety_contract_sha256": v142.EXPECTED_TERMINAL_SAFETY_SHA256,
            "preservation_baseline_sha256": checkpoint_receipt,
        },
    }
    request["request_sha256"] = core.digest(request)
    return request


def _completion_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), timeout=5.0, isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS completions (
            objective_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            completion_receipt_sha256 TEXT NOT NULL
        )
        """
    )
    return connection


def commit_completion_once(
    path: Path,
    *,
    fence: Any,
    lease: Any,
    now: float,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    # This check is intentionally adjacent to the durable transaction boundary.
    fence.assert_current(lease, now=now)
    unsigned = dict(payload)
    unsigned["objective_id"] = OBJECTIVE_ID
    unsigned["lease_id"] = lease.lease_id
    unsigned["holder_id"] = lease.holder_id
    unsigned["source_writeback"] = False
    unsigned["authority_delta"] = 0
    receipt = sha256(unsigned)
    payload_json = canonical_bytes(unsigned).decode("utf-8")
    connection = _completion_db(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT payload_json, completion_receipt_sha256 FROM completions WHERE objective_id = ?",
            (OBJECTIVE_ID,),
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO completions(objective_id, payload_json, completion_receipt_sha256) VALUES (?, ?, ?)",
                (OBJECTIVE_ID, payload_json, receipt),
            )
            connection.execute("COMMIT")
            return {"state": "COMMITTED", "completion_receipt_sha256": receipt}
        if row[0] != payload_json or row[1] != receipt:
            connection.execute("ROLLBACK")
            raise RuntimeError("HOLD_RECONCILE: completion identity rebound")
        connection.execute("COMMIT")
        return {"state": "IDEMPOTENT_REPLAY", "completion_receipt_sha256": receipt}
    except BaseException:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        connection.close()


def completion_count(path: Path) -> int:
    connection = _completion_db(path)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM completions").fetchone()[0])
    finally:
        connection.close()


async def _open_controller(api: Mapping[str, Any], work_root: Path, fenced_store_factory):
    journal = api["JanusHippocampusBufferedJournal"](
        work_root / "hippocampus.db",
        batch_size=100,
        flush_interval_seconds=60,
        synchronous="FULL",
    )
    await journal.start()
    base_store = api["JanusDemiurgeSupervisorCheckpointJournal"](journal)
    checkpoint_store = fenced_store_factory(base_store)
    supervisor = ScriptedSupervisor(api, terminal_window=4)
    controller = api["JanusDemiurgeBootControllerV11"](
        journal=journal,
        checkpoint_store=checkpoint_store,
        supervisor=supervisor,
        supervisor_source_head=api["PINNED_SUPERVISOR_HEAD"],
    )
    return journal, checkpoint_store, supervisor, controller


async def worker_a(work_root: Path, swarm_root: Path, demihead_root: Path) -> None:
    api = _imports(swarm_root, demihead_root)
    if api["PINNED_SUPERVISOR_HEAD"] != DEMIURGE_SUPERVISOR_HEAD:
        raise RuntimeError("SUPERVISOR_HEAD_DRIFT")
    fence = api["ObjectiveLeaseFence"](
        work_root / "lease.db",
        holder_id="worker-A",
        boot_controller_head=BOOT_CONTROLLER_HEAD,
        supervisor_head=DEMIURGE_SUPERVISOR_HEAD,
    )
    lease = fence.acquire(
        OBJECTIVE_ID,
        authorized_by="Hawkar-usls",
        now=A_NOW,
        ttl_seconds=A_TTL,
    )
    fence.assert_current(lease, now=A_NOW)

    journal, fenced_store, supervisor, controller = await _open_controller(
        api,
        work_root,
        lambda inner: FencedCheckpointStore(inner, fence, lease, commit_now=A_COMMIT_NOW),
    )
    base = {"alpha": 0.08, "gamma": 0.86, "epsilon": 0.65}
    target = {"alpha": 0.31, "gamma": 0.975, "epsilon": 0.12}
    await controller.register_objective(
        objective_id=OBJECTIVE_ID,
        base_config=base,
        target_config=target,
        root_seed=37037,
        generation_window=3,
        segment_windows=2,
        candidate_count=8,
        patience_windows=4,
        min_window_improvement=0.0,
        weights={"alpha": 1.0, "gamma": 1.0, "epsilon": 1.0},
    )
    first = await controller.run_registered_objective(OBJECTIVE_ID, max_segments=1)
    if first["state"] != "CONTROLLER_BUDGET_EXHAUSTED":
        raise RuntimeError(f"WORKER_A_UNEXPECTED_STATE:{first['state']}")
    if fenced_store.persist_delegations != 1:
        raise RuntimeError("WORKER_A_FENCE_NOT_ADJACENT_TO_CHECKPOINT_COMMIT")
    checkpoint = first["checkpoint"]
    checkpoint_receipt = str(checkpoint["receipt_sha256"])

    _configure_nohand_env()
    v142 = api["nohand_v142"]
    core = api["nohand_core"]
    v142.configure_v142_namespace()
    request = _build_nohand_request(api, checkpoint_receipt)
    request_path = work_root / core.INBOX / f"{request['request_id']}.json"
    core.create_json(request_path, request)
    peer_result = v142.process(work_root)
    if peer_result.get("status") != "PASS" or peer_result.get("created_responses") != 1:
        raise RuntimeError("NOHAND_WORKER_A_RESPONSE_NOT_CREATED")
    response_path = work_root / core.OUTBOX / f"{request['request_id']}.json"
    response = core.read_json(response_path)

    handoff = {
        "schema": "janus.habitat.process_death_handoff.v1",
        "objective_id": OBJECTIVE_ID,
        "worker_a_lease": _lease_json(lease),
        "checkpoint_receipt_sha256": checkpoint_receipt,
        "nohand_request_id": request["request_id"],
        "nohand_request_sha256": request["request_sha256"],
        "nohand_response_sha256": response["response_sha256"],
        "boot_controller_head": BOOT_CONTROLLER_HEAD,
        "swarm_fence_head": SWARM_FENCE_HEAD,
        "demihead_nohand_head": DEMIHEAD_NOHAND_HEAD,
        "checkpoint_fence_checked_immediately_before_delegate": True,
        "source_writeback": False,
        "authority_delta": 0,
    }
    handoff["handoff_receipt_sha256"] = sha256(handoff)
    write_create_only(work_root / "handoff" / "worker-a.json", handoff)
    write_create_only(work_root / "handoff" / "worker-a-lease.json", _lease_json(lease))

    # Do not gracefully close the journal.  The durable checkpoint and NOHAND
    # files have already been committed; os._exit destroys in-memory state.
    os._exit(WORKER_A_EXIT)


async def worker_b(work_root: Path, swarm_root: Path, demihead_root: Path) -> None:
    api = _imports(swarm_root, demihead_root)
    handoff = read_json(work_root / "handoff" / "worker-a.json")
    if handoff.get("handoff_receipt_sha256") != sha256({k: v for k, v in handoff.items() if k != "handoff_receipt_sha256"}):
        raise RuntimeError("HANDOFF_RECEIPT_MISMATCH")

    fence = api["ObjectiveLeaseFence"](
        work_root / "lease.db",
        holder_id="worker-B",
        boot_controller_head=BOOT_CONTROLLER_HEAD,
        supervisor_head=DEMIURGE_SUPERVISOR_HEAD,
    )
    lease = fence.acquire(
        OBJECTIVE_ID,
        authorized_by="Hawkar-usls",
        now=B_NOW,
        ttl_seconds=B_TTL,
    )
    if lease.lease_id == handoff["worker_a_lease"]["lease_id"]:
        raise RuntimeError("TAKEOVER_REUSED_STALE_FENCING_TOKEN")

    journal, fenced_store, supervisor, controller = await _open_controller(
        api,
        work_root,
        lambda inner: FencedCheckpointStore(inner, fence, lease, commit_now=B_COMMIT_NOW),
    )
    before = await fenced_store.recover_latest(
        objective_id=OBJECTIVE_ID,
        source_head=DEMIURGE_SUPERVISOR_HEAD,
        policy_id="DEMIURGE_SUPERVISOR_CHECKPOINT_V1",
    )
    if before.get("state") != "RECOVERED":
        raise RuntimeError("WORKER_B_DURABLE_CHECKPOINT_NOT_RECOVERED")
    recovered_checkpoint = before["checkpoint"]
    if recovered_checkpoint.get("receipt_sha256") != handoff["checkpoint_receipt_sha256"]:
        raise RuntimeError("WORKER_B_RECOVERED_DIFFERENT_CHECKPOINT")

    second = await controller.run_registered_objective(OBJECTIVE_ID, max_segments=2)
    if second["state"] != "WAIT_PLATEAU" or second.get("recovered_checkpoint") is not True:
        raise RuntimeError("WORKER_B_DID_NOT_RESUME_TO_WAIT")
    if supervisor.run_calls != 0 or supervisor.resume_calls != 1:
        raise RuntimeError("WORKER_B_RESTARTED_INSTEAD_OF_RESUMING")
    if fenced_store.persist_delegations != 1:
        raise RuntimeError("WORKER_B_FENCE_NOT_ADJACENT_TO_CHECKPOINT_COMMIT")

    final_checkpoint = second["checkpoint"]
    completion_payload = {
        "handoff_receipt_sha256": handoff["handoff_receipt_sha256"],
        "nohand_request_id": handoff["nohand_request_id"],
        "nohand_response_sha256": handoff["nohand_response_sha256"],
        "recovered_checkpoint_receipt_sha256": handoff["checkpoint_receipt_sha256"],
        "final_checkpoint_receipt_sha256": final_checkpoint["receipt_sha256"],
        "controller_state": second["state"],
    }
    first_commit = commit_completion_once(
        work_root / "completion.db",
        fence=fence,
        lease=lease,
        now=B_COMMIT_NOW,
        payload=completion_payload,
    )
    replay_commit = commit_completion_once(
        work_root / "completion.db",
        fence=fence,
        lease=lease,
        now=B_COMMIT_NOW,
        payload=completion_payload,
    )
    if first_commit["state"] != "COMMITTED" or replay_commit["state"] != "IDEMPOTENT_REPLAY":
        raise RuntimeError("COMPLETION_IDEMPOTENCY_FAILED")
    if completion_count(work_root / "completion.db") != 1:
        raise RuntimeError("COMPLETION_ROW_COUNT_NOT_ONE")

    _configure_nohand_env()
    v142 = api["nohand_v142"]
    core = api["nohand_core"]
    v142.configure_v142_namespace()
    outcome: dict[str, Any] = {
        "schema": core.OUTCOME_SCHEMA,
        "request_id": handoff["nohand_request_id"],
        "action": "LOCAL_TO_GIT",
        "success": True,
        "response_sha256": handoff["nohand_response_sha256"],
        "completion_receipt_sha256": first_commit["completion_receipt_sha256"],
    }
    outcome["outcome_sha256"] = core.digest(outcome)
    core.create_json(work_root / core.OUTCOMES / f"{outcome['outcome_sha256']}.json", outcome)
    peer_result = v142.process(work_root)
    if peer_result.get("status") != "PASS" or peer_result.get("settled_outcomes") != 1:
        raise RuntimeError("NOHAND_WORKER_B_OUTCOME_NOT_SETTLED")

    receipt = {
        "schema": "janus.habitat.process_death_worker_b.v1",
        "objective_id": OBJECTIVE_ID,
        "worker_b_lease": _lease_json(lease),
        "worker_a_lease_id": handoff["worker_a_lease"]["lease_id"],
        "fresh_process": True,
        "worker_a_stdout_consumed": False,
        "worker_a_process_memory_available": False,
        "durable_inputs": [
            "hippocampus.db",
            "lease.db",
            "handoff/worker-a.json",
            "habitat/nohand/v1_4_2/*",
        ],
        "recovered_checkpoint": True,
        "resume_calls": supervisor.resume_calls,
        "run_calls": supervisor.run_calls,
        "checkpoint_fence_checked_immediately_before_delegate": True,
        "first_completion_state": first_commit["state"],
        "duplicate_completion_state": replay_commit["state"],
        "completion_receipt_sha256": first_commit["completion_receipt_sha256"],
        "completion_row_count": 1,
        "source_writeback": False,
        "authority_delta": 0,
    }
    receipt["receipt_sha256"] = sha256(receipt)
    write_create_only(work_root / "handoff" / "worker-b.json", receipt)
    await journal.close()


async def stale_worker_a_attempt(work_root: Path, swarm_root: Path, demihead_root: Path) -> None:
    api = _imports(swarm_root, demihead_root)
    old_lease = _lease_from_json(api, read_json(work_root / "handoff" / "worker-a-lease.json"))
    fence = api["ObjectiveLeaseFence"](
        work_root / "lease.db",
        holder_id="worker-A",
        boot_controller_head=BOOT_CONTROLLER_HEAD,
        supervisor_head=DEMIURGE_SUPERVISOR_HEAD,
    )

    class DelegateMustNotRun:
        def __init__(self) -> None:
            self.called = False

        async def persist_checkpoint(self, *args, **kwargs):
            self.called = True
            raise RuntimeError("STALE_DELEGATE_WAS_CALLED")

    delegate = DelegateMustNotRun()
    fenced = FencedCheckpointStore(delegate, fence, old_lease, commit_now=STALE_A_NOW)
    rejected = False
    try:
        await fenced.persist_checkpoint({"invalid": "must-never-reach-delegate"})
    except api["LeaseFenceLost"]:
        rejected = True
    if not rejected or delegate.called or fenced.persist_delegations != 0:
        raise RuntimeError("STALE_WORKER_A_REACHED_CHECKPOINT_DELEGATE")
    if completion_count(work_root / "completion.db") != 1:
        raise RuntimeError("STALE_WORKER_A_CHANGED_COMPLETION_COUNT")
    receipt = {
        "schema": "janus.habitat.stale_worker_rejection.v1",
        "old_lease_id": old_lease.lease_id,
        "stale_fence_rejected_before_checkpoint_delegate": True,
        "delegate_called": False,
        "completion_row_count_after_attempt": 1,
        "source_writeback": False,
        "authority_delta": 0,
    }
    receipt["receipt_sha256"] = sha256(receipt)
    write_create_only(work_root / "handoff" / "stale-worker-a.json", receipt)


def _fresh_child_env() -> dict[str, str]:
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "PYTHONUTF8", "PYTHONIOENCODING", "SYSTEMROOT")
    return {key: os.environ[key] for key in keep if key in os.environ}


def _run_child(phase: str, work_root: Path, swarm_root: Path, demihead_root: Path) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--phase",
        phase,
        "--work-root",
        str(work_root),
        "--swarm-root",
        str(swarm_root),
        "--demihead-root",
        str(demihead_root),
    ]
    return subprocess.run(
        command,
        cwd=str(GENESIS_ROOT),
        env=_fresh_child_env(),
        text=True,
        capture_output=True,
        check=False,
    )


def _validate_nohand_final(work_root: Path, api: Mapping[str, Any], handoff: Mapping[str, Any]) -> dict[str, Any]:
    v142 = api["nohand_v142"]
    core = api["nohand_core"]
    v142.configure_v142_namespace()
    snapshots = sorted((work_root / core.SNAPSHOTS).glob("*.json"))
    if len(snapshots) != 2:
        raise RuntimeError(f"NOHAND_SNAPSHOT_COUNT:{len(snapshots)}")
    final_state = core.read_json(snapshots[-1])
    if final_state.get("sequence") != 2 or final_state.get("pending") != {}:
        raise RuntimeError("NOHAND_FINAL_STATE_NOT_SETTLED")
    if final_state.get("raw_context_persisted") is not False:
        raise RuntimeError("NOHAND_RAW_CONTEXT_PERSISTED")
    settled = sorted((work_root / core.SETTLED).glob("*.json"))
    if len(settled) != 1:
        raise RuntimeError("NOHAND_SETTLEMENT_COUNT_NOT_ONE")
    return {
        "snapshot_count": 2,
        "final_sequence": 2,
        "pending_count": 0,
        "settlement_count": 1,
        "request_id": handoff["nohand_request_id"],
        "raw_context_persisted": False,
    }


def run_parent(work_root: Path, swarm_root: Path, demihead_root: Path, receipt_path: Path | None) -> dict[str, Any]:
    work_root.mkdir(parents=True, exist_ok=True)
    api = _imports(swarm_root, demihead_root)

    a = _run_child("worker-a", work_root, swarm_root, demihead_root)
    if a.returncode != WORKER_A_EXIT:
        raise RuntimeError(f"WORKER_A_DID_NOT_DIE_AS_REQUIRED:{a.returncode}:{a.stderr[-500:]}")
    if not (work_root / "handoff" / "worker-a.json").exists():
        raise RuntimeError("WORKER_A_DIED_BEFORE_DURABLE_HANDOFF")

    # No stdout/stderr, object, pipe, or environment payload from A is supplied
    # to B. B receives only source roots plus the common durable work-root path.
    b = _run_child("worker-b", work_root, swarm_root, demihead_root)
    if b.returncode != 0:
        raise RuntimeError(f"WORKER_B_FAILED:{b.returncode}:{b.stderr[-1000:]}")

    stale = _run_child("stale-a", work_root, swarm_root, demihead_root)
    if stale.returncode != 0:
        raise RuntimeError(f"STALE_A_CHALLENGE_FAILED:{stale.returncode}:{stale.stderr[-1000:]}")

    handoff = read_json(work_root / "handoff" / "worker-a.json")
    worker_b_receipt = read_json(work_root / "handoff" / "worker-b.json")
    stale_receipt = read_json(work_root / "handoff" / "stale-worker-a.json")
    nohand = _validate_nohand_final(work_root, api, handoff)
    if completion_count(work_root / "completion.db") != 1:
        raise RuntimeError("FINAL_COMPLETION_COUNT_NOT_ONE")

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "PASS",
        "scope": "CONTROLLED_CROSS_PROCESS_SINGLE_HOST_SQLITE",
        "source_heads": {
            "janus_genesis_boot_controller": BOOT_CONTROLLER_HEAD,
            "swarm_objective_lease_fencing": SWARM_FENCE_HEAD,
            "demihead_nohand_peer": DEMIHEAD_NOHAND_HEAD,
            "demiurge_supervisor_binding": DEMIURGE_SUPERVISOR_HEAD,
        },
        "experiment": {
            "worker_a_exit_code": a.returncode,
            "worker_a_memory_destroyed_by_process_exit": True,
            "worker_b_started_as_fresh_interpreter": True,
            "worker_a_stdout_passed_to_worker_b": False,
            "worker_b_durable_inputs_only": True,
            "worker_a_lease_id": handoff["worker_a_lease"]["lease_id"],
            "worker_b_lease_id": worker_b_receipt["worker_b_lease"]["lease_id"],
            "lease_token_changed_on_takeover": handoff["worker_a_lease"]["lease_id"] != worker_b_receipt["worker_b_lease"]["lease_id"],
            "checkpoint_fence_before_worker_a_commit": handoff["checkpoint_fence_checked_immediately_before_delegate"],
            "checkpoint_fence_before_worker_b_commit": worker_b_receipt["checkpoint_fence_checked_immediately_before_delegate"],
            "stale_worker_a_rejected_before_delegate": stale_receipt["stale_fence_rejected_before_checkpoint_delegate"],
            "completion_row_count": worker_b_receipt["completion_row_count"],
            "duplicate_completion_state": worker_b_receipt["duplicate_completion_state"],
            "nohand": nohand,
        },
        "gates": {
            "G8_SESSION_DROP_RECOVERY": "PASS",
            "G9_HANDOFF_CONSUMED_WITHOUT_HIDDEN_SESSION_CONTEXT": "PASS",
            "G11_EXACTLY_ONCE_COMPLETION": "PASS",
            "CONTINUOUS_EXECUTION_FENCING_UNTIL_CHECKPOINT_COMMIT": True,
            "STALE_WORKER_CANNOT_COMMIT_AFTER_TAKEOVER": True,
            "NOHAND_REQUEST_RESPONSE_SETTLEMENT_REPLAY": True,
            "SOURCE_WRITEBACK_OBSERVED": False,
            "AUTHORITY_DELTA": 0,
        },
        "claim_ceiling": {
            "FULL_ISSUE_162_ACCEPTANCE": False,
            "CROSS_HOST_SHARED_FILESYSTEM_VALIDATED": False,
            "REAL_OWNER_44_SOURCE_REPLAY": False,
            "RESIDENT_REAL_MODEL_CALL_INCLUDED": False,
            "FEDERATION_FINAL_VIEW_INCLUDED": False,
            "GLOBAL_DISTRIBUTED_EXACTLY_ONCE": False,
        },
        "source_writeback": False,
        "destructive_action": False,
        "authority_delta": 0,
    }
    result["receipt_sha256"] = sha256(result)
    target = receipt_path or (work_root / "JANUS-HABITAT-G8-G9-G11-RECEIPT.json")
    write_create_only(target, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS Habitat process-death handoff gauntlet v1")
    parser.add_argument("--phase", choices=("parent", "worker-a", "worker-b", "stale-a"), default="parent")
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--swarm-root", type=Path, required=True)
    parser.add_argument("--demihead-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        if args.phase == "worker-a":
            asyncio.run(worker_a(args.work_root.resolve(), args.swarm_root.resolve(), args.demihead_root.resolve()))
            return 0
        if args.phase == "worker-b":
            asyncio.run(worker_b(args.work_root.resolve(), args.swarm_root.resolve(), args.demihead_root.resolve()))
            return 0
        if args.phase == "stale-a":
            asyncio.run(stale_worker_a_attempt(args.work_root.resolve(), args.swarm_root.resolve(), args.demihead_root.resolve()))
            return 0
        result = run_parent(
            args.work_root.resolve(),
            args.swarm_root.resolve(),
            args.demihead_root.resolve(),
            args.receipt.resolve() if args.receipt else None,
        )
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "HOLD", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
