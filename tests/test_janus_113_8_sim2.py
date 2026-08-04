from __future__ import annotations

import inspect
import json
import unittest

from sim import janus_113_8_sim2_builder as builder
from sim import janus_113_8_sim2_evaluator as evaluator
from sim import janus_113_8_sim2_router as router


DATA = b"JANUS PUBLIC FIXTURE\nrequired marker\n"
SNAPSHOT = {
    "source_id": "TEST_SOURCE",
    "repository": "example/project",
    "ref": "v1.0.0",
    "path": "README",
    "raw_url": "https://raw.githubusercontent.com/example/project/v1.0.0/README",
    "required_marker": "required marker",
    "observed_sha256": builder.sha256_bytes(DATA),
    "observed_size_bytes": len(DATA),
    "required_marker_present": True,
}


def build_fixture(seed: int = 1138001938):
    return builder.build_cases([SNAPSHOT], seed=seed, repetitions=1)


def fake_fetch(url: str) -> bytes:
    if ".janus-missing-" in url:
        raise RuntimeError("synthetic 404")
    if url == SNAPSHOT["raw_url"]:
        return DATA
    raise AssertionError(f"unexpected network target: {url}")


class JanusSim2Tests(unittest.TestCase):
    def test_builder_is_deterministic(self) -> None:
        first = build_fixture()
        second = build_fixture()
        self.assertEqual(first, second)

    def test_different_seed_changes_held_out_order(self) -> None:
        first_cases, _ = build_fixture(1)
        second_cases, _ = build_fixture(2)
        self.assertNotEqual(
            [case["case_id"] for case in first_cases],
            [case["case_id"] for case in second_cases],
        )

    def test_all_mutation_classes_are_emitted(self) -> None:
        _, truth = build_fixture()
        self.assertEqual(
            {item["mutation_class"] for item in truth},
            set(builder.MUTATIONS),
        )
        self.assertEqual(len(truth), 10)

    def test_public_cases_preserve_fail_closed_authority(self) -> None:
        cases, _ = build_fixture()
        for case in cases:
            self.assertIs(case["read_only"], True)
            self.assertEqual(case["runtime_authority"], "NONE")
            self.assertNotIn("expected_terminal", case)
            self.assertNotIn("mutation_class", case)

    def test_router_matches_all_synthetic_terminals(self) -> None:
        cases, truth = build_fixture()
        truth_by_id = {item["case_id"]: item for item in truth}
        cache: dict[str, bytes | Exception] = {}
        decisions = [router.evaluate_case(case, fetcher=fake_fetch, cache=cache) for case in cases]
        self.assertEqual(
            {decision["case_id"] for decision in decisions},
            set(truth_by_id),
        )
        for decision in decisions:
            self.assertEqual(
                decision["decision_terminal"],
                truth_by_id[decision["case_id"]]["expected_terminal"],
                decision,
            )

    def test_router_does_not_fetch_blocked_or_unpinned_cases(self) -> None:
        cases, truth = build_fixture()
        truth_by_id = {item["case_id"]: item for item in truth}
        calls: list[str] = []

        def forbidden_fetch(url: str) -> bytes:
            calls.append(url)
            raise AssertionError("fetch should not be called")

        selected = [
            case
            for case in cases
            if truth_by_id[case["case_id"]]["mutation_class"]
            in {"unpinned_ref", "disallowed_host", "unsupported_scheme", "conflicting_claims"}
        ]
        for case in selected:
            router.evaluate_case(case, fetcher=forbidden_fetch, cache={})
        self.assertEqual(calls, [])

    def test_evaluator_reconstructs_all_terminals_without_router(self) -> None:
        cases, truth = build_fixture()
        truth_by_id = {item["case_id"]: item for item in truth}
        cache: dict[str, bytes | Exception] = {
            SNAPSHOT["raw_url"]: DATA,
        }
        for case in cases:
            if ".janus-missing-" in case["source_url"]:
                cache[case["source_url"]] = RuntimeError("synthetic 404")
            terminal, _ = evaluator.independent_terminal(case, cache)
            self.assertEqual(terminal, truth_by_id[case["case_id"]]["expected_terminal"])

    def test_evaluator_does_not_import_builder_or_router(self) -> None:
        source = inspect.getsource(evaluator)
        self.assertNotIn("import janus_113_8_sim2_builder", source)
        self.assertNotIn("import janus_113_8_sim2_router", source)
        self.assertNotIn("from sim import janus_113_8_sim2_builder", source)
        self.assertNotIn("from sim import janus_113_8_sim2_router", source)

    def test_calibration_metric_contract(self) -> None:
        probabilities = [0.99] * 20 + [0.01] * 80
        labels = [1] * 20 + [0] * 80
        brier = sum((p - y) ** 2 for p, y in zip(probabilities, labels, strict=True)) / len(labels)
        ece, bins = evaluator.expected_calibration_error(probabilities, labels)
        self.assertAlmostEqual(brier, 0.0001, places=12)
        self.assertAlmostEqual(ece, 0.01, places=12)
        self.assertEqual(sum(row["count"] for row in bins), 100)

    def test_witness_ledger_replay_and_tamper_detection(self) -> None:
        cases, _ = build_fixture()
        predictions = [router.evaluate_case(case, fetcher=fake_fetch, cache={}) for case in cases]
        previous = "0" * 64
        ledger = []
        for ordinal, prediction in enumerate(predictions):
            body = {
                "ordinal": ordinal,
                "case_id": prediction["case_id"],
                "prediction_sha256": prediction["prediction_sha256"],
                "prev_hash": previous,
            }
            entry_hash = evaluator.sha256_text(evaluator.canonical_json(body))
            ledger.append({**body, "entry_hash": entry_hash})
            previous = entry_hash
        ok, final_hash = evaluator.verify_witness_ledger(predictions, ledger)
        self.assertTrue(ok)
        self.assertEqual(final_hash, previous)
        tampered = json.loads(json.dumps(ledger))
        tampered[-1]["entry_hash"] = "0" * 64
        ok, _ = evaluator.verify_witness_ledger(predictions, tampered)
        self.assertFalse(ok)

    def test_repetition_bounds_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            builder.build_cases([SNAPSHOT], seed=1, repetitions=0)
        with self.assertRaises(ValueError):
            builder.build_cases(
                [SNAPSHOT], seed=1, repetitions=builder.MAX_REPETITIONS + 1
            )

    def test_router_prediction_hash_is_self_consistent(self) -> None:
        cases, truth = build_fixture()
        exact_id = next(
            item["case_id"] for item in truth if item["mutation_class"] == "exact_valid"
        )
        case = next(item for item in cases if item["case_id"] == exact_id)
        prediction = router.evaluate_case(case, fetcher=fake_fetch, cache={})
        claimed = prediction.pop("prediction_sha256")
        self.assertEqual(claimed, router.sha256_text(router.canonical_json(prediction)))


if __name__ == "__main__":
    unittest.main()
