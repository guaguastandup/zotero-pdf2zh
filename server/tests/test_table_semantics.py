"""Model grouping preserves source fragments and rejects unsafe responses."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from utils.table_semantics import INPUT_MARKER, group_table_semantics


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

        self.translator.llm_translate.reset_mock()
        self.translator.llm_translate.side_effect = RuntimeError("service unavailable")
        self.assertIs(self.group(), self.units)
        self.translator.llm_translate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
