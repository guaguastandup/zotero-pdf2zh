import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pymupdf

from utils.cropper import Cropper


class CropRenderingTests(unittest.TestCase):
    def test_both_columns_remain_visible_after_crop_compare(self):
        # Exercise actual PDF serialization and raster rendering, not just text
        # extraction: selectable text alone does not establish visibility.
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.TB_dual.pdf"
            result = Path(tmp) / "sample.crop-compare.pdf"
            labels = (("ORIGINAL_LEFT", "ORIGINAL_RIGHT"), ("TRANSLATED_LEFT", "TRANSLATED_RIGHT"))
            with pymupdf.open() as document:
                for left, right in labels:
                    page = document.new_page(width=600, height=800)
                    page.insert_text((90, 180), left, fontsize=12, color=(0, 0, 0))
                    page.insert_text((370, 180), right, fontsize=12, color=(0, 0, 0))
                document.save(source)
            config = SimpleNamespace(pdf_w_offset=40, pdf_h_offset=20, pdf_offset_ratio=5)
            with contextlib.redirect_stdout(io.StringIO()):
                Cropper().crop_pdf(config, str(source), "dual", str(result), "crop-compare")
            with pymupdf.open(result) as document:
                self.assertEqual(len(document), 2)
                for index, page in enumerate(document):
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), colorspace=pymupdf.csGRAY)
                    matrix = page.rect.torect(pix.irect)
                    for pair in labels:
                        hits = page.search_for(pair[index])
                        self.assertEqual(len(hits), 1)
                        white_fraction, _ = pix.color_topusage(clip=hits[0] * matrix)
                        self.assertLess(white_fraction, 0.98, f"Invisible text: {pair[index]}")


if __name__ == "__main__":
    unittest.main()
