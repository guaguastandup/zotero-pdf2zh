"""Cell-contained alignment and balanced wrapping for translated table text."""

import copy
from functools import lru_cache
from statistics import median


class MeasuredFormulaUnit:
    """Expose the emitted glyph advances to the table's native line fitter."""

    def __init__(self, unit):
        self.unit = unit

    def __getattr__(self, name):
        return getattr(self.unit, name)

    @property
    def box(self):
        boxes = [self.unit.box]
        for char in self.formular.pdf_character:
            boxes.extend([char.box, char.visual_bbox.box])
        result = copy.copy(self.unit.box)
        result.x, result.y = min(b.x for b in boxes), min(b.y for b in boxes)
        result.x2, result.y2 = max(b.x2 for b in boxes), max(b.y2 for b in boxes)
        return result

    @property
    def width(self):
        return self.box.x2 - self.box.x

    @property
    def height(self):
        return self.box.y2 - self.box.y

    def relocate(self, x, y, scale):
        box = self.box
        return MeasuredFormulaUnit(
            self.unit.relocate(
                x + (self.formular.box.x - box.x) * scale,
                y + (self.formular.box.y - box.y) * scale,
                scale,
            )
        )


def measure_formula_units(units):
    return [
        MeasuredFormulaUnit(u)
        if getattr(u, "formular", None) and not isinstance(u, MeasuredFormulaUnit)
        else u
        for u in units
    ]


def move_positioned_unit(unit, x, y):
    # Native formula relocation applies its source offsets on every call.
    # An aligned unit already contains those offsets; apply only the movement.
    formula = getattr(unit, "formular", None)
    if formula:
        x -= formula.x_offset
        y -= formula.y_offset
    moved = unit.relocate(x, y, 1.0)
    moved.scale = unit.scale
    return moved


def contain_cell_layout(units, box):
    """Correct placement, not size, using a single rigid translation."""
    if not units:
        return units
    boxes = [u.box for u in units]
    for u in units:
        for c in u.render()[0]:
            boxes.append(c.box)
            if c.visual_bbox:
                boxes.append(c.visual_bbox.box)
    x, y = min(b.x for b in boxes), min(b.y for b in boxes)
    x2, y2 = max(b.x2 for b in boxes), max(b.y2 for b in boxes)
    if x2 - x > box.x2 - box.x + 0.05 or y2 - y > box.y2 - box.y + 0.05:
        return units
    dx = max(box.x - x, min(0, box.x2 - x2))
    dy = max(box.y - y, min(0, box.y2 - y2))
    if abs(dx) + abs(dy) < 1e-8:
        return units
    return [
        move_positioned_unit(
            u, u.box.x + dx, (u.y if u.y is not None else u.box.y) + dy
        )
        for u in units
    ]


def source_alignment(lines, peers=(), anchor_hint=None):
    """Infer alignment from source edges; uncertain text keeps its left edge.

    Multiline cells supply their own evidence. Short one-line cells can use
    repeated peer edges/centers in the same column, including numerical cells.
    Anchors refer to source text, never the center of an expanded envelope.
    """
    if anchor_hint is not None:
        return "center", anchor_hint

    def bounds(line):
        boxes = [c.visual_bbox.box for c in line if (c.char_unicode or "").strip()]
        return min(b.x for b in boxes), max(b.x2 for b in boxes)

    edges = [
        bounds(line)
        for line in lines
        if any((c.char_unicode or "").strip() for c in line)
    ]
    if not edges:
        return "left", 0.0
    lefts, rights = zip(*edges)
    centers = [(a + b) / 2 for a, b in edges]
    size = median(c.pdf_style.font_size or 8 for line in lines for c in line)
    anchors = {"left": min(lefts), "right": max(rights), "center": median(centers)}
    spreads = {
        "left": max(lefts) - min(lefts),
        "right": max(rights) - min(rights),
        "center": max(centers) - min(centers),
    }
    if len(edges) > 1:
        best = min(spreads, key=spreads.get)
        alternatives = [v for k, v in spreads.items() if k != best]
        if (
            spreads[best] <= size * 0.25
            and min(alternatives) - spreads[best] > size * 0.12
        ):
            return best, anchors[best]
        if spreads["left"] <= size * 0.25:
            return "left", anchors["left"]
    votes = {k: 0 for k in anchors}
    for peer in peers:
        if peer is lines:
            continue
        for line in peer:
            if not any((c.char_unicode or "").strip() for c in line):
                continue
            a, b = bounds(line)
            if (a, b) in edges:
                continue
            for kind, value in (("left", a), ("right", b), ("center", (a + b) / 2)):
                if abs(value - anchors[kind]) <= size * 0.2:
                    votes[kind] += 1
    best = max(votes, key=votes.get)
    if (
        votes[best] >= 2
        and votes[best] >= max(v for k, v in votes.items() if k != best) + 2
    ):
        return best, anchors[best]
    return "left", anchors["left"]


