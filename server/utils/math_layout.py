"""Correct formula boxes containing prose in legacy mathematical PDFs.

The visual detector sometimes marks a paragraph containing several radicals as
one display equation. Confirm substantial prose in the native text layer before
turning a low-confidence formula box into text. Real equations remain protected
by BabelDOC's character/font formula detection.
"""
import re
import copy

WORD = re.compile(r'[A-Za-z]{2,}[,.:;!?]?')
CONNECTORS = {'the', 'is', 'are', 'we', 'with', 'and', 'of', 'to', 'from', 'have', 'for', 'as'}


def numbered_math_headings(native):
    from utils import math_fonts as mathfonts
    headings = []
    for block in native.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            spans = line.get('spans', [])
            text = ''.join(span.get('text', '') for span in spans)
            if (re.match(r'^\(\d+\)\s+[A-Za-z]{3,}', text.strip())
                    and mathfonts.detect(span.get('font') for span in spans)):
                headings.append(tuple(line['bbox']))
    return headings


def split_math_lists(result, native):
    """Keep numbered math cases in separate paragraphs after reclassification."""
    headings = numbered_math_headings(native)
    names = result.names
    items = names.items() if isinstance(names, dict) else enumerate(names)
    title = next((key for key, name in items if name == 'title'), None)
    if len(headings) < 2 or title is None:
        return 0
    additions, removed = [], set()
    for index, outer in enumerate(result.boxes):
        if names[outer.cls] != 'plain text' or index in removed:
            continue
        x0, y0, x1, y1 = map(float, outer.xyxy)
        inside = sorted((h for h in headings if x0 <= h[0] and h[2] <= x1
                         and y0 <= h[1] and h[3] <= y1), key=lambda h: h[1])
        if len(inside) < 2:
            continue
        # Remove overlapping text predictions contained by the same enclosing
        # paragraph, so they cannot rejoin cases across a new title boundary.
        for other_index, other in enumerate(result.boxes):
            if names[other.cls] not in ('plain text', 'title'):
                continue
            a, b, c, d = map(float, other.xyxy)
            if x0 <= a and c <= x1 and y0 <= b and d <= y1:
                removed.add(other_index)
        def append_box(top, bottom, cls):
            if bottom - top <= 1:
                return
            box = copy.copy(outer)
            box.xyxy = (x0, top, x1, bottom)
            box.cls = cls
            additions.append(box)
        cursor = y0
        for heading in inside:
            top, bottom = heading[1] - 0.5, heading[3] + 0.5
            append_box(cursor, top, outer.cls)
            append_box(top, bottom, title)
            cursor = bottom
        append_box(cursor, y1, outer.cls)
    result.boxes = [box for i, box in enumerate(result.boxes) if i not in removed] + additions
    return len(additions)


def contains_prose(words):
    tokens = [str(w[4]).lower().rstrip(',.:;!?') for w in words if WORD.fullmatch(str(w[4]))]
    return len(tokens) >= 4 and sum(t in CONNECTORS for t in tokens) >= 2


class MathLayoutModel:
    def __init__(self, model):
        self.model = model
        self.corrected_pages = set()
        self.corrected_boxes = 0
        self.split_boxes = 0

    @property
    def stride(self):
        return self.model.stride

    def handle_document(self, pages, mupdf_doc, translate_config, save_debug_image):
        for page, result in self.model.handle_document(pages, mupdf_doc, translate_config, save_debug_image):
            names = result.names
            items = names.items() if isinstance(names, dict) else enumerate(names)
            plain = next((key for key, name in items if name == 'plain text'), None)
            native = mupdf_doc[page.page_number]
            # Rotation needs an explicit coordinate transform. Leave it to the
            # engine rather than guessing at the detector's coordinate system.
            if plain is not None and not native.rotation:
                for box in result.boxes:
                    if names[box.cls] != 'isolate_formula' or float(box.conf) >= 0.75:
                        continue
                    words = native.get_text('words', clip=tuple(float(c) for c in box.xyxy))
                    if contains_prose(words):
                        box.cls = plain
                        self.corrected_pages.add(page.page_number + 1)
                        self.corrected_boxes += 1
                if page.page_number + 1 in self.corrected_pages:
                    self.split_boxes += split_math_lists(result, native)
            yield page, result

    def diagnostics(self):
        return {'layoutCorrectedPages': sorted(self.corrected_pages),
                'layoutCorrectedBoxes': self.corrected_boxes,
                'mathListLayoutBoxes': self.split_boxes}
