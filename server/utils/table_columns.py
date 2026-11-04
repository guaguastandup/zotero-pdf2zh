"""Coalesce physical text lines only where repeated table gutters support it."""

import math
import re
from bisect import bisect_right
from collections import defaultdict
from itertools import pairwise
from statistics import median


def _bounds(run):
    boxes = [c.visual_bbox.box for c in run]
    return min(b.x for b in boxes), max(b.x2 for b in boxes)


def _is_value(text):
    """Recognize numeric data, including scale/unit suffixes and dimensions."""
    text = re.sub(r"\s+", "", text)
    return bool(
        (re.search(r"\d", text) and not any(c.isalpha() for c in text))
        or re.fullmatch(
            r"[+−-]?\d[\d.,]*(?:[eE][+−-]?\d+)?"
            r"(?:[x×]\d[\d.,]*)*"
            r"(?:[kKmMbBgGtTpP]|[kKmMgGtT]?[bB]|%|"
            r"[pnµμmcdkMGT]?(?:s|g|m|A|K|mol|cd|Hz|Pa|J|W|V|N))?\+?",
            text,
        )
    )


def candidate_groups(original, proposed):
    """Map proposed merges to original fragment IDs without consuming them."""
    owners = {id(c): i for i, u in enumerate(original) for run in u for c in run}
    return [
        ids
        for unit in proposed
        if len(ids := sorted({owners[id(c)] for run in unit for c in run})) > 1
    ]


def coalesce_table_lines(lines, table_box, column_boundaries=None):
    """Keep justified word spaces inside a column, without inferring data rows.

    Sparse/numerical tables retain the existing conservative splitter. Only
    persistent whitespace bands across several physical lines define columns;
    spanning headings remain intact. Cross-line/cell semantics stays with LLM.
    """
    runs = [r for row in lines for r in row]
    if not runs:
        return lines
    numeric_matrix = (
        sum(_is_value("".join(c.char_unicode or "" for c in r)) for r in runs)
        >= len(runs) * 0.25
    )
    if len(lines) < 6 and not (len(lines) >= 4 and numeric_matrix):
        return lines
    size = median(c.pdf_style.font_size or 8 for r in runs for c in r)
    intervals = [[_bounds(r) for r in row] for row in lines]
    bands = []
    for x in range(math.ceil(table_box.x + size), math.floor(table_box.x2 - size)):
        eligible = [
            row
            for row in intervals
            if row and row[0][0] < x - size * 0.5 and row[-1][1] > x + size * 0.5
        ]
        if len(eligible) < max(4, len(lines) * 0.3):
            continue
        occupied = sum(any(a - 0.1 <= x <= b + 0.1 for a, b in row) for row in eligible)
        if occupied / len(eligible) > 0.12:
            continue
        if bands and x == bands[-1][-1] + 1:
            bands[-1].append(x)
        else:
            bands.append([x])
    boundaries = [
        (band[0] + band[-1]) / 2 for band in bands if band[-1] - band[0] >= size * 0.6
    ]
    if not 1 <= len(boundaries) <= 11:
        return lines
    if column_boundaries is not None:
        column_boundaries.extend(boundaries)
    # Numeric columns still constrain LLM merges, without coalescing their rows.
    if (
        sum(
            _is_value("".join(c.char_unicode or "" for c in r))
            or not any(c.isalpha() for c in "".join(c.char_unicode or "" for c in r))
            for r in runs
        )
        >= len(runs) * 0.25
    ):
        return lines
    result = []
    for row in lines:
        bounds = [_bounds(r) for r in row]
        if any(a < x < b for a, b in bounds for x in boundaries):
            result.append(row)  # A spanning heading does not define separate cells.
            continue
        merged, previous = [], None
        for run, (left, right) in zip(row, bounds):
            column = bisect_right(boundaries, (left + right) / 2)
            if column == previous:
                merged[-1].extend(run)
            else:
                merged.append(list(run))
            previous = column
        result.append(merged)
    return result


