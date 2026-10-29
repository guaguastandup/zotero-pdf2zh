"""The code guard must be a no-op for ordinary Round 16 table decisions."""

import unittest

from utils.table_code import protect_code_region


class TableCodeTests(unittest.TestCase):
    def test_non_code_result_does_not_mutate_policies_or_status(self):
        policies, status = {"existing": "policy"}, {"success": False}
        self.assertFalse(
            protect_code_region({"is_code": False}, [], None, policies, status)
        )
        self.assertEqual(policies, {"existing": "policy"})
        self.assertEqual(status, {"success": False})

    def test_code_retains_all_fragments_except_explicit_title(self):
        units = [[["Title"]], [["x = x - delta"]]]
        policies, status = {}, {}
        self.assertTrue(
            protect_code_region(
                {"is_code": True, "caption_ids": [0]},
                units,
                lambda run: run[0],
                policies,
                status,
            )
        )
        self.assertEqual(status["preserve_ids"], [1])
        self.assertTrue(policies[frozenset([id(units[0][0][0])])][0]["translate"])
        self.assertFalse(policies[frozenset([id(units[1][0][0])])][0]["translate"])

    def test_invalid_decision_or_caption_ids_cannot_enable_translation(self):
        for result in (
            {},
            {"is_code": "false"},
            {"is_code": True, "caption_ids": [True]},
            {"is_code": True, "caption_ids": [1]},
            {"is_code": True, "caption_ids": [0, 0]},
        ):
            policies, status = {}, {"success": False}
            with self.assertRaises(ValueError):
                protect_code_region(
                    result, [[["Code"]]], lambda run: run[0], policies, status
                )
            self.assertEqual(policies, {})
            self.assertFalse(status["success"])
