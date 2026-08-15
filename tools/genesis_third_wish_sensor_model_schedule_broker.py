# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.43 — Third Wish sensor/model/schedule/actuator broker.

This descendant keeps four powers separate:

* DEVICE.SENSOR.READ observes an operator-registered sensor alias. It does not
  expose arbitrary host paths, buses, GPIO, or actuator control.
* MODEL.CALL invokes an operator-registered ChatProvider. Provider endpoint and
  credential custody stay outside actor parameters; returned text is neither
  truth nor an executable Genesis action.
* SCHEDULE.CREATE durably creates a reminder/request capsule. It does not mint a
  future capability, credential, or exemption from fresh authorization.
* DEVICE.ACTUATOR.COMMAND is a typed adapter protocol only. The v18.7.40 core
  still requires fresh verified human reauthorization on every use. The
  reference simulator proves protocol behavior, not physical-device access.

No historical Third Wish layer is rewritten.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from genesis_v18_7_35_windows_safe_durable_writer import WindowsSafeDurableJsonWriter
from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    ThirdWishCapabilityFabric,
)
from genesis_v18_7_ai import AIProviderConfig, ChatProvider, build_provider
from janus_portable_lock_v2 import PortableProcessLockV2

SENSOR_MODEL_SCHEDULE_VERSION = "18.7.43"
SCHEDULE_SCHEMA = "janus.genesis.third_wish.schedule.v1"
SCHEDULE_ITEM_SCHEMA = "janus.genesis.third_wish.schedule.item.v1"
MAX_SENSOR_TEXT_BYTES = 64 * 1024
MAX_MODEL_MESSAGES = 24
MAX_MODEL_INPUT_BYTES = 64 * 1024
MAX_MODEL_OUTPUT_CHARS = 32_000
MAX_SCHEDULE_MESSAGE_BYTES = 8 * 1024
MAX_SCHEDULE_HORIZON_SECONDS = 366 * 24 * 60 * 60
MAX_RECURRENCE_OCCURRENCES = 365
MIN_RECURRENCE_SECONDS = 60 * 60
MAX_RECURRENCE_SECONDS = 31 * 24 * 60 * 60
MAX_ACTUATOR_ARGUMENT_BYTES = 16 * 1024


class SensorModelScheduleError(RuntimeError):
    pass


class ScheduleRequestConflict(SensorModelScheduleError):
    pass


class SensorReader(Protocol):
    def read(self) -> Mapping[str, Any]: ...


