from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager


class GenesisV1876TriumvirateTests(unittest.TestCase):
    @staticmethod
    def _source_claim(
        world: PlayableGenesisV187,
        *,
        path: str,
        text: str,
        about: str = "door",
    ) -> str:
        origin = world.import_origin_bytes(
            repository="example/registry",
            commit="one",
            path=path,
            raw=json.dumps({"claim": text}, ensure_ascii=False).encode("utf-8"),
            source_public=True,
        )
        return world.record_source_assertion(
            origin["origin_key"],
            evidence={"kind": "json_pointer", "pointer": "/claim"},
            about=about,
            confidence=0.8,
        )

    def test_primary_runtime_reports_triumvirate_version(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.8")

    def test_two_grounded_voices_are_not_a_canonical_dispute(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            left = self._source_claim(world, path="data/left.json", text="open")
            right = self._source_claim(world, path="data/right.json", text="closed")

            with self.assertRaisesRegex(ValueError, "three-voice triumvirate"):
                world.relate_origin_claims(left, right, "DISPUTES")
            with self.assertRaisesRegex(ValueError, "exactly three claims"):
                world.record_triumvirate_dispute([left, right])

            state = world.triumvirate_witness_state()
            self.assertEqual(state["triumvirate_count"], 0)
            self.assertTrue(state["valid"], state["error"])

    def test_three_grounded_independent_voices_form_one_dispute(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            claims = [
                self._source_claim(world, path="data/open.json", text="open"),
                self._source_claim(world, path="data/closed.json", text="closed"),
                self._source_claim(world, path="data/changing.json", text="changing"),
            ]

            dispute_id = world.record_triumvirate_dispute(claims, confidence=0.9)
            state = world.triumvirate_witness_state()
            store = world._plural_store()
            graph = world._graph()
            dispute = store["triumvirates"][dispute_id]
            edges = [
                edge for edge in graph["edges"]
                if edge["relation"] == "DISPUTES" and edge["to"] == dispute_id
            ]

            self.assertEqual(state["triumvirate_count"], 1)
            self.assertEqual(state["verified_triumvirates"], 1)
            self.assertTrue(state["valid"], state["error"])
            self.assertEqual(len(dispute["claim_ids"]), 3)
            self.assertEqual(len(set(dispute["voice_scopes"])), 3)
            self.assertEqual(len(edges), 3)
            self.assertEqual({edge["from"] for edge in edges}, set(claims))
            self.assertTrue(all(edge["payload"]["member_role"] == "equal_voice" for edge in edges))

    def test_three_claims_from_one_source_are_still_one_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            origin = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/one-voice.json",
                raw=json.dumps(
                    {"first": "open", "second": "closed", "third": "changing"}
                ).encode("utf-8"),
                source_public=True,
            )
            claims = [
                world.record_source_assertion(
                    origin["origin_key"],
                    evidence={"kind": "json_pointer", "pointer": pointer},
                    about="door",
                )
                for pointer in ("/first", "/second", "/third")
            ]

            with self.assertRaisesRegex(ValueError, "independent voice scopes"):
                world.record_triumvirate_dispute(claims)

    def test_triumvirate_rejects_ungrounded_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            first = self._source_claim(world, path="data/a.json", text="open")
            second = self._source_claim(world, path="data/b.json", text="closed")
            third_origin = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/c.json",
                raw=b'{"claim":"changing"}',
                source_public=True,
            )
            third = world.record_reader_interpretation(
                third_origin["origin_key"],
                "changing",
                reader_id="third-reader",
                about="door",
            )

            with self.assertRaisesRegex(ValueError, "must be grounded"):
                world.record_triumvirate_dispute([first, second, third])

    def test_triumvirate_requires_one_shared_subject(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            claims = [
                self._source_claim(world, path="data/door.json", text="open", about="door"),
                self._source_claim(world, path="data/bridge.json", text="closed", about="bridge"),
                self._source_claim(world, path="data/window.json", text="changing", about="window"),
            ]

            with self.assertRaisesRegex(ValueError, "same explicit subject"):
                world.record_triumvirate_dispute(claims)

    def test_third_voice_is_not_judge_and_no_winner_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            claims = [
                self._source_claim(world, path="data/a.json", text="A"),
                self._source_claim(world, path="data/b.json", text="B"),
                self._source_claim(world, path="data/c.json", text="C"),
            ]
            dispute_id = world.record_triumvirate_dispute(claims)
            dispute = world._plural_store()["triumvirates"][dispute_id]
            node = next(node for node in world._graph()["nodes"] if node["id"] == dispute_id)

            self.assertFalse(dispute["third_voice_is_judge"])
            self.assertFalse(dispute["winner_selected"])
            self.assertFalse(dispute["silent_reconciliation"])
            self.assertTrue(node["payload"]["role_equality"])
            self.assertFalse(node["payload"]["third_voice_is_judge"])
            self.assertFalse(node["payload"]["winner_selected"])

    def test_triumvirate_crosses_portable_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            source_path = Path(source)
            target_path = Path(target)
            world = PlayableGenesisV187(source_path)
            claims = [
                self._source_claim(world, path="data/a.json", text="A"),
                self._source_claim(world, path="data/b.json", text="B"),
                self._source_claim(world, path="data/c.json", text="C"),
            ]
            dispute_id = world.record_triumvirate_dispute(claims, confidence=0.91)

            output = source_path.parent / "triumvirate.genesis-save.json"
            try:
                manager = PortableSaveManager(source_path)
                manager.export_to(output, label="Three grounded voices")
                bundle = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(bundle["runtime_version"], "18.7.8")
                self.assertTrue(manager.verify_bundle(bundle)[0])

                PortableSaveManager(target_path).import_bundle(bundle)
                restored = PlayableGenesisV187(target_path)
                state = restored.triumvirate_witness_state()
                dispute = restored._plural_store()["triumvirates"][dispute_id]

                self.assertTrue(state["valid"], state["error"])
                self.assertEqual(state["verified_triumvirates"], 1)
                self.assertEqual(len(dispute["claim_ids"]), 3)
                self.assertEqual(len(set(dispute["voice_scopes"])), 3)
                self.assertFalse(dispute["third_voice_is_judge"])
                self.assertFalse(dispute["winner_selected"])
            finally:
                output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
