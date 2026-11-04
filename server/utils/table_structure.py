"""Conservative recovery of wrapped labels spanning several numerical rows.

This is deliberately narrower than general cell reconstruction. Unruled tables,
ordinary data rows and ambiguous column boundaries keep their original runs.
"""

import re
from itertools import pairwise
from statistics import median


def identifier_list(text):
    """Recognize identifier rosters, without treating prose lists as names.

    Require multiple technical identifiers and exclusively name-like tokens.
    This is a structural guard, with no document-specific vocabulary.
    """
    entries = re.split(r"[,;，；]", text.strip())
    if len(entries) < 3 or any(not e.strip() for e in entries):
        return False
    technical = 0
    for entry in entries:
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]*", entry)
        if not tokens or re.sub(r"[A-Za-z0-9\s._+()/\-]", "", entry):
            return False
        if any(
            t.isdigit() or not (t[0].isupper() or re.search(r"[a-z][A-Z]|\d", t))
            for t in tokens
        ):
            return False
        technical += any(re.search(r"\d|[a-z][A-Z]|[A-Z]{2}", t) for t in tokens)
    return technical >= 2


def same_table_content(source, target):
    """Punctuation-only edits do not justify retypesetting untranslated text."""

    def compact(value):
        return "".join(c for c in (value or "") if c.isalnum())

    original = compact(source)
    return bool(original) and original == compact(target)


def _bounds(run):
    boxes = [c.visual_bbox.box for c in run]
    return (
        min(b.x for b in boxes),
        min(b.y for b in boxes),
        max(b.x2 for b in boxes),
        max(b.y2 for b in boxes),
    )


def join_wrapped_text(texts):
    result = texts[0].strip()
    for text in texts[1:]:
        text = text.strip()
        # A line break alone cannot prove that words form one identifier.
        # Only an explicitly printed hyphen between letters joins tightly.
        tight = (
            len(result) >= 2
            and result.endswith("-")
            and result[-2].isalpha()
            and text
            and text[0].isalpha()
        )
        result += ("" if tight else " ") + text
    return result


def keeps_identifier_words(units):
    """Do not rewrap a recovered Latin word/identifier through its middle."""
    previous = None
    for unit in units:
        text = unit.try_get_unicode() or ""
        baseline = unit.y if unit.y is not None else unit.box.y
        if previous is not None:
            last, y = previous
            if (
                last
                and text
                and last[-1].isascii()
                and text[0].isascii()
                and last[-1].isalnum()
                and text[0].isalnum()
                and abs(y - baseline) > 0.1
            ):
                return False
        previous = text, baseline
    return True


def consistent_label_translation(source, target):
    """Treat the label before a parenthetical qualifier as an atomic name."""
    source_core = re.split(r"[（(]", source, maxsplit=1)[0].strip()
    target_core = re.split(r"[（(]", target, maxsplit=1)[0].strip()
    if not target_core:
        return False
    if not re.search(r"[A-Za-z]", source_core):
        return True
    if re.search(r"[\u3400-\u9fff]", target_core):
        # Do not accept partial translations such as "EPIC 厨房" or an
        # artificial hyphen inside translated Chinese words ("厨-房").
        return not re.search(
            r"[A-Za-z]|[\u3400-\u9fff]\s*[-‐‑–—]\s*[\u3400-\u9fff]", target_core
        )

    def normalize(text):
        return re.sub(r"[\s-]+", "", text).casefold()

    return normalize(source_core) == normalize(target_core)


def atomic_label_translation(source, target):
    if consistent_label_translation(source, target):
        return target
    source_core = re.split(r"[（(]", source, maxsplit=1)[0].strip()
    qualifier = re.search(r"[（(].*", target)
    if re.search(r"[（(]", source) and qualifier:
        return source_core + qualifier.group()
    return source


def translation_characters(run):
    """Exclude a hyphen overprinted on letters from the translation input.

    Keep all original glyphs separately for lossless layout fallback. Ordinary
    hyphens between characters do not have this substantial spatial overlap.
    """
    result = []
    for char in run:
        box = char.visual_bbox.box
        if char.char_unicode == "-" and any(
            other is not char
            and re.fullmatch(r"[A-Za-z0-9]", other.char_unicode)
            and min(box.x2, other.visual_bbox.box.x2)
            - max(box.x, other.visual_bbox.box.x)
            > (box.x2 - box.x) * 0.5
            and min(box.y2, other.visual_bbox.box.y2)
            - max(box.y, other.visual_bbox.box.y)
            > (box.y2 - box.y) * 0.5
            for other in run
        ):
            continue
        result.append(char)
    return result