class ActuatorAdapter(Protocol):
    simulated: bool

    def preflight(self, command: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def execute(
        self,
        *,
        command: str,
        arguments: Mapping[str, Any],
        effect_key: str,
    ) -> Mapping[str, Any]: ...


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_size(value: Any) -> int:
    return len(_canonical(value).encode("utf-8"))


def _require(parameters: Mapping[str, Any], key: str) -> Any:
    if key not in parameters:
        raise SensorModelScheduleError(f"MISSING_PARAMETER:{key}")
    return parameters[key]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise SensorModelScheduleError("UTC_TIME_REQUIRED")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SensorModelScheduleError("UTC_TIME_INVALID") from exc
    if parsed.tzinfo is None:
        raise SensorModelScheduleError("UTC_TIME_MUST_BE_OFFSET_AWARE")
    return parsed.astimezone(timezone.utc)


_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def _alias_from_target(target: str, prefix: str) -> str:
    text = str(target).strip()
    marker = prefix + ":"
    if not text.startswith(marker):
        raise SensorModelScheduleError(f"TARGET_PREFIX_REQUIRED:{marker}")
    alias = text[len(marker):]
    if not _ALIAS_RE.fullmatch(alias):
        raise SensorModelScheduleError("INVALID_ALIAS")
    return alias


@dataclass(frozen=True)
class HostLoadAverageSensor:
    """Real host-telemetry reference sensor; not a physical-sensor truth proof."""

    unit: str = "load-average"

    def read(self) -> Mapping[str, Any]:
        one, five, fifteen = os.getloadavg()
        return {
            "source_kind": "HOST_OS_TELEMETRY",
            "measurement": {
                "load_1m": float(one),
                "load_5m": float(five),
                "load_15m": float(fifteen),
            },
            "unit": self.unit,
            "physical_sensor": False,
        }


@dataclass(frozen=True)
class FixedFileSensor:
    """Operator-bound read-only file sensor; actor never selects the path."""

    path: Path
    unit: str | None = None
    parse_float: bool = False

    def read(self) -> Mapping[str, Any]:
        path = self.path.resolve(strict=True)
        if not path.is_file():
            raise SensorModelScheduleError("SENSOR_SOURCE_NOT_FILE")
        raw = path.read_bytes()
        if len(raw) > MAX_SENSOR_TEXT_BYTES:
            raise SensorModelScheduleError("SENSOR_SAMPLE_TOO_LARGE")
        text = raw.decode("utf-8", errors="strict").strip()
        value: Any = text
        if self.parse_float:
            try:
                value = float(text)
            except ValueError as exc:
                raise SensorModelScheduleError("SENSOR_FLOAT_PARSE_FAILED") from exc
        return {
            "source_kind": "OPERATOR_BOUND_FILE",
            "measurement": value,
            "unit": self.unit,
            "source_bytes_sha256": hashlib.sha256(raw).hexdigest(),
            "physical_sensor": False,
        }


@dataclass(frozen=True)
class ModelAlias:
    alias: str
    provider: ChatProvider
    provider_name: str
    model_name: str
    endpoint_label: str

    @classmethod
    def from_config(cls, alias: str, config: AIProviderConfig) -> "ModelAlias":
        # Config, endpoint and credential-env name are installed by the operator;
        # they never come from ActionIntent.parameters.
        return cls(
            alias=alias,
            provider=build_provider(config),
            provider_name=str(config.provider),
            model_name=str(config.model),
            endpoint_label="operator_registered",
        )


class DurableThirdWishScheduleStore:
    """Durable schedule declarations, not a future effect executor."""

    def __init__(
        self,
        root: str | Path,
        *,
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "third_wish_schedules_v18_7_43.json"
        self.lock = PortableProcessLockV2(
            self.root / "third_wish_schedules_v18_7_43.lock"
        )
        self.writer = WindowsSafeDurableJsonWriter()
        self.now_utc = now_utc or _utc_now
        with self.lock.exclusive():
            if not self.path.exists():
                self._save(self._default_state())
            else:
                self._load()

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "schema": SCHEDULE_SCHEMA,
            "items": [],
            "request_bindings": {},
            "invariants": {
                "schedule_is_future_capability": False,
                "future_effect_preauthorized": False,
                "credentials_stored": False,
                "automatic_external_effect_execution": False,
            },
        }

    def _load(self) -> dict[str, Any]:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SensorModelScheduleError("SCHEDULE_STORE_UNREADABLE") from exc
        if not isinstance(state, dict) or state.get("schema") != SCHEDULE_SCHEMA:
            raise SensorModelScheduleError("SCHEDULE_STORE_SCHEMA_INVALID")
        if not isinstance(state.get("items"), list) or not isinstance(
            state.get("request_bindings"), dict
        ):
            raise SensorModelScheduleError("SCHEDULE_STORE_SHAPE_INVALID")
        return state

    def _save(self, state: Mapping[str, Any]) -> None:
        self.writer.write(self.path, dict(state))

    @staticmethod
    def _binding_payload(
        *,
        actor_id: str,
        target: str,
        operation: str,
        parameters: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "actor_id": str(actor_id),
            "target": str(target),
            "operation": str(operation).upper(),
            "parameters": copy.deepcopy(dict(parameters)),
        }

    def inspect_binding(
        self,
        *,
        request_id: str,
        actor_id: str,
        target: str,
        operation: str,
        parameters: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        binding_hash = _sha256(
            self._binding_payload(
                actor_id=actor_id,
                target=target,
                operation=operation,
                parameters=parameters,
            )
        )
        with self.lock.exclusive():
            state = self._load()
            existing = state["request_bindings"].get(str(request_id))
        if existing is None:
            return None
        if not isinstance(existing, dict) or existing.get("binding_sha256") != binding_hash:
            raise ScheduleRequestConflict(str(request_id))
        return copy.deepcopy(existing)

    def create(
        self,
        *,
        request_id: str,
        actor_id: str,
        target: str,
        operation: str,
        parameters: Mapping[str, Any],
    ) -> dict[str, Any]:
        binding_payload = self._binding_payload(
            actor_id=actor_id,
            target=target,
            operation=operation,
            parameters=parameters,
        )
        binding_hash = _sha256(binding_payload)
        now = self.now_utc().astimezone(timezone.utc)
        due = _parse_utc(str(_require(parameters, "not_before_utc")))
        message = str(_require(parameters, "message"))
        recurrence = copy.deepcopy(parameters.get("recurrence"))

        with self.lock.exclusive():
            state = self._load()
            existing = state["request_bindings"].get(str(request_id))
            if existing is not None:
                if (
                    not isinstance(existing, dict)
                    or existing.get("binding_sha256") != binding_hash
                ):
                    raise ScheduleRequestConflict(str(request_id))
                schedule_id = str(existing.get("schedule_id") or "")
                row = next(
                    (
                        item
                        for item in state["items"]
                        if item.get("schedule_id") == schedule_id
                    ),
                    None,
                )
                if row is None:
                    raise SensorModelScheduleError(
                        "SCHEDULE_REQUEST_BINDING_DANGLING"
                    )
                return copy.deepcopy(row)

            schedule_id = _sha256({
                "schema": SCHEDULE_ITEM_SCHEMA,
                "request_id": request_id,
                "binding_sha256": binding_hash,
            })
            row = {
                "schema": SCHEDULE_ITEM_SCHEMA,
                "schedule_id": schedule_id,
                "request_id": str(request_id),
                "actor_id": str(actor_id),
                "created_at_utc": _iso_utc(now),
                "not_before_utc": _iso_utc(due),
                "message": message,
                "message_sha256": hashlib.sha256(
                    message.encode("utf-8")
                ).hexdigest(),
                "recurrence": recurrence,
                "state": "SCHEDULED",
                "future_effect_preauthorized": False,
                "future_capability_granted": False,
                "credentials_stored": False,
                "automatic_external_effect_execution": False,
                "future_run_requires_its_own_effect_authority": True,
            }
            row["record_sha256"] = _sha256(row)
            state["items"].append(row)
            state["request_bindings"][str(request_id)] = {
                "binding_sha256": binding_hash,
                "schedule_id": schedule_id,
            }
            self._save(state)
            return copy.deepcopy(row)

    def list_items(self) -> list[dict[str, Any]]:
        with self.lock.exclusive():
            return copy.deepcopy(self._load()["items"])


@dataclass(frozen=True)
class SimulatedActuator:
    """Protocol/effect sink used only for harness tests; never a physical claim."""

    allowed_commands: tuple[str, ...] = ("SET_LEVEL",)
    simulated: bool = True

    def preflight(
        self,
        command: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        command = str(command).upper()
        if command not in self.allowed_commands:
            raise SensorModelScheduleError("ACTUATOR_COMMAND_NOT_ALLOWED")
        if command == "SET_LEVEL":
            try:
                level = float(_require(arguments, "level"))
            except (TypeError, ValueError) as exc:
                raise SensorModelScheduleError("ACTUATOR_LEVEL_INVALID") from exc
            if not 0.0 <= level <= 1.0:
                raise SensorModelScheduleError("ACTUATOR_LEVEL_OUT_OF_RANGE")
        return {
            "validated": True,
            "simulated": True,
            "physical_effect_entered": False,
        }

    def execute(
        self,
        *,
        command: str,
        arguments: Mapping[str, Any],
        effect_key: str,
    ) -> Mapping[str, Any]:
        self.preflight(command, arguments)
        return {
            "provider_receipt_id": _sha256(
                {
                    "effect_key": effect_key,
                    "command": str(command).upper(),
                    "arguments": dict(arguments),
                }
            ),
            "effect_key": effect_key,
            "effect_acknowledged": True,
            "simulated": True,
            "real_physical_effect_established": False,
        }


@dataclass
class ThirdWishSensorModelScheduleBroker:
    sensors: Mapping[str, SensorReader]
    models: Mapping[str, ModelAlias]
    schedule_store: DurableThirdWishScheduleStore
    actuators: Mapping[str, ActuatorAdapter]
    now_utc: Callable[[], datetime] = _utc_now

    REGISTERED_CAPABILITIES = (
        "DEVICE.SENSOR.READ",
        "MODEL.CALL",
        "SCHEDULE.CREATE",
        "DEVICE.ACTUATOR.COMMAND",
    )

    @classmethod
    def system(
        cls,
        data_dir: str | Path,
        *,
        sensors: Mapping[str, SensorReader] | None = None,
        models: Mapping[str, ModelAlias] | None = None,
        actuators: Mapping[str, ActuatorAdapter] | None = None,
        now_utc: Callable[[], datetime] | None = None,
    ) -> "ThirdWishSensorModelScheduleBroker":
        clock = now_utc or _utc_now
        return cls(
            sensors=dict(sensors or {"host-loadavg": HostLoadAverageSensor()}),
            models=dict(models or {}),
            schedule_store=DurableThirdWishScheduleStore(
                data_dir,
                now_utc=clock,
            ),
            actuators=dict(actuators or {}),
            now_utc=clock,
        )

    def register(self, fabric: ThirdWishCapabilityFabric) -> None:
        handlers = {
            "DEVICE.SENSOR.READ": self.sensor_read,
            "MODEL.CALL": self.model_call,
            "SCHEDULE.CREATE": self.schedule_create,
            "DEVICE.ACTUATOR.COMMAND": self.actuator_command,
        }
        for capability_id, handler in handlers.items():
            fabric.register_handler(
                capability_id,
                handler,
                preflight=self.preflight,
            )

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        cap = intent.capability_id
        operation = intent.operation.upper()
        p = intent.parameters
        if cap == "DEVICE.SENSOR.READ":
            alias = _alias_from_target(intent.target, "device-sensor")
            if operation != "READ":
                raise SensorModelScheduleError("SENSOR_READ_OPERATION_REQUIRED")
            if alias not in self.sensors:
                raise SensorModelScheduleError("SENSOR_ALIAS_NOT_REGISTERED")
            if p:
                raise SensorModelScheduleError(
                    "SENSOR_READ_ACCEPTS_NO_ACTOR_SELECTED_PATH_OR_BUS_PARAMETERS"
                )
        elif cap == "MODEL.CALL":
            alias = _alias_from_target(intent.target, "model")
            if operation != "CHAT":
                raise SensorModelScheduleError("MODEL_CHAT_OPERATION_REQUIRED")
            if alias not in self.models:
                raise SensorModelScheduleError("MODEL_ALIAS_NOT_REGISTERED")
            messages = _require(p, "messages")
            if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MODEL_MESSAGES:
                raise SensorModelScheduleError("MODEL_MESSAGES_SHAPE_INVALID")
            clean_messages = self._validated_messages(messages)
            if _json_size(clean_messages) > MAX_MODEL_INPUT_BYTES:
                raise SensorModelScheduleError("MODEL_INPUT_TOO_LARGE")
            forbidden = {
                "endpoint",
                "url",
                "api_key_env",
                "provider",
                "model",
                "authorization",
            }
            if forbidden.intersection(str(key).lower() for key in p):
                raise SensorModelScheduleError(
                    "MODEL_TRANSPORT_CONFIGURATION_IS_OPERATOR_OWNED"
                )
        elif cap == "SCHEDULE.CREATE":
            if str(intent.target) != "schedule:local":
                raise SensorModelScheduleError("SCHEDULE_TARGET_NOT_REGISTERED")
            if operation not in {"CREATE_REMINDER", "CREATE_RECURRING_REMINDER"}:
                raise SensorModelScheduleError("SCHEDULE_OPERATION_NOT_ALLOWED")
            self._validate_schedule_parameters(operation, p)
            existing = self.schedule_store.inspect_binding(
                request_id=intent.request_id,
                actor_id=intent.actor_id,
                target=intent.target,
                operation=operation,
                parameters=p,
            )
            if existing is not None:
                return {
                    "validated": True,
                    "durable_schedule_request_replay": True,
                    "future_effect_preauthorized": False,
                }
        elif cap == "DEVICE.ACTUATOR.COMMAND":
            alias = _alias_from_target(intent.target, "device-actuator")
            if operation != "COMMAND":
                raise SensorModelScheduleError("ACTUATOR_COMMAND_OPERATION_REQUIRED")
            adapter = self.actuators.get(alias)
            if adapter is None:
                raise SensorModelScheduleError("ACTUATOR_ALIAS_NOT_REGISTERED")
            command = str(_require(p, "command")).upper()
            arguments = _require(p, "arguments")
            if not isinstance(arguments, Mapping):
                raise SensorModelScheduleError("ACTUATOR_ARGUMENTS_MUST_BE_OBJECT")
            if _json_size(arguments) > MAX_ACTUATOR_ARGUMENT_BYTES:
                raise SensorModelScheduleError("ACTUATOR_ARGUMENTS_TOO_LARGE")
            validation = dict(adapter.preflight(command, dict(arguments)))
            if validation.get("validated") is not True:
                raise SensorModelScheduleError("ACTUATOR_ADAPTER_PREFLIGHT_NOT_VALIDATED")
            if getattr(adapter, "simulated", False) and validation.get(
                "physical_effect_entered"
            ) is not False:
                raise SensorModelScheduleError("SIMULATED_PREFLIGHT_CLAIMS_PHYSICAL_EFFECT")
        else:
            raise SensorModelScheduleError(
                "CAPABILITY_NOT_INSTALLED_BY_SENSOR_MODEL_SCHEDULE_BROKER"
            )
        return {
            "validated": True,
            "capability_id": cap,
            "operation": operation,
            "world_state_mutated": False,
            "future_effect_preauthorized": False,
        }

    @staticmethod
    def _validated_messages(messages: Sequence[Any]) -> list[dict[str, str]]:
        allowed_roles = {"system", "user", "assistant"}
        clean: list[dict[str, str]] = []
        for row in messages:
            if not isinstance(row, Mapping):
                raise SensorModelScheduleError("MODEL_MESSAGE_NOT_OBJECT")
            if set(row) != {"role", "content"}:
                raise SensorModelScheduleError("MODEL_MESSAGE_FIELDS_INVALID")
            role = str(row["role"]).strip().lower()
            content = str(row["content"])
            if role not in allowed_roles:
                raise SensorModelScheduleError("MODEL_MESSAGE_ROLE_INVALID")
            if not content or len(content.encode("utf-8")) > 16 * 1024:
                raise SensorModelScheduleError("MODEL_MESSAGE_CONTENT_INVALID")
            clean.append({"role": role, "content": content})
        return clean

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
        now = self.now_utc().astimezone(timezone.utc)
        delta = (due - now).total_seconds()
        if delta <= 0:
            raise SensorModelScheduleError("SCHEDULE_TIME_MUST_BE_FUTURE")
        if delta > MAX_SCHEDULE_HORIZON_SECONDS:
            raise SensorModelScheduleError("SCHEDULE_TIME_BEYOND_REFERENCE_HORIZON")

        recurrence = parameters.get("recurrence")
        if operation == "CREATE_REMINDER":
            if recurrence not in {None, {}}:
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

    def sensor_read(self, intent: ActionIntent) -> Mapping[str, Any]:
        alias = _alias_from_target(intent.target, "device-sensor")
        sample = copy.deepcopy(dict(self.sensors[alias].read()))
        sample_hash = _sha256(sample)
        return {
            "sensor_alias": alias,
            "sample": sample,
            "sample_sha256": sample_hash,
            "observed_at_utc": _iso_utc(self.now_utc()),
            "sensor_sample_integrity_hash_is_sensor_truth_proof": False,
            "physical_causality_proven": False,
            "missing_sensor_treated_as_zero": False,
            "actuator_authority": False,
        }

    def model_call(self, intent: ActionIntent) -> Mapping[str, Any]:
        alias = _alias_from_target(intent.target, "model")
        model = self.models[alias]
        messages = self._validated_messages(_require(intent.parameters, "messages"))
        output = str(model.provider.chat(messages))
        truncated = len(output) > MAX_MODEL_OUTPUT_CHARS
        actor_output = output[:MAX_MODEL_OUTPUT_CHARS]
        return {
            "model_alias": alias,
            "provider_name": model.provider_name,
            "model_name": model.model_name,
            "endpoint_label": model.endpoint_label,
            "output": actor_output,
            "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "output_truncated": truncated,
            "world_state_mutated": False,
            "executed_as_genesis_action": False,
            "model_output_is_truth": False,
            "model_output_is_authority": False,
            "credential_material_visible_to_actor": False,
        }

    def schedule_create(self, intent: ActionIntent) -> Mapping[str, Any]:
        row = self.schedule_store.create(
            request_id=intent.request_id,
            actor_id=intent.actor_id,
            target=intent.target,
            operation=intent.operation,
            parameters=intent.parameters,
        )
        return {
            "schedule": row,
            "future_effect_preauthorized": False,
            "future_capability_granted": False,
            "schedule_executes_external_effect_by_itself": False,
            "future_run_requires_its_own_effect_authority": True,
        }

    def actuator_command(self, intent: ActionIntent) -> Mapping[str, Any]:
        alias = _alias_from_target(intent.target, "device-actuator")
        adapter = self.actuators[alias]
        command = str(_require(intent.parameters, "command")).upper()
        arguments = copy.deepcopy(dict(_require(intent.parameters, "arguments")))
        effect_key = "THIRD-WISH-ACTUATOR:" + _sha256({
            "request_id": intent.request_id,
            "actor_id": intent.actor_id,
            "target": intent.target,
            "command": command,
            "arguments": arguments,
        })
        receipt = copy.deepcopy(dict(adapter.execute(
            command=command,
            arguments=arguments,
            effect_key=effect_key,
        )))
        required = {
            "provider_receipt_id",
            "effect_key",
            "effect_acknowledged",
            "simulated",
            "real_physical_effect_established",
        }
        if not required.issubset(receipt):
            raise SensorModelScheduleError("ACTUATOR_PROVIDER_RECEIPT_INCOMPLETE")
        if str(receipt["effect_key"]) != effect_key:
            raise SensorModelScheduleError("ACTUATOR_EFFECT_KEY_MISMATCH")
        if receipt["effect_acknowledged"] is not True:
            raise SensorModelScheduleError("ACTUATOR_EFFECT_NOT_ACKNOWLEDGED")
        if bool(getattr(adapter, "simulated", False)) != bool(receipt["simulated"]):
            raise SensorModelScheduleError("ACTUATOR_SIMULATION_CLASS_MISMATCH")
        if bool(receipt["simulated"]) and bool(
            receipt["real_physical_effect_established"]
        ):
            raise SensorModelScheduleError("SIMULATED_ACTUATOR_CANNOT_CLAIM_PHYSICAL_EFFECT")
        return {
            "actuator_alias": alias,
            "command": command,
            "provider_receipt": receipt,
            "fresh_human_reauthorization_was_core_gate": True,
            "simulated": bool(receipt["simulated"]),
            "real_physical_effect_established": bool(
                receipt["real_physical_effect_established"]
            ),
        }


SENSOR_MODEL_SCHEDULE_CLAIM_BOUNDARY = {
    "registered_protocol_capability_count": len(
        ThirdWishSensorModelScheduleBroker.REGISTERED_CAPABILITIES
    ),
    "sensor_actor_selects_arbitrary_host_path": False,
    "sensor_read_grants_actuator_authority": False,
    "sensor_hash_proves_sensor_truth": False,
    "model_actor_selects_endpoint": False,
    "model_actor_selects_credential_env": False,
    "model_call_mutates_genesis_world": False,
    "model_output_is_truth": False,
    "model_output_is_authority": False,
    "schedule_is_future_capability": False,
    "schedule_preauthorizes_future_effect": False,
    "schedule_stores_credentials": False,
    "actuator_requires_fresh_human_reauthorization_each_use": True,
    "simulated_actuator_proves_physical_access": False,
    "generic_raw_device_bus_access": False,
    "capability_is_command": False,
}
