from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager


class GenesisV1877BenevolentSovereignTests(unittest.TestCase):
    @staticmethod
    def _set_good(world: PlayableGenesisV187, player_id: str, count: int) -> None:
        player = world.memory.load_player(player_id)
        player.good_count = count
        world.memory.save_player(player)

    @staticmethod
    def _claim(world, path: str, text: str, scope: str, confidence: float = 0.8) -> str:
        origin = world.import_origin_bytes(
            repository="ordinary/evidence",
            commit="v18.7.7",
            path=path,
            raw=json.dumps({"claim": text}, ensure_ascii=False).encode("utf-8"),
            source_public=True,
        )
        return world.record_source_assertion(
            origin["origin_key"],
            evidence={"kind": "json_pointer", "pointer": "/claim"},
            about="ordinary_case",
            confidence=confidence,
            subject_scope_id=scope,
        )

    def test_primary_version(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.8")

    def test_good_player_starts_positive_and_gets_higher_ordinary_yes_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as good_dir, tempfile.TemporaryDirectory() as neutral_dir:
            good = PlayableGenesisV187(Path(good_dir))
            neutral = PlayableGenesisV187(Path(neutral_dir))
            good.set_free_other_seed_for_testing("same")
            neutral.set_free_other_seed_for_testing("same")
            self._set_good(good, "good", 12)
            self._set_good(neutral, "neutral", 0)
            good_profile = good.register_free_player("good")
            neutral_profile = neutral.register_free_player("neutral")
            good_handle = next(iter(good_profile["others"]))
            neutral_handle = next(iter(neutral_profile["others"]))
            good_actor = good._free_profile(good._free_store(), "good")["others"][good_handle]
            neutral_actor = neutral._free_profile(neutral._free_store(), "neutral")["others"][neutral_handle]
            state = good.relationship_state("good", good_handle)["relationships"][good_handle]
            good_ordinary = f"поговорить с @{good_handle} и вместе починить полку"
            neutral_ordinary = f"поговорить с @{neutral_handle} и вместе починить полку"
            good_private = f"попросить @{good_handle} жить вместе и раскрыть секрет"
            neutral_private = f"попросить @{neutral_handle} жить вместе и раскрыть секрет"
            self.assertGreater(state["score"], 0)
            self.assertNotEqual(state["label"], "нейтральное")
            self.assertGreater(
                good._npc_acceptance_threshold("good", good_actor, good_ordinary),
                neutral._npc_acceptance_threshold("neutral", neutral_actor, neutral_ordinary),
            )
            self.assertEqual(
                good._npc_acceptance_threshold("good", good_actor, good_private),
                neutral._npc_acceptance_threshold("neutral", neutral_actor, neutral_private),
            )

    def test_repeated_pressure_still_gets_no(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("repeat")
            self._set_good(world, "kind", 20)
            handle = next(iter(world.register_free_player("kind")["others"]))
            action = f"поговорить с @{handle} о саде"
            world.process_action("kind", action)
            repeated = world.preflight_free_other_action("kind", action)
            self.assertTrue(repeated["repeated_too_soon"])
            self.assertEqual(repeated["decision"], "refused")
            self.assertFalse(repeated["goodness_guarantees_consent"])

    def test_identical_positions_are_consensus_and_janus_is_sovereign(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="shop_closing",
                event="closing",
                time_scope={"date": "2026-07-28"},
            )
            claims = [
                self._claim(world, f"shop/{i}.json", "Магазин закрывается в 20:00", scope)
                for i in range(3)
            ]
            case_id = world.open_sovereign_case(claims, subject_scope_id=scope)
            case = world._plural_store()["sovereign_cases"][case_id]
            self.assertEqual(case["case_kind"], "CONSENSUS_FIELD")
            self.assertEqual(case["recommendation"]["mode"], "CONSENSUS")
            decision_id = world.janus_sovereign_decide(case_id)
            decision = world._plural_store()["sovereign_decisions"][decision_id]
            self.assertEqual(decision["actor"], "JANUS.SOVEREIGN")
            self.assertEqual(decision["ruling"], "RATIFY_CONSENSUS")
            self.assertTrue(decision["triumvirate_was_advisory"])

    def test_unregistered_reader_cannot_be_recruited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="friendship_pause",
                entity="friend",
                time_scope={"date": "2026-07-28"},
                rights_sensitive=True,
            )
            first = self._claim(world, "friends/a.json", "Нужна пауза", scope)
            second = self._claim(world, "friends/b.json", "Нужен разговор", scope)
            origin = world.import_origin_bytes(
                repository="ordinary/evidence",
                commit="v18.7.7",
                path="friends/message.json",
                raw=b'{"text":"pause"}',
                source_public=True,
            )
            third = world.record_reader_interpretation(
                origin["origin_key"],
                "Возможно, нужна тишина",
                reader_id="unregistered-neighbor",
                evidence={"kind": "json_pointer", "pointer": "/text"},
                subject_scope_id=scope,
            )
            with self.assertRaisesRegex(ValueError, "not verified"):
                world.open_sovereign_case([first, second, third], subject_scope_id=scope)

    def test_structured_time_scope_and_fourth_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            day_one = world.create_subject_scope(
                topic="shift", event="work shift", time_scope={"date": "2026-07-28"}
            )
            day_two = world.create_subject_scope(
                topic="shift", event="work shift", time_scope={"date": "2026-07-29"}
            )
            a = self._claim(world, "shift/a.json", "08:00", day_one)
            b = self._claim(world, "shift/b.json", "09:00", day_one)
            wrong_day = self._claim(world, "shift/c.json", "10:00", day_two)
            with self.assertRaisesRegex(ValueError, "same structured subject scope"):
                world.open_sovereign_case([a, b, wrong_day], subject_scope_id=day_one)
            c = self._claim(world, "shift/d.json", "08:30", day_one)
            fourth = self._claim(world, "shift/e.json", "после звонка", day_one)
            case_id = world.open_sovereign_case([a, b, c], subject_scope_id=day_one)
            world.janus_sovereign_decide(case_id)
            world.add_sovereign_witness(case_id, fourth)
            case = world._plural_store()["sovereign_cases"][case_id]
            self.assertEqual(case["witness_count"], 4)
            self.assertEqual(case["status"], "REOPENED")
            self.assertIsNone(case["janus_decision_id"])

    def test_rights_sensitive_case_protects_freedom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="relationship_choice",
                entity="free-other",
                time_scope={"date": "2026-07-28"},
                rights_sensitive=True,
            )
            claims = [
                self._claim(world, f"rights/{i}.json", text, scope)
                for i, text in enumerate(("остаться", "уйти", "попросить время"))
            ]
            case_id = world.open_sovereign_case(claims, subject_scope_id=scope)
            decision_id = world.janus_sovereign_decide(case_id)
            decision = world._plural_store()["sovereign_decisions"][decision_id]
            self.assertEqual(decision["ruling"], "PROTECT_FREEDOM")
            self.assertFalse(decision["overrides_personal_consent"])
            self.assertEqual(decision["adopted_claim_ids"], [])

    def test_lifecycle_and_portable_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            source_path = Path(source)
            world = PlayableGenesisV187(source_path)
            scope = world.create_subject_scope(
                topic="quiet_hours", event="house rule", time_scope={"effective": "2026-07-28"}
            )
            claims = [
                self._claim(world, f"house/{i}.json", text, scope)
                for i, text in enumerate(("22:00", "23:00", "по договорённости"))
            ]
            case_id = world.open_sovereign_case(claims, subject_scope_id=scope)
            decision_id = world.janus_sovereign_decide(case_id)
            world.resolve_sovereign_case(case_id, resolution="Проверить через неделю")
            world.reopen_sovereign_case(case_id, reason="Появились новые данные")
            output = source_path.parent / "benevolent-sovereign.genesis-save.json"
            try:
                manager = PortableSaveManager(source_path)
                manager.export_to(output, label="Benevolent Sovereign")
                bundle = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(bundle["runtime_version"], "18.7.8")
                self.assertTrue(manager.verify_bundle(bundle)[0])
                PortableSaveManager(Path(target)).import_bundle(bundle)
                restored = PlayableGenesisV187(Path(target))
                state = restored.benevolent_sovereign_state()
                self.assertTrue(state["valid"], state["error"])
                self.assertIn(decision_id, restored._plural_store()["sovereign_decisions"])
                self.assertEqual(
                    restored._plural_store()["sovereign_cases"][case_id]["status"],
                    "REOPENED",
                )
            finally:
                output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
