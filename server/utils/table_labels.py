"""Map verified label parts to original glyphs; never freeze names in sentences."""

from bisect import bisect_right
from statistics import median


def split_label_parts(lines, parts):
    """Return (source runs, translate) pairs, or None for whole-unit handling.

    Ignore whitespace only when mapping back to PDF glyphs: line-wrap spaces
    may have been synthesized. A ligature/glyph spanning a part boundary cannot
    be split safely. All actual glyphs must be assigned exactly once.
    """
    if not parts or all(p["translate"] for p in parts):
        return None

    def compact(text):
        return "".join(c for c in text if not c.isspace())

    chars = [c for line in lines for c in line]
    source = "".join(compact(c.char_unicode or "") for c in chars)
    if source != "".join(compact(p["text"]) for p in parts):
        return None
    ends, offset = [], 0
    for part in parts:
        offset += len(compact(part["text"]))
        ends.append(offset)
    owners, offset = {}, 0
    for char in chars:
        length = len(compact(char.char_unicode or ""))
        index = bisect_right(ends, offset if length else max(0, offset - 1))
        if index >= len(parts) or offset + length > ends[index]:
            return None
        owners[id(char)] = index
        offset += length
    result = []
    for i, part in enumerate(parts):
        runs = [[c for c in line if owners[id(c)] == i] for line in lines]
        runs = [run for run in runs if run]
        if runs:
            result.append((runs, part["translate"]))
    return result


def label_anchor(lines, whole_lines):
    """Keep a one-line replacement on its original baseline and alignment."""
    chars = [c for line in lines for c in line if (c.char_unicode or "").strip()]
    whole = [c for line in whole_lines for c in line if (c.char_unicode or "").strip()]
    size = median(c.pdf_style.font_size or 8 for c in chars)
    if max(c.box.y for c in chars) - min(c.box.y for c in chars) > size * 0.3:
        return None  # Multi-line labels retain native bounded wrapping.
    left = min(c.visual_bbox.box.x for c in chars)
    right = max(c.visual_bbox.box.x2 for c in chars)
    middle = (left + right) / 2
    whole_middle = (
        min(c.visual_bbox.box.x for c in whole)
        + max(c.visual_bbox.box.x2 for c in whole)
    ) / 2
    own = {id(c) for c in chars}
    baseline = median(c.box.y for c in chars)
    same_line_neighbour = any(
        id(c) not in own and abs(c.box.y - baseline) <= size * 0.3 for c in whole
    )
    centered = not same_line_neighbour and abs(middle - whole_middle) <= size * 0.5
    return left, right, baseline, centered


def anchor_label_units(units, anchor):
    """Position one translated line; the caller still checks all final bounds."""
    from utils.table_layout import move_positioned_unit

    if not units or anchor is None:
        return units
    left, right, baseline, centered = anchor
    baselines = [u.y if u.y is not None else u.box.y for u in units]
    if max(baselines) - min(baselines) > 0.1:
        return []  # A single-line replacement must not spill onto another row.
    start = min(u.box.x for u in units)
    width = max(u.box.x2 for u in units) - start
    shift = ((left + right - width) / 2 if centered else left) - start
    result = []
    for unit in units:
        moved = move_positioned_unit(unit, unit.box.x + shift, baseline)
        result.append(moved)
    return result
