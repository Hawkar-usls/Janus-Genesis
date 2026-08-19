from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from genesis_v18_7_53_spiral import (
    CONTRACT,
    FORMULA,
    GenesisSpiralIntegrityError,
    GenesisSpiralJournal,
    GenesisSpiralRuntimeAdapter,
)


class _FakeWorld:
    def __init__(self) -> None:
        self.tick = 0

    def public_state(self, actor_id: str):
        return {"actor_id": actor_id, "tick": self.tick, "memory": [f"t{n}" for n in range(self.tick)]}


class _FakeBaseRuntime:
    def __init__(self, world: _FakeWorld) -> None:
        self.world = world
        self.requests: dict[tuple[str, str], tuple[str, str, dict]] = {}

    def execute(self, *, client_id: str, request_id: str, actor_id: str, action: str):
        key = (client_id, request_id)
        existing = self.requests.get(key)
        if existing is not None:
            old_actor, old_action, result = existing
            if (old_actor, old_action) != (actor_id, action):
                raise RuntimeError("request conflict")
            return result
        self.world.tick += 1
        result = {"status": "OK", "actor_id": actor_id, "tick": self.world.tick}
        self.requests[key] = (actor_id, action, result)
        return result

    def request_state(self, *, client_id: str, request_id: str):
        return {"exists": (client_id, request_id) in self.requests}


class GenesisSpiralTests(unittest.TestCase):
    def _advance(self, journal: GenesisSpiralJournal, *, request_id: str, origin_tick: int, return_tick: int):
        return journal.advance(
            client_id="test-client",
            request_id=request_id,
            actor_id="traveler",
            action=f"action-{request_id}",
            origin_state={"tick": origin_tick},
            result={"status": "OK", "tick": return_tick},
            return_state={"tick": return_tick},
        )

    def test_frozen_contract_declares_spiral_not_reset(self):
        contract = json.loads(
            (Path(__file__).resolve().parents[1] / "contracts" / "JANUS_GENESIS_SPIRAL_V18_7_53_FROZEN_CONTRACT.json").read_text(encoding="utf-8")
        )
        self.assertEqual(contract["status"], "FROZEN_BEFORE_IMPLEMENTATION")
        self.assertEqual(contract["demihead_spiral_lineage"]["required_formula"], FORMULA)
        self.assertEqual(contract["transition_model"]["kind"], "APPEND_ONLY_STATE_SPIRAL")
        self.assertEqual(contract["transition_model"]["return_rule"], "RETURN is integration, not reset.")
        self.assertTrue(contract["transition_model"]["technical_event_loops_unchanged"])
        self.assertEqual(contract["control"]["authority_delta"], 0)
        self.assertEqual(contract["control"]["mass_effect_budget_delta"], 0)

    def test_first_turn_has_no_parent_and_second_turn_carries_origin_prime(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = GenesisSpiralJournal(tmp)
            first = self._advance(journal, request_id="R1", origin_tick=0, return_tick=1)
            second = self._advance(journal, request_id="R2", origin_tick=1, return_tick=2)
            self.assertEqual(first["turn_index"], 1)
            self.assertIsNone(first["parent_turn_sha256"])
            self.assertEqual(second["turn_index"], 2)
            self.assertEqual(second["parent_turn_sha256"], first["turn_sha256"])
            self.assertEqual(second["parent_origin_prime_sha256"], first["origin_prime_sha256"])
            self.assertNotEqual(second["origin_sha256"], first["origin_sha256"])
            self.assertFalse(second["return_is_reset"])

    def test_replay_same_request_returns_same_turn_without_increment(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = GenesisSpiralJournal(tmp)
            first = self._advance(journal, request_id="R1", origin_tick=0, return_tick=1)
            replay = self._advance(journal, request_id="R1", origin_tick=99, return_tick=100)
            self.assertEqual(replay, first)
            state = journal.state(actor_id="traveler")
            self.assertEqual(state["turn_count"], 1)
            self.assertEqual(state["head"]["turn_sha256"], first["turn_sha256"])

    def test_receipt_is_content_addressed_and_zero_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = GenesisSpiralJournal(tmp)
            receipt = self._advance(journal, request_id="R1", origin_tick=0, return_tick=1)
            receipt_path = Path(tmp) / "spiral_v18_7_53" / "receipts" / f"{receipt['turn_sha256']}.json"
            self.assertTrue(receipt_path.exists())
            self.assertEqual(receipt["contract"], CONTRACT)
            self.assertEqual(receipt["formula"], FORMULA)
            self.assertEqual(receipt["authority_delta"], 0)
            self.assertEqual(receipt["mass_effect_budget_delta"], 0)
            self.assertFalse(receipt["execution_authority_created"])
            self.assertFalse(receipt["automatic_reexecution"])

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = GenesisSpiralJournal(tmp)
            self._advance(journal, request_id="R1", origin_tick=0, return_tick=1)
            state_path = Path(tmp) / "spiral_v18_7_53" / "state.json"
            value = json.loads(state_path.read_text(encoding="utf-8"))
            value["heads"]["traveler"]["turn_index"] = 999
            state_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(GenesisSpiralIntegrityError):
                journal.state(actor_id="traveler")

    def test_runtime_adapter_preserves_base_idempotency_and_spiralizes_new_intents(self):
        with tempfile.TemporaryDirectory() as tmp:
            world = _FakeWorld()
            base = _FakeBaseRuntime(world)
            runtime = GenesisSpiralRuntimeAdapter(base, world, tmp)
            first_result = runtime.execute(
                client_id="play-genesis", request_id="R1", actor_id="traveler", action="look"
            )
            first_spiral = runtime.spiral_projection_status(client_id="play-genesis", request_id="R1")
            replay_result = runtime.execute(
                client_id="play-genesis", request_id="R1", actor_id="traveler", action="look"
            )
            replay_spiral = runtime.spiral_projection_status(client_id="play-genesis", request_id="R1")
            second_result = runtime.execute(
                client_id="play-genesis", request_id="R2", actor_id="traveler", action="walk"
            )
            second_spiral = runtime.spiral_projection_status(client_id="play-genesis", request_id="R2")
            self.assertEqual(first_result, replay_result)
            self.assertEqual(first_spiral["receipt"]["turn_sha256"], replay_spiral["receipt"]["turn_sha256"])
            self.assertEqual(world.tick, 2)
            self.assertEqual(second_result["tick"], 2)
            self.assertEqual(second_spiral["receipt"]["turn_index"], 2)
            self.assertEqual(
                second_spiral["receipt"]["parent_turn_sha256"],
                first_spiral["receipt"]["turn_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
