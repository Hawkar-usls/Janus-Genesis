# -*- coding: utf-8 -*-
"""Final v18.7.43 precision/recovery layer.

Known schedule conflicts stay pre-effect. Physical actuator requests are bound in
an independent durable store so process restart cannot silently repeat a prior
EFFECT_ENTERING operation. Provider lookup may recover only authoritative
SETTLED or NO_EFFECT evidence; UNKNOWN never becomes retry permission.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from genesis_v18_7_35_windows_safe_durable_writer import WindowsSafeDurableJsonWriter
from genesis_v18_7_40_third_wish_capability_fabric import ActionIntent
from janus_portable_lock_v2 import PortableProcessLockV2
from tools.genesis_third_wish_sensor_model_schedule_broker import (
    MAX_RECURRENCE_OCCURRENCES,
    MAX_RECURRENCE_SECONDS,
    MAX_SCHEDULE_HORIZON_SECONDS,
    MAX_SCHEDULE_MESSAGE_BYTES,
    MIN_RECURRENCE_SECONDS,
    SensorModelScheduleError,
    ThirdWishSensorModelScheduleBroker,
    _alias_from_target,
    _parse_utc,
    _require,
    _sha256,
)

ACTUATOR_REQUEST_SCHEMA = "janus.genesis.third_wish.actuator_requests.v1"


class ActuatorRequestConflict(SensorModelScheduleError):
    pass


class PhysicalEffectOutcomeUndetermined(SensorModelScheduleError):
    pass


class ActuatorReceiptIntegrityError(SensorModelScheduleError):
    pass


class DurableActuatorRequestStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "third_wish_actuator_requests_v18_7_43.json"
        self.lock = PortableProcessLockV2(
            self.root / "third_wish_actuator_requests_v18_7_43.lock"
        )
        self.writer = WindowsSafeDurableJsonWriter()
        with self.lock.exclusive():
            if not self.path.exists():
                self._save({
                    "schema": ACTUATOR_REQUEST_SCHEMA,
                    "requests": {},
                    "invariants": {
                        "effect_entering_can_auto_retry": False,
                        "unknown_lookup_can_open_retry": False,
                        "settled_request_can_reexecute": False,
                        "same_request_can_change_effect": False,
                    },
                })
            else:
                self._load()

    def _load(self) -> dict[str, Any]:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ActuatorReceiptIntegrityError(
                "ACTUATOR_REQUEST_STORE_UNREADABLE"
            ) from exc
        if (
            not isinstance(state, dict)
            or state.get("schema") != ACTUATOR_REQUEST_SCHEMA
            or not isinstance(state.get("requests"), dict)
        ):
            raise ActuatorReceiptIntegrityError(
                "ACTUATOR_REQUEST_STORE_SCHEMA_INVALID"
            )
        return state

    def _save(self, state: Mapping[str, Any]) -> None:
        self.writer.write(self.path, dict(state))

    def get(self, request_id: str) -> dict[str, Any] | None:
        with self.lock.exclusive():
            value = self._load()["requests"].get(str(request_id))
        return copy.deepcopy(value) if isinstance(value, dict) else None

    def bind(
        self,
        *,
        request_id: str,
        binding_sha256: str,
        effect_key: str,
    ) -> dict[str, Any]:
        with self.lock.exclusive():
            state = self._load()
            existing = state["requests"].get(str(request_id))
            if existing is not None:
                if (
                    not isinstance(existing, dict)
                    or existing.get("binding_sha256") != binding_sha256
                    or existing.get("effect_key") != effect_key
                ):
                    raise ActuatorRequestConflict(str(request_id))
                return copy.deepcopy(existing)
            value = {
                "binding_sha256": binding_sha256,
                "effect_key": effect_key,
                "state": "BOUND",
                "provider_receipt": None,
                "actor_result": None,
            }
            state["requests"][str(request_id)] = value
            self._save(state)
            return copy.deepcopy(value)

    def update(self, request_id: str, **fields: Any) -> dict[str, Any]:
        with self.lock.exclusive():
            state = self._load()
            value = state["requests"].get(str(request_id))
            if not isinstance(value, dict):
                raise ActuatorReceiptIntegrityError(
                    "ACTUATOR_REQUEST_BINDING_MISSING"
                )
            value.update(copy.deepcopy(fields))
            state["requests"][str(request_id)] = value
            self._save(state)
            return copy.deepcopy(value)


class RecoverableThirdWishSensorModelScheduleBroker(
    ThirdWishSensorModelScheduleBroker
):
    """Final reference broker for v18.7.43."""

    @property
    def actuator_store(self) -> DurableActuatorRequestStore:
        cached = getattr(self, "_actuator_store_cache", None)
        if cached is None:
            cached = DurableActuatorRequestStore(self.schedule_store.root)
            setattr(self, "_actuator_store_cache", cached)
        return cached

    def _validate_schedule_parameters(
        self,
        operation: str,
        parameters: Mapping[str, Any],
    ) -> None:
        allowed_keys = {"not_before_utc", "message", "recurrence"}
        unknown = set(parameters).difference(allowed_keys)
        if unknown:
            raise SensorModelScheduleError(
                "SCHEDULE_PARAMETERS_NOT_ALLOWED:" + ",".join(sorted(unknown))
            )
        message = str(_require(parameters, "message"))
        if not message or len(message.encode("utf-8")) > MAX_SCHEDULE_MESSAGE_BYTES:
            raise SensorModelScheduleError("SCHEDULE_MESSAGE_INVALID")
        due = _parse_utc(str(_require(parameters, "not_before_utc")))
        now = self.now_utc().astimezone(due.tzinfo)
        delta = (due - now).total_seconds()
        if delta <= 0:
            raise SensorModelScheduleError("SCHEDULE_TIME_MUST_BE_FUTURE")
        if delta > MAX_SCHEDULE_HORIZON_SECONDS:
            raise SensorModelScheduleError("SCHEDULE_TIME_BEYOND_REFERENCE_HORIZON")

        recurrence = parameters.get("recurrence")
        if operation == "CREATE_REMINDER":
            if recurrence is not None and recurrence != {}:
                raise SensorModelScheduleError("ONE_SHOT_REMINDER_CANNOT_RECUR")
            return
        if not isinstance(recurrence, Mapping):
            raise SensorModelScheduleError("RECURRENCE_OBJECT_REQUIRED")
        if set(recurrence) != {"interval_seconds", "max_occurrences"}:
            raise SensorModelScheduleError("RECURRENCE_FIELDS_INVALID")
        try:
            interval = int(recurrence["interval_seconds"])
            count = int(recurrence["max_occurrences"])
        except (TypeError, ValueError) as exc:
            raise SensorModelScheduleError("RECURRENCE_VALUES_INVALID") from exc
        if not MIN_RECURRENCE_SECONDS <= interval <= MAX_RECURRENCE_SECONDS:
            raise SensorModelScheduleError("RECURRENCE_INTERVAL_OUT_OF_RANGE")
        if not 1 <= count <= MAX_RECURRENCE_OCCURRENCES:
            raise SensorModelScheduleError("RECURRENCE_COUNT_OUT_OF_RANGE")

    @staticmethod
    def _actuator_binding(intent: ActionIntent) -> tuple[str, str]:
        command = str(_require(intent.parameters, "command")).upper()
        arguments = copy.deepcopy(dict(_require(intent.parameters, "arguments")))
        binding = {
            "actor_id": intent.actor_id,
            "target": intent.target,
            "command": command,
            "arguments": arguments,
        }
        binding_sha256 = _sha256(binding)
        effect_key = "THIRD-WISH-ACTUATOR:" + _sha256({
            "request_id": intent.request_id,
            **binding,
        })
        return binding_sha256, effect_key

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        result = dict(super().preflight(intent))
        if intent.capability_id != "DEVICE.ACTUATOR.COMMAND":
            return result
        binding_sha256, effect_key = self._actuator_binding(intent)
        existing = self.actuator_store.get(intent.request_id)
        if existing is not None:
            if (
                existing.get("binding_sha256") != binding_sha256
                or existing.get("effect_key") != effect_key
            ):
                raise ActuatorRequestConflict(intent.request_id)
            result["durable_actuator_request_state"] = existing.get("state")
            result["actuator_recovery_may_be_required"] = (
                existing.get("state") == "EFFECT_ENTERING"
            )
        else:
            result["durable_actuator_request_state"] = "UNBOUND"
            result["actuator_recovery_may_be_required"] = False
        return result

    @staticmethod
    def _validate_provider_receipt(
        receipt: Mapping[str, Any],
        *,
        effect_key: str,
        expected_simulated: bool,
    ) -> dict[str, Any]:
        value = copy.deepcopy(dict(receipt))
        required = {
            "provider_receipt_id",
            "effect_key",
            "effect_acknowledged",
            "simulated",
            "real_physical_effect_established",
        }
        if not required.issubset(value):
            raise ActuatorReceiptIntegrityError("ACTUATOR_PROVIDER_RECEIPT_INCOMPLETE")
        if str(value["effect_key"]) != effect_key:
            raise ActuatorReceiptIntegrityError("ACTUATOR_EFFECT_KEY_MISMATCH")
        if value["effect_acknowledged"] is not True:
            raise ActuatorReceiptIntegrityError("ACTUATOR_EFFECT_NOT_ACKNOWLEDGED")
        if bool(value["simulated"]) != bool(expected_simulated):
            raise ActuatorReceiptIntegrityError("ACTUATOR_SIMULATION_CLASS_MISMATCH")
        if bool(value["simulated"]) and bool(value["real_physical_effect_established"]):
            raise ActuatorReceiptIntegrityError(
                "SIMULATED_ACTUATOR_CANNOT_CLAIM_PHYSICAL_EFFECT"
            )
        return value

    def _reconcile_actuator(
        self,
        *,
        adapter: Any,
        effect_key: str,
        expected_simulated: bool,
    ) -> tuple[str, dict[str, Any] | None]:
        lookup = getattr(adapter, "lookup", None)
        if not callable(lookup):
            raise PhysicalEffectOutcomeUndetermined(
                "ACTUATOR_EFFECT_ENTERING_WITHOUT_PROVIDER_LOOKUP"
            )
        observation = lookup(effect_key)
        if not isinstance(observation, Mapping):
            raise PhysicalEffectOutcomeUndetermined("ACTUATOR_LOOKUP_NOT_STRUCTURED")
        if observation.get("authoritative") is not True:
            raise PhysicalEffectOutcomeUndetermined("ACTUATOR_LOOKUP_NOT_AUTHORITATIVE")
        status = str(observation.get("status") or "UNKNOWN").upper()
        if status == "SETTLED":
            receipt = observation.get("provider_receipt")
            if not isinstance(receipt, Mapping):
                raise ActuatorReceiptIntegrityError(
                    "SETTLED_LOOKUP_REQUIRES_PROVIDER_RECEIPT"
                )
            return "SETTLED", self._validate_provider_receipt(
                receipt,
                effect_key=effect_key,
                expected_simulated=expected_simulated,
            )
        if status == "NO_EFFECT":
            return "NO_EFFECT", None
        raise PhysicalEffectOutcomeUndetermined("ACTUATOR_EFFECT_OUTCOME_UNKNOWN")

    def actuator_command(self, intent: ActionIntent) -> Mapping[str, Any]:
        alias = _alias_from_target(intent.target, "device-actuator")
        adapter = self.actuators[alias]
        command = str(_require(intent.parameters, "command")).upper()
        arguments = copy.deepcopy(dict(_require(intent.parameters, "arguments")))
        binding_sha256, effect_key = self._actuator_binding(intent)
        stored = self.actuator_store.bind(
            request_id=intent.request_id,
            binding_sha256=binding_sha256,
            effect_key=effect_key,
        )

        if stored.get("state") == "SETTLED":
            actor_result = stored.get("actor_result")
            if not isinstance(actor_result, Mapping):
                raise ActuatorReceiptIntegrityError(
                    "SETTLED_ACTUATOR_REQUEST_HAS_NO_ACTOR_RESULT"
                )
            return copy.deepcopy(dict(actor_result))

        expected_simulated = bool(getattr(adapter, "simulated", False))
        if stored.get("state") == "EFFECT_ENTERING":
            status, receipt = self._reconcile_actuator(
                adapter=adapter,
                effect_key=effect_key,
                expected_simulated=expected_simulated,
            )
            if status == "SETTLED" and receipt is not None:
                actor_result = {
                    "actuator_alias": alias,
                    "command": command,
                    "provider_receipt": receipt,
                    "fresh_human_reauthorization_was_core_gate": True,
                    "simulated": bool(receipt["simulated"]),
                    "real_physical_effect_established": bool(
                        receipt["real_physical_effect_established"]
                    ),
                    "recovered_from_provider_lookup": True,
                }
                self.actuator_store.update(
                    intent.request_id,
                    state="SETTLED",
                    provider_receipt=receipt,
                    actor_result=actor_result,
                )
                return actor_result
            self.actuator_store.update(
                intent.request_id,
                state="BOUND",
                provider_receipt=None,
                actor_result=None,
                authoritative_no_effect_reconciled=True,
            )

        self.actuator_store.update(intent.request_id, state="EFFECT_ENTERING")
        receipt = adapter.execute(
            command=command,
            arguments=arguments,
            effect_key=effect_key,
        )
        if not isinstance(receipt, Mapping):
            raise ActuatorReceiptIntegrityError("ACTUATOR_PROVIDER_RECEIPT_NOT_OBJECT")
        verified = self._validate_provider_receipt(
            receipt,
            effect_key=effect_key,
            expected_simulated=expected_simulated,
        )
        actor_result = {
            "actuator_alias": alias,
            "command": command,
            "provider_receipt": verified,
            "fresh_human_reauthorization_was_core_gate": True,
            "simulated": bool(verified["simulated"]),
            "real_physical_effect_established": bool(
                verified["real_physical_effect_established"]
            ),
            "recovered_from_provider_lookup": False,
        }
        self.actuator_store.update(
            intent.request_id,
            state="SETTLED",
            provider_receipt=verified,
            actor_result=actor_result,
        )
        return actor_result


SENSOR_MODEL_SCHEDULE_RECOVERY_CLAIMS = {
    "final_reference_class": "RecoverableThirdWishSensorModelScheduleBroker",
    "known_schedule_request_conflict_pre_effect": True,
    "physical_request_binding_durable_across_restart": True,
    "effect_entering_auto_retry": False,
    "authoritative_settled_lookup_can_recover_receipt": True,
    "authoritative_no_effect_lookup_can_reopen_execution": True,
    "unknown_lookup_can_open_retry": False,
    "non_authoritative_lookup_can_open_retry": False,
    "same_request_changed_actuator_effect_pre_effect_rejected": True,
    "simulated_actuator_is_physical_access_proof": False,
    "cross_host_exactly_once_claimed": False,
}
