"""Native-layout reference preservation without network calls or model assets."""
import sys
import subprocess
import multiprocessing
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

try:
    import numpy as np
except ImportError:
    np = None
import pymupdf

from utils import reference_skip
from utils.reference_layout import ReferenceLayoutModel, _reading_order, install_reference_layout_policy


def box(bounds, cls=0):
    return SimpleNamespace(xyxy=bounds, cls=cls, conf=np.float64(1))


class Model:
    stride = 32
    font_mapper = None

    def __init__(self, results):
        self.results = results

    def handle_document(self, pages, *_):
        for page in pages:
            yield page, self.results[page.page_number]


def fixture():
    doc = pymupdf.open()
    first = doc.new_page(width=600, height=800)
    for i in range(8):
        first.insert_text((50, 50 + 30 * i), f'Body paragraph number {i} remains translatable.')
    first.insert_text((50, 350), 'References')
    first.insert_text((50, 380), '[1] ReferenceAlpha. A research paper, 2021.')
    first.insert_text((50, 410), '[2] ReferenceBeta. Another paper, 2022.')
    second = doc.new_page(width=600, height=800)
    second.insert_text((50, 50), '[3] ReferenceGamma. Last paper, 2023.')
    second.insert_text((50, 90), 'Appendix A')
    second.insert_text((50, 120), 'Appendix prose must still be translated.')
    results = [SimpleNamespace(names={0: 'plain text'}, boxes=[box((40, 20, 560, 780))]) for _ in doc]
    pages = [SimpleNamespace(page_number=i) for i in range(len(doc))]
    return doc, results, pages


