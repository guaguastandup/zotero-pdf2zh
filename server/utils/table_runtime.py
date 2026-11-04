"""Opt-in, child-process-only adapter for BabelDOC table layout.

No installed engine files are changed. Keep the integration here so it can be
replaced by an upstream table-policy API when one becomes available.
"""

import copy
import logging
import re
import shutil
from pathlib import Path
from statistics import median

from utils.table_batching import process_page_in_table_batches
from utils.table_columns import (
    _is_value,
    assemble_table_cells,
    candidate_groups,
    coalesce_table_lines,
)
from utils.table_labels import anchor_label_units, label_anchor, split_label_parts
from utils.table_geometry import (
    isolated_spanning_line,
    numeric_column_centers,
    split_header_run,
    header_alignment_hints,
)
from utils.table_layout import (
    alignment_box,
    balanced_cell_layout,
    cell_horizontal_bounds,
    separate_cell_envelopes,
    source_alignment,
    measure_formula_units,
    contain_cell_layout,
)
from utils.table_images import avoid_images, image_boxes, overlaps, rect
from utils.table_mode import parse_table_mode
from utils.table_semantics import group_table_semantics
from utils.table_structure import (
    atomic_label_translation,
    consistent_label_translation,
    group_table_runs,
    identifier_list,
    join_wrapped_text,
    keeps_identifier_words,
    same_table_content,
    translation_characters,
)

FLAG = "--zotero-table-mode"
REFERENCE_FLAG = "--zotero-reference-skip"
SUPPORTED_BABELDOC_VERSIONS = ("0.6.2", "0.6.4")
logger = logging.getLogger(__name__)


def table_policy_supported():
    from importlib.metadata import version

    from packaging.version import Version

    return Version(version("BabelDOC")) in {
        Version(item) for item in SUPPORTED_BABELDOC_VERSIONS
    }


def warn_native_table_fallback():
    from importlib.metadata import version

    logger.warning(
        "BabelDOC %s 暂不支持增强表格（已验证版本：%s）；本次使用原生表格处理。",
        version("BabelDOC"),
        ", ".join(SUPPORTED_BABELDOC_VERSIONS),
    )


def prepare_table_runtime_command(command):
    if FLAG not in command and REFERENCE_FLAG not in command:
        return command
    args = list(command)
    reference_skip = REFERENCE_FLAG in args
    if reference_skip:
        args.remove(REFERENCE_FLAG)
    mode = None
    if FLAG in args:
        index = args.index(FLAG)
        if index + 1 >= len(args):
            raise ValueError("Missing table mode")
        mode = parse_table_mode(args[index + 1])
        del args[index : index + 2]
    if not mode and not reference_skip:
        return args
    if not args:
        raise ValueError("Missing engine command")

    executable = Path(shutil.which(args[0]) or args[0])
    if executable.stem.lower() in ("python", "python3", "python3.12", "python3.11"):
        module_index = args.index("-m") if "-m" in args else -1
        if (
            module_index < 0
            or module_index + 1 >= len(args)
            or args[module_index + 1] != "pdf2zh_next"
        ):
            raise ValueError("Table modes require a pdf2zh_next Python invocation")
        engine_args = args[module_index + 2 :]
        python = executable
    else:
        if executable.stem.lower() != "pdf2zh_next":
            raise ValueError("Table modes require the pdf2zh_next Python engine")
        candidates = (
            executable.parent / "python.exe",
            executable.parent.parent / "python.exe",
            executable.parent / "python",
        )
        python = next((p for p in candidates if p.is_file()), None)
        if python is None:
            raise ValueError("Cannot locate the Python interpreter beside pdf2zh_next")
        engine_args = args[1:]
    runner = Path(__file__).with_name("table_runner.py")
    return [
        str(python), "-u", str(runner), mode or "none",
        *([REFERENCE_FLAG] if reference_skip else []),
        *engine_args,
    ]


