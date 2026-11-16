import tempfile
import unittest
from pathlib import Path

import pymupdf
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject
from pypdf.generic import BooleanObject, FloatObject, NameObject, NumberObject

from utils.math_rules import has_tex_math, normalize_rules, solid_rule_mask


def stream(data):
    result = DecodedStreamObject()
    result.set_data(data)
    return result


class MathRulesTest(unittest.TestCase):
    def test_inline_rule_mask_requires_opaque_stencil_and_thin_shape(self):
        settings = {'/IM': BooleanObject(True), '/W': 1, '/H': 1, '/BPC': 1}
        mask = {'settings': settings, 'data': b'\x00'}
        matrix = (30, 0, 0, -0.4, 10, 20)
        self.assertTrue(solid_rule_mask(mask, matrix))
        self.assertFalse(solid_rule_mask(mask, (0.4, 0, 0, -30, 10, 20)))
        self.assertFalse(solid_rule_mask(mask, (30, 1, 0, -0.4, 10, 20)))
        self.assertFalse(solid_rule_mask(mask, (240, 0, 0, -0.4, 10, 20)))
        self.assertFalse(solid_rule_mask({**mask, 'data': b'\x80'}, matrix))
        inverted = {'settings': {**settings, '/D': [1, 0]}, 'data': b'\x80'}
        self.assertTrue(solid_rule_mask(inverted, matrix))
        for override in ({'/IM': BooleanObject(False)}, {'/W': 2}, {'/F': '/Fl'}, {'/D': [0.2, 1]}):
            self.assertFalse(solid_rule_mask({**mask, 'settings': {**settings, **override}}, matrix))

    def test_inline_stencil_preserves_fill_alpha_and_unselected_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'mask.pdf'
            writer = PdfWriter()
            resources = DictionaryObject({NameObject('/ExtGState'): DictionaryObject({
                NameObject('/Alpha'): DictionaryObject({NameObject('/ca'): FloatObject(0.5)})})})
            # The fill colour and opacity of the image mask must survive.
            data = (b'q /Alpha gs 0.4 g q 40 0 0 -2 20 40 cm '
                    b'BI /IM true /W 1 /H 1 /BPC 1 ID \x00 EI Q Q')
            content = writer._add_object(stream(data))
            for _ in range(2):
                page = writer.add_blank_page(100, 100)
                page[NameObject('/Resources')] = resources
                page[NameObject('/Contents')] = content
            writer.write(path)
            writer.close()
            with pymupdf.open(path) as doc:
                pixels = [p.get_pixmap(matrix=pymupdf.Matrix(2, 2)).samples for p in doc]
            self.assertEqual(normalize_rules(path, [0]), 1)
            with pymupdf.open(path) as doc:
                self.assertEqual(pixels, [p.get_pixmap(matrix=pymupdf.Matrix(2, 2)).samples for p in doc])
                self.assertEqual(len(doc[0].get_image_info()), 0)
                self.assertEqual(len(doc[1].get_image_info()), 1)
            self.assertEqual(normalize_rules(path, [0]), 0)

    def test_math_font_gate(self):
        self.assertTrue(has_tex_math({'ABCDEF+CMMI10', 'Times'}))
        self.assertTrue(has_tex_math({'CMSY7'}))
        self.assertFalse(has_tex_math({'Times', 'SomeCMMI10Text'}))

    def test_shared_forms_selected_page_and_rendering_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.pdf'
            writer = PdfWriter()
            form = stream(b'[] 0 d 0 J 0.4 w 0 0 m 30 0 l S')
            form.update({NameObject('/Type'): NameObject('/XObject'),
                         NameObject('/Subtype'): NameObject('/Form'),
                         NameObject('/BBox'): ArrayObject([NumberObject(x) for x in (-1, -1, 32, 2)]),
                         NameObject('/Resources'): DictionaryObject()})
            form_ref = writer._add_object(form)
            resources = DictionaryObject({NameObject('/XObject'): DictionaryObject({
                NameObject('/F'): form_ref})})
            content = writer._add_object(stream(
                b'q 1 0 0 1 20 20 cm /F Do Q '
                b'q 0.5 G 1 0 0 1 20 40 cm /F Do Q '
                b'q 0.5 g 1 0 0 1 20 60 cm /F Do Q'))
            for _ in range(2):
                page = writer.add_blank_page(100, 100)
                page[NameObject('/Resources')] = resources
                page[NameObject('/Contents')] = content
            writer.write(path)
            writer.close()
            with pymupdf.open(path) as doc:
                pixels = [p.get_pixmap(matrix=pymupdf.Matrix(3, 3)).samples for p in doc]
            self.assertEqual(normalize_rules(path, [0]), 2)
            with pymupdf.open(path) as doc:
                self.assertEqual(pixels, [p.get_pixmap(matrix=pymupdf.Matrix(3, 3)).samples for p in doc])
            with PdfReader(path) as reader:
                # The untouched page still references the unmodified shared form.
                untouched = reader.pages[1]['/Resources']['/XObject']['/F'].get_data()
                self.assertEqual(untouched, form.get_data())
                self.assertEqual(len(reader.pages[0]['/Resources']['/XObject']), 3)
                self.assertEqual(len(reader.pages[1]['/Resources']['/XObject']), 1)
            before = path.read_bytes()
            self.assertEqual(normalize_rules(path, [0]), 0)
            self.assertEqual(path.read_bytes(), before)

    def test_unsafe_strokes_are_left_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.pdf'
            writer = PdfWriter()
            page = writer.add_blank_page(100, 100)
            page[NameObject('/Contents')] = writer._add_object(stream(
                b'q [2 1] 0 d 0 J 0.4 w 10 10 m 50 10 l S Q '
                b'q [] 0 d 1 J 0.4 w 10 20 m 50 20 l S Q '
                b'q [] 0 d 0 J 0 w 10 30 m 50 30 l S Q '
                b'q [] 0 d 0 J 0.4 w 10 40 m 50 45 l S Q '
                b'q 0.5 G [] 0 d 0 J 0.4 w 10 50 m 50 50 l S Q '
                b'q /Alpha gs [] 0 d 0 J 0.4 w 10 60 m 50 60 l S Q '
                b'q [] 0 d 0 J 0.4 w 10 90 m 250 90 l S Q '
                b'q 10 70 m 30 80 l [] 0 d 0 J 0.4 w 10 80 m 50 80 l S Q'))
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/ExtGState'):
                DictionaryObject({NameObject('/Alpha'): DictionaryObject({
                    NameObject('/CA'): FloatObject(0.5)})})})
            writer.write(path)
            writer.close()
            before = path.read_bytes()
            self.assertEqual(normalize_rules(path, [0]), 0)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