@unittest.skipIf(np is None, 'layout adapter requires the engine numpy dependency')
class NativeReferenceLayoutTests(unittest.TestCase):
    def test_policy_survives_worker_startup(self):
        try:
            available = reference_skip.policy_supported() and version('BabelDOC') == '0.7.1'
        except PackageNotFoundError:
            available = False
        if not available:
            self.skipTest('requires pdf2zh-next 2.10.2 / BabelDOC 0.7.1')
        for method in multiprocessing.get_all_start_methods():
            with self.subTest(method=method):
                result = subprocess.run([sys.executable, str(Path(__file__).parent /
                    'fixtures/reference_process_probe.py'), method], capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_validated_runtime_pairs_only(self):
        for engine, babel, expected in [('2.9.0', '0.6.4', True), ('2.10.2', '0.7.1', True),
                                        ('2.10.2', '0.6.4', False), ('2.10.3', '0.7.1', False)]:
            with self.subTest(engine=engine, babel=babel), patch.object(
                reference_skip, 'version', side_effect=lambda name: engine if name == 'pdf2zh-next' else babel
            ):
                self.assertEqual(reference_skip.policy_supported(), expected)

    def test_mixed_page_cross_page_and_appendix_keep_tight_original_line_boxes(self):
        doc, results, pages = fixture()
        with doc:
            model = ReferenceLayoutModel(Model(results))
            outputs = list(model.handle_document(pages, doc, None, None))
            self.assertEqual(model.preserved_records, 3)
            for page, result in outputs:
                self.assertIsNot(result, results[page.page_number])
                selected = [b for b in result.boxes if result.names[b.cls] == 'reference']
                self.assertEqual(len(selected), 2 if page.page_number == 0 else 1)
                for b in selected:
                    text = doc[page.page_number].get_text(clip=b.xyxy)
                    self.assertIn('Reference', text)
                    self.assertNotIn('Appendix', text)
                    self.assertNotIn('Body', text)
            self.assertTrue(all(len(r.boxes) == 1 and len(r.names) == 1 for r in results))

    def test_two_columns_keep_right_column_references_and_resume_at_appendix(self):
        doc, results, pages = fixture()
        with doc:
            page = doc[0]
            # Bibliography starts in the left column and continues at the top
            # of the right column; sorting only by y would miss these entries.
            page.insert_text((330, 50), '[3] RightAlpha, 2023.', fontsize=9)
            page.insert_text((330, 80), '[4] RightBeta, 2024.', fontsize=9)
            page.insert_text((330, 120), 'Appendix A', fontsize=9)
            page.insert_text((330, 150), 'Appendix remains translatable.', fontsize=9)
            model = ReferenceLayoutModel(Model(results))
            outputs = list(model.handle_document(pages[:1], doc, None, None))
            selected = [b for b in outputs[0][1].boxes if outputs[0][1].names[b.cls] == 'reference']
            self.assertEqual(len(selected), 4)
            protected = ''.join(page.get_text(clip=b.xyxy) for b in selected)
            self.assertIn('RightAlpha', protected)
            self.assertNotIn('Appendix', protected)

    def test_caption_boundary_even_when_title_is_not_detected(self):
        doc, results, pages = fixture()
        with doc:
            # Reproduce arXiv 1706.03762v7: next section title is classified
            # as figure_caption, not title. It must end the bibliography.
            page = doc.new_page(width=600, height=800)
            page.insert_text((50, 50), 'Attention Visualizations')
            page.insert_text((50, 100), 'Caption and additional content.')
            # Remove the explicit appendix on page 2 for this boundary test.
            doc.delete_page(1)
            pages = [SimpleNamespace(page_number=i) for i in range(2)]
            results[1] = SimpleNamespace(names={0: 'figure_caption'}, boxes=[box((40, 20, 560, 150))])
            model = ReferenceLayoutModel(Model(results))
            outputs = list(model.handle_document(pages, doc, None, None))
            self.assertEqual(model.preserved_records, 2)
            self.assertIs(outputs[1][1], results[1])

    def test_ambiguous_or_rotated_input_keeps_original_predictions(self):
        for rotated in (False, True):
            doc, results, pages = fixture()
            with doc:
                if rotated:
                    doc[0].set_rotation(90)
                else:
                    # No bibliography heading on selected page.
                    pages = pages[1:]
                outputs = list(ReferenceLayoutModel(Model(results)).handle_document(pages, doc, None, None))
                self.assertTrue(all(result is results[p.page_number] for p, result in outputs))

    def test_reading_order_stays_column_major(self):
        def item(name, bounds):
            return SimpleNamespace(unicode=name, bounds=bounds)
        items = [item('right2', (330, 200, 560, 220)), item('left2', (40, 200, 270, 220)),
                 item('right1', (330, 100, 560, 120)), item('left1', (40, 100, 270, 120)),
                 item('full', (40, 50, 560, 70))]
        self.assertEqual([p.unicode for p in _reading_order(items, 600)],
                         ['full', 'left1', 'left2', 'right1', 'right2'])

    def test_factory_preserves_rpc_character_requirements_and_restores_hooks(self):
        engine = ModuleType('pdf2zh_next')
        native_model = Model([])
        native_model.font_mapper = 'old'
        native = lambda: SimpleNamespace(doc_layout_model=native_model)
        engine.high_level = SimpleNamespace(create_babeldoc_config=native)
        babel = ModuleType('babeldoc')
        needs = lambda model: model is native_model
        babel.rust_layout_service = SimpleNamespace(needs_characters=needs)
        with patch.dict(sys.modules, {'pdf2zh_next': engine, 'babeldoc': babel}):
            restore = install_reference_layout_policy()
            try:
                config = engine.high_level.create_babeldoc_config()
                self.assertIsInstance(config.doc_layout_model, ReferenceLayoutModel)
                self.assertTrue(babel.rust_layout_service.needs_characters(config.doc_layout_model))
                config.doc_layout_model.font_mapper = 'new'
                self.assertEqual(native_model.font_mapper, 'new')
                self.assertEqual(config.doc_layout_model.stride, 32)
            finally:
                restore()
            self.assertIs(engine.high_level.create_babeldoc_config, native)
            self.assertIs(babel.rust_layout_service.needs_characters, needs)


if __name__ == '__main__':
    unittest.main()
