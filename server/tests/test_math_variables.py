import tempfile
import unittest
from pathlib import Path

from utils import math_variables as mathrepair

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ContentStream, DecodedStreamObject, DictionaryObject, NameObject
except ImportError:
    PdfWriter = None


class VariableRunTest(unittest.TestCase):
    def test_variable_and_prose_are_distinguished(self):
        self.assertTrue(mathrepair.variable_run([([b'c'], b'Tj')]))
        self.assertTrue(mathrepair.variable_run([([[b' ', -10, b'x']], b'TJ')]))
        for ops in ([([b'italic prose'], b'Tj')],
                    [([b'w'], b'Tj'), ([b'o'], b'Tj'), ([b'r'], b'Tj'), ([b'd'], b'Tj')],
                    [([b'12'], b'Tj')], [([b'c'], b"'")]):
            self.assertFalse(mathrepair.variable_run(ops))


@unittest.skipIf(PdfWriter is None, 'requires the bridge pypdf dependency')
class FontResourceTest(unittest.TestCase):
    def test_only_selected_variable_runs_change_and_font_is_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.pdf'
            writer = PdfWriter()
            descriptor = DictionaryObject({NameObject('/Type'): NameObject('/FontDescriptor'),
                                           NameObject('/FontName'): NameObject('/ABCDEF+AdvOTtest.I')})
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                     NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/ABCDEF+AdvOTtest.I'),
                                     NameObject('/FontDescriptor'): writer._add_object(descriptor)})
            resources = DictionaryObject({NameObject('/Font'): DictionaryObject({
                NameObject('/F1'): writer._add_object(font)})})
            body = b'BT /F1 10 Tf (c) Tj ET BT (whole word) Tj ET BT /F1 10 Tf (w) Tj (o) Tj (r) Tj (d) Tj ET'
            for _ in range(2):
                page = writer.add_blank_page(width=300, height=400)
                page[NameObject('/Resources')] = writer._add_object(resources)
                stream = DecodedStreamObject()
                stream.set_data(body)
                page[NameObject('/Contents')] = writer._add_object(stream)
            writer.write(path)
            writer.close()
            self.assertEqual(mathrepair.protect_variables(path, [0]), 1)
            doc = PdfReader(path)
            protected = doc.pages[0]['/Resources']['/Font']
            untouched = doc.pages[1]['/Resources']['/Font']
            self.assertEqual(list(untouched), ['/F1'])
            self.assertEqual(doc.pages[1].get_contents().get_data(), body)
            self.assertEqual(protected['/F1']['/BaseFont'], '/ABCDEF+AdvOTtest.I')
            alias = next(k for k in protected if k != '/F1')
            self.assertEqual(protected[alias]['/BaseFont'], protected[alias]['/FontDescriptor']['/FontName'])
            ops = ContentStream(doc.pages[0].get_contents(), doc).operations
            fonts = [args[0] for args, op in ops if op == b'Tf']
            self.assertEqual(fonts, [alias, '/F1', '/F1'])
            self.assertEqual([str(args[0]) for args, op in ops if op == b'Tj'],
                             ['c', 'whole word', 'w', 'o', 'r', 'd'])
            before = path.read_bytes()
            self.assertEqual(mathrepair.protect_variables(path, [0]), 0)
            self.assertEqual(path.read_bytes(), before)
            doc.close()


if __name__ == '__main__':
    unittest.main()
