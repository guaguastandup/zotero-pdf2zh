import json
import os
import re
from statistics import median

import fitz


TEXT_TYPES = {"text", "paragraph", "para", "list", "list_item"}
TITLE_TYPES = {"title", "heading", "section_title"}
FIGURE_TYPES = {"image", "figure", "fig", "chart", "plot", "diagram"}
TABLE_TYPES = {"table"}
EQUATION_TYPES = {"equation", "interline_equation", "inline_equation", "formula"}
ALGORITHM_TYPES = {"algorithm"}
CODE_TYPES = {"code"}
AUXILIARY_TYPES = {
    "header",
    "footer",
    "page_header",
    "page_footer",
    "page_number",
    "aside_text",
    "page_aside_text",
    "page_footnote",
    "ref_text",
}
DEFAULT_PARAGRAPH_MIN_CHARS = 200
DEFAULT_CONTEXT_RADIUS = 2
MEDIA_NUMBER_RE = r"(?:S\s*)?\d+[A-Za-z]?(?:[.-]\d+)?[A-Za-z]?"
MEDIA_REFERENCE_RE = re.compile(
    rf"""
    (?<![A-Za-z])
    (?P<prefix>(?:Extended\s+Data|Supplementary|Supplemental|Suppl\.?|SI)\s+)?
    (?P<kind>
        Figures?|Figs?\.?|图|
        Tables?|Tabs?\.?|表|
        Equations?|Eqs?\.?|Eqns?\.?|Eqn\.?|Formulae?|Formulas?|公式|式|
        Algorithms?|Algs?\.?|算法
    )
    \s*\(?\s*(?P<number>{MEDIA_NUMBER_RE})
    """,
    re.I | re.X,
)
METADATA_PATTERNS = [
    r"^https?://",
    r"^doi\b",
    r"^received:",
    r"^accepted:",
    r"^published online:",
    r"^open access$",
    r"^check for updates$",
    r"^article$",
    r"^nature\b",
]


def build_doc_ir(pdf_path, mineru_dir, include_short_paragraphs=False):
    content_path = find_mineru_file(mineru_dir, prefer_v2=True)
    if not content_path:
        raise ValueError("MinerU content_list JSON not found")

    with open(content_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)
    if isinstance(raw_items, dict):
        raw_items = raw_items.get("content") or raw_items.get("pages") or raw_items.get("items") or []
    if not isinstance(raw_items, list):
        raise ValueError("MinerU content_list JSON has unsupported shape")

    with fitz.open(pdf_path) as pdf_doc:
        page_sizes = [{"width": page.rect.width, "height": page.rect.height} for page in pdf_doc]

    blocks = []
    for index, item in enumerate(flatten_content_items(raw_items)):
        block = normalize_block(
            item,
            index,
            page_sizes,
            mineru_dir,
            include_short_paragraphs=include_short_paragraphs,
        )
        if not block:
            continue
        blocks.append(block)

    blocks.sort(key=reading_order_key)
    blocks = merge_chart_subfigure_groups(blocks, pdf_path, mineru_dir)
    pages = build_pages(page_sizes, blocks)
    assign_sections(blocks)
    sections = build_sections(blocks)
    annotate_block_positions(blocks, sections)
    merge_nearby_chart_fragments_into_labeled_figures(blocks, pdf_path, mineru_dir)
    suppress_redundant_figure_fragments(blocks)
    infer_missing_media_labels(blocks)
    annotate_paragraph_media_references(blocks)
    media_ref_index = build_media_ref_index(blocks)

    title = first_title(blocks) or os.path.splitext(os.path.basename(pdf_path))[0]
    abstract = infer_abstract(blocks)
    return {
        "title": title,
        "abstract": abstract,
        "sourcePdf": pdf_path,
        "mineruDir": mineru_dir,
        "contentListPath": content_path,
        "pages": pages,
        "sections": sections,
        "mediaRefIndex": media_ref_index,
        "blocks": blocks,
    }


def apply_skip_last_pages(doc_ir, skip_last_pages=0):
    try:
        skip_count = max(0, int(skip_last_pages or 0))
    except (TypeError, ValueError):
        skip_count = 0
    if skip_count <= 0:
        doc_ir["skipLastPages"] = 0
        return doc_ir

    pages = doc_ir.get("pages") or []
    total_pages = len(pages) or max((int(block.get("page") or 0) for block in doc_ir.get("blocks") or []), default=0)
    active_page_end = max(0, total_pages - skip_count)
    doc_ir["skipLastPages"] = skip_count
    doc_ir["activePageEnd"] = active_page_end

    for page in pages:
        try:
            page_number = int(page.get("number") or 0)
        except (TypeError, ValueError):
            page_number = 0
        page["skippedBySkipLastPages"] = page_number > active_page_end

    for block in doc_ir.get("blocks") or []:
        try:
            page_number = int(block.get("page") or 0)
        except (TypeError, ValueError):
            page_number = 0
        if page_number > active_page_end:
            block["skimEligible"] = False
            block["skipForSkim"] = True
            block["skipForTranslation"] = True
    return doc_ir


def find_mineru_file(root, prefer_v2=True):
    candidates = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            low = name.lower()
            if low.endswith("_content_list_v2.json") or low == "content_list_v2.json":
                candidates.append((0, os.path.join(dirpath, name)))
            elif low.endswith("_content_list.json") or low == "content_list.json":
                candidates.append((1, os.path.join(dirpath, name)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0] if prefer_v2 else (0 if item[0] == 1 else 1))
    return candidates[0][1]


def flatten_content_items(items):
    for page_index, item in enumerate(items):
        if isinstance(item, list):
            for child in item:
                if isinstance(child, dict):
                    child = child.copy()
                    child.setdefault("page_idx", page_index)
                    yield child
            continue
        if not isinstance(item, dict):
            continue
        if "blocks" in item and isinstance(item["blocks"], list):
            page_idx = extract_page_index(item)
            for child in item["blocks"]:
                if isinstance(child, dict):
                    child = child.copy()
                    child.setdefault("page_idx", page_idx)
                    yield child
        else:
            yield item


