"""Geometry for mixed image/text tables; no network required."""

import unittest
from types import SimpleNamespace as NS

from utils.table_images import avoid_images, image_boxes, overlaps


class TableImagesTests(unittest.TestCase):
    def test_shallow_text_intersection_is_opt_in_and_does_not_allow_real_overlap(self):
        source = (10, 10, 30, 20)
        neighbour = (12, 19.76, 32, 28)
        self.assertIsNone(avoid_images(source, source, [neighbour]))
        self.assertEqual(
            avoid_images(source, source, [neighbour], tolerance=0.3), source
        )
        self.assertIsNone(
            avoid_images(source, source, [(12, 19, 32, 28)], tolerance=0.3)
        )

    def test_only_native_images_with_positive_table_overlap(self):
        table = NS(x=0, y=0, x2=100, y2=100)
        image = NS(x=20, y=20, x2=40, y2=40)
        page = NS(
            pdf_form=[
                NS(form_type="form", box=table),
                NS(form_type="image", box=image),
                NS(form_type="image", box=NS(x=100, y=0, x2=110, y2=10)),
            ]
        )
        self.assertEqual(image_boxes(page, table), [(20, 20, 40, 40)])

    def test_expansion_is_clipped_in_each_direction(self):
        source = (10, 10, 20, 20)
        for image in [(22, 0, 30, 30), (0, 0, 8, 30), (0, 22, 30, 30), (0, 0, 30, 8)]:
            safe = avoid_images((5, 5, 25, 25), source, [image])
            self.assertIsNotNone(safe)
            self.assertFalse(overlaps(safe, image))
            self.assertLessEqual(safe[0], source[0])
            self.assertGreaterEqual(safe[2], source[2])

    def test_source_overlay_is_preserved(self):
        self.assertIsNone(
            avoid_images((5, 5, 25, 25), (10, 10, 20, 20), [(15, 15, 30, 30)])
        )


if __name__ == "__main__":
    unittest.main()
