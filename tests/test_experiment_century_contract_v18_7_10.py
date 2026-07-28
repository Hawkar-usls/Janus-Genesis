from __future__ import annotations

import unittest

from experiments.century_of_absurd_professions_v18_7_10 import (
    ABSURD_ACTIONS,
    CAST_CATALOG,
    PROFESSIONS,
    YEARS_TO_LIVE,
)


class CenturyLivedAuditContractTests(unittest.TestCase):
    def test_century_contract_is_large_and_distinct(self) -> None:
        self.assertGreaterEqual(YEARS_TO_LIVE, 100)
        self.assertEqual(len(PROFESSIONS), 50)
        self.assertEqual(len({name for name, _frame in PROFESSIONS}), 50)
        self.assertGreaterEqual(len(ABSURD_ACTIONS), 10)
        self.assertGreaterEqual(len(CAST_CATALOG), 10)

    def test_immoral_professions_are_explicitly_fictional_and_powerless(self) -> None:
        immoral = [
            (name, frame)
            for name, frame in PROFESSIONS
            if frame == "fictional_immoral_role_no_real_authority"
        ]
        self.assertGreaterEqual(len(immoral), 10)
        self.assertTrue(all(frame.endswith("no_real_authority") for _name, frame in immoral))


if __name__ == "__main__":
    unittest.main()
