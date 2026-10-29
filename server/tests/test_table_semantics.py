"""Text-only grouping contract and geometric rejection; no engine or API needed."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from utils.table_semantics import INPUT_MARKER, MAX_FRAGMENTS, group_table_semantics


def box(x, y, x2, y2):
    return SimpleNamespace(x=x, y=y, x2=x2, y2=y2)


def unit(text, x, y, width=25):
    char = SimpleNamespace(
        text=text,
        visual_bbox=SimpleNamespace(box=box(x, y, x + width, y + 8)),
        pdf_style=SimpleNamespace(font_size=10),
        xobj_id=0,
    )
    return [[char]]


class TableSemanticsTests(unittest.TestCase):
    def test_wide_spacing_still_obeys_column_and_rule_boundaries(self):
        from utils.table_semantics import _valid_group

        units = [unit("Long", 10, 20, 15), unit("label", 50, 20, 15)]
        bounds = [(10, 20, 25, 28), (50, 20, 65, 28)]
        args = ([0, 1], bounds, units, ["Long", "label"])
        self.assertFalse(_valid_group(*args, [], columns=[80]))
        self.assertTrue(_valid_group(*args, [], columns=[80], allow_wide_spacing=True))
        self.assertFalse(_valid_group(*args, [], columns=[40], allow_wide_spacing=True))
        self.assertFalse(
            _valid_group(*args, [(40, 0, 40, 40)], allow_wide_spacing=True)
        )

    def test_shared_baseline_orders_different_height_glyphs_left_to_right(self):
        from utils.table_semantics import _reading_order

        units = [unit("limits;", 10, 20, 15), unit("and", 30, 22.6, 15)]
        for u in units:
            u[0][0].box = box(0, 18, 0, 28)
        self.assertEqual(
            _reading_order([1, 0], [(10, 20, 25, 28), (30, 22.6, 45, 30.6)], units),
            [0, 1],
        )

    def test_retained_rotated_text_blocks_merge_without_image_payload(self):
        units = [unit("Upper", 110, 360), unit("lower", 110, 346)]
        translator = SimpleNamespace(
            llm_translate=Mock(return_value='{"is_code":false,"merge_groups":[[0,1]]}')
        )
        result = group_table_semantics(
            units,
            box(100, 200, 300, 400),
            [],
            lambda r: r[0].text,
            translator,
            protected_rects=[(110, 355, 135, 359)],
        )
        self.assertIs(result, units)
        payload = json.loads(
            translator.llm_translate.call_args.args[0].split(INPUT_MARKER)[1]
        )
        self.assertIn("retained_text_obstacles", payload)
        self.assertNotIn("image_obstacles", payload)

    def test_empty_image_list_leaves_ordinary_table_prompt_identical(self):
        units = [unit("Header", 110, 360)]
        translator = SimpleNamespace(
            llm_translate=Mock(return_value='{"is_code":false,"merge_groups":[]}')
        )
        args = (units, box(100, 200, 300, 400), [], lambda r: r[0].text, translator)
        group_table_semantics(*args)
        original = translator.llm_translate.call_args.args[0]
        group_table_semantics(*args, image_rects=[])
        self.assertEqual(translator.llm_translate.call_args.args[0], original)
        self.assertNotIn("image_obstacles", original)

    def test_image_blocks_merge_and_only_coordinates_are_submitted(self):
        units = [unit("Upper", 110, 360), unit("lower", 110, 346)]
        translator = SimpleNamespace(
            llm_translate=Mock(return_value='{"is_code":false,"merge_groups":[[0,1]]}')
        )
        result = group_table_semantics(
            units,
            box(100, 200, 300, 400),
            [],
            lambda r: r[0].text,
            translator,
            image_rects=[(110, 355, 135, 359)],
        )
        self.assertIs(result, units)
        payload = json.loads(
            translator.llm_translate.call_args.args[0].split(INPUT_MARKER)[1]
        )
        self.assertEqual(payload["image_obstacles"], [[10, 41, 35, 45]])

    def test_rejected_candidate_retains_source_pieces_without_forcing_merge(self):
        units = [unit("Upper", 110, 360), unit("lower", 110, 346)]
        translator = SimpleNamespace(
            llm_translate=Mock(return_value='{"is_code":false,"merge_groups":[[0,1]]}')
        )
        policies = {}
        result = group_table_semantics(
            units,
            box(100, 200, 300, 400),
            [],
            lambda r: r[0].text,
            translator,
            policies,
            row_boundaries=[355],
            merge_candidates=[[0, 1]],
        )
        self.assertIs(result, units)
        self.assertEqual(len(policies), 2)
        self.assertTrue(all(not p[0]["translate"] for p in policies.values()))

    def test_inline_count_requires_both_candidate_and_sentence_confirmation(self):
        units = [unit("25", 110, 360, 10), unit("samples", 125, 360, 30)]
        for candidate, sentence, expected in [
            (True, True, 1),
            (False, True, 2),
            (True, False, 2),
        ]:
            response = {
                "is_code": False,
                "merge_groups": [[0, 1]],
                "units": ([{"ids": [0, 1], "kind": "sentence"}] if sentence else []),
            }
            translator = SimpleNamespace(
                llm_translate=Mock(return_value=json.dumps(response))
            )
            result = group_table_semantics(
                units,
                box(100, 200, 300, 400),
                [],
                lambda r: r[0].text,
                translator,
                merge_candidates=[[0, 1]] if candidate else [],
            )
            self.assertEqual(len(result), expected)

    def test_inferred_row_through_glyph_is_weak_but_real_rule_still_blocks(self):
        units = [unit("Upper", 110, 360), unit("lower", 110, 346)]
        translator = SimpleNamespace(
            llm_translate=Mock(return_value='{"is_code":false,"merge_groups":[[0,1]]}')
        )
        for y, curves, expected in [
            (362, [], 1),
            (355, [], 2),
            (362, [SimpleNamespace(box=box(100, 362, 300, 362))], 2),
        ]:
            with self.subTest(y=y, real=bool(curves)):
                result = group_table_semantics(
                    units,
                    box(100, 200, 300, 400),
                    curves,
                    lambda r: r[0].text,
                    translator,
                    row_boundaries=[y],
                )
                self.assertEqual(len(result), expected)

    def test_confirmed_spanning_label_can_cross_inferred_row_but_not_real_rule(self):
        units = [unit("Group", 110, 360), unit("label", 110, 346)]
        translator = SimpleNamespace(
            llm_translate=Mock(return_value='{"is_code":false,"merge_groups":[[0,1]]}')
        )
        for curves, expected in [
            ([], 1),
            ([SimpleNamespace(box=box(100, 355, 300, 355))], 2),
        ]:
            with self.subTest(real_rule=bool(curves)):
                result = group_table_semantics(
                    units,
                    box(100, 200, 300, 400),
                    curves,
                    lambda r: r[0].text,
                    translator,
                    row_boundaries=[355],
                    spanning_candidates=[[0, 1]],
                )
                self.assertEqual(len(result), expected)

    def test_local_candidate_can_be_rejected_or_split_without_losing_fragments(self):
        units = [
            unit("Revenue", 110, 360),
            unit("before tax", 110, 346),
            unit("Notes", 210, 346),
        ]
        for groups, sizes in [([], [1, 1, 1]), ([[0, 1]], [2, 1])]:
            translator = SimpleNamespace(
                llm_translate=Mock(
                    return_value=json.dumps({"is_code": False, "merge_groups": groups})
                )
            )
            result = group_table_semantics(
                units,
                box(100, 200, 300, 400),
                [],
                lambda r: r[0].text,
                translator,
                merge_candidates=[[0, 1, 2]],
            )
            self.assertEqual([len(u) for u in result], sizes)
            self.assertCountEqual(
                [id(c) for u in result for r in u for c in r],
                [id(c) for u in units for r in u for c in r],
            )
            payload = json.loads(
                translator.llm_translate.call_args.args[0].split(INPUT_MARKER)[1]
            )
            self.assertEqual(payload["merge_candidates"], [[0, 1, 2]])
            self.assertEqual(len(payload["fragments"]), 3)

    def setUp(self):
        self.table = box(100, 200, 300, 400)
        self.units = [unit("Human", 110, 360), unit("2Robot", 110, 346)]
        self.translator = SimpleNamespace(
            llm_translate=Mock(return_value='{"is_code":false,"merge_groups":[[1,0]]}')
        )

    def group(self, units=None, curves=()):
        return group_table_semantics(
            self.units if units is None else units,
            self.table,
            curves,
            lambda run: "".join(c.text for c in run),
            self.translator,
        )

    def test_unruled_wrapped_label_groups_in_reading_order_without_changing_glyphs(
        self,
    ):
        result = self.group()
        self.assertEqual(result, [self.units[0] + self.units[1]])
        self.assertIs(result[0][0][0], self.units[0][0][0])
        self.translator.llm_translate.assert_called_once()

    def test_payload_contains_entire_table_text_and_clipped_relative_rules(self):
        units = self.units + [unit("0.95", 210, 360)]
        curves = [
            SimpleNamespace(box=box(90, 380, 310, 380)),
            SimpleNamespace(box=box(180, 190, 180, 410)),
            SimpleNamespace(box=box(110, 210, 130, 230)),  # Drawing, not a rule.
        ]
        self.group(units, curves)
        prompt = self.translator.llm_translate.call_args.args[0]
        payload = json.loads(prompt.split(INPUT_MARKER)[1])
        self.assertEqual(payload["fragments"][0]["bbox"], [10, 32, 35, 40])
        self.assertEqual(
            [f["text"] for f in payload["fragments"]], ["Human", "2Robot", "0.95"]
        )
        self.assertCountEqual(payload["lines"], [[0, 20, 200, 20], [80, 0, 80, 200]])

    def test_same_line_word_fragments_can_merge(self):
        result = self.group([unit("Task", 110, 360), unit("description", 141, 360)])
        self.assertEqual(len(result), 1)

    def test_font_height_difference_preserves_left_to_right_reading_order(self):
        result = self.group([unit("Task", 110, 360), unit("description", 141, 360.5)])
        self.assertEqual([run[0].text for run in result[0]], ["Task", "description"])

    def test_repeated_symbol_columns_prevent_close_header_merge_without_gutters(self):
        units = [unit("Left", 110, 360, 15), unit("Right", 135, 360, 15)]
        for y in [340, 325, 310]:
            units.extend([unit("✓", 113, y, 9), unit("×", 138, y, 9)])
        self.assertIs(self.group(units), units)

    def test_numeric_unit_cannot_be_merged_into_adjacent_text(self):
        for value in ["90M", "1080p", "2e-3", "1920x1080"]:
            with self.subTest(value=value):
                units = [unit("Data", 110, 360), unit(value, 140, 360)]
                self.assertIs(self.group(units), units)

    def test_small_font_top_difference_cannot_hide_a_cross_column_gap(self):
        units = [unit("Left", 110, 360), unit("Right", 210, 360.1)]
        self.assertIs(self.group(units), units)

    def test_inferred_column_boundary_prevents_close_metric_header_merge(self):
        units = [unit("M1", 110, 360, width=10), unit("M2", 126, 360, width=10)]
        result = group_table_semantics(
            units,
            self.table,
            [],
            lambda r: r[0].text,
            self.translator,
            column_boundaries=[123],
        )
        self.assertIs(result, units)

    def test_original_local_group_is_indivisible(self):
        local = [self.units[0] + self.units[1], unit("Dataset", 210, 360)]
        self.translator.llm_translate.return_value = (
            '{"is_code":false,"merge_groups":[]}'
        )
        result = self.group(local)
        self.assertEqual(result, local)
        payload = json.loads(
            self.translator.llm_translate.call_args.args[0].split(INPUT_MARKER)[1]
        )
        self.assertEqual(payload["fragments"][0]["text"], "Human 2Robot")

    def test_invalid_schema_or_ids_fall_back_to_original_groups(self):
        for response in [
            "not JSON",
            "[]",
            '{"is_code":false,"merge_groups":null}',
            '{"is_code":false,"merge_groups":[[0,2]]}',
            '{"is_code":false,"merge_groups":[[true,1]]}',
            '{"is_code":false,"merge_groups":[[0,0]]}',
            '{"is_code":false,"merge_groups":[[0]]}',
            '{"is_code":false,"merge_groups":[],"translated_text":"changed"}',
        ]:
            with self.subTest(response=response):
                self.translator.llm_translate.return_value = response
                self.assertIs(self.group(), self.units)

    def test_singletons_and_duplicate_safe_groups_do_not_discard_other_cells(self):
        self.translator.llm_translate.return_value = (
            '{"is_code":false,"merge_groups":[[0],[0,1]]}'
        )
        self.assertEqual(len(self.group()), 1)
        self.translator.llm_translate.return_value = (
            '{"is_code":false,"merge_groups":[[0,1],[0,1]]}'
        )
        self.assertEqual(len(self.group()), 1)

    def test_conflicting_groups_are_rejected_without_losing_independent_group(self):
        units = [
            unit("first", 110, 370),
            unit("second", 110, 356),
            unit("third", 110, 342),
            unit("Other", 210, 370),
            unit("label", 210, 356),
        ]
        self.translator.llm_translate.return_value = (
            '{"is_code":false,"merge_groups":[[0,1],[1,2],[3,4]]}'
        )
        result = self.group(units)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[-1], units[3] + units[4])

    def test_horizontal_separator_prevents_merge(self):
        curves = [SimpleNamespace(box=box(100, 357, 300, 357))]
        self.assertIs(self.group(curves=curves), self.units)

    def test_vertical_separator_prevents_same_line_merge(self):
        units = [unit("Task", 110, 360), unit("description", 141, 360)]
        curves = [SimpleNamespace(box=box(138, 350, 138, 380))]
        self.assertIs(self.group(units, curves), units)

    def test_adjacent_columns_and_numeric_values_cannot_be_consumed(self):
        for other in [unit("Method", 210, 346), unit("7.96", 110, 346)]:
            units = [self.units[0], other]
            self.assertIs(self.group(units), units)

    def test_intervening_fragment_prevents_merge(self):
        units = [self.units[0], unit("next row", 110, 345), unit("label", 110, 330)]
        self.translator.llm_translate.return_value = (
            '{"is_code":false,"merge_groups":[[0,2]]}'
        )
        self.assertIs(self.group(units), units)

    def test_api_failure_does_not_retry_or_change_local_result(self):
        self.translator.llm_translate.side_effect = RuntimeError("service unavailable")
        self.assertIs(self.group(), self.units)
        self.translator.llm_translate.assert_called_once()

    def test_unavailable_translator_and_large_table_do_not_request(self):
        self.assertEqual(
            group_table_semantics(self.units, self.table, [], str, None), self.units
        )
        units = self.units * (MAX_FRAGMENTS // len(self.units) + 1)
        self.assertIs(self.group(units), units)
        self.translator.llm_translate.assert_not_called()

    def test_fenced_json_is_accepted(self):
        self.translator.llm_translate.return_value = (
            '```json\n{"is_code":false,"merge_groups":[[0,1]]}\n```'
        )
        self.assertEqual(len(self.group()), 1)

    def test_label_policy_matches_complete_final_group_source(self):
        policies = {}
        self.translator.llm_translate.return_value = json.dumps(
            {
                "is_code": False,
                "merge_groups": [[0, 1]],
                "units": [
                    {
                        "ids": [0, 1],
                        "kind": "label",
                        "parts": [{"text": "Human 2Robot", "translate": False}],
                    }
                ],
            }
        )
        group_table_semantics(
            self.units,
            self.table,
            [],
            lambda run: run[0].text,
            self.translator,
            policies,
        )
        self.assertEqual(len(policies), 1)

    def test_wrapped_label_policy_reaches_glyph_mapping_despite_spacing(self):
        from utils.table_labels import split_label_parts

        for qualifier in ("Seen", "Unseen"):
            for separator in ("", " ", "\u00a0"):
                with self.subTest(qualifier=qualifier, separator=separator):
                    units = [
                        unit("EPIC", 110, 360),
                        unit("Kitchens", 110, 346),
                        unit(f"({qualifier})", 110, 332),
                    ]
                    for lines in units:
                        lines[0][0].char_unicode = lines[0][0].text
                    parts = [
                        {"text": "EPIC" + separator, "translate": False},
                        {"text": "Kitchens" + separator, "translate": False},
                        {"text": f"({qualifier})", "translate": True},
                    ]
                    self.translator.llm_translate.return_value = json.dumps(
                        {
                            "is_code": False,
                            "merge_groups": [[0, 1, 2]],
                            "units": [
                                {"ids": [0, 1, 2], "kind": "label", "parts": parts}
                            ],
                        }
                    )
                    policies = {}
                    grouped = group_table_semantics(
                        units,
                        self.table,
                        [],
                        lambda run: run[0].text,
                        self.translator,
                        policies,
                    )
                    self.assertEqual(list(policies.values()), [parts])
                    mapped = split_label_parts(grouped[0], parts)
                    self.assertEqual(
                        [translate for _, translate in mapped], [False, False, True]
                    )
                    self.assertIs(mapped[0][0][0][0], units[0][0][0])
                    self.assertIs(mapped[1][0][0][0], units[1][0][0])
                    self.assertIs(mapped[2][0][0][0], units[2][0][0])

    def test_label_policy_still_rejects_non_whitespace_changes(self):
        for changed in ("Human 2Robots", "2Robot Human", "Human (2Robot)"):
            with self.subTest(changed=changed):
                self.translator.llm_translate.return_value = json.dumps(
                    {
                        "is_code": False,
                        "merge_groups": [[0, 1]],
                        "units": [
                            {
                                "ids": [0, 1],
                                "kind": "label",
                                "parts": [{"text": changed, "translate": False}],
                            }
                        ],
                    }
                )
                policies = {}
                group_table_semantics(
                    self.units,
                    self.table,
                    [],
                    lambda run: run[0].text,
                    self.translator,
                    policies,
                )
                self.assertEqual(policies, {})

    def test_sentence_or_changed_source_cannot_enable_partial_replacement(self):
        for kind, source in [("sentence", "Human2Robot"), ("label", "Invented name")]:
            with self.subTest(kind=kind, source=source):
                policies = {}
                self.translator.llm_translate.return_value = json.dumps(
                    {
                        "is_code": False,
                        "merge_groups": [[0, 1]],
                        "units": [
                            {
                                "ids": [0, 1],
                                "kind": kind,
                                "parts": [{"text": source, "translate": False}],
                            }
                        ],
                    }
                )
                group_table_semantics(
                    self.units,
                    self.table,
                    [],
                    lambda run: run[0].text,
                    self.translator,
                    policies,
                )
                if kind == "sentence":
                    self.assertEqual(list(policies.values()), [None])
                else:
                    self.assertEqual(policies, {})


if __name__ == "__main__":
    unittest.main()
