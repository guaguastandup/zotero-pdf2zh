"""Keep every page and respect page-specific geometry during PDF post-processing."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pymupdf as fitz
from utils.cropper import Cropper


class CropIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.config = SimpleNamespace(pdf_w_offset=0, pdf_h_offset=0,
                                      pdf_offset_ratio=5, trans_first=True)
        self.cropper = Cropper()

    def source(self, sizes, name='paper.TB_dual.pdf'):
        source = self.root / name
        with fitz.open() as doc:
            for i, (w, h) in enumerate(sizes):
                page = doc.new_page(width=w, height=h)
                page.insert_text((20, 45), f'PAGE_{i}_LEFT')
                page.insert_text((w / 2 + 20, h - 45), f'PAGE_{i}_RIGHT')
            doc.save(source)
        return source

    def assert_all_labels(self, path, count):
        with fitz.open(path) as doc:
            text = ''.join(p.get_text() for p in doc)
            for i in range(count):
                for side in ('LEFT', 'RIGHT'):
                    self.assertEqual(text.count(f'PAGE_{i}_{side}'), 1, text)

    def test_odd_trailing_page_survives_both_dual_crop_modes(self):
        for count in (1, 3):
            for mode in ('dual-cut', 'crop-compare'):
                with self.subTest(count=count, mode=mode):
                    source = self.source([(600, 800)] * count)
                    output = self.root / f'{mode}.pdf'
                    self.cropper.crop_pdf(self.config, str(source), 'dual', str(output), mode)
                    self.assert_all_labels(output, count)
                    with fitz.open(output) as doc:
                        expected = count * 2 if mode == 'dual-cut' else ((count + 1) // 2) * 2
                        self.assertEqual(len(doc), expected)

    def test_mixed_page_sizes_do_not_lose_the_larger_pages_right_or_bottom(self):
        sizes = [(600, 800), (1000, 1200)]
        for mode in ('mono-cut', 'dual-cut', 'crop-compare'):
            with self.subTest(mode=mode):
                source = self.source(sizes)
                output = self.root / f'{mode}.pdf'
                self.cropper.crop_pdf(self.config, str(source), 'dual', str(output), mode)
                self.assert_all_labels(output, 2)

    def test_lr_split_calculates_each_pages_dimensions(self):
        source = self.source([(600, 800), (1000, 1200)], 'paper.LR_dual.pdf')
        _, output = self.cropper.pdf_dual_mode(str(source), 'LR', 'TB')
        self.assert_all_labels(output, 2)
        with fitz.open(output) as doc:
            self.assertEqual([p.rect.width for p in doc], [300, 300, 500, 500])

    def test_original_first_uses_original_dimensions_when_pair_sizes_differ(self):
        source = self.source([(600, 800), (1000, 1200)])
        output = self.root / 'compare.pdf'
        self.cropper.merge_pdf(str(source), str(output), trans_first=False)
        with fitz.open(output) as doc:
            # Unscaled original page at x=0 and translated page at x=1000.
            self.assertAlmostEqual(doc[0].search_for('PAGE_1_LEFT')[0].x0, 20, delta=0.1)
            self.assertAlmostEqual(doc[0].search_for('PAGE_0_LEFT')[0].x0, 1020, delta=0.1)

    def test_rotated_and_blank_pages_remain_valid(self):
        source = self.root / 'rotated.pdf'
        with fitz.open() as doc:
            page = doc.new_page(width=800, height=600)
            page.insert_text((50, 80), 'ROTATED_TEXT')
            page.set_rotation(90)
            doc.new_page(width=600, height=800)
            doc.save(source)
        for mode in ('mono-cut', 'dual-cut', 'crop-compare'):
            output = self.root / f'rotated-{mode}.pdf'
            self.cropper.crop_pdf(self.config, str(source), 'dual', str(output), mode)
            with fitz.open(output) as doc:
                self.assertIn('ROTATED_TEXT', ''.join(p.get_text() for p in doc))
                for page in doc:
                    page.get_pixmap()
        output = self.root / 'blank-compare.pdf'
        self.cropper.merge_pdf(str(source), str(output))
        with fitz.open(output) as doc:
            self.assertEqual(len(doc), 1)
            self.assertIn('ROTATED_TEXT', doc[0].get_text())

    def test_cropbox_offsets_use_visible_page_coordinates(self):
        source = self.root / 'cropbox.pdf'
        with fitz.open() as doc:
            page = doc.new_page(width=900, height=1000)
            page.insert_text((240, 280), 'VISIBLE_LEFT')
            page.insert_text((540, 800), 'VISIBLE_RIGHT')
            page.set_cropbox(fitz.Rect(200, 200, 800, 900))
            doc.save(source)
        output = self.root / 'cropbox-cut.pdf'
        self.cropper.crop_pdf(self.config, str(source), 'mono', str(output), 'mono-cut')
        with fitz.open(output) as doc:
            self.assertEqual(len(doc), 2)
            self.assertEqual(doc[0].rect.width, 300)
            self.assertIn('VISIBLE_LEFT', doc[0].get_text())
            self.assertIn('VISIBLE_RIGHT', doc[1].get_text())

    def test_invalid_crop_offsets_fail_before_creating_output(self):
        source = self.source([(600, 800)])
        self.config.pdf_offset_ratio = 0
        output = self.root / 'invalid.pdf'
        with self.assertRaisesRegex(ValueError, '裁剪'):
            self.cropper.crop_pdf(self.config, str(source), 'mono', str(output), 'mono-cut')
        self.assertFalse(output.exists())
