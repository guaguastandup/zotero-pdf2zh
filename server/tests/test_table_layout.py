"""Cell boundaries respect rules without cutting source glyphs."""

import unittest
from types import SimpleNamespace as NS

from utils.table_layout import (
    cell_horizontal_bounds,
)


class CellBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.table = NS(x=0, y=0, x2=100, y2=100)
        self.source = (20, 30, 40, 40)
        self.bounds = (20, 28, 45, 42)

    def test_cell_boundaries_respect_rules_and_preserve_source(self):
        curves = [NS(box=NS(x=x, x2=x, y=10, y2=50)) for x in (15, 48)]
        self.assertEqual(
            cell_horizontal_bounds(self.bounds, self.source, self.table, curves, []),
            (15.5, 28, 47.5, 42),
        )
        for columns in ([], [10, 30, 50]):
            with self.subTest(columns=columns):
                bounds = cell_horizontal_bounds(
                    self.bounds, self.source, self.table, [], columns
                )
                self.assertLessEqual(bounds[0], self.source[0])
                self.assertGreaterEqual(bounds[2], self.source[2])


if __name__ == "__main__":
    unittest.main()
