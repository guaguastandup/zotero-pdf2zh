"""Source glyph ownership and safe local replacement boundaries."""

import unittest
from types import SimpleNamespace

from utils.table_labels import split_label_parts


def char(text):
    return SimpleNamespace(char_unicode=text)


class TableLabelPartsTests(unittest.TestCase):
    def test_one_line_keeps_each_source_glyph_once_including_spaces(self):
        chars = [char(c) for c in "Name (Seen)"]
        result = split_label_parts(
            [chars],
            [
                {"text": "Name ", "translate": False},
                {"text": "(Seen)", "translate": True},
            ],
        )
        retained = [
            c
            for runs, translate in result
            if not translate
            for run in runs
            for c in run
        ]
        translated = [
            c for runs, translate in result if translate for run in runs for c in run
        ]
        self.assertEqual("".join(c.char_unicode for c in retained), "Name ")
        self.assertEqual("".join(c.char_unicode for c in translated), "(Seen)")
        self.assertEqual([id(c) for c in retained + translated], [id(c) for c in chars])

    def test_wrapped_label_maps_synthesized_spaces_without_changing_glyphs(self):
        lines = [[char(c) for c in text] for text in ["EPIC", "Kitchens", "(Seen)"]]
        result = split_label_parts(
            lines,
            [
                {"text": "EPIC Kitchens", "translate": False},
                {"text": " (Seen)", "translate": True},
            ],
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], lines[:2])
        self.assertEqual(result[1][0], lines[2:])

    def test_mapping_failure_or_glyph_spanning_boundary_keeps_whole_unit(self):
        for glyphs, parts in [
            ([char("Name")], [{"text": "Wrong", "translate": False}]),
            (
                [char("fi")],
                [{"text": "f", "translate": False}, {"text": "i", "translate": True}],
            ),
        ]:
            self.assertIsNone(split_label_parts([glyphs], parts))

    def test_all_translated_parts_stay_one_semantic_unit(self):
        self.assertIsNone(
            split_label_parts(
                [[char("Sentence")]], [{"text": "Sentence", "translate": True}]
            )
        )


if __name__ == "__main__":
    unittest.main()