def group_table_runs(lines, table_box, curves, text_of_run):
    """Return units containing one or more original lines, without moving glyphs.

    Join only a separated leading-column label centered across at least three
    numerical rows in a rule-bounded band. Require no more label lines than data
    rows and different line spacing from those rows. No semantic/name allowlist
    is used; uncertain runs remain separate.
    """
    runs = [run for line in lines for run in line]
    if not runs:
        return []
    bounds = [_bounds(run) for run in runs]
    texts = [text_of_run(run).strip() for run in runs]
    size = median(c.pdf_style.font_size or 8 for run in runs for c in run)
    width = table_box.x2 - table_box.x
    rules = sorted(
        {
            (curve.box.y + curve.box.y2) / 2
            for curve in curves
            if curve.box is not None
            and curve.box.y2 - curve.box.y <= 0.5
            and min(curve.box.x2, table_box.x2) - max(curve.box.x, table_box.x)
            >= width * 0.8
        }
    )
    merged, consumed = {}, set()
    numeric = re.compile(r"[+−-]?\d+(?:\.\d+)?%?")
    for bottom, top in pairwise(rules):
        indices = [i for i, b in enumerate(bounds) if bottom < b[1] and b[3] < top]
        # Establish actual data baselines from multiple numeric columns, not
        # digits embedded in names, years or section headings.
        rows = []
        for i in sorted(indices, key=lambda i: -bounds[i][1]):
            if not numeric.fullmatch(texts[i]):
                continue
            y = runs[i][0].box.y
            row = next((r for r in rows if abs(r[0] - y) < size * 0.2), None)
            if row is None:
                rows.append([y, i])
            else:
                row.append(i)
        rows = [r for r in rows if len(r) >= 3]
        if len(rows) < 3:
            continue
        ys = sorted(r[0] for r in rows)
        row_gap = median(b - a for a, b in pairwise(ys))
        if any(abs((b - a) - row_gap) > size * 0.15 for a, b in pairwise(ys)):
            continue
        numeric_left = min(bounds[i][0] for r in rows for i in r[1:])
        left = sorted(
            (i for i in indices if bounds[i][2] < numeric_left - size * 0.4),
            key=lambda i: bounds[i][0],
        )
        if not left:
            continue
        # Connected horizontal intervals identify a leading column. A visible
        # gutter and another text column must separate it from the data values.
        candidates, edge = [], bounds[left[0]][2]
        for i in left:
            if bounds[i][0] > edge:
                break
            candidates.append(i)
            edge = max(edge, bounds[i][2])
        others = [i for i in left if i not in candidates]
        if not others or min(bounds[i][0] for i in others) - edge < size * 0.6:
            continue
        candidates.sort(key=lambda i: -bounds[i][1])
        if not 2 <= len(candidates) <= min(len(rows), 4):
            continue
        if any(
            numeric.fullmatch(texts[i]) or not re.search(r"[A-Za-z]", texts[i])
            for i in candidates
        ):
            continue
        glyphs = [c for i in candidates for c in runs[i]]
        if len({(c.xobj_id, c.pdf_style.font_id) for c in glyphs}) != 1:
            continue
        font_sizes = [c.pdf_style.font_size or 8 for c in glyphs]
        label_size = median(font_sizes)
        if max(font_sizes) - min(font_sizes) > label_size * 0.05:
            continue
        centers = [(bounds[i][0] + bounds[i][2]) / 2 for i in candidates]
        if max(centers) - min(centers) > label_size * 0.2:
            continue
        label_ys = [runs[i][0].box.y for i in candidates]
        gaps = [a - b for a, b in pairwise(label_ys)]
        if any(not row_gap * 1.07 < gap < label_size * 1.8 for gap in gaps):
            continue
        if (
            abs((label_ys[0] + label_ys[-1]) / 2 - (ys[0] + ys[-1]) / 2)
            > label_size * 0.35
        ):
            continue
        # Partial rules through this column also prevent joining; do not rely
        # only on the full-width rules used to discover bands above.
        if any(
            curve.box is not None
            and curve.box.y2 - curve.box.y <= 0.5
            and label_ys[-1] < curve.box.y < label_ys[0]
            and curve.box.x < edge
            and curve.box.x2 > min(bounds[i][0] for i in candidates)
            for curve in curves
        ):
            continue
        merged[candidates[0]] = [runs[i] for i in candidates]
        consumed.update(candidates[1:])
    return [merged.get(i, [run]) for i, run in enumerate(runs) if i not in consumed]
