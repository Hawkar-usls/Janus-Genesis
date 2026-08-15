# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityOutcomeUndetermined,
    THIRD_WISH_INTENT_SCHEMA,
    ThirdWishCapabilityFabric,
)
from tools.genesis_third_wish_sensor_model_schedule_broker import (
    FixedFileSensor,
    ModelAlias,
    SENSOR_MODEL_SCHEDULE_CLAIM_BOUNDARY,
    SimulatedActuator,
)
from tools.genesis_third_wish_sensor_model_schedule_recovery import (
    SENSOR_MODEL_SCHEDULE_RECOVERY_CLAIMS,
    RecoverableThirdWishSensorModelScheduleBroker,
)


class CountingProvider:
    def __init__(self, output="MODEL-ANSWER"):
        self.output = output
        self.calls = []

    def chat(self, messages):
        self.calls.append(copy.deepcopy(messages))
        return self.output


class RecoverableSimulatedActuator:
    simulated = True

    def __init__(self):
        self.preflight_calls = 0
        self.execute_calls = 0
        self.receipts = {}
        self.lookup_overrides = {}
        self.crash_after_effect = False
        self.fail_before_effect = False

    def preflight(self, command, arguments):
        self.preflight_calls += 1
        if str(command).upper() != "SET_LEVEL":
            raise ValueError("unsupported command")
        level = float(arguments["level"])
        if not 0.0 <= level <= 1.0:
            raise ValueError("level out of range")
        return {
            "validated": True,
            "simulated": True,
            "physical_effect_entered": False,
        }

    @staticmethod
    def _receipt(effect_key, command, arguments):
        return {
            "provider_receipt_id": hashlib.sha256(
                f"{effect_key}:{command}:{arguments}".encode("utf-8")
            ).hexdigest(),
            "effect_key": effect_key,
            "effect_acknowledged": True,
            "simulated": True,
            "real_physical_effect_established": False,
        }

    def execute(self, *, command, arguments, effect_key):
        self.execute_calls += 1
        if self.fail_before_effect:
            self.fail_before_effect = False
            raise RuntimeError("injected before-effect provider failure")
        receipt = self._receipt(effect_key, command, arguments)
        self.receipts[effect_key] = copy.deepcopy(receipt)
        if self.crash_after_effect:
            self.crash_after_effect = False
            raise RuntimeError("injected crash after simulated effect")
        return receipt

    def lookup(self, effect_key):
        override = self.lookup_overrides.get(effect_key)
        if override is not None:
            return copy.deepcopy(override)
        if effect_key in self.receipts:
            return {
                "status": "SETTLED",
                "authoritative": True,
                "provider_receipt": copy.deepcopy(self.receipts[effect_key]),
            }
        return {"status": "UNKNOWN", "authoritative": True}


class ThirdWishSensorModelScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sensor_file = self.root / "sensor.txt"
        self.sensor_file.write_text("23.5\n", encoding="utf-8")
        self.clock = datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc)
        self.provider = CountingProvider()
        self.actuator = RecoverableSimulatedActuator()
        self.broker = RecoverableThirdWishSensorModelScheduleBroker.system(
            self.root,
            sensors={
                "temperature-reference": FixedFileSensor(
                    self.sensor_file,
                    unit="C",
                    parse_float=True,
                )
            },
            models={
                "local-reference": ModelAlias(
                    alias="local-reference",
                    provider=self.provider,
                    provider_name="test-provider",
                    model_name="deterministic-test-model",
                    endpoint_label="operator_registered",
                )
            },
            actuators={"reference-level": self.actuator},
            now_utc=lambda: self.clock,
        )
        self.fabric = self.new_fabric(1000)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def reauth_verifier(intent, evidence):
        return (
            isinstance(evidence, dict)
            and evidence.get("approved") is True
            and evidence.get("request_id") == intent.request_id
            and evidence.get("purpose") == "third-wish-v18.7.43-test"
        )

    def new_fabric(self, tick):
        fabric = ThirdWishCapabilityFabric(
            now_tick=lambda: tick,
            reauthorization_verifier=self.reauth_verifier,
        )
        self.broker.register(fabric)
        return fabric

    def grant(self, capability, scope, suffix, *, fabric=None):
        fabric = fabric or self.fabric
        return fabric.issue_grant(
            grant_id=f"G-{suffix}",
            actor_id="JANUS",
            capability_id=capability,
            resource_pattern=scope,
            source="V1843_TEST",
        )

    @staticmethod
    def intent(grant, request_id, target, operation, parameters=None):
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id=grant.grant_id,
            capability_id=grant.capability_id,
            target=target,
            operation=operation,
            purpose="exercise Third Wish v18.7.43 boundary",
            parameters=parameters or {},
            origin="V1843_TEST",
        )

    @staticmethod
    def approval(request_id):
        return {
            "approved": True,
            "request_id": request_id,
            "purpose": "third-wish-v18.7.43-test",
            "witness": "operator-test-fixture",
        }

    def test_registered_surface_and_claim_ceiling(self):
        expected = {
            "DEVICE.SENSOR.READ",
            "MODEL.CALL",
            "SCHEDULE.CREATE",
            "DEVICE.ACTUATOR.COMMAND",
        }
        self.assertEqual(expected, set(self.fabric.handlers))
        self.assertEqual(expected, set(self.fabric.preflights))
        self.assertFalse(
            SENSOR_MODEL_SCHEDULE_CLAIM_BOUNDARY[
                "sensor_read_grants_actuator_authority"
            ]
        )
        self.assertFalse(
            SENSOR_MODEL_SCHEDULE_CLAIM_BOUNDARY["model_call_mutates_genesis_world"]
        )
        self.assertFalse(
            SENSOR_MODEL_SCHEDULE_CLAIM_BOUNDARY[
                "schedule_preauthorizes_future_effect"
            ]
        )
        self.assertTrue(
            SENSOR_MODEL_SCHEDULE_CLAIM_BOUNDARY[
                "actuator_requires_fresh_human_reauthorization_each_use"
            ]
        )
        self.assertFalse(
            SENSOR_MODEL_SCHEDULE_RECOVERY_CLAIMS[
                "simulated_actuator_is_physical_access_proof"
            ]
        )

    def test_sensor_reads_registered_alias_not_actor_path(self):
        grant = self.grant("DEVICE.SENSOR.READ", "device-sensor:*", "SENSOR")
        result = self.fabric.execute(self.intent(
            grant,
            "SENSOR-1",
            "device-sensor:temperature-reference",
            "READ",
        ))
        self.assertEqual("SETTLED", result["status"])
        actor = result["actor_result"]
        self.assertEqual(23.5, actor["sample"]["measurement"])
        self.assertEqual("C", actor["sample"]["unit"])
        self.assertFalse(actor["actuator_authority"])
        self.assertFalse(actor["sensor_sample_integrity_hash_is_sensor_truth_proof"])
        self.assertNotIn(str(self.sensor_file), str(actor))

    def test_sensor_path_injection_is_pre_effect_rejected(self):
        grant = self.grant("DEVICE.SENSOR.READ", "device-sensor:*", "SENSOR-PATH")
        result = self.fabric.execute(self.intent(
            grant,
            "SENSOR-PATH-1",
            "device-sensor:temperature-reference",
            "READ",
            {"path": "/etc/passwd"},
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertFalse(result["external_call_entered"])

    def test_model_call_returns_text_without_world_authority_and_ledger_raw_output(self):
        grant = self.grant("MODEL.CALL", "model:*", "MODEL")
        result = self.fabric.execute(self.intent(
            grant,
            "MODEL-1",
            "model:local-reference",
            "CHAT",
            {"messages": [{"role": "user", "content": "hello model"}]},
        ))
        self.assertEqual("SETTLED", result["status"])
        actor = result["actor_result"]
        self.assertEqual("MODEL-ANSWER", actor["output"])
        self.assertFalse(actor["world_state_mutated"])
        self.assertFalse(actor["executed_as_genesis_action"])
        self.assertFalse(actor["model_output_is_truth"])
        self.assertFalse(actor["model_output_is_authority"])
        self.assertFalse(actor["credential_material_visible_to_actor"])
        self.assertEqual(1, len(self.provider.calls))
        self.assertNotIn("MODEL-ANSWER", str(self.fabric.ledger.events))

    def test_model_transport_substitution_is_pre_effect_rejected(self):
        grant = self.grant("MODEL.CALL", "model:*", "MODEL-BLOCK")
        for index, extra in enumerate((
            {"endpoint": "http://evil.invalid"},
            {"provider": "other"},
            {"model": "other-model"},
            {"api_key_env": "STEAL_THIS"},
        ), 1):
            params = {
                "messages": [{"role": "user", "content": "hello"}],
                **extra,
            }
            result = self.fabric.execute(self.intent(
                grant,
                f"MODEL-BLOCK-{index}",
                "model:local-reference",
                "CHAT",
                params,
            ))
            self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
            self.assertFalse(result["external_call_entered"])
        self.assertEqual(0, len(self.provider.calls))

    def test_schedule_requires_fresh_verified_reauthorization_before_preflight(self):
        grant = self.grant("SCHEDULE.CREATE", "schedule:*", "SCH-REAUTH")
        request_id = "SCH-REAUTH-1"
        params = {
            "not_before_utc": (self.clock + timedelta(hours=1)).isoformat(),
            "message": "future reminder",
        }
        intent = self.intent(
            grant,
            request_id,
            "schedule:local",
            "CREATE_REMINDER",
            params,
        )
        missing = self.fabric.execute(intent)
        self.assertEqual("FRESH_HUMAN_REAUTHORIZATION_REQUIRED", missing["status"])
        self.assertFalse(missing["effect_executed"])
        self.assertEqual([], self.broker.schedule_store.list_items())

        invalid = self.fabric.execute(
            intent,
            human_reauthorization={"approved": True, "request_id": "wrong"},
        )
        self.assertEqual("FRESH_HUMAN_REAUTHORIZATION_REQUIRED", invalid["status"])
        self.assertEqual([], self.broker.schedule_store.list_items())

        settled = self.fabric.execute(
            intent,
            human_reauthorization=self.approval(request_id),
        )
        self.assertEqual("SETTLED", settled["status"])
        schedule = settled["actor_result"]["schedule"]
        self.assertFalse(schedule["future_effect_preauthorized"])
        self.assertFalse(schedule["future_capability_granted"])
        self.assertTrue(schedule["future_run_requires_its_own_effect_authority"])

    def test_schedule_replay_survives_new_fabric_and_changed_request_rejects_pre_effect(self):
        params = {
            "not_before_utc": (self.clock + timedelta(hours=2)).isoformat(),
            "message": "STABLE-SCHEDULE-MARKER",
        }
        grant = self.grant("SCHEDULE.CREATE", "schedule:*", "SCH-STABLE")
        request_id = "SCH-STABLE-1"
        first = self.fabric.execute(
            self.intent(
                grant,
                request_id,
                "schedule:local",
                "CREATE_REMINDER",
                params,
            ),
            human_reauthorization=self.approval(request_id),
        )
        schedule_id = first["actor_result"]["schedule"]["schedule_id"]

        fabric2 = self.new_fabric(1001)
        grant2 = self.grant(
            "SCHEDULE.CREATE",
            "schedule:*",
            "SCH-STABLE-2",
            fabric=fabric2,
        )
        replay = fabric2.execute(
            self.intent(
                grant2,
                request_id,
                "schedule:local",
                "CREATE_REMINDER",
                params,
            ),
            human_reauthorization=self.approval(request_id),
        )
        self.assertEqual(
            schedule_id,
            replay["actor_result"]["schedule"]["schedule_id"],
        )
        self.assertEqual(1, len(self.broker.schedule_store.list_items()))

        fabric3 = self.new_fabric(1002)
        grant3 = self.grant(
            "SCHEDULE.CREATE",
            "schedule:*",
            "SCH-STABLE-3",
            fabric=fabric3,
        )
        changed = dict(params)
        changed["message"] = "different future reminder"
        rejected = fabric3.execute(
            self.intent(
                grant3,
                request_id,
                "schedule:local",
                "CREATE_REMINDER",
                changed,
            ),
            human_reauthorization=self.approval(request_id),
        )
        self.assertEqual("PRE_EFFECT_REJECTED", rejected["status"])
        self.assertFalse(rejected["external_call_entered"])
        self.assertEqual(1, len(self.broker.schedule_store.list_items()))

    def test_schedule_does_not_store_future_capability_or_raw_credentials(self):
        grant = self.grant("SCHEDULE.CREATE", "schedule:*", "SCH-AUTH")
        request_id = "SCH-AUTH-1"
        result = self.fabric.execute(
            self.intent(
                grant,
                request_id,
                "schedule:local",
                "CREATE_RECURRING_REMINDER",
                {
                    "not_before_utc": (
                        self.clock + timedelta(hours=3)
                    ).isoformat(),
                    "message": "recurring observation reminder",
                    "recurrence": {
                        "interval_seconds": 3600,
                        "max_occurrences": 3,
                    },
                },
            ),
            human_reauthorization=self.approval(request_id),
        )
        row = result["actor_result"]["schedule"]
        self.assertFalse(row["future_effect_preauthorized"])
        self.assertFalse(row["credentials_stored"])
        self.assertFalse(row["automatic_external_effect_execution"])
        self.assertNotIn("capability_token", str(row))

    def test_actuator_reauthorization_gate_runs_before_adapter_preflight(self):
        grant = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-REAUTH",
        )
        request_id = "ACT-REAUTH-1"
        intent = self.intent(
            grant,
            request_id,
            "device-actuator:reference-level",
            "COMMAND",
            {"command": "SET_LEVEL", "arguments": {"level": 0.5}},
        )
        result = self.fabric.execute(intent)
        self.assertEqual("FRESH_HUMAN_REAUTHORIZATION_REQUIRED", result["status"])
        self.assertEqual(0, self.actuator.preflight_calls)
        self.assertEqual(0, self.actuator.execute_calls)

    def test_simulated_actuator_settles_but_never_claims_physical_effect(self):
        grant = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-SIM",
        )
        request_id = "ACT-SIM-1"
        result = self.fabric.execute(
            self.intent(
                grant,
                request_id,
                "device-actuator:reference-level",
                "COMMAND",
                {"command": "SET_LEVEL", "arguments": {"level": 0.75}},
            ),
            human_reauthorization=self.approval(request_id),
        )
        self.assertEqual("SETTLED", result["status"])
        actor = result["actor_result"]
        self.assertTrue(actor["simulated"])
        self.assertFalse(actor["real_physical_effect_established"])
        self.assertEqual(1, self.actuator.execute_calls)

    def test_actuator_settled_replay_survives_new_fabric_without_second_effect(self):
        params = {"command": "SET_LEVEL", "arguments": {"level": 0.25}}
        request_id = "ACT-STABLE-1"
        grant = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-STABLE",
        )
        first = self.fabric.execute(
            self.intent(
                grant,
                request_id,
                "device-actuator:reference-level",
                "COMMAND",
                params,
            ),
            human_reauthorization=self.approval(request_id),
        )
        receipt_id = first["actor_result"]["provider_receipt"]["provider_receipt_id"]
        self.assertEqual(1, self.actuator.execute_calls)

        fabric2 = self.new_fabric(1010)
        grant2 = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-STABLE-2",
            fabric=fabric2,
        )
        second = fabric2.execute(
            self.intent(
                grant2,
                request_id,
                "device-actuator:reference-level",
                "COMMAND",
                params,
            ),
            human_reauthorization=self.approval(request_id),
        )
        self.assertEqual(
            receipt_id,
            second["actor_result"]["provider_receipt"]["provider_receipt_id"],
        )
        self.assertEqual(1, self.actuator.execute_calls)

    def test_same_actuator_request_changed_effect_is_pre_effect_rejected(self):
        request_id = "ACT-CONFLICT-1"
        grant = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-CONFLICT",
        )
        self.fabric.execute(
            self.intent(
                grant,
                request_id,
                "device-actuator:reference-level",
                "COMMAND",
                {"command": "SET_LEVEL", "arguments": {"level": 0.2}},
            ),
            human_reauthorization=self.approval(request_id),
        )
        fabric2 = self.new_fabric(1020)
        grant2 = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-CONFLICT-2",
            fabric=fabric2,
        )
        result = fabric2.execute(
            self.intent(
                grant2,
                request_id,
                "device-actuator:reference-level",
                "COMMAND",
                {"command": "SET_LEVEL", "arguments": {"level": 0.9}},
            ),
            human_reauthorization=self.approval(request_id),
        )
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertFalse(result["external_call_entered"])
        self.assertEqual(1, self.actuator.execute_calls)

    def test_crash_after_effect_recovers_settled_receipt_without_second_execute(self):
        request_id = "ACT-CRASH-SETTLED"
        self.actuator.crash_after_effect = True
        grant = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-CRASH-S",
        )
        intent = self.intent(
            grant,
            request_id,
            "device-actuator:reference-level",
            "COMMAND",
            {"command": "SET_LEVEL", "arguments": {"level": 0.4}},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(
                intent,
                human_reauthorization=self.approval(request_id),
            )
        self.assertEqual(1, self.actuator.execute_calls)

        fabric2 = self.new_fabric(1030)
        grant2 = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-CRASH-S2",
            fabric=fabric2,
        )
        recovered = fabric2.execute(
            self.intent(
                grant2,
                request_id,
                "device-actuator:reference-level",
                "COMMAND",
                {"command": "SET_LEVEL", "arguments": {"level": 0.4}},
            ),
            human_reauthorization=self.approval(request_id),
        )
        self.assertEqual("SETTLED", recovered["status"])
        self.assertTrue(recovered["actor_result"]["recovered_from_provider_lookup"])
        self.assertEqual(1, self.actuator.execute_calls)

    def test_unknown_actuator_outcome_never_auto_reexecutes(self):
        request_id = "ACT-UNKNOWN"
        self.actuator.fail_before_effect = True
        grant = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-UNKNOWN-1",
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(
                self.intent(
                    grant,
                    request_id,
                    "device-actuator:reference-level",
                    "COMMAND",
                    {"command": "SET_LEVEL", "arguments": {"level": 0.6}},
                ),
                human_reauthorization=self.approval(request_id),
            )
        self.assertEqual(1, self.actuator.execute_calls)

        fabric2 = self.new_fabric(1040)
        grant2 = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-UNKNOWN-2",
            fabric=fabric2,
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            fabric2.execute(
                self.intent(
                    grant2,
                    request_id,
                    "device-actuator:reference-level",
                    "COMMAND",
                    {"command": "SET_LEVEL", "arguments": {"level": 0.6}},
                ),
                human_reauthorization=self.approval(request_id),
            )
        self.assertEqual(1, self.actuator.execute_calls)

    def test_authoritative_no_effect_lookup_can_reopen_only_with_fresh_reauth(self):
        request_id = "ACT-NO-EFFECT"
        self.actuator.fail_before_effect = True
        grant = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-NO-EFFECT-1",
        )
        params = {"command": "SET_LEVEL", "arguments": {"level": 0.1}}
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(
                self.intent(
                    grant,
                    request_id,
                    "device-actuator:reference-level",
                    "COMMAND",
                    params,
                ),
                human_reauthorization=self.approval(request_id),
            )
        stored = self.broker.actuator_store.get(request_id)
        effect_key = stored["effect_key"]
        self.actuator.lookup_overrides[effect_key] = {
            "status": "NO_EFFECT",
            "authoritative": True,
        }

        fabric2 = self.new_fabric(1050)
        grant2 = self.grant(
            "DEVICE.ACTUATOR.COMMAND",
            "device-actuator:*",
            "ACT-NO-EFFECT-2",
            fabric=fabric2,
        )
        retry_intent = self.intent(
            grant2,
            request_id,
            "device-actuator:reference-level",
            "COMMAND",
            params,
        )
        no_auth = fabric2.execute(retry_intent)
        self.assertEqual("FRESH_HUMAN_REAUTHORIZATION_REQUIRED", no_auth["status"])
        self.assertEqual(1, self.actuator.execute_calls)

        self.actuator.lookup_overrides[effect_key] = {
            "status": "NO_EFFECT",
            "authoritative": True,
        }
        settled = fabric2.execute(
            retry_intent,
            human_reauthorization=self.approval(request_id),
        )
        self.assertEqual("SETTLED", settled["status"])
        self.assertEqual(2, self.actuator.execute_calls)
        self.assertFalse(settled["actor_result"]["real_physical_effect_established"])


if __name__ == "__main__":
    unittest.main()
