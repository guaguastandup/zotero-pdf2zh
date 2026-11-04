"""Optional checks against real BabelDOC IL objects; no model or API calls."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from utils.table_runtime import SUPPORTED_BABELDOC_VERSIONS, install_table_policy


@unittest.skipUnless(importlib.util.find_spec("babeldoc"), "BabelDOC is not installed")
class BabelDOCTablePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from importlib.metadata import version

        if version("BabelDOC") not in SUPPORTED_BABELDOC_VERSIONS:
            raise unittest.SkipTest("Unsupported BabelDOC version")
        # translator.cache opens a SQLite database at import time. Do not write
        # to the user's translation cache while testing the adapter.
        import babeldoc.const as constants

        cls.cache_dir = tempfile.TemporaryDirectory()
        previous = constants.CACHE_FOLDER
        constants.CACHE_FOLDER = Path(cls.cache_dir.name)
        try:
            from babeldoc.translator import cache

            cls.cache = cache
        finally:
            constants.CACHE_FOLDER = previous
        from babeldoc.format.pdf.document_il import il_version_1 as il
        from babeldoc.format.pdf.document_il.midend.paragraph_finder import (
            ParagraphFinder,
        )
        from babeldoc.format.pdf.document_il.midend.typesetting import Typesetting

        cls.finder_class, cls.typesetter_class, cls.il = (
            ParagraphFinder,
            Typesetting,
            il,
        )

    @classmethod
    def tearDownClass(cls):
        cls.cache.db.close()
        cls.cache_dir.cleanup()

    def char(self, text, x=10, y=10):
        il = self.il
        return il.PdfCharacter(
            box=il.Box(x, y, x + 4, y + 8),
            visual_bbox=il.VisualBbox(box=il.Box(x, y, x + 4, y + 8)),
            pdf_style=il.PdfStyle(font_id="f1", font_size=10),
            char_unicode=text,
            vertical=False,
            xobj_id=-1,
        )

    def page(self, chars):
        return self.il.Page(
            page_number=0,
            pdf_character=chars,
            page_layout=[
                self.il.PageLayout(
                    id=1, class_name="table", box=self.il.Box(0, 0, 100, 100)
                )
            ],
        )

    def finder(self):
        finder = object.__new__(self.finder_class)
        finder.translation_config = SimpleNamespace(ocr_workaround=False)
        return finder

    def test_numeric_figure_columns_bypass_native_paragraph_reflow(self):
        values = [
            self.char(c, x=10 + col * 45 + i * 4, y=10)
            for col, text in enumerate(("0.2480", "0.4521", "0.8825"))
            for i, c in enumerate(text)
        ]
        label = self.char("A", x=10, y=40)
        page = self.page([*values, label])
        page.page_layout[0].class_name = "figure"
        page.page_layout[0].box.x2 = 150
        before = [(c.box.x, c.box.y, c.pdf_style.font_id) for c in values]
        seen = []

        def native(finder, page):
            seen.extend(page.pdf_character)
            page.pdf_character = []

        with patch.object(self.finder_class, "process_page", native):
            restore = install_table_policy("fixed")
            try:
                self.finder().process_page(page)
            finally:
                restore()
        self.assertEqual(seen, [label])
        self.assertEqual(page.pdf_character, values)
        self.assertEqual(
            [(c.box.x, c.box.y, c.pdf_style.font_id) for c in values], before
        )

    def test_fixed_falls_back_to_original_glyphs_when_translation_cannot_fit(self):
        original = self.char("Dataset")
        page = self.page([original])
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                self.finder().process_page(page)
                paragraph = page.pdf_paragraph[0]
                source_box = paragraph.box
                typesetter = object.__new__(self.typesetter_class)
                with patch.object(
                    self.typesetter_class,
                    "_layout_typesetting_units",
                    return_value=([], False),
                ):
                    scale, units = typesetter._find_optimal_scale_and_layout(
                        paragraph, page, []
                    )
                self.assertEqual(paragraph.box, source_box)
                self.assertEqual(paragraph.unicode, "Dataset")
                self.assertEqual(
                    paragraph.pdf_paragraph_composition[0].pdf_character, original
                )
                from babeldoc.format.pdf.document_il.backend.pdf_creater import (
                    PDFCreater,
                )

                creator = object.__new__(PDFCreater)
                self.assertEqual(
                    creator.render_paragraph_to_char(paragraph), [original]
                )
                self.assertEqual(scale, 1)
                self.assertIsNone(units)
            finally:
                restore()


if __name__ == "__main__":
    unittest.main()
