from __future__ import annotations

import unittest

from tools.select_git_habitat_inbox_issues import is_habitat_inbox_issue, select_rows


class HabitatInboxSelectorTests(unittest.TestCase):
    def row(self, number: int, title: str, labels=None):
        return {
            "number": number,
            "title": title,
            "body": "body",
            "url": f"https://github.test/issues/{number}",
            "updatedAt": "2026-08-16T14:00:00Z",
            "labels": labels or [],
        }

    def test_explicit_label_is_selected(self):
        row = self.row(1, "ordinary issue", [{"name": "janus-inbox"}])
        self.assertTrue(is_habitat_inbox_issue(row))

    def test_face_issue_is_selected_without_label(self):
        self.assertTrue(is_habitat_inbox_issue(self.row(2, "[JANUS FACE: GUARD_PLUS] Check CI")))
        self.assertTrue(is_habitat_inbox_issue(self.row(3, "[JANUS FACE COUNCIL] Dispatch")))

    def test_similar_but_unbound_title_is_not_selected(self):
        self.assertFalse(is_habitat_inbox_issue(self.row(4, "JANUS FACE: no brackets")))
        self.assertFalse(is_habitat_inbox_issue(self.row(5, "Re: [JANUS FACE: GUARD_PLUS]")))
        self.assertFalse(is_habitat_inbox_issue(self.row(6, "ordinary issue")))

    def test_selector_strips_labels_and_preserves_issue_identity_fields(self):
        rows = [
            self.row(7, "[JANUS FACE: LEFT_HRAIN] receipt"),
            self.row(8, "ordinary issue"),
        ]
        selected = select_rows(rows)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0], {
            "number": 7,
            "title": "[JANUS FACE: LEFT_HRAIN] receipt",
            "body": "body",
            "url": "https://github.test/issues/7",
            "updatedAt": "2026-08-16T14:00:00Z",
        })
        self.assertNotIn("labels", selected[0])

    def test_selection_does_not_assign_authority_fields(self):
        selected = select_rows([self.row(9, "[JANUS FACE: RIGHT_INAIHR] context")])
        self.assertEqual(len(selected), 1)
        self.assertNotIn("command_authority", selected[0])
        self.assertNotIn("external_effect_authority", selected[0])


if __name__ == "__main__":
    unittest.main()