def alignment_box(box, alignment, anchor):
    result = copy.copy(box)
    if alignment == "left":
        result.x = max(box.x, anchor)
    elif alignment == "right":
        result.x2 = min(box.x2, anchor)
    else:
        radius = max(0, min(anchor - box.x, box.x2 - anchor))
        result.x, result.x2 = anchor - radius, anchor + radius
    return result


def text_lines(units):
    lines = []
    for unit in units:
        y = getattr(unit, "y", None)
        y = y if y is not None else unit.box.y
        # Formula/raw-glyph boxes can have a different bottom from the native
        # text baseline on the SAME line. Only a horizontal reset together
        # with a baseline change identifies a new native line.
        if not lines or (
            abs(y - lines[-1][0]) > 0.1 and unit.box.x <= lines[-1][1][-1].box.x + 0.1
        ):
            lines.append((y, []))
        lines[-1][1].append(unit)
    return lines


def align_lines(lines, box, alignment="center"):
    result = []
    for _, units in lines:
        visible = [
            u
            for u in units
            if (
                (getattr(u, "try_get_unicode", lambda: "")() or "").strip()
                or any(
                    (c.char_unicode or "").strip()
                    for c in getattr(getattr(u, "formular", None), "pdf_character", ())
                )
            )
        ] or units
        left = min(u.box.x for u in visible)
        right = max(u.box.x2 for u in visible)
        shift = {
            "left": box.x - left,
            "right": box.x2 - right,
            "center": (box.x + box.x2 - left - right) / 2,
        }[alignment]
        if abs(shift) < 1e-8:
            result.extend(units)
            continue
        for unit in units:
            y = unit.y if unit.y is not None else unit.box.y
            moved = move_positioned_unit(unit, unit.box.x + shift, y)
            result.append(moved)
    return result


def balanced_cell_layout(units, laid_out, box, scale, layout, alignment=None):
    """Balance character counts without adding lines or splitting Latin words.

    Native layout validates each proposed line (including punctuation and font
    spacing). Formula/raw-glyph runs retain native breaks and source alignment.
    The caller must still validate final glyph bounds and obstacles.
    """
    lines = text_lines(laid_out)
    if len(lines) < 2:
        return align_lines(lines, box, alignment) if alignment and lines else laid_out
    alignment = alignment or "center"
    texts = [u.try_get_unicode() or "" for u in units]
    if (
        not units
        or len(units) > 512
        or len(lines) > 32
        or any(not getattr(u, "unicode", None) for u in units)
    ):
        return align_lines(lines, box, alignment)
    counts, widths = [0], [0.0]
    for unit, text in zip(units, texts):
        counts.append(counts[-1] + sum(not c.isspace() for c in text))
        widths.append(widths[-1] + unit.width * scale)
    target = counts[-1] / len(lines)

    def allowed(i):
        if i == len(units):
            return True
        a, b = texts[i - 1], texts[i]
        if (
            a
            and b
            and a[-1].isascii()
            and b[0].isascii()
            and a[-1].isalnum()
            and b[0].isalnum()
        ):
            return False
        return not (
            getattr(units[i - 1], "is_cannot_appear_in_line_end_punctuation", False)
            or (b and b[0] in "，。！？；：、）】》,.!?;:)]}")
        )

    @lru_cache(None)
    def solve(start, remaining, maximum):
        if remaining == 0:
            return (0, ()) if start == len(units) else (float("inf"), ())
        best = (float("inf"), ())
        # Prefer a longer earlier line when character-count costs are equal.
        for end in range(len(units) - remaining + 1, start, -1):
            if widths[end] - widths[start] > box.x2 - box.x + 0.01 or not allowed(end):
                continue
            count = counts[end] - counts[start]
            if not count or count > maximum:
                continue
            tail, breaks = solve(end, remaining - 1, count)
            cost = (count - target) ** 2 + tail
            if cost < best[0]:
                best = cost, (end, *breaks)
        return best

    _, breaks = solve(0, len(lines), counts[-1])
    balanced, start = [], 0
    for (baseline, _), end in zip(lines, breaks):
        trial, fits = layout(units[start:end], copy.copy(box))
        trial_lines = text_lines(trial)
        if not fits or len(trial_lines) != 1:
            return align_lines(lines, box, alignment)
        native_y = trial_lines[0][0]
        moved = []
        for unit in trial:
            y = unit.y if unit.y is not None else unit.box.y
            shifted = move_positioned_unit(unit, unit.box.x, y + baseline - native_y)
            moved.append(shifted)
        balanced.append((baseline, moved))
        start = end
    return align_lines(
        balanced if len(balanced) == len(lines) else lines, box, alignment
    )


