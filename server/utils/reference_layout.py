"""Preserve bibliography glyphs via BabelDOC 0.7.1's native reference layout.

The Rust paragraph finder keeps non-text layout characters on the original page,
so neither translation nor term extraction sees them. No PDF overlay, redaction,
installed package modification, or replacement translation prompt is required.
"""
from __future__ import annotations

import copy
import logging
import re
from types import SimpleNamespace

from utils.reference_skip import (
    REFERENCE_HEADINGS, POST_REFERENCE_HEADINGS, HEADING_LABELS, CAPTION_LABELS,
    _normalize, _citation_like, find_reference_paragraph_ids,
)

logger = logging.getLogger(__name__)


def _heading(text):
    value = _normalize(text)
    return value in REFERENCE_HEADINGS or value in POST_REFERENCE_HEADINGS or bool(
        re.match(r'^(?:appendix|supplementary|supplement)\s+[a-z0-9](?:[.:\s]|$)', value)
    )


def _layout_label(bounds, result):
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    labels = []
    for box in result.boxes:
        a, b, c, d = map(float, box.xyxy)
        name = str(result.names[box.cls]).lower().replace('_', ' ')
        if a <= cx <= c and b <= cy <= d:
            labels.append(name)
    # Preserve caption/noise labels too: a caption at the start of the next
    # page ends the bibliography even when the detector misses its title.
    for label in labels:
        if label in HEADING_LABELS | CAPTION_LABELS:
            return label
    return labels[0] if labels else 'text'


def _records(native, result):
    """Split native blocks at headings/entry starts, retaining per-line bounds."""
    import pymupdf

    records = []
    # Only text geometry is needed; avoid decoding/embedding large PDF images.
    flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    for block in native.get_text('dict', flags=flags)['blocks']:
        group = []
        def flush():
            if not group:
                return
            text = ' '.join(item[0] for item in group)
            bounds = (min(item[1][0] for item in group), min(item[1][1] for item in group),
                      max(item[1][2] for item in group), max(item[1][3] for item in group))
            records.append(SimpleNamespace(unicode=text, debug_id=len(records),
                layout_label='title' if _heading(text) else _layout_label(bounds, result),
                bounds=bounds, lines=tuple(item[1] for item in group)))
            group.clear()
        for line in block.get('lines', []):
            text = ''.join(span.get('text', '') for span in line.get('spans', [])).strip()
            if not text:
                continue
            bounds = tuple(line['bbox'])
            title = _heading(text) or _layout_label(bounds, result) in HEADING_LABELS
            if title or _citation_like(text):
                flush()
            group.append((text, bounds))
            if title:
                flush()
        flush()
    return _reading_order(records, native.rect.width)


def _reading_order(records, width):
    # Two-column reading order within bands separated by full-width blocks.
    # Require evidence on both sides; normal indented lists stay single-column.
    left = [p for p in records if p.bounds[0] < width * .4 and p.bounds[2] < width * .55]
    right = [p for p in records if p.bounds[0] >= width * .45]
    if len(left) < 2 or len(right) < 2:
        return sorted(records, key=lambda p: (p.bounds[1], p.bounds[0]))
    spanning = sorted((p for p in records if p.bounds[0] < width * .4 and p.bounds[2] > width * .6),
                      key=lambda p: p.bounds[1])
    output, remaining = [], list(records)
    for separator in spanning:
        band = [p for p in remaining if p is not separator and p.bounds[1] < separator.bounds[1]]
        output.extend(sorted(band, key=lambda p: (p.bounds[0] >= width * .45, p.bounds[1], p.bounds[0])))
        output.append(separator)
        removed = {id(p) for p in band} | {id(separator)}
        remaining = [p for p in remaining if id(p) not in removed]
    output.extend(sorted(remaining, key=lambda p: (p.bounds[0] >= width * .45, p.bounds[1], p.bounds[0])))
    return output


class ReferenceLayoutModel:
    def __init__(self, model):
        self.model = model
        self.preserved_records = 0

    def __getattr__(self, name):
        return getattr(self.model, name)

    @property
    def font_mapper(self):
        return self.model.font_mapper

    @font_mapper.setter
    def font_mapper(self, value):
        self.model.font_mapper = value

    def handle_document(self, pages, mupdf_doc, translate_config, save_debug_image):
        # Compute one document-wide decision before returning any marked pages.
        predictions = list(self.model.handle_document(pages, mupdf_doc, translate_config, save_debug_image))
        ordered = sorted(predictions, key=lambda item: item[0].page_number)
        records = {}
        for page, result in ordered:
            if translate_config is not None:
                translate_config.raise_if_cancelled()
            native = mupdf_doc[page.page_number]
            # Do not guess coordinate transforms for rotation/cropped pages.
            if native.rotation or native.cropbox != native.mediabox:
                logger.warning('Reference Skip: rotated/cropped page detected; keeping native document layout')
                yield from predictions
                return
            records[page.page_number] = _records(native, result)
        document = SimpleNamespace(page=[SimpleNamespace(pdf_paragraph=records[p.page_number]) for p, _ in ordered])
        skipped = find_reference_paragraph_ids(document)
        self.preserved_records += len(skipped)
        for page, original in predictions:
            selected = [p for p in records[page.page_number] if id(p) in skipped]
            if not selected:
                yield page, original
                continue
            import numpy as np
            result = copy.copy(original)
            result.names = dict(original.names) if isinstance(original.names, dict) else dict(enumerate(original.names))
            class_id = max(result.names, default=-1) + 1
            result.names[class_id] = 'reference'
            result.boxes = list(original.boxes)
            for record in selected:
                # Tight line boxes do not cover adjacent body columns/captions.
                for bounds in record.lines:
                    result.boxes.append(SimpleNamespace(xyxy=bounds, conf=np.float64(1.0), cls=class_id))
            yield page, result
        logger.info('Reference Skip: preserved %s reference records through native Rust layout', len(skipped))


def install_reference_layout_policy():
    from pdf2zh_next import high_level
    from babeldoc import rust_layout_service
    native_needs_characters = rust_layout_service.needs_characters

    def needs_characters(model):
        if isinstance(model, ReferenceLayoutModel):
            model = model.model
        return native_needs_characters(model)

    native = high_level.create_babeldoc_config
    def create_config(*args, **kwargs):
        config = native(*args, **kwargs)
        config.doc_layout_model = ReferenceLayoutModel(config.doc_layout_model)
        return config
    high_level.create_babeldoc_config = create_config
    rust_layout_service.needs_characters = needs_characters
    def restore():
        high_level.create_babeldoc_config = native
        rust_layout_service.needs_characters = native_needs_characters
    return restore
