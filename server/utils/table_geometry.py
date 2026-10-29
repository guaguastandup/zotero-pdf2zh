"""Evidence-based local table repairs; no document-specific vocabulary."""

from bisect import bisect_right
from statistics import median

from utils.table_columns import _is_value


def bounds(chars):
    boxes = [c.visual_bbox.box for c in chars]
    return (
        min(b.x for b in boxes),
        min(b.y for b in boxes),
        max(b.x2 for b in boxes),
        max(b.y2 for b in boxes),
    )


def isolated_spanning_line(lines, units, curves):
    """A source-supported spanning sentence owns its row, not neighbouring cells."""
    own = {id(c) for r in lines for c in r}
    x, y, x2, y2 = bounds([c for r in lines for c in r])
    if any(
        min(y2, b[3]) - max(y, b[1]) > 0.3
        for u in units
        if not all(id(c) in own for r in u for c in r)
        for b in [bounds([c for r in u for c in r])]
    ):
        return False
    return not any(
        c.box
        and c.box.x2 - c.box.x <= 0.5
        and x + 0.1 < c.box.x < x2 - 0.1
        and min(y2, c.box.y2) - max(y, c.box.y) > 0.3
        for c in curves
    )


def numeric_column_centers(units, text):
    clusters = []
    for unit in units:
        if len(unit) != 1 or not _is_value(text(unit[0])):
            continue
        b = bounds(unit[0])
        center = (b[0] + b[2]) / 2
        size = median(c.pdf_style.font_size or 8 for c in unit[0])
        cluster = next(
            (r for r in clusters if abs(median(r[0]) - center) <= size * 0.4), None
        )
        if cluster is None:
            cluster = [[], set()]
            clusters.append(cluster)
        cluster[0].append(center)
        cluster[1].add(round(b[1] / size, 1))
    return sorted(median(xs) for xs, ys in clusters if len(ys) >= 3)


def split_header_run(lines, units, curves, centers):
    """Split glued short headers only when repeated data columns support them.

    Whole sentences must be excluded by the caller. Never split a glyph or
    numeric value. Sparse titles without a neighbouring header tier stay whole.
    """
    if len(lines) != 1 or len(centers) < 3:
        return None
    chars = lines[0]
    x, y, x2, y2 = bounds(chars)
    size = median(c.pdf_style.font_size or 8 for c in chars)
    nearby = [
        u
        for u in units
        if len(u) == 1
        and u is not lines
        and not _is_value("".join(c.char_unicode or "" for c in u[0]))
        and abs(bounds(u[0])[1] - y) <= size * 2.5
        and bounds(u[0])[2] - bounds(u[0])[0] <= size * 6
    ]
    if len(nearby) < 4:
        return None
    tokens = []
    for c in chars:
        value = c.char_unicode or ""
        if not tokens or (
            value.strip()
            and (
                not (tokens[-1][-1].char_unicode or "").strip()
                or (
                    value[:1].isupper()
                    and (
                        (tokens[-1][-1].char_unicode or "")[-1:].islower()
                        or (tokens[-1][-1].char_unicode or "")[-1:] in ".:;"
                    )
                )
                or c.box.x - tokens[-1][-1].box.x2 > size * 0.15
            )
        ):
            tokens.append([])
        tokens[-1].append(c)
    if len(tokens) < 2:
        return None
    fences = [(a + b) / 2 for a, b in zip(centers, centers[1:])]
    groups = {}
    for token in tokens:
        visible = [c for c in token if (c.char_unicode or "").strip()]
        if not visible:
            return None
        b = bounds(visible)
        mid = (b[0] + b[2]) / 2
        index = bisect_right(fences, mid)
        gap = min(
            (abs(centers[index] - v) for j, v in enumerate(centers) if j != index),
            default=size * 4,
        )
        lo = centers[index - 1] if index else centers[0] - (centers[1] - centers[0])
        hi = (
            centers[index + 1]
            if index + 1 < len(centers)
            else centers[-1] + (centers[-1] - centers[-2])
        )
        # A long header word can overhang its numerical column's midpoint
        # boundary. Reject consumption of another column center, not word width.
        if b[0] <= lo or b[2] >= hi or abs(mid - centers[index]) > gap * 0.48:
            return None
        groups.setdefault(index, []).extend(token)
    if len(groups) < 2 or len(groups) < len(tokens) * 0.7:
        return None
    # Broad titles with just a few words should remain merged headings.
    same_row = sum(abs(bounds(u[0])[1] - y) <= size * 0.3 for u in nearby)
    if len(tokens) < 4 and same_row < 4:
        return None
    for group in groups.values():
        a, b, c, d = bounds(group)
        if any(
            rule.box
            and rule.box.x2 - rule.box.x <= 0.5
            and a + 0.1 < rule.box.x < c - 0.1
            and min(d, rule.box.y2) - max(b, rule.box.y) > 0.3
            for rule in curves
        ):
            return None
    return [[groups[i]] for i in sorted(groups)]


def header_alignment_hints(split_units, units, curves, centers):
    """Recover the common centers of two source header tiers after splitting."""
    hints = {}
    fences = [(a + b) / 2 for a, b in zip(centers, centers[1:])]
    for unit in split_units:
        a = bounds(unit[0])
        middle = (a[0] + a[2]) / 2
        size = median(c.pdf_style.font_size or 8 for c in unit[0])
        choices = []
        for peer in units:
            if peer is unit or len(peer) != 1:
                continue
            if _is_value("".join(c.char_unicode or "" for c in peer[0])):
                continue
            b = bounds(peer[0])
            center = (b[0] + b[2]) / 2
            if not (
                size * 0.4 < b[1] - a[1] < size * 2
                and abs(center - middle) <= size * 0.5
                and bisect_right(fences, center) == bisect_right(fences, middle)
            ):
                continue
            if any(
                c.box
                and c.box.y2 - c.box.y <= 0.5
                and a[3] < c.box.y < b[1]
                and c.box.x < max(a[2], b[2])
                and c.box.x2 > min(a[0], b[0])
                for c in curves
            ):
                continue
            choices.append((b[1] - a[1], peer, b, center))
        if choices:
            _, peer, b, center = min(choices, key=lambda v: v[0])
            hint = ((middle + center) / 2, min(a[0], b[0]), max(a[2], b[2]))
            for item in (unit, peer):
                hints[frozenset(id(c) for row in item for c in row)] = hint
    return hints