def normalize_block(item, index, page_sizes, mineru_dir, include_short_paragraphs=False):
    page_idx = extract_page_index(item)
    if page_idx < 0 or page_idx >= len(page_sizes):
        page_idx = max(0, min(page_idx, len(page_sizes) - 1)) if page_sizes else 0
    page_size = page_sizes[page_idx] if page_sizes else {"width": 1000, "height": 1000}
    raw_type = str(item.get("type", item.get("category", item.get("block_type", "")))).strip()
    block_type = normalize_type(raw_type, item)
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    if content:
        preformatted_text = extract_preformatted_text(item, block_type, content)
        text = clean_text(preformatted_text or extract_structured_content_text(content))
        caption = clean_text(extract_structured_caption(content))
        footnote = clean_text(extract_structured_footnote(content))
        table_body = clean_text(extract_structured_table(content))
        latex = clean_text(extract_structured_equation(content))
        asset_path = resolve_asset_path(mineru_dir, extract_structured_asset_path(content))
    else:
        preformatted_text = extract_preformatted_text(item, block_type, content)
        text = clean_text(preformatted_text or extract_text(item, block_type))
        caption = clean_text(extract_caption(item))
        footnote = clean_text(extract_footnote(item))
        latex = clean_text(extract_first(item, ["latex", "latex_text", "formula", "equation", "text_format"]))
        table_body = clean_text(extract_first(item, ["table_body", "table_html", "html", "table_text"]))
        asset_path = resolve_asset_path(mineru_dir, extract_first(item, [
            "img_path", "image_path", "table_img_path", "figure_path", "path",
        ]))

    has_content = text or caption or table_body or latex or asset_path
    if not has_content:
        return None

    bbox = normalize_bbox(item.get("bbox") or item.get("poly") or item.get("box"), page_size)
    block_id = f"{prefix_for_type(block_type)}_{index + 1:04d}"
    block = {
        "id": block_id,
        "type": block_type,
        "rawType": raw_type,
        "page": page_idx + 1,
        "pageWidth": page_size.get("width"),
        "pageHeight": page_size.get("height"),
        "bbox": bbox,
        "column": "single",
        "sectionId": "sec_default",
        "text": text,
        "caption": caption,
        "footnote": footnote,
        "latex": latex,
        "tableBody": table_body,
        "assetPath": asset_path,
        "preformattedText": clean_preformatted_text(preformatted_text),
        "textLevel": item.get("text_level", item.get("level", content.get("level") if content else None)),
        "skimEligible": block_type in {"paragraph", "figure", "table", "equation", "algorithm"},
        "contextEligible": block_type == "paragraph",
        "source": item,
    }
    if block_type == "title":
        block["skimEligible"] = False
        block["contextEligible"] = False
    if block_type == "paragraph" and len(text) < 20:
        block["skimEligible"] = False
    if block_type == "paragraph" and is_metadata_paragraph(text):
        block["skimEligible"] = False
        block["contextEligible"] = False
    if block_type == "paragraph" and is_author_list_paragraph(text):
        block["skimEligible"] = False
        block["contextEligible"] = False
    if not include_short_paragraphs and block_type == "paragraph" and len(text) < paragraph_min_chars():
        block["skimEligible"] = False
    if block_type == "figure" and is_tiny_unlabeled_visual(block):
        block["skimEligible"] = False
    return block


def paragraph_min_chars():
    try:
        return max(0, int(os.getenv("SKIM_PARAGRAPH_MIN_CHARS", str(DEFAULT_PARAGRAPH_MIN_CHARS))))
    except ValueError:
        return DEFAULT_PARAGRAPH_MIN_CHARS


def context_radius():
    try:
        return max(0, int(os.getenv("SKIM_CONTEXT_RADIUS", str(DEFAULT_CONTEXT_RADIUS))))
    except ValueError:
        return DEFAULT_CONTEXT_RADIUS


def is_metadata_paragraph(text):
    normalized = clean_text(text).lower()
    if not normalized:
        return True
    for pattern in METADATA_PATTERNS:
        if re.match(pattern, normalized, re.I):
            return True
    return False


