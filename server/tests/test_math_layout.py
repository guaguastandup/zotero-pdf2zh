from types import SimpleNamespace
import unittest

from utils.math_layout import MathLayoutModel, contains_prose, split_math_lists


def words(text):
    return [(0, 0, 1, 1, word) for word in text.split()]


class LayoutTest(unittest.TestCase):
    def test_prose_not_math_operators(self):
        for text in ('Recalling Eq. (94) and letting x = 0, we have',
                     'Otherwise, the position is min(',
                     'the shortest distance from the origin'):
            self.assertTrue(contains_prose(words(text)), text)
        for text in ('min max sin cos log exp', 'c0 + c1 x = 0', 'for all x', ''):
            self.assertFalse(contains_prose(words(text)), text)

    def test_only_low_confidence_prose_formula_is_reclassified(self):
        boxes = [SimpleNamespace(cls=1, conf=0.3, xyxy=(0, 0, 10, 10)),
                 SimpleNamespace(cls=1, conf=0.9, xyxy=(0, 0, 10, 10)),
                 SimpleNamespace(cls=2, conf=0.3, xyxy=(0, 0, 10, 10))]
        result = SimpleNamespace(names={0: 'plain text', 1: 'isolate_formula', 2: 'figure'}, boxes=boxes)
        page = SimpleNamespace(page_number=0)
        native = SimpleNamespace(rotation=0, get_text=lambda kind, **kw: (
            {'blocks': []} if kind == 'dict' else words('Otherwise the position is')))
        underlying = SimpleNamespace(stride=32, handle_document=lambda *a: iter([(page, result)]))
        wrapper = MathLayoutModel(underlying)
        self.assertEqual(list(wrapper.handle_document([page], [native], None, None)), [(page, result)])
        self.assertEqual([b.cls for b in boxes], [0, 1, 2])
        self.assertEqual(wrapper.diagnostics(), {'layoutCorrectedPages': [1], 'layoutCorrectedBoxes': 1,
                                               'mathListLayoutBoxes': 0})
        self.assertEqual(wrapper.stride, 32)
        boxes[0].cls = 1
        native.rotation = 90
        list(wrapper.handle_document([page], [native], None, None))
        self.assertEqual(boxes[0].cls, 1)

    def test_numbered_cases_are_split_without_changing_equation_boxes(self):
        heading = lambda top, n: {'bbox': (10, top, 70, top + 10), 'spans': [
            {'text': f'({n}) Boundary with ', 'font': 'Times'},
            {'text': 'x = 0', 'font': 'AdvMacMthSyN'}]}
        native = SimpleNamespace(get_text=lambda kind: {'blocks': [
            {'lines': [heading(10, 1), heading(50, 2)]}]})
        outer = SimpleNamespace(cls=0, xyxy=(0, 0, 100, 100), conf=0.4)
        duplicate = SimpleNamespace(cls=0, xyxy=(5, 10, 80, 22), conf=0.5)
        equation = SimpleNamespace(cls=2, xyxy=(10, 30, 70, 40), conf=0.9)
        result = SimpleNamespace(names={0: 'plain text', 1: 'title', 2: 'isolate_formula'},
                                 boxes=[outer, duplicate, equation])
        self.assertEqual(split_math_lists(result, native), 5)
        self.assertEqual(len(result.boxes), 6)
        self.assertIs(result.boxes[0], equation)
        self.assertEqual([b.cls for b in result.boxes[1:]], [0, 1, 0, 1, 0])


if __name__ == '__main__':
    unittest.main()
