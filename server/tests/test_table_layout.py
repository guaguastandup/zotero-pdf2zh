import unittest
from types import SimpleNamespace as NS

from utils.table_layout import (
    cell_horizontal_bounds,
    separate_cell_envelopes,
    source_alignment,
)
from utils.table_structure import identifier_list, same_table_content


class CellBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.table = NS(x=0, y=0, x2=100, y2=100)
        self.source = (20, 30, 40, 40)
        self.bounds = (20, 28, 45, 42)

    def test_no_column_evidence_keeps_whitespace_bounds(self):
        self.assertEqual(
            cell_horizontal_bounds(self.bounds, self.source, self.table, [], []),
            self.bounds,
        )

    def test_inferred_column_supplies_common_alignment_envelope(self):
        self.assertEqual(
            cell_horizontal_bounds(self.bounds, self.source, self.table, [], [10, 50]),
            (20, 28, 49.5, 42),
        )

    def test_actual_vertical_rules_bound_cell(self):
        curves = [NS(box=NS(x=x, x2=x, y=10, y2=50)) for x in (15, 48)]
        self.assertEqual(
            cell_horizontal_bounds(self.bounds, self.source, self.table, curves, []),
            (15.5, 28, 47.5, 42),
        )

    def test_partial_vertical_rule_does_not_split_spanning_cell(self):
        curves = [NS(box=NS(x=25, x2=25, y=0, y2=20))]
        self.assertEqual(
            cell_horizontal_bounds(self.bounds, self.source, self.table, curves, []),
            self.bounds,
        )

    def test_inferred_boundary_inside_source_cannot_cut_glyphs(self):
        bounds = cell_horizontal_bounds(
            self.bounds, self.source, self.table, [], [10, 30, 50]
        )
        self.assertLessEqual(bounds[0], self.source[0])
        self.assertGreaterEqual(bounds[2], self.source[2])

    def test_adjacent_cells_share_gap_instead_of_both_expanding_into_it(self):
        bounds = [(0, 0, 60, 30), (40, 0, 100, 30)]
        sources = [(10, 10, 30, 20), (70, 10, 90, 20)]
        a, b = separate_cell_envelopes(bounds, sources)
        self.assertEqual(a[2], 50)
        self.assertEqual(b[0], 50)

    def test_stacked_cells_share_vertical_gap(self):
        a, b = separate_cell_envelopes(
            [(0, 0, 50, 60), (0, 40, 50, 100)], [(10, 10, 40, 30), (10, 70, 40, 90)]
        )
        self.assertEqual(a[3], 50)
        self.assertEqual(b[1], 50)


class SourceStyleTests(unittest.TestCase):
    def line(self, left, right):
        return [
            NS(
                char_unicode="Text",
                visual_bbox=NS(box=NS(x=left, x2=right)),
                pdf_style=NS(font_size=10),
            )
        ]

    def test_multiline_original_alignment(self):
        for edges, expected in [
            ([(10, 50), (10, 40)], ("left", 10)),
            ([(10, 50), (20, 40)], ("center", 30)),
            ([(10, 50), (20, 50)], ("right", 50)),
        ]:
            self.assertEqual(
                source_alignment([self.line(a, b) for a, b in edges]), expected
            )

    def test_ambiguous_single_line_keeps_source_left_edge(self):
        self.assertEqual(source_alignment([self.line(20, 40)]), ("left", 20))

    def test_single_line_center_requires_repeated_peer_evidence(self):
        source = [self.line(20, 40)]
        peers = [[self.line(25, 35)], [self.line(22, 38)], [self.line(24, 36)]]
        self.assertEqual(source_alignment(source, peers), ("center", 30))

    def test_identifier_rosters_preserved_but_prose_is_not(self):
        self.assertTrue(
            identifier_list("Allegro, Revo2, DexHand021, Leap, Orca, RH56DFX")
        )
        self.assertTrue(
            identifier_list("Jaka Zu7 + DexHand021, KUKA + Sharpa, UR5 + Shadow Hand")
        )
        self.assertFalse(
            identifier_list("Revo2 is fast, DexHand021 works well, Leap looks good")
        )
        self.assertFalse(identifier_list("Open, Close, Turn"))
        self.assertFalse(identifier_list("Speed 10, Mass 20, Height 30"))

    def test_punctuation_only_edits_do_not_count_as_translation(self):
        self.assertTrue(same_table_content("Allegro, Revo2", "Allegro、Revo2"))
        self.assertFalse(same_table_content("Dataset", "数据集"))
        self.assertFalse(same_table_content("Model 25", "Model 26"))