def is_author_list_paragraph(text):
    normalized = clean_text(text)
    if len(normalized) > 500 or "@" in normalized:
        return False
    if "✉" in normalized:
        return True
    comma_count = normalized.count(",")
    digit_count = len(re.findall(r"\d", normalized))
    capitalized_names = len(re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", normalized))
    return comma_count >= 8 and digit_count >= 8 and capitalized_names >= 5


def is_tiny_unlabeled_visual(block):
    bbox = block.get("bbox") or [0, 0, 0, 0]
    width = max(0, float(bbox[2]) - float(bbox[0]))
    height = max(0, float(bbox[3]) - float(bbox[1]))
    has_label = bool(block.get("text") or block.get("caption") or block.get("footnote"))
    return not has_label and (width < 40 or height < 25)


def merge_chart_subfigure_groups(blocks, pdf_path, mineru_dir):
    charts = [b for b in blocks if is_chart_figure(b)]
    if not charts:
        return blocks

    used = set()
    merged_blocks = []
    for chart in charts:
        if chart["id"] in used:
            continue
        label = chart.get("displayLabel") or infer_media_label(chart)
        if not label:
            continue
        chart["displayLabel"] = label
        label_number = media_label_number(label)
        if not label_number:
            continue
        group = [
            candidate for candidate in charts
            if candidate["id"] not in used
            and candidate["page"] == chart["page"]
            and chart_same_row(candidate, chart)
            and chart_label_compatible(candidate, label_number)
        ]
        if len(group) < 2:
            continue
        group.sort(key=lambda b: (b["bbox"][0], b["bbox"][1]))
        merged = build_merged_chart_block(group, chart, pdf_path, mineru_dir)
        if not merged:
            continue
        used.update(b["id"] for b in group)
        merged_blocks.append(merged)

    if not used:
        return blocks

    kept = [b for b in blocks if b["id"] not in used]
    kept.extend(merged_blocks)
    kept.sort(key=reading_order_key)
    return kept


def is_chart_figure(block):
    raw_type = str(block.get("rawType") or "").lower()
    return block.get("type") == "figure" and ("chart" in raw_type or "plot" in raw_type or "diagram" in raw_type)


def chart_same_row(candidate, anchor):
    candidate_bbox = candidate.get("bbox") or [0, 0, 0, 0]
    anchor_bbox = anchor.get("bbox") or [0, 0, 0, 0]
    overlap = vertical_overlap_ratio(candidate_bbox, anchor_bbox)
    center_delta = abs(bbox_center_y(candidate_bbox) - bbox_center_y(anchor_bbox))
    return overlap > 0.35 or center_delta < max(45, bbox_height(anchor_bbox) * 0.75)


def vertical_overlap_ratio(a, b):
    top = max(a[1], b[1])
    bottom = min(a[3], b[3])
    overlap = max(0.0, bottom - top)
    smaller = max(1.0, min(bbox_height(a), bbox_height(b)))
    return overlap / smaller


def chart_label_compatible(block, label_number):
    block_number = media_label_number(block.get("displayLabel") or "")
    return not block_number or parent_media_number(block_number) == parent_media_number(label_number)


def media_label_number(label):
    refs = matching_media_references(label or "", "figure")
    if refs:
        return refs[0]["number"]
    return ""


def build_merged_chart_block(group, labeled_chart, pdf_path, mineru_dir):
    bbox = union_bbox([b["bbox"] for b in group])
    asset_path = crop_merged_chart_asset(pdf_path, mineru_dir, labeled_chart, bbox)
    if not asset_path:
        return None

    label = labeled_chart.get("displayLabel") or infer_media_label(labeled_chart)
    caption = merged_chart_caption(group, labeled_chart)
    table_body = merged_chart_data(group)
    merged = labeled_chart.copy()
    merged.update({
        "id": labeled_chart["id"],
        "type": "figure",
        "rawType": "chart_group",
        "bbox": bbox,
        "text": "",
        "caption": caption,
        "tableBody": table_body,
        "assetPath": asset_path,
        "displayLabel": label,
        "skimEligible": True,
        "source": {
            "type": "chart_group",
            "mergedFrom": [b["id"] for b in group],
        },
    })
    return merged


def union_bbox(boxes):
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def crop_merged_chart_asset(pdf_path, mineru_dir, labeled_chart, bbox):
    try:
        page_number = int(labeled_chart.get("page") or 1)
    except (TypeError, ValueError):
        page_number = 1
    output_dir = os.path.join(mineru_dir, "skim_generated")
    os.makedirs(output_dir, exist_ok=True)
    safe_label = re.sub(r"[^A-Za-z0-9]+", "_", labeled_chart.get("displayLabel") or labeled_chart["id"]).strip("_")
    bbox_key = "_".join(str(int(round(value))) for value in bbox)
    output_path = os.path.join(output_dir, f"{safe_label or labeled_chart['id']}_page_{page_number}_{bbox_key}.png")
    if os.path.exists(output_path):
        return output_path

    try:
        with fitz.open(pdf_path) as doc:
            page = doc[page_number - 1]
            page_rect = page.rect
            padding_x = 8
            padding_top = 5
            padding_bottom = 58
            clip = fitz.Rect(
                max(page_rect.x0, bbox[0] - padding_x),
                max(page_rect.y0, bbox[1] - padding_top),
                min(page_rect.x1, bbox[2] + padding_x),
                min(page_rect.y1, bbox[3] + padding_bottom),
            )
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
            pix.save(output_path)
        return output_path
    except Exception:
        return ""


def merged_chart_caption(group, labeled_chart):
    full_caption = ""
    subcaptions = []
    for block in group:
        caption = clean_text(block.get("caption") or "")
        if not caption:
            continue
        subcaption, full = split_chart_caption(caption)
        if subcaption:
            subcaptions.append(subcaption)
        if full and not full_caption:
            full_caption = full
    if not full_caption:
        full_caption = clean_text(labeled_chart.get("caption") or "")
    if subcaptions:
        return clean_text(f"{full_caption} Subfigures: {'; '.join(subcaptions)}")
    return full_caption


def split_chart_caption(caption):
    match = re.search(r"\b(?:Figure|Fig\.?)\s*\d", caption, re.I)
    if not match:
        return caption, ""
    subcaption = clean_text(caption[:match.start()])
    full_caption = clean_text(caption[match.start():])
    return subcaption, full_caption


def merged_chart_data(group):
    parts = []
    for block in group:
        label = clean_text(block.get("caption") or block.get("displayLabel") or block["id"])
        data = clean_text(block.get("tableBody") or block.get("text") or "")
        if data:
            parts.append(f"{label}\n{data}")
    return "\n\n".join(parts)


def merge_nearby_chart_fragments_into_labeled_figures(blocks, pdf_path, mineru_dir):
    labeled = [
        block for block in blocks
        if block.get("type") == "figure"
        and block.get("displayLabel")
        and has_explicit_media_label(block)
    ]
    if not labeled:
        return

    for target in labeled:
        if "Fig" not in (target.get("displayLabel") or ""):
            continue
        fragments = [
            block for block in blocks
            if block is not target
            and is_chart_figure(block)
            and block.get("page") == target.get("page")
            and not has_explicit_media_label(block)
            and chart_fragment_near_target(block, target)
        ]
        if not fragments:
            continue
        group = fragments + [target]
        bbox = union_bbox([block["bbox"] for block in group])
        target["bbox"] = bbox
        target["assetPath"] = crop_merged_chart_asset(pdf_path, mineru_dir, target, bbox) or target.get("assetPath", "")
        data_parts = [target.get("tableBody") or target.get("text") or ""]
        data_parts.extend(block.get("tableBody") or block.get("text") or "" for block in fragments)
        target["tableBody"] = "\n\n".join(clean_text(part) for part in data_parts if clean_text(part))
        merged_ids = list(target.get("mergedFrom") or [])
        merged_ids.extend(block["id"] for block in fragments)
        target["mergedFrom"] = list(dict.fromkeys(merged_ids))
        target["rawType"] = "chart_group"
        for fragment in fragments:
            fragment["skimEligible"] = False
            fragment["mergedInto"] = target["id"]
            fragment["displayLabel"] = ""
            fragment["suppressMediaLabel"] = True


def has_explicit_media_label(block):
    label_text = "\n".join([
        block.get("caption") or "",
        block.get("displayLabel") or "",
        block.get("text") or "",
    ])
    return bool(matching_media_references(label_text[:500], block.get("type") or ""))


def chart_fragment_near_target(fragment, target):
    fragment_box = fragment.get("bbox") or [0, 0, 0, 0]
    target_box = target.get("bbox") or [0, 0, 0, 0]
    if horizontal_overlap_ratio(fragment_box, target_box) < 0.15:
        return False
    gap = vertical_gap(fragment_box, target_box)
    max_gap = max(80, bbox_height(target_box) * 0.75, bbox_height(fragment_box) * 0.75)
    return gap <= max_gap


def horizontal_overlap_ratio(a, b):
    left = max(a[0], b[0])
    right = min(a[2], b[2])
    overlap = max(0.0, right - left)
    smaller = max(1.0, min(bbox_width(a), bbox_width(b)))
    return overlap / smaller


def vertical_gap(a, b):
    if a[3] < b[1]:
        return b[1] - a[3]
    if b[3] < a[1]:
        return a[1] - b[3]
    return 0.0


def extract_page_index(item):
    if "page_idx" in item:
        return normalize_page_index(item.get("page_idx"), zero_based=True)
    if "page_id" in item:
        return normalize_page_index(item.get("page_id"), zero_based=True)
    if "page" in item:
        return normalize_page_index(item.get("page"), zero_based=False)
    return 0


def normalize_page_index(value, zero_based=True):
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return 0
    if zero_based:
        return idx
    return max(0, idx - 1)


def normalize_type(raw_type, item):
    low = raw_type.lower()
    subtype = str(item.get("sub_type") or "").lower()
    if low in AUXILIARY_TYPES or subtype == "ref_text":
        return "other"
    if low in TITLE_TYPES or item.get("text_level") is not None or item.get("level") is not None:
        return "title"
    if low in FIGURE_TYPES or "image" in low or "figure" in low or "chart" in low or "plot" in low:
        return "figure"
    if low in TABLE_TYPES or "table" in low:
        return "table"
    if low in EQUATION_TYPES or "equation" in low or "formula" in low:
        return "equation"
    if low in ALGORITHM_TYPES or (low == "code" and subtype == "algorithm"):
        return "algorithm"
    if low in CODE_TYPES:
        return "code"
    if low in TEXT_TYPES or "text" in low or "para" in low:
        return "paragraph"
    return "paragraph" if extract_first(item, ["text"]) else "other"


def extract_text(item, block_type):
    if block_type == "table":
        return extract_first(item, ["text", "table_caption", "table_body", "table_html", "html"])
    if block_type == "equation":
        return extract_first(item, ["text", "latex", "formula", "latex_text", "equation"])
    if block_type in {"algorithm", "code"}:
        return extract_first(item, ["text", "algorithm_content", "algorithm_body", "code_body", "code"])
    return extract_first(item, ["text", "content", "paragraph", "markdown", "md"])


def extract_structured_content_text(content):
    keys = ["paragraph_content", "title_content", "list_items", "algorithm_content", "code_content", "text", "content"]
    return "\n".join(extract_text_fragments(content.get(key)) for key in keys if content.get(key))


def extract_structured_caption(content):
    return "\n".join(
        extract_text_fragments(content.get(key))
        for key in ["image_caption", "table_caption", "chart_caption", "algorithm_caption", "code_caption", "caption"]
        if content.get(key)
    )


def extract_structured_footnote(content):
    return "\n".join(
        extract_text_fragments(content.get(key))
        for key in ["image_footnote", "table_footnote", "chart_footnote", "algorithm_footnote", "code_footnote", "footnote"]
        if content.get(key)
    )


def extract_structured_table(content):
    for key in ["table_body", "table_html", "html", "table_text"]:
        value = content.get(key)
        if value:
            return extract_text_fragments(value)
    return ""


def extract_structured_equation(content):
    for key in ["latex", "latex_text", "formula", "equation", "math_content", "text_format"]:
        value = content.get(key)
        if value:
            return extract_text_fragments(value)
    return ""


def extract_preformatted_text(item, block_type, content=None):
    if block_type not in {"algorithm", "code"}:
        return ""
    content = content if isinstance(content, dict) else {}
    for value in [
        content.get("algorithm_content"),
        content.get("code_content"),
        item.get("algorithm_content"),
        item.get("code_content"),
        item.get("algorithm_body"),
        item.get("code_body"),
        item.get("code"),
        item.get("text"),
    ]:
        extracted = extract_preformatted_fragments(value)
        if extracted.strip():
            return extracted
    return ""


def extract_preformatted_fragments(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(extract_preformatted_fragments(item) for item in value)
    if isinstance(value, dict):
        if "content" in value:
            return extract_preformatted_fragments(value.get("content"))
        if "text" in value:
            return extract_preformatted_fragments(value.get("text"))
        return "".join(extract_preformatted_fragments(v) for v in value.values())
    return str(value)


def clean_preformatted_text(text):
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+$", "", line) for line in text.split("\n")]
    compacted = []
    blank_count = 0
    for line in lines:
        if line.strip():
            blank_count = 0
            compacted.append(line)
            continue
        blank_count += 1
        if blank_count <= 1:
            compacted.append("")
    return "\n".join(compacted).strip()


def extract_structured_asset_path(content):
    for key in ["image_source", "table_source", "source"]:
        value = content.get(key)
        if isinstance(value, dict):
            for path_key in ["path", "img_path", "image_path"]:
                if value.get(path_key):
                    return str(value.get(path_key))
        elif value:
            return str(value)
    return ""


def extract_text_fragments(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(extract_text_fragments(item) for item in value)
    if isinstance(value, dict):
        if "content" in value:
            return extract_text_fragments(value.get("content"))
        if "text" in value:
            return extract_text_fragments(value.get("text"))
        return " ".join(extract_text_fragments(v) for v in value.values())
    return str(value)


def extract_caption(item):
    parts = []
    for key in ["image_caption", "figure_caption", "table_caption", "chart_caption", "algorithm_caption", "code_caption", "caption"]:
        value = item.get(key)
        if isinstance(value, list):
            parts.extend(str(v) for v in value if v)
        elif value:
            parts.append(str(value))
    return "\n".join(parts)


def extract_footnote(item):
    parts = []
    for key in ["image_footnote", "table_footnote", "chart_footnote", "algorithm_footnote", "code_footnote", "footnote"]:
        value = item.get(key)
        if isinstance(value, list):
            parts.extend(str(v) for v in value if v)
        elif value:
            parts.append(str(value))
    return "\n".join(parts)


def extract_first(item, keys):
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            value = "\n".join(str(v) for v in value if v)
        elif isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = str(value)
        if value.strip():
            return value
    return ""


def normalize_bbox(value, page_size):
    width = float(page_size.get("width") or 1000)
    height = float(page_size.get("height") or 1000)
    default = [0.0, 0.0, width, height]
    if not value:
        return default

    if isinstance(value, dict):
        coords = [
            value.get("x0", value.get("left", value.get("x", 0))),
            value.get("y0", value.get("top", value.get("y", 0))),
            value.get("x1", value.get("right", 0)),
            value.get("y1", value.get("bottom", 0)),
        ]
        if not coords[2] and value.get("width"):
            coords[2] = float(coords[0]) + float(value.get("width"))
        if not coords[3] and value.get("height"):
            coords[3] = float(coords[1]) + float(value.get("height"))
    else:
        coords = list(value)
        if len(coords) >= 8:
            xs = [float(coords[i]) for i in range(0, 8, 2)]
            ys = [float(coords[i]) for i in range(1, 8, 2)]
            coords = [min(xs), min(ys), max(xs), max(ys)]
        elif len(coords) < 4:
            return default
        else:
            coords = coords[:4]

    try:
        x0, y0, x1, y1 = [float(c) for c in coords]
    except (TypeError, ValueError):
        return default

    max_coord = max(abs(x0), abs(y0), abs(x1), abs(y1))
    if max_coord <= 1.5:
        x0, x1 = x0 * width, x1 * width
        y0, y1 = y0 * height, y1 * height
    elif max_coord <= 1000 and (width != 1000 or height != 1000):
        x0, x1 = x0 / 1000.0 * width, x1 / 1000.0 * width
        y0, y1 = y0 / 1000.0 * height, y1 / 1000.0 * height

    x0, x1 = sorted((max(0.0, x0), min(width, x1)))
    y0, y1 = sorted((max(0.0, y0), min(height, y1)))
    return [x0, y0, x1, y1]


def resolve_asset_path(root, path):
    if not path:
        return ""
    path = path.replace("\\", os.sep).replace("/", os.sep)
    if os.path.isabs(path) and os.path.exists(path):
        return path
    direct = os.path.abspath(os.path.join(root, path))
    if os.path.exists(direct):
        return direct
    basename = os.path.basename(path)
    if not basename:
        return ""
    for dirpath, _, filenames in os.walk(root):
        if basename in filenames:
            return os.path.join(dirpath, basename)
    return direct


def build_pages(page_sizes, blocks):
    pages = []
    by_page = {}
    for block in blocks:
        by_page.setdefault(block["page"], []).append(block)

    for index, size in enumerate(page_sizes):
        page_num = index + 1
        page_blocks = by_page.get(page_num, [])
        layout = detect_page_layout(size, page_blocks)
        for block in page_blocks:
            block["column"] = assign_column(block, size, layout)
        pages.append({
            "page": page_num,
            "width": size["width"],
            "height": size["height"],
            "layout": layout,
            "blockIds": [b["id"] for b in page_blocks],
        })
    return pages


def detect_page_layout(size, blocks):
    width = float(size["width"] or 1)
    layout_blocks = [
        b for b in blocks
        if b["type"] in {"paragraph", "title", "figure", "table", "equation"}
        and bbox_width(b["bbox"]) < width * 0.72
        and bbox_height(b["bbox"]) > 5
    ]
    if len(layout_blocks) < 4:
        return "single"

    centers = [bbox_center_x(b["bbox"]) for b in layout_blocks]
    left = [b for b in layout_blocks if bbox_center_x(b["bbox"]) < width * 0.48]
    right = [b for b in layout_blocks if bbox_center_x(b["bbox"]) > width * 0.52]
    left_text = [b for b in left if b["type"] in {"paragraph", "title"}]
    right_text = [b for b in right if b["type"] in {"paragraph", "title"}]
    if len(left) < 2 or len(right) < 2:
        return "single"
    if not left_text or not right_text:
        return "single"

    left_right_edge = median([b["bbox"][2] for b in left])
    right_left_edge = median([b["bbox"][0] for b in right])
    median_gap = right_left_edge - left_right_edge
    center_gap = median([c for c in centers if c > width * 0.52]) - median([c for c in centers if c < width * 0.48])
    if median_gap > width * 0.01 and center_gap > width * 0.25:
        return "double"
    return "single"


def assign_column(block, size, layout):
    width = float(size["width"] or 1)
    height = float(size["height"] or 1)
    if layout != "double":
        return "single"
    bbox = block["bbox"]
    center = width / 2
    spans_gutter = bbox[0] < center - width * 0.05 and bbox[2] > center + width * 0.05
    if spans_gutter and bbox_width(bbox) > width * 0.54:
        return "full"
    if bbox_width(bbox) > width * 0.82:
        return "full"
    return "left" if bbox_center_x(bbox) < center else "right"


def assign_sections(blocks):
    anchors = build_section_anchors(blocks)
    if not anchors:
        for block in blocks:
            block["sectionId"] = "sec_default"
            block["sectionPath"] = ["Introduction"]
            block["isSectionTitle"] = False
        return

    for block in blocks:
        if block["type"] == "title":
            anchor = next((item for item in anchors if item["blockId"] == block["id"]), None)
            if anchor:
                block["sectionId"] = anchor["id"]
                block["sectionLevel"] = anchor["level"]
                block["sectionPath"] = anchor["path"]
                block["isSectionTitle"] = True
                continue
            best = best_section_anchor_for_block(block, anchors)
            block["sectionId"] = best["id"] if best else "sec_default"
            block["sectionPath"] = best["path"] if best else ["Introduction"]
            block["isSectionTitle"] = False
            continue

        best = best_section_anchor_for_block(block, anchors)
        block["sectionId"] = best["id"] if best else "sec_default"
        block["sectionPath"] = best["path"] if best else ["Introduction"]
        block["isSectionTitle"] = False


def build_section_anchors(blocks):
    section_counter = 0
    stack = []
    anchors = []
    section_title_count = 0
    titles = [
        block for block in blocks
        if block.get("type") == "title" and block.get("text")
    ]
    for block in sorted(titles, key=visual_order_key):
        if is_non_section_title(block, section_title_count):
            continue
        section_title_count += 1
        section_counter += 1
        section_id = f"sec_{section_counter:03d}"
        level = infer_heading_level(block, stack)
        title = clean_text(block["text"])
        stack = [entry for entry in stack if entry["level"] < level]
        stack.append({"level": level, "title": title})
        anchors.append({
            "id": section_id,
            "blockId": block["id"],
            "title": title,
            "level": level,
            "path": section_path_from_stack(stack),
            "page": block.get("page") or 1,
            "column": block.get("column") or "single",
            "bbox": block.get("bbox") or [0, 0, 0, 0],
        })
    return anchors


def best_section_anchor_for_block(block, anchors):
    candidates = [
        anchor for anchor in anchors
        if anchor_precedes_block(anchor, block) and section_anchor_column_compatible(anchor, block)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda anchor: anchor_rank(anchor, block))


def anchor_precedes_block(anchor, block):
    block_page = block.get("page") or 1
    anchor_page = anchor.get("page") or 1
    if anchor_page < block_page:
        return True
    if anchor_page > block_page:
        return False
    anchor_bottom = (anchor.get("bbox") or [0, 0, 0, 0])[3]
    block_top = (block.get("bbox") or [0, 0, 0, 0])[1]
    return anchor_bottom <= block_top + 1


def section_anchor_column_compatible(anchor, block):
    anchor_col = anchor.get("column") or "single"
    block_col = block.get("column") or "single"
    if anchor_col in {"single", "full"} or block_col in {"single", "full"}:
        return True
    if anchor_col == block_col:
        return True
    if anchor_col == "left" and block_col == "right":
        return True
    return False


def anchor_rank(anchor, block):
    bbox = anchor.get("bbox") or [0, 0, 0, 0]
    anchor_col = anchor.get("column") or "single"
    block_col = block.get("column") or "single"
    same_page = int(anchor.get("page") or 1) == int(block.get("page") or 1)
    same_column = anchor_col == block_col or anchor_col in {"single", "full"} or block_col in {"single", "full"}
    column_score = 2 if same_column else (1 if not same_page else 0)
    return (anchor.get("page") or 1, column_score, bbox[1], bbox[0])


def visual_order_key(block):
    bbox = block.get("bbox") or [0, 0, 0, 0]
    return (block.get("page") or 1, bbox[1], bbox[0])


def is_non_section_title(block, section_counter):
    title = clean_text(block.get("text", ""))
    if not title:
        return True
    if title.lower() == "article":
        return True
    if title.lower() in {"input image", "inpainting results"}:
        return True
    if section_counter == 0 and block.get("page") == 1 and len(title) > 40:
        return True
    return False


def infer_heading_level(block, stack):
    text_level = block.get("textLevel")
    try:
        level = int(text_level)
        if level > 0:
            return min(level, 6)
    except (TypeError, ValueError):
        pass

    title = clean_text(block.get("text", "")).lower()
    if title in {"methods", "references", "data availability", "code availability", "additional information"}:
        return 1
    if stack and stack[-1]["title"].lower() == "methods":
        return 2
    return 1


def section_path_from_stack(stack):
    if not stack:
        return ["Introduction"]
    return [entry["title"] for entry in stack]


def build_sections(blocks):
    sections = {
        "sec_default": {
            "id": "sec_default",
            "title": "Document",
            "numberText": "",
            "page": 1,
            "blockIds": [],
            "paragraphIds": [],
            "figureIds": [],
            "tableIds": [],
            "equationIds": [],
            "algorithmIds": [],
        }
    }
    for block in blocks:
        if block["type"] == "title" and block.get("isSectionTitle"):
            sections[block["sectionId"]] = {
                "id": block["sectionId"],
                "title": block["text"][:200],
                "numberText": infer_section_number(block["text"]),
                "path": block.get("sectionPath") or [block["text"][:200]],
                "page": block["page"],
                "blockIds": [],
                "paragraphIds": [],
                "figureIds": [],
                "tableIds": [],
                "equationIds": [],
                "algorithmIds": [],
            }
        section = sections.setdefault(block["sectionId"], {
            "id": block["sectionId"],
            "title": "Introduction",
            "numberText": "",
            "path": block.get("sectionPath") or ["Introduction"],
            "page": block["page"],
            "blockIds": [],
            "paragraphIds": [],
            "figureIds": [],
            "tableIds": [],
            "equationIds": [],
            "algorithmIds": [],
        })
        section["blockIds"].append(block["id"])
        if block["type"] == "paragraph":
            section["paragraphIds"].append(block["id"])
        elif block["type"] == "figure":
            section["figureIds"].append(block["id"])
        elif block["type"] == "table":
            section["tableIds"].append(block["id"])
        elif block["type"] == "equation":
            section["equationIds"].append(block["id"])
        elif block["type"] == "algorithm":
            section["algorithmIds"].append(block["id"])
    return list(sections.values())


def annotate_block_positions(blocks, sections):
    section_map = {section["id"]: section for section in sections}
    paragraph_counts = {}
    for block in blocks:
        section = section_map.get(block.get("sectionId"), {})
        path = block.get("sectionPath") or section.get("path") or [section.get("title") or "Introduction"]
        block["sectionPath"] = path
        block["sectionTitle"] = path[-1] if path else "Introduction"
        block["sectionPathText"] = " > ".join(path)
        if block["type"] == "paragraph" and block.get("skimEligible"):
            paragraph_counts[block["sectionId"]] = paragraph_counts.get(block["sectionId"], 0) + 1
            block["paragraphIndex"] = paragraph_counts[block["sectionId"]]
            block["displayLabel"] = f"第{block['paragraphIndex']}段"
        elif block["type"] == "paragraph":
            block["paragraphIndex"] = None
            block["displayLabel"] = ""
        elif block["type"] in {"figure", "table", "equation", "algorithm"}:
            block["displayLabel"] = infer_media_label(block)


def suppress_redundant_figure_fragments(blocks):
    caption_pages = set()
    labeled_figure_pages = set()
    for block in blocks:
        if block["type"] == "paragraph" and re.search(r"\b(?:Extended\s+Data\s+)?(?:Fig\.?|Figure)\s*\d", block.get("text", ""), re.I):
            caption_pages.add(block["page"])
        if block["type"] == "figure" and block.get("displayLabel"):
            labeled_figure_pages.add(block["page"])

    for block in blocks:
        if block["type"] != "figure" or block.get("displayLabel"):
            continue
        text = clean_text(" ".join([block.get("caption") or "", block.get("text") or ""]))
        if block["page"] in caption_pages and len(text) < 180:
            block["skimEligible"] = False
        elif block["page"] in labeled_figure_pages and len(text) < 80:
            block["skimEligible"] = False


def infer_missing_media_labels(blocks):
    for block in blocks:
        if (
            block["type"] in {"figure", "table"}
            and not block.get("displayLabel")
            and not block.get("suppressMediaLabel")
        ):
            label = nearest_referenced_media_label(block, blocks)
            if label:
                block["displayLabel"] = label

    equation_index = 0
    for block in blocks:
        if block["type"] == "equation" and block.get("skimEligible"):
            if not block.get("displayLabel"):
                equation_index += 1
                block["displayLabel"] = f"Eq. {equation_index}"


def nearest_referenced_media_label(block, blocks):
    if block["type"] not in {"figure", "table", "algorithm"}:
        return ""
    best = None
    block_cx = bbox_center_x(block["bbox"])
    block_cy = bbox_center_y(block["bbox"])
    for paragraph in blocks:
        if paragraph["type"] != "paragraph" or paragraph["page"] != block["page"]:
            continue
        text = paragraph.get("text") or ""
        for ref in parse_media_references(text):
            if ref["type"] != block["type"]:
                continue
            score = abs(bbox_center_x(paragraph["bbox"]) - block_cx) * 2 + abs(bbox_center_y(paragraph["bbox"]) - block_cy)
            if paragraph.get("column") == block.get("column"):
                score -= 80
            if best is None or score < best[0]:
                best = (score, media_label_from_reference(ref))
    return best[1] if best else ""


def annotate_paragraph_media_references(blocks):
    for block in blocks:
        if block["type"] != "paragraph":
            continue
        refs = parse_media_references(block.get("text") or "")
        block["mediaRefs"] = dedupe_media_refs(refs)


def build_media_ref_index(blocks):
    index = {}
    for block in blocks:
        if block["type"] != "paragraph" or not is_context_text_block(block):
            continue
        for ref in block.get("mediaRefs") or []:
            for key in media_reference_lookup_keys(ref):
                block_ids = index.setdefault(key, [])
                if block["id"] not in block_ids:
                    block_ids.append(block["id"])
    return index


def document_brief(doc_ir, max_chars=5000):
    section_lines = "\n".join(f"- {s['title']}" for s in doc_ir["sections"][:30] if s["title"])
    abstract = clamp_text(doc_ir.get("abstract") or "", 1800)
    body = "\n".join(
        b["text"] for b in doc_ir["blocks"]
        if is_reading_text_block(b) and not is_skippable_section(doc_ir, b["sectionId"])
    )
    return clamp_text(
        "\n\n".join([
            f"论文标题: {doc_ir.get('title') or ''}",
            f"摘要: {abstract or '未识别'}",
            f"章节结构:\n{section_lines or '未识别'}",
            f"正文摘录:\n{clamp_text(body, 2200)}",
        ]),
        max_chars,
    )


def section_position(doc_ir, section_id):
    sections = doc_ir.get("sections") or []
    section = section_by_id(doc_ir, section_id)
    index = next((i for i, s in enumerate(sections) if s["id"] == section_id), 0)
    return "\n".join([
        "对象层级: 正文章节",
        f"章节位置: {index + 1}/{len(sections)}",
        f"章节编号: {section.get('numberText') or '无'}",
        f"章节标题: {section.get('title') or 'Document'}",
        f"章节路径: {' > '.join(section.get('path') or [section.get('title') or 'Document'])}",
        f"章节聚合规模: {len(section.get('paragraphIds') or [])} 段, {len(section.get('figureIds') or [])} 图, {len(section.get('tableIds') or [])} 表, {len(section.get('algorithmIds') or [])} 算法",
    ])


def block_position_label(block):
    if block.get("type") == "paragraph":
        label = block.get("displayLabel") or "段落"
    else:
        label = block.get("displayLabel") or {
            "figure": "图",
            "table": "表",
            "equation": "式",
            "algorithm": "算法",
        }.get(block.get("type"), "对象")
    path = block.get("sectionPathText") or block.get("sectionTitle") or "Introduction"
    return f"{path} / {label}"


def block_context(doc_ir, block, radius=None):
    radius = context_radius() if radius is None else max(0, int(radius or 0))
    section = section_by_id(doc_ir, block.get("sectionId"))
    paragraph_ids = context_text_ids(doc_ir, section)
    if block["id"] not in paragraph_ids:
        return nearest_paragraph_texts(doc_ir, block, 3)
    index = paragraph_ids.index(block["id"])
    by_id = {b["id"]: b for b in doc_ir["blocks"]}
    start = bounded_context_index(paragraph_ids, by_id, index, radius, -1)
    end = bounded_context_index(paragraph_ids, by_id, index, radius, 1)
    ids = paragraph_ids[start:index] + paragraph_ids[index + 1:end + 1]
    return [by_id[i]["text"] for i in ids if i in by_id and by_id[i].get("text")]


def bounded_context_index(paragraph_ids, by_id, anchor_index, radius, direction):
    if radius <= 0:
        return anchor_index
    counted = 0
    selected = anchor_index
    index = anchor_index + direction
    while 0 <= index < len(paragraph_ids):
        block = by_id.get(paragraph_ids[index])
        if block and is_reading_text_block(block):
            counted += 1
        selected = index
        if counted >= radius:
            break
        index += direction
    return selected


def media_context(doc_ir, block):
    target_refs = media_reference_signatures(block)
    matches = []
    if target_refs:
        matches = referenced_paragraphs(doc_ir, target_refs)
        if not matches:
            for paragraph in doc_ir["blocks"]:
                if not is_context_text_block(paragraph):
                    continue
                if paragraph_mentions_media(paragraph["text"], target_refs):
                    matches.append(paragraph)
    if matches:
        by_id = {}
        for match in matches:
            for text in block_context(doc_ir, match, radius=1):
                by_id[text] = text
            by_id[match["text"]] = match["text"]
        return "\n\n".join(by_id.values())
    return "\n\n".join(nearest_paragraph_texts(doc_ir, block, 3))


def build_media_reference_patterns(block):
    patterns = []
    for signature in media_reference_signatures(block):
        namespace, block_type, number = signature
        kind_words = media_kind_words(block_type, namespace)
        for word in kind_words:
            patterns.append(re.compile(rf"\b{word}\s*\(?\s*{re.escape(number)}\)?\b", re.I))
    return patterns


def referenced_paragraphs(doc_ir, target_refs):
    ref_index = doc_ir.get("mediaRefIndex") or {}
    if not ref_index:
        return []
    by_id = {b["id"]: b for b in doc_ir.get("blocks") or []}
    seen = set()
    paragraphs = []
    for signature in target_refs:
        for block_id in ref_index.get(media_signature_key(signature), []):
            if block_id in seen:
                continue
            block = by_id.get(block_id)
            if block and is_context_text_block(block):
                seen.add(block_id)
                paragraphs.append(block)
    return paragraphs


def media_kind_words(block_type, namespace="main"):
    if block_type == "figure":
        if namespace == "extended":
            return [r"Extended\s+Data\s+(?:Figures?|Figs?\.?)"]
        if namespace == "supplementary":
            return [r"(?:Supplementary|Supplemental|Suppl\.?|SI)\s+(?:Figures?|Figs?\.?)", r"(?:Figures?|Figs?\.?)\s*S"]
        return [r"(?<!Data\s)(?<!Supplementary\s)(?<!Supplemental\s)(?<!Suppl\.\s)(?<!SI\s)(?:Figures?|Figs?\.?)", "图"]
    if block_type == "table":
        if namespace == "extended":
            return [r"Extended\s+Data\s+Tables?"]
        if namespace == "supplementary":
            return [r"(?:Supplementary|Supplemental|Suppl\.?|SI)\s+(?:Tables?|Tabs?\.?)", r"(?:Tables?|Tabs?\.?)\s*S"]
        return [r"(?<!Data\s)(?<!Supplementary\s)(?<!Supplemental\s)(?<!Suppl\.\s)(?<!SI\s)(?:Tables?|Tabs?\.?)", "表"]
    if block_type == "equation":
        return [r"(?:Equations?|Eqs?\.?|Eqns?\.?|Eqn\.?|Formulae?|Formulas?)", "式", "公式"]
    if block_type == "algorithm":
        return [r"(?:Algorithms?|Algs?\.?)", "算法"]
    return []


def parse_media_references(text):
    refs = []
    for match in MEDIA_REFERENCE_RE.finditer(text or ""):
        block_type = media_type_from_kind(match.group("kind"))
        if not block_type:
            continue
        number = normalize_media_number(match.group("number"))
        if not number:
            continue
        namespace = media_namespace_from_prefix(match.group("prefix"), number, block_type)
        refs.append({
            "type": block_type,
            "namespace": namespace,
            "number": number,
            "displayNumber": display_media_number(number),
            "label": media_label_from_parts(namespace, block_type, number),
            "key": media_signature_key((namespace, block_type, number)),
            "lookupKeys": media_lookup_keys_from_parts(namespace, block_type, number),
            "text": match.group(0),
        })
    return refs


def dedupe_media_refs(refs):
    deduped = []
    seen = set()
    for ref in refs:
        key = media_reference_key(ref)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def media_type_from_kind(kind):
    normalized = (kind or "").strip().lower().rstrip(".")
    if normalized in {"图"} or normalized.startswith(("fig", "figure")):
        return "figure"
    if normalized in {"表"} or normalized.startswith(("tab", "table")):
        return "table"
    if normalized in {"式", "公式"} or normalized.startswith(("eq", "equation", "formula")):
        return "equation"
    if normalized in {"算法"} or normalized.startswith(("alg", "algorithm")):
        return "algorithm"
    return ""


def media_namespace_from_prefix(prefix, number, block_type):
    normalized = clean_text(prefix).lower().rstrip(".")
    if normalized == "extended data":
        return "extended"
    if normalized in {"supplementary", "supplemental", "suppl", "si"}:
        return "supplementary"
    if block_type in {"figure", "table", "algorithm"} and number.upper().startswith("S"):
        return "supplementary"
    return "main"


def normalize_media_number(number):
    number = re.sub(r"\s+", "", str(number or "")).strip()
    if not number:
        return ""
    if number[0].isalpha():
        return number[0].upper() + number[1:].lower()
    return number.lower()


def display_media_number(number):
    number = normalize_media_number(number)
    return number[0].upper() + number[1:] if number.startswith("s") else number


def media_reference_signature(ref):
    return (ref["namespace"], ref["type"], ref["number"])


def media_reference_key(ref):
    return media_signature_key(media_reference_signature(ref))


def media_reference_lookup_keys(ref):
    return media_lookup_keys_from_parts(ref["namespace"], ref["type"], ref["number"])


def media_lookup_keys_from_parts(namespace, block_type, number):
    keys = [media_signature_key((namespace, block_type, number))]
    parent = parent_media_number(number)
    if parent and block_type in {"figure", "table", "algorithm"}:
        keys.append(media_signature_key((namespace, block_type, parent)))
    return keys


def parent_media_number(number):
    normalized = normalize_media_number(number)
    match = re.match(r"^((?:S)?\d+)[a-z]$", normalized)
    return match.group(1) if match else ""


def media_signature_key(signature):
    namespace, block_type, number = signature
    return f"{namespace}:{block_type}:{number}"


def media_reference_signatures(block):
    block_type = block.get("type")
    if block_type not in {"figure", "table", "equation", "algorithm"}:
        return set()

    label_refs = matching_media_references(block.get("displayLabel") or "", block_type)
    if label_refs:
        return {media_reference_signature(label_refs[0])}

    text = clean_text("\n".join([
        block.get("caption") or "",
        block.get("text") or "",
        block.get("latex") or "",
    ]))
    refs = matching_media_references(text[:500], block_type)
    if refs:
        return {media_reference_signature(refs[0])}

    if block_type == "equation":
        match = re.search(r"\((\d+[A-Za-z]?)\)", text[:120])
        if match:
            return {("main", "equation", normalize_media_number(match.group(1)))}
    return set()


def matching_media_references(text, block_type):
    return [ref for ref in parse_media_references(text) if ref["type"] == block_type]


def paragraph_mentions_media(text, target_refs):
    target_keys = {media_signature_key(signature) for signature in target_refs}
    mentioned_keys = set()
    for ref in parse_media_references(text):
        mentioned_keys.update(media_reference_lookup_keys(ref))
    return bool(mentioned_keys.intersection(target_keys))


def media_label_from_reference(ref):
    return media_label_from_parts(ref.get("namespace"), ref.get("type"), ref.get("number"))


def media_label_from_parts(namespace, block_type, number):
    number = display_media_number(number)
    if block_type == "figure":
        if namespace == "extended":
            return f"Extended Data Fig. {number}"
        if namespace == "supplementary":
            return f"Supplementary Fig. {number}"
        return f"Fig. {number}"
    if block_type == "table":
        if namespace == "extended":
            return f"Extended Data Table {number}"
        if namespace == "supplementary":
            return f"Supplementary Table {number}"
        return f"Table {number}"
    if block_type == "equation":
        return f"Eq. {number}"
    if block_type == "algorithm":
        if namespace == "supplementary":
            return f"Supplementary Algorithm {number}"
        return f"Algorithm {number}"
    return ""


def nearest_paragraph_texts(doc_ir, block, limit):
    same_section = [
        b for b in doc_ir["blocks"]
        if is_context_text_block(b) and b["sectionId"] == block.get("sectionId")
    ]
    if not same_section:
        same_section = [b for b in doc_ir["blocks"] if is_context_text_block(b)]
    sorted_candidates = sorted(
        same_section,
        key=lambda candidate: abs(candidate["page"] - block["page"]) * 10000 + abs(bbox_center_y(candidate["bbox"]) - bbox_center_y(block["bbox"])),
    )
    return [b["text"] for b in take_context_paragraphs(sorted_candidates, limit)]


def take_context_paragraphs(candidates, limit):
    result = []
    counted = 0
    for candidate in candidates:
        result.append(candidate)
        if is_reading_text_block(candidate):
            counted += 1
            if counted >= limit:
                break
    return result


def section_by_id(doc_ir, section_id):
    for section in doc_ir.get("sections") or []:
        if section["id"] == section_id:
            return section
    return doc_ir["sections"][0] if doc_ir.get("sections") else {"id": "sec_default", "title": "Document"}


def is_skippable_section(doc_ir, section_id):
    title = (section_by_id(doc_ir, section_id).get("title") or "").strip().lower()
    return bool(re.match(r"^(references|bibliography|acknowledg|appendix|supplementary)", title))


def readable_text_ids(doc_ir, section):
    ids = []
    by_id = {b["id"]: b for b in doc_ir["blocks"]}
    for block_id in section.get("blockIds") or []:
        block = by_id.get(block_id)
        if block and is_reading_text_block(block):
            ids.append(block_id)
    return ids


def context_text_ids(doc_ir, section):
    ids = []
    by_id = {b["id"]: b for b in doc_ir["blocks"]}
    for block_id in section.get("blockIds") or []:
        block = by_id.get(block_id)
        if block and is_context_text_block(block):
            ids.append(block_id)
    return ids


def is_reading_text_block(block):
    return block.get("type") == "paragraph" and block.get("text") and block.get("skimEligible", True)


def is_context_text_block(block):
    return block.get("type") == "paragraph" and block.get("text") and block.get("contextEligible", True)


def infer_media_label(block):
    text = clean_text("\n".join([
        block.get("caption") or "",
        block.get("text") or "",
        block.get("latex") or "",
    ]))
    refs = matching_media_references(text[:500], block["type"])
    if refs:
        return media_label_from_reference(refs[0])
    if block["type"] == "algorithm":
        match = re.search(r"\bAlgorithm\s+(\d+[A-Za-z]?)", text, re.I)
        if match:
            return f"Algorithm {match.group(1)}"
    if block["type"] == "equation":
        match = re.search(r"\((\d+[A-Za-z]?)\)", text)
        if match:
            return f"Eq. {match.group(1)}"
    return ""


def first_title(blocks):
    for block in blocks:
        if block["type"] == "title" and block.get("text"):
            return clean_text(block["text"])
    return ""


def infer_abstract(blocks):
    for i, block in enumerate(blocks):
        if block["type"] == "title" and re.search(r"\babstract\b|摘要", block.get("text", ""), re.I):
            texts = []
            for next_block in blocks[i + 1: i + 6]:
                if next_block["type"] == "title":
                    break
                if next_block["type"] == "paragraph" and next_block.get("text"):
                    texts.append(next_block["text"])
            return clamp_text("\n".join(texts), 1800)
    for block in blocks:
        if block["type"] == "paragraph" and block.get("text"):
            return clamp_text(block["text"], 1200)
    return ""


def infer_section_number(text):
    match = re.match(r"^\s*([A-Z]?\d+(?:\.\d+)*|[IVX]+)\s+(.+)", text or "", re.I)
    return match.group(1) if match else ""


def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def clamp_text(text, limit):
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def prefix_for_type(block_type):
    return {
        "paragraph": "p",
        "title": "h",
        "figure": "fig",
        "table": "tbl",
        "equation": "eq",
        "algorithm": "alg",
        "code": "code",
    }.get(block_type, "blk")


def reading_order_key(block):
    column = block.get("column")
    if column in {"left", "right"}:
        column_weight = {"left": 0, "right": 1}[column]
        return (block["page"], 1, column_weight, block["bbox"][1], block["bbox"][0])
    if column == "full":
        page_height = float(block.get("pageHeight") or 800)
        return (block["page"], 0 if block["bbox"][1] < page_height * 0.55 else 2, 0, block["bbox"][1], block["bbox"][0])
    return (block["page"], 1, 0, block["bbox"][1], block["bbox"][0])


def bbox_width(bbox):
    return max(0.0, bbox[2] - bbox[0])


def bbox_height(bbox):
    return max(0.0, bbox[3] - bbox[1])


def bbox_center_x(bbox):
    return (bbox[0] + bbox[2]) / 2


def bbox_center_y(bbox):
    return (bbox[1] + bbox[3]) / 2