def cell_horizontal_bounds(bounds, source, table_box, curves, columns):
    """Use enclosing rules/column gutters only when they do not bisect source."""
    left, bottom, right, top = bounds
    x, y, x2, y2 = source
    fences = [table_box.x, table_box.x2, *columns]
    ruled_fences = [
        (c.box.x + c.box.x2) / 2
        for c in curves
        if c.box is not None
        and c.box.x2 - c.box.x <= 0.5
        and c.box.y <= y + 0.1
        and c.box.y2 >= y2 - 0.1
    ]
    fences.extend(ruled_fences)
    # No evidence of a column: keep conservative whitespace bounds.
    if len(fences) == 2:
        return bounds
    lo = max((f for f in fences if f <= x + 0.1), default=left)
    hi = min((f for f in fences if f >= x2 - 0.1), default=right)
    # A spanning cell may cross inferred gutters; never shrink through glyphs.
    # An inferred band can contain several undiscovered columns. Do not shift
    # a header to that band's far-left edge without an actual enclosing rule.
    if lo not in ruled_fences:
        lo = max(lo, left - 0.5)
    return min(x, lo + 0.5), bottom, max(x2, hi - 0.5), top


def separate_cell_envelopes(bounds, sources):
    """Share whitespace at its midpoint instead of letting both cells use it."""
    result = [list(b) for b in bounds]
    for i, a in enumerate(sources):
        for j in range(i + 1, len(sources)):
            b = sources[j]
            if min(result[i][2], result[j][2]) <= max(
                result[i][0], result[j][0]
            ) or min(result[i][3], result[j][3]) <= max(result[i][1], result[j][1]):
                continue
            horizontal = min(a[3], b[3]) > max(a[1], b[1])
            vertical = min(a[2], b[2]) > max(a[0], b[0])
            if not horizontal and not vertical:
                horizontal = max(b[0] - a[2], a[0] - b[2]) >= max(
                    b[1] - a[3], a[1] - b[3]
                )
                vertical = not horizontal
            if horizontal:
                lo, hi = (i, j) if a[2] <= b[0] else (j, i)
                if sources[lo][2] <= sources[hi][0]:
                    fence = (sources[lo][2] + sources[hi][0]) / 2
                    result[lo][2] = min(result[lo][2], fence)
                    result[hi][0] = max(result[hi][0], fence)
            elif vertical:
                lo, hi = (i, j) if a[3] <= b[1] else (j, i)
                if sources[lo][3] <= sources[hi][1]:
                    fence = (sources[lo][3] + sources[hi][1]) / 2
                    result[lo][3] = min(result[lo][3], fence)
                    result[hi][1] = max(result[hi][1], fence)
    return [tuple(b) for b in result]