def contains(box, char):
    visual = char.visual_bbox.box
    x, y = (visual.x + visual.x2) / 2, (visual.y + visual.y2) / 2
    return box.x <= x <= box.x2 and box.y <= y <= box.y2


def snapshot_character(char):
    """Copy mutable glyph geometry, sharing the engine's paint/clip state.

    Clip states can form very deep linked chains. BabelDOC's own glyph
    relocation shares that state as well; recursively copying it is unnecessary
    and can exceed Python's recursion limit on otherwise valid PDFs.
    """
    snapshot = copy.copy(char)
    snapshot.pdf_style = copy.copy(char.pdf_style)
    snapshot.box = copy.copy(char.box)
    snapshot.visual_bbox = copy.copy(char.visual_bbox)
    snapshot.visual_bbox.box = copy.copy(char.visual_bbox.box)
    return snapshot


def split_table_lines(chars):
    """Split original characters at baselines and visible horizontal gutters.

    This intentionally does not infer merged cells or a complete table grid.
    Each original text run is a conservative, independently bounded unit.
    """
    lines = []
    for char in sorted(chars, key=lambda c: -c.box.y):
        size = char.pdf_style.font_size or 8
        line = next(
            (line for line in lines if abs(line[0].box.y - char.box.y) <= size * 0.3),
            None,
        )
        if line is None:
            line = []
            lines.append(line)
        line.append(char)
    for line in lines:
        line.sort(key=lambda c: c.visual_bbox.box.x)
        size = median(c.pdf_style.font_size or 8 for c in line)
        runs = [[]]
        for char in line:
            if (
                runs[-1]
                and char.visual_bbox.box.x - runs[-1][-1].visual_bbox.box.x2
                > size * 0.45
            ):
                runs.append([])
            runs[-1].append(char)
        yield runs


def protected_run(text):
    compact = re.sub(r"\s+", "", text)
    return (
        not compact
        or not re.search(r"[A-Za-z\u3400-\u9fff]", compact)
        or bool(re.fullmatch(r"[A-Z\d_↑↓%()./+−-]+", compact))
    )


def bounded_run_box(run, table_chars, table_box, curves=(), image_rects=()):
    """Use nearby whitespace without crossing another glyph or a table rule."""
    boxes = [char.visual_bbox.box for char in run]
    left, right = min(b.x for b in boxes), max(b.x2 for b in boxes)
    bottom, top = min(b.y for b in boxes), max(b.y2 for b in boxes)
    size = median(char.pdf_style.font_size or 8 for char in run)
    own = {id(char) for char in run}
    obstacles = [char.visual_bbox.box for char in table_chars if id(char) not in own]
    next_column = min(
        (b.x for b in obstacles if b.x >= right and b.y < top and b.y2 > bottom),
        default=table_box.x2,
    )
    right = min(right + size * 2, (right + next_column) / 2, table_box.x2)
    above, below = table_box.y2, table_box.y
    for obstacle in obstacles:
        if obstacle.x < right and obstacle.x2 > left:
            if obstacle.y >= top:
                above = min(above, obstacle.y)
            if obstacle.y2 <= bottom:
                below = max(below, obstacle.y2)
    for curve in curves:
        box = getattr(curve, "box", None)
        if box and box.y2 - box.y <= 0.5 and box.x < right and box.x2 > left:
            if box.y >= top:
                above = min(above, box.y)
            if box.y2 <= bottom:
                below = max(below, box.y2)
    bounds = (
        max(left, table_box.x),
        max(bottom - size * 0.25, (bottom + below) / 2, table_box.y),
        right,
        min(top + size * 0.25, (top + above) / 2, table_box.y2),
    )
    source = (min(b.x for b in boxes), bottom, max(b.x2 for b in boxes), top)
    return avoid_images(bounds, source, image_rects) if image_rects else bounds