def assemble_table_cells(units, columns, table_box, curves, text_of_run):
    """Recover cells when leading enumeration or repeated spacing proves rows.

    This uses generic numbered row labels and geometric rules, not dataset names
    or scientific terms. Without enough evidence, keep the existing units.
    """
    if not units:
        return units, []

    def bounds(unit):
        boxes = [c.visual_bbox.box for run in unit for c in run]
        return (
            min(b.x for b in boxes),
            min(b.y for b in boxes),
            max(b.x2 for b in boxes),
            max(b.y2 for b in boxes),
        )

    boxes = [bounds(u) for u in units]
    size = median(c.pdf_style.font_size or 8 for u in units for run in u for c in run)
    numeric = [i for i, u in enumerate(units) if _is_value(text_of_run(u[0]))]
    repeated = defaultdict(list)
    for i, unit in enumerate(units):
        text = text_of_run(unit[0]).strip()
        if len(unit) == 1 and 1 <= len(text) <= 24:
            repeated[text].append(i)
    row_labels = []
    for ids in repeated.values():
        if (
            len(ids) < 3
            or max(boxes[i][0] for i in ids) - min(boxes[i][0] for i in ids)
            > size * 0.5
        ):
            continue
        for i in ids:
            center = (boxes[i][1] + boxes[i][3]) / 2
            # Repeated short entries aligned with two other columns are data
            # rows, not continuations of one long paragraph.
            peers = [
                j
                for j, b in enumerate(boxes)
                if j != i
                and abs((b[1] + b[3]) / 2 - center) < size * 0.3
                and (b[2] <= boxes[i][0] or b[0] >= boxes[i][2])
            ]
            if len(peers) >= 2:
                row_labels.append(i)
    data_units = sum(
        _is_value(text_of_run(u[0])) or not any(c.isalpha() for c in text_of_run(u[0]))
        for u in units
    )
    if data_units >= len(units) * 0.25 or len(row_labels) >= 3:
        numeric = sorted(set(numeric + row_labels))
        if not numeric:
            return units, []
        rows = []
        for i in sorted(numeric, key=lambda i: -boxes[i][3]):
            center = (boxes[i][1] + boxes[i][3]) / 2
            row = next((row for row in rows if abs(row[0] - center) < size * 0.3), None)
            if row is None:
                rows.append([center, i])
            else:
                row.append(i)
        aligned = any(
            max(values) - min(values) <= size * 0.6
            for values in [
                [boxes[i][0] for i in numeric],
                [boxes[i][2] for i in numeric],
                [(boxes[i][0] + boxes[i][2]) / 2 for i in numeric],
            ]
        )
        barriers = (
            [(a[0] + b[0]) / 2 for a, b in pairwise(rows)]
            if len(rows) >= 3
            and (all(len(row) >= 3 for row in rows) or aligned or len(row_labels) >= 3)
            else []
        )
        return units, barriers
    if not columns:
        return units, []
    marker = re.compile(r"^(?:[A-Za-z]{0,3}\d+[:.)])(?=\s|[A-Za-z])")
    anchors = [
        i
        for i, u in enumerate(units)
        if boxes[i][2] < columns[0] and marker.match(text_of_run(u[0]).strip())
    ]
    if len(anchors) < 3:
        leading = sorted(
            (i for i, b in enumerate(boxes) if b[2] < columns[0]),
            key=lambda i: -boxes[i][3],
        )
        if len(leading) < 3:
            return units, []
        gaps = [boxes[a][3] - boxes[b][3] for a, b in pairwise(leading)]
        threshold = max(size * 1.6, min(median(gaps), size * 1.1) * 1.6)
        anchors = [
            leading[0],
            *[
                b
                for a, b in pairwise(leading)
                if boxes[a][1] - boxes[b][3] > threshold - size * 0.7
            ],
        ]
        votes = []
        for col in range(len(columns) + 1):
            indices = sorted(
                (
                    i
                    for i, b in enumerate(boxes)
                    if not any(b[0] < x < b[2] for x in columns)
                    and bisect_right(columns, (b[0] + b[2]) / 2) == col
                ),
                key=lambda i: -boxes[i][3],
            )
            for a, b in pairwise(indices):
                if boxes[a][1] - boxes[b][3] <= threshold - size * 0.7:
                    continue
                row = next(
                    (
                        v
                        for v in votes
                        if abs(boxes[v[0]][3] - boxes[b][3]) <= size * 0.45
                    ),
                    None,
                )
                if row is None:
                    votes.append([b, {col}])
                else:
                    row[1].add(col)
        for i, cols in votes:
            if len(cols) >= 2 and not any(
                abs(boxes[a][3] - boxes[i][3]) <= size * 0.5 for a in anchors
            ):
                anchors.append(i)
        if len(anchors) < 3:
            return units, []
    barriers = []
    for i in anchors:
        top = boxes[i][3]
        previous = [b[1] for b in boxes if b[1] > top + 0.1]
        if previous:
            barriers.append((top + min(previous)) / 2)
    rules = [
        (c.box.y + c.box.y2) / 2
        for c in curves
        if c.box is not None
        and c.box.y2 - c.box.y <= 0.5
        and min(c.box.x2, table_box.x2) - max(c.box.x, table_box.x)
        >= (table_box.x2 - table_box.x) * 0.8
    ]
    bands = sorted({table_box.y, table_box.y2, *rules, *barriers})
    cells, free = {}, []
    for i, (left, bottom, right, top) in enumerate(boxes):
        if any(left < x < right for x in columns) or any(
            bottom + 0.1 < y < top - 0.1 for y in bands
        ):
            free.append([i])
            continue
        key = (
            bisect_right(columns, (left + right) / 2),
            bisect_right(bands, (bottom + top) / 2),
        )
        cells.setdefault(key, []).append(i)
    for key, ids in list(cells.items()):
        if any(
            _is_value(text_of_run(units[i][0]))
            or not any(c.isalpha() for c in text_of_run(units[i][0]))
            for i in ids
        ):
            free.extend([i] for i in ids)
            del cells[key]
    ordered = sorted([*cells.values(), *free], key=min)
    return [
        [
            run
            for i in sorted(ids, key=lambda i: (-boxes[i][3], boxes[i][0]))
            for run in units[i]
        ]
        for ids in ordered
    ], barriers
