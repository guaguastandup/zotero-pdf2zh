"""Table row/column detection and source glyph preservation."""

import unittest
from types import SimpleNamespace

from utils.table_columns import assemble_table_cells


def run(text, x, right, y=0):
    return [
        SimpleNamespace(
            char_unicode=text,
            visual_bbox=SimpleNamespace(
                box=SimpleNamespace(x=x, x2=right, y=y, y2=y + 8)
            ),
            pdf_style=SimpleNamespace(font_size=10),
        )
    ]


class TableColumnsTests(unittest.TestCase):
    def test_enumerated_rows_bound_complete_cells_without_merging_rows(self):
        units = []
        for i, top in enumerate([170, 140, 110], 1):
            units.extend(
                [
                    [run(f"R{i}: label", 0, 70, top)],
                    [run("Sentence", 130, 210, top)],
                    [run("continued", 0, 70, top - 10)],
                    [run("continued", 130, 210, top - 10)],
                ]
            )
        result, barriers = assemble_table_cells(
            units,
            [100],
            SimpleNamespace(x=0, x2=220, y=0, y2=200),
            [],
            lambda r: r[0].char_unicode,
        )
        self.assertEqual(len(result), 6)
        self.assertTrue(all(len(u) == 2 for u in result))
        self.assertEqual(len(barriers), 2)
        self.assertCountEqual(
            [id(c) for u in result for r in u for c in r],
            [id(c) for u in units for r in u for c in r],
        )


if __name__ == "__main__":
    unittest.main()