def numeric_figure_row_characters(page):
    """Keep separated numeric figure columns out of paragraph reflow.

    Figure score rows can be labelled fallback_line rather than table. Require
    an entirely numeric baseline with multiple visibly separated values; text
    labels and sentences containing numbers remain on their normal path.
    """
    protected = set()
    for region in page.page_layout:
        if region.class_name != "figure":
            continue
        chars = [
            c for c in page.pdf_character if not c.vertical and contains(region.box, c)
        ]
        for runs in split_table_lines(chars):
            runs = [r for r in runs if any((c.char_unicode or "").strip() for c in r)]
            if len(runs) < 2 or not all(
                _is_value("".join(c.char_unicode or "" for c in run)) for run in runs
            ):
                continue
            size = median(c.pdf_style.font_size or 8 for run in runs for c in run)
            if not any(
                min(c.visual_bbox.box.x for c in right)
                - max(c.visual_bbox.box.x2 for c in left)
                > size * 1.5
                for left, right in zip(runs, runs[1:])
            ):
                continue
            protected.update(id(c) for run in runs for c in run)
    return [c for c in page.pdf_character if id(c) in protected]


def install_table_policy(mode):
    """Install scoped hooks in this translation child process only."""
    parse_table_mode(mode)
    # Check metadata before importing any private engine API: a newer engine
    # may have moved or removed those modules entirely.
    if not table_policy_supported():
        warn_native_table_fallback()
        return lambda: None

    from babeldoc.babeldoc_exception.BabelDOCException import ExtractTextError
    from babeldoc.format.pdf.document_il import (
        Box,
        PdfLine,
        PdfParagraph,
        PdfParagraphComposition,
    )
    from babeldoc.format.pdf.document_il.midend.il_translator import ILTranslator
    from babeldoc.format.pdf.document_il.midend.il_translator_llm_only import (
        ILTranslatorLLMOnly,
    )
    from babeldoc.format.pdf.document_il.midend.paragraph_finder import (
        ParagraphFinder,
        generate_base58_id,
    )
    from babeldoc.format.pdf.document_il.midend.typesetting import Typesetting
    from babeldoc.format.pdf.document_il.utils.layout_helper import (
        get_char_unicode_string,
    )

    original_page = ParagraphFinder.process_page
    original_process = ParagraphFinder.process
    original_fit = Typesetting._find_optimal_scale_and_layout
    original_llm_page = ILTranslatorLLMOnly.process_page
    original_post = ILTranslator.post_translate_paragraph
    originals = {}
    wrapped = set()
    atomic_names = set()
    label_anchors = {}
    protected_pages = set()
    paragraph_images = {}
    paragraph_text_obstacles = {}
    source_rows, row_styles, row_scales = {}, {}, {}
    alignments = {}

    def process_page(finder, page):
        numeric_chars = numeric_figure_row_characters(page)
        protected_ids = {id(c) for c in numeric_chars}
        page.pdf_character = [
            c for c in page.pdf_character if id(c) not in protected_ids
        ]
        try:
            return process_table_page(finder, page)
        finally:
            page.pdf_character.extend(numeric_chars)
            if numeric_chars:
                protected_pages.add(page.page_number)
                logger.info(
                    "Preserved %s numeric figure glyphs on page %s at source positions",
                    len(numeric_chars),
                    page.page_number + 1,
                )

    def process_table_page(finder, page):
        regions = [
            layout for layout in page.page_layout if layout.class_name == "table"
        ]
        if not regions:
            return original_page(finder, page)
        if finder.translation_config.ocr_workaround:
            raise RuntimeError(
                "Table modes are not yet supported with the OCR workaround. Disable it or use legacy table settings."
            )
        groups = [[] for _ in regions]
        remaining = []
        for char in page.pdf_character:
            region = next(
                (i for i, layout in enumerate(regions) if contains(layout.box, char)),
                None,
            )
            if region is None:
                remaining.append(char)
            else:
                groups[region].append(char)
        page.pdf_character = remaining
        original_page(finder, page)
        for region, chars in zip(regions, groups):
            if not chars:
                continue
            protected_pages.add(page.page_number)
            if mode == "preserve":
                page.pdf_character.extend(chars)
                continue
            table_chars = chars
            rotated = [char for char in chars if char.vertical]
            page.pdf_character.extend(rotated)
            chars = [char for char in chars if not char.vertical]
            if not chars:
                continue
            images = image_boxes(page, region.box)
            retained_boxes = [rect(c.visual_bbox.box) for c in rotated]
            obstacles = [*images, *retained_boxes]
            columns = []
            original_lines = list(split_table_lines(chars))
            units = group_table_runs(
                coalesce_table_lines(original_lines, region.box, columns),
                region.box,
                page.pdf_curve,
                lambda run: get_char_unicode_string(translation_characters(run)),
            )
            # Keep existing recovered-name protection. New semantic groups may
            # also be ordinary headers/sentences containing legitimate metrics.
            names = {
                frozenset(id(c) for line in unit for c in line)
                for unit in units
                if len(unit) > 1
            }
            spanning_units = [unit for unit in units if len(unit) > 1]
            units, row_boundaries = assemble_table_cells(
                units,
                columns,
                region.box,
                page.pdf_curve,
                lambda run: get_char_unicode_string(translation_characters(run)),
            )
            translator = getattr(finder.translation_config, "translator", None)
            candidates = []
            spans = []
            if callable(getattr(translator, "llm_translate", None)):
                # Keep raw fragments available: local recovery must not prevent
                # the whole-table analysis from rejecting a proposed merge.
                original_units = [[run] for line in original_lines for run in line]
                candidates = candidate_groups(original_units, units)
                spans = candidate_groups(original_units, spanning_units)
                units = original_units
            cancelled = getattr(finder.translation_config, "raise_if_cancelled", None)
            if cancelled:
                cancelled()
            policies = {}
            analysis_status = {}
            analysis_units = units
            units = group_table_semantics(
                units,
                region.box,
                page.pdf_curve,
                lambda run: get_char_unicode_string(translation_characters(run)),
                translator,
                policies,
                column_boundaries=columns,
                row_boundaries=row_boundaries,
                merge_candidates=candidates,
                status=analysis_status,
                spanning_candidates=spans,
                image_rects=images,
                protected_rects=retained_boxes,
            )
            if cancelled:
                cancelled()
            if callable(
                getattr(translator, "llm_translate", None)
            ) and not analysis_status.get("success"):
                # Missing/oversized/invalid analysis must not turn a formerly
                # complete table into many independent word translations.
                page.pdf_character.extend(chars)
                logger.warning(
                    "Table on page %s kept unchanged: semantic analysis unavailable",
                    page.page_number + 1,
                )
                continue
            replacements = []

            def text_of_run(run):
                return get_char_unicode_string(translation_characters(run))

            centers = numeric_column_centers(units, text_of_run)
            repaired = []
            split_units = []
            for lines in units:
                key = frozenset(id(c) for line in lines for c in line)
                # A confirmed sentence remains one cell; only unresolved glued
                # headers are subdivided using repeated numerical evidence.
                split = (
                    None
                    if key in policies
                    else split_header_run(lines, units, page.pdf_curve, centers)
                )
                repaired.extend(split or [lines])
                if split:
                    split_units.extend(split)
            units = repaired
            header_hints = header_alignment_hints(
                split_units, units, page.pdf_curve, centers
            )
            preserved_chars = {
                id(c)
                for i in analysis_status.get("preserve_ids", [])
                for run in analysis_units[i]
                for c in run
            }
            for lines in units:
                if obstacles and any(
                    overlaps(rect(c.visual_bbox.box), image)
                    for run in lines
                    for c in run
                    for image in obstacles
                ):
                    page.pdf_character.extend(c for run in lines for c in run)
                    continue
                if all(id(c) in preserved_chars for run in lines for c in run):
                    page.pdf_character.extend(c for run in lines for c in run)
                    continue
                clean = [translation_characters(line) for line in lines]
                key = frozenset(id(c) for line in lines for c in line)
                if key in policies and policies[key] is None:
                    names.discard(key)
                parts = split_label_parts(clean, policies.get(key))
                if parts is None:
                    replacements.append((lines, None, None))
                    continue
                for part_lines, translate in parts:
                    if translate:
                        replacements.append(
                            (part_lines, label_anchor(part_lines, clean), clean)
                        )
                    else:
                        # Original glyph IDs/styles/coordinates bypass translation
                        # and typesetting entirely, even within a single line.
                        page.pdf_character.extend(
                            c for line in part_lines for c in line
                        )
            pending = []
            for lines, anchor, whole_lines in replacements:
                run = [char for line in lines for char in line]
                text = join_wrapped_text(
                    [
                        get_char_unicode_string(translation_characters(line))
                        for line in lines
                    ]
                )
                if identifier_list(text):
                    page.pdf_character.extend(run)
                    continue
                if protected_run(text) and (
                    whole_lines is None or not re.search(r"[A-Za-z\u3400-\u9fff]", text)
                ):
                    page.pdf_character.extend(run)
                    continue
                bounds = bounded_run_box(
                    run, table_chars, region.box, page.pdf_curve, obstacles
                )
                if bounds is None:
                    page.pdf_character.extend(run)
                    continue
                boxes = [c.visual_bbox.box for c in run]
                source_rect = (
                    min(b.x for b in boxes),
                    min(b.y for b in boxes),
                    max(b.x2 for b in boxes),
                    max(b.y2 for b in boxes),
                )
                if (
                    len(lines) == 1
                    and sum(source_rect[0] < c < source_rect[2] for c in columns) >= 2
                    and re.search(r"[A-Za-z].*\s.*[A-Za-z]", text)
                    and not (
                        frozenset(id(c) for c in run) in policies
                        and policies[frozenset(id(c) for c in run)] is None
                        and isolated_spanning_line(lines, units, page.pdf_curve)
                    )
                ):
                    # A physical header run can contain several adjacent cells
                    # when their word gaps are too small for the PDF splitter.
                    # Its column ownership is unresolved: preserve source layout.
                    page.pdf_character.extend(run)
                    continue
                # Inline label parts must remain anchored to retained glyphs.
                if whole_lines is None:
                    own_ids = {id(g) for g in run}
                    hint = header_hints.get(frozenset(own_ids))
                    if hint:
                        bounds = (
                            min(bounds[0], hint[1]),
                            bounds[1],
                            max(bounds[2], hint[2]),
                            bounds[3],
                        )
                    bounds = cell_horizontal_bounds(
                        bounds, source_rect, region.box, page.pdf_curve, columns
                    )
                    bounds = avoid_images(
                        bounds,
                        source_rect,
                        [
                            rect(c.visual_bbox.box)
                            for c in table_chars
                            if id(c) not in own_ids
                        ],
                        tolerance=min(
                            0.3, median(c.pdf_style.font_size or 8 for c in run) * 0.04
                        ),
                    )
                    if bounds is None:
                        page.pdf_character.extend(run)
                        continue
                left, bottom, right, top = bounds
                if anchor and anchor[3]:
                    # A centered qualifier can use its label's original column
                    # width, without resizing or moving the retained name.
                    left = min(
                        c.visual_bbox.box.x for line in whole_lines for c in line
                    )
                    right = max(
                        c.visual_bbox.box.x2 for line in whole_lines for c in line
                    )
                if obstacles and any(
                    overlaps((left, bottom, right, top), b) for b in obstacles
                ):
                    page.pdf_character.extend(run)
                    continue
                paragraph = PdfParagraph(
                    box=Box(left, bottom, right, top),
                    pdf_style=copy.copy(run[0].pdf_style),
                    unicode=text,
                    first_line_indent=False,
                    vertical=False,
                    xobj_id=run[0].xobj_id,
                    layout_id=region.id,
                    layout_label="table_text",
                    debug_id=generate_base58_id(),
                    pdf_paragraph_composition=[
                        finder.create_line(translation_characters(line))
                        for line in lines
                    ],
                    render_order=min(
                        (c.render_order for c in run if c.render_order is not None),
                        default=0,
                    ),
                )
                # Keep the object alive across engine split parts so Python
                # cannot reuse its id for an unrelated body paragraph.
                source = copy.copy(paragraph)
                source.box = copy.copy(paragraph.box)
                source.pdf_style = copy.copy(paragraph.pdf_style)
                source.pdf_paragraph_composition = [
                    PdfParagraphComposition(pdf_character=snapshot_character(char))
                    for line in lines
                    for char in translation_characters(line)
                ]
                originals[id(paragraph)] = (paragraph, source)
                hint = header_hints.get(frozenset(id(c) for c in run))
                alignments[id(paragraph)] = (
                    source_alignment(lines, units, anchor_hint=hint[0])
                    if hint
                    else source_alignment(lines, units)
                )
                source_rows[id(paragraph)] = (
                    max(median(c.box.y for c in line) for line in lines),
                    len(lines),
                    median(c.pdf_style.font_size or 8 for c in run),
                )
                if obstacles:
                    paragraph_images[id(paragraph)] = obstacles
                if anchor:
                    label_anchors[id(paragraph)] = anchor
                if len(lines) > 1:
                    wrapped.add(id(paragraph))
                if frozenset(id(c) for c in run) in names:
                    atomic_names.add(id(paragraph))
                pending.append((paragraph, run))
            if pending:
                # Validate complete peer cells, not only individual source
                # glyphs. Different-height header lines can otherwise let
                # neighbouring paragraphs expand into the same whitespace.
                source_bounds = []
                for paragraph, run in pending:
                    boxes = [c.visual_bbox.box for c in run]
                    source_bounds.append(
                        (
                            min(b.x for b in boxes),
                            min(b.y for b in boxes),
                            max(b.x2 for b in boxes),
                            max(b.y2 for b in boxes),
                        )
                    )
                envelopes = separate_cell_envelopes(
                    [rect(p.box) for p, _ in pending], source_bounds
                )
                # One source row supplies a common top anchor. Multi-line peers
                # at the same source font size also share the readable scale
                # found during the engine's preflight pass.
                rows = []
                for i, (paragraph, _) in enumerate(pending):
                    y, count, size = source_rows[id(paragraph)]
                    row = next(
                        (
                            r
                            for r in rows
                            if abs(r[0] - y) <= size * 0.3
                            and abs(r[1] - size) <= size * 0.05
                        ),
                        None,
                    )
                    if row is None:
                        row = [y, size, []]
                        rows.append(row)
                    row[2].append((i, paragraph, count))
                for _, _, members in rows:
                    if len(members) < 2:
                        continue
                    top = min(envelopes[i][3] for i, _, _ in members)
                    for i, paragraph, count in members:
                        if id(paragraph) not in label_anchors:
                            key = (id(page), id(region), members[0][0], count)
                            row_styles[id(paragraph)] = (
                                top,
                                key if count > 1 else None,
                            )
                for i, (paragraph, run) in enumerate(pending):
                    peers = [b for j, b in enumerate(source_bounds) if j != i]
                    tolerance = min(
                        0.3, median(c.pdf_style.font_size or 8 for c in run) * 0.04
                    )
                    bounds = avoid_images(
                        envelopes[i], source_bounds[i], peers, tolerance=tolerance
                    )
                    if bounds is None:
                        page.pdf_character.extend(run)
                        continue
                    paragraph.box = Box(*bounds)
                    originals[id(paragraph)][1].box = copy.copy(paragraph.box)
                    paragraph_images[id(paragraph)] = obstacles
                    paragraph_text_obstacles[id(paragraph)] = (peers, tolerance)
                    page.pdf_paragraph.append(paragraph)

    def process(finder, document):
        try:
            return original_process(finder, document)
        except ExtractTextError:
            if protected_pages and not any(
                page.pdf_paragraph for page in document.page
            ):
                return None  # A table-only document may legitimately have nothing to translate.
            raise

    def fit(
        typesetter,
        paragraph,
        page,
        units,
        initial_scale=1.0,
        use_english_line_break=True,
        apply_layout=True,
    ):
        saved = originals.get(id(paragraph))
        if saved is None:
            return original_fit(
                typesetter,
                paragraph,
                page,
                units,
                initial_scale,
                use_english_line_break,
                apply_layout,
            )
        source = saved[1]
        chinese_target = (
            getattr(getattr(typesetter, "translation_config", None), "lang_out", "")
            .lower()
            .startswith("zh")
        )
        if (
            chinese_target
            and id(paragraph) in atomic_names
            and not consistent_label_translation(source.unicode, paragraph.unicode)
        ):
            if apply_layout:
                restore_source(paragraph, source)
                logger.warning(
                    "Table label kept unchanged on page %s: partial name translation",
                    page.page_number + 1,
                )
            return 1.0, None
        # Fixed tables never use the engine's paragraph-space expansion. Keep
        # the original text if a translation cannot fit at a readable scale.
        paragraph.box = copy.copy(source.box)
        alignment, anchor = alignments[id(paragraph)]
        layout_box = alignment_box(paragraph.box, alignment, anchor)
        if id(paragraph) in label_anchors:
            layout_box = paragraph.box
        row_style = row_styles.get(id(paragraph))
        if row_style:
            layout_box = copy.copy(layout_box)
            layout_box.y2 = min(layout_box.y2, row_style[0])
        units = measure_formula_units(units)
        failures = []
        for step in range(7):
            scale = 1 - step * 0.05
            if (
                apply_layout
                and row_style
                and row_style[1] is not None
                and scale > row_scales.get(row_style[1], 1) + 1e-8
            ):
                continue
            if not units:
                failures.append("no typesetting units")
                break
            laid_out, fits = typesetter._layout_typesetting_units(
                units, layout_box, scale, 1.0, paragraph, use_english_line_break
            )
            reason = "native layout" if not fits else None
            if fits and id(paragraph) not in label_anchors:
                laid_out = balanced_cell_layout(
                    units,
                    laid_out,
                    layout_box,
                    scale,
                    lambda line, box: typesetter._layout_typesetting_units(
                        line, box, scale, 1.0, paragraph, use_english_line_break
                    ),
                    alignment=alignment,
                )
            if fits and id(paragraph) in label_anchors:
                laid_out = anchor_label_units(laid_out, label_anchors[id(paragraph)])
                fits = bool(laid_out)
                if not fits:
                    reason = "label anchor"
            if fits and id(paragraph) not in label_anchors:
                laid_out = contain_cell_layout(laid_out, paragraph.box)
            # Upstream permits hanging punctuation and only checks the baseline
            # vertically. Validate final glyph bounds as well as its fit flag.
            box = paragraph.box
            bounded = all(
                unit.box.x >= box.x - 0.05
                and unit.box.x2 <= box.x2 + 0.05
                and unit.box.y >= box.y - 0.05
                and unit.box.y2 <= box.y2 + 0.05
                for unit in laid_out
            )
            if fits and not bounded:
                reason = "unit bounds"
            fits = fits and bounded
            if fits and id(paragraph) in wrapped:
                fits = keeps_identifier_words(laid_out)
                if not fits:
                    reason = "identifier word break"
            if fits and id(paragraph) in paragraph_images:
                fits = not any(
                    overlaps(rect(unit.box), image)
                    for unit in laid_out
                    for image in paragraph_images[id(paragraph)]
                )
                if not fits:
                    reason = "image obstacle"
            if fits and id(paragraph) in paragraph_text_obstacles:
                peers, tolerance = paragraph_text_obstacles[id(paragraph)]
                fits = not any(
                    overlaps(rect(unit.box), peer, tolerance=tolerance)
                    for unit in laid_out
                    for peer in peers
                )
                if not fits:
                    reason = "text obstacle"
            if fits:
                # Formula unit boxes can understate the emitted source glyphs.
                # Validate the actual render before committing a replacement.
                fits = all(
                    char.box.x >= box.x - 0.05
                    and char.box.x2 <= box.x2 + 0.05
                    and char.box.y >= box.y - 0.05
                    and char.box.y2 <= box.y2 + 0.05
                    for unit in laid_out
                    for char in unit.render()[0]
                )
                if not fits:
                    reason = "rendered glyph bounds"
            if fits:
                if not apply_layout and row_style and row_style[1] is not None:
                    row_scales[row_style[1]] = min(
                        scale, row_scales.get(row_style[1], 1)
                    )
                if apply_layout:
                    paragraph.scale = scale
                    paragraph.pdf_paragraph_composition = []
                    for unit in laid_out:
                        chars, curves, forms = unit.render()
                        paragraph.pdf_paragraph_composition.extend(
                            PdfParagraphComposition(pdf_character=char)
                            for char in chars
                        )
                        page.pdf_curve.extend(curves)
                        page.pdf_form.extend(forms)
                return scale, laid_out
            failures.append(f"{scale:.2f}:{reason}")
        if apply_layout:
            restore_source(paragraph, source)
            logger.warning(
                "Table text kept unchanged on page %s [%s]: translation does not fit (%s)",
                page.page_number + 1,
                source.unicode[:100],
                ", ".join(failures),
            )
        return 1.0, None

    def restore_source(paragraph, source, passthrough=False):
        chars = [
            snapshot_character(c.pdf_character)
            for c in source.pdf_paragraph_composition
        ]
        if passthrough:
            # The 0.6.2 raw-character input branch reads a missing paragraph
            # field. Native line passthrough retains the same glyphs safely.
            paragraph.pdf_paragraph_composition = [
                PdfParagraphComposition(
                    pdf_line=PdfLine(box=copy.copy(source.box), pdf_character=chars)
                )
            ]
        else:
            paragraph.pdf_paragraph_composition = [
                PdfParagraphComposition(pdf_character=c) for c in chars
            ]
        paragraph.unicode = source.unicode
        paragraph.scale = 1.0

    def llm_page(translator, page, executor, *args, **kwargs):
        return process_page_in_table_batches(
            original_llm_page, translator, page, executor, *args, **kwargs
        )

    def post_translate(
        translator, paragraph, tracker, translate_input, translated_text
    ):
        chinese_target = (
            getattr(getattr(translator, "translation_config", None), "lang_out", "")
            .lower()
            .startswith("zh")
        )
        if id(paragraph) in atomic_names and chinese_target:
            translated_text = atomic_label_translation(
                originals[id(paragraph)][1].unicode, translated_text
            )
        saved = originals.get(id(paragraph))
        if saved and (
            same_table_content(saved[1].unicode, translated_text)
            or (
                isinstance(translate_input, str)
                and same_table_content(translate_input, translated_text)
            )
        ):
            restore_source(paragraph, saved[1], passthrough=True)
            return False
        return original_post(
            translator, paragraph, tracker, translate_input, translated_text
        )

    ParagraphFinder.process_page = process_page
    ParagraphFinder.process = process
    Typesetting._find_optimal_scale_and_layout = fit
    ILTranslatorLLMOnly.process_page = llm_page
    ILTranslator.post_translate_paragraph = post_translate

    def restore():
        ParagraphFinder.process_page = original_page
        ParagraphFinder.process = original_process
        Typesetting._find_optimal_scale_and_layout = original_fit
        ILTranslatorLLMOnly.process_page = original_llm_page
        ILTranslator.post_translate_paragraph = original_post

    return restore
