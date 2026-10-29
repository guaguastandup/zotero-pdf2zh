import unittest
from types import SimpleNamespace

from utils.table_columns import (
    _is_value,
    assemble_table_cells,
    candidate_groups,
    coalesce_table_lines,
)


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
    def test_candidates_keep_original_fragments_available_for_rejection(self):
        original = [[run("Account", 0, 30)], [run("details", 0, 30, -10)]]
        original_ids = [id(c) for u in original for r in u for c in r]
        self.assertEqual(
            candidate_groups(original, [original[0] + original[1]]), [[0, 1]]
        )
        self.assertEqual([id(c) for u in original for r in u for c in r], original_ids)
        self.assertEqual(len(original), 2)

    def test_si_units_and_unicode_identifiers_are_not_confused(self):
        for text in ["50 ms", "1.5 kg", "12 µm", "120 Hz", "2 mol"]:
            with self.subTest(text=text):
                self.assertTrue(_is_value(text))
        for text in ["α1", "β2", "é3", "2Robot", "5 cats"]:
            with self.subTest(text=text):
                self.assertFalse(_is_value(text))

    def test_small_numeric_table_still_supplies_metric_column_boundaries(self):
        rows = [
            [run("Label", 0, 35), run("0.62", 65, 85), run("0.71", 115, 135)]
            for _ in range(4)
        ]
        columns = []
        result = coalesce_table_lines(rows, SimpleNamespace(x=0, x2=150), columns)
        self.assertIs(result, rows)
        self.assertEqual(len(columns), 2)
        self.assertTrue(35 < columns[0] < 65)
        self.assertTrue(85 < columns[1] < 115)

    def test_symbol_matrix_does_not_merge_text_description_rows(self):
        units = []
        for y in [170, 150, 130]:
            units.extend(
                [
                    [run(text, x, x + 15, y)]
                    for text, x in [
                        ("Name", 0),
                        ("✓", 40),
                        ("×", 70),
                        ("90M", 100),
                        ("Metric", 150),
                    ]
                ]
            )
        result, barriers = assemble_table_cells(
            units,
            [30, 60, 90, 130],
            SimpleNamespace(x=0, x2=200, y=0, y2=200),
            [],
            lambda r: r[0].char_unicode,
        )
        self.assertIs(result, units)
        self.assertEqual(len(barriers), 2)

    def test_repeated_short_column_values_keep_individual_data_rows(self):
        units = []
        for i, y in enumerate([170, 150, 130]):
            units.extend(
                [
                    [run(f"Model {i}", 0, 40, y)],
                    [run("API", 80, 100, y)],
                    [run("Images + Text", 130, 200, y)],
                ]
            )
        result, barriers = assemble_table_cells(
            units,
            [60, 115],
            SimpleNamespace(x=0, x2=220, y=0, y2=200),
            [],
            lambda r: r[0].char_unicode,
        )
        self.assertIs(result, units)
        self.assertEqual(len(barriers), 2)

    def test_numeric_units_are_values_but_identifiers_are_not(self):
        for text in ["90M", "338K", "1080p", "4K", "14B", "1.5GB", "1920x1080", "2e-3"]:
            with self.subTest(text=text):
                self.assertTrue(_is_value(text))
        for text in ["2Robot", "TI2V5B", "M1", "Model 2", "3 methods"]:
            with self.subTest(text=text):
                self.assertFalse(_is_value(text))

    def test_unit_matrix_does_not_merge_values_with_headers(self):
        units = []
        for y in [170, 150, 130]:
            units.extend([[run("Method", 0, 40, y)], [run("338K", 80, 110, y)]])
        result, barriers = assemble_table_cells(
            units,
            [60],
            SimpleNamespace(x=0, x2=120, y=0, y2=200),
            [],
            lambda r: r[0].char_unicode,
        )
        self.assertIs(result, units)
        self.assertEqual(len(barriers), 2)

    def test_persistent_gutter_keeps_justified_words_in_their_columns(self):
        rows = [
            [
                run("Long", 0, 20 + i * 3),
                run("text", 45 + i * 3, 85),
                run("Other", 130, 150 + i * 3),
                run("words", 175 + i * 3, 215),
            ]
            for i in range(10)
        ]
        spanning = [run("Full width heading", 0, 215)]
        result = coalesce_table_lines(rows + [spanning], SimpleNamespace(x=0, x2=220))
        self.assertEqual([len(r) for r in result], [2] * 10 + [1])
        self.assertEqual(
            [id(c) for row in result for r in row for c in r],
            [id(c) for row in rows + [spanning] for r in row for c in r],
        )

    def test_numeric_matrix_keeps_original_runs(self):
        rows = [
            [run("Name", 0, 30), run("1.23", 50, 70), run("4.56", 90, 110)]
            for _ in range(10)
        ]
        self.assertIs(coalesce_table_lines(rows, SimpleNamespace(x=0, x2=120)), rows)

    def test_sparse_table_does_not_infer_columns(self):
        rows = [[run("One", 0, 20), run("Two", 90, 110)]]
        self.assertIs(coalesce_table_lines(rows, SimpleNamespace(x=0, x2=120)), rows)

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

    def test_numeric_matrix_is_never_assembled_and_provides_row_barriers(self):
        units = []
        for y in [170, 150, 130]:
            units.extend([[run("Name", 0, 40, y)], [run("0.710", 80, 110, y)]])
        result, barriers = assemble_table_cells(
            units,
            [60],
            SimpleNamespace(x=0, x2=120, y=0, y2=200),
            [],
            lambda r: r[0].char_unicode,
        )
        self.assertIs(result, units)
        self.assertEqual(len(barriers), 2)
