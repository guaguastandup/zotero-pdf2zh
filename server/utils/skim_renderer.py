import json
import os

import fitz


class SkimRenderError(RuntimeError):
    pass


def render_skim_pdf(input_pdf, doc_ir, skim_data, output_pdf, sidebar_width=None):
    margin = env_float("SKIM_CARD_MARGIN", 9)
    gap = env_float("SKIM_CARD_GAP", 7)
    min_font = env_float("SKIM_CARD_MIN_FONT", 4.0)
    default_font = 6.5
    max_body_lines = env_int("SKIM_CARD_MAX_LINES", 9)
    font_config = resolve_font_config()
    layout_config = resolve_layout_config(sidebar_width)
    skim_data = sync_skim_data_with_doc(doc_ir, skim_data)

    items_by_page = {}
    for item in skim_data.get("items") or []:
        if item.get("skimText"):
            items_by_page.setdefault(int(item.get("page") or 1), []).append(item)

    page_layouts = {int(p["page"]): p.get("layout", "single") for p in doc_ir.get("pages") or []}
    left_width, right_width, fixed_box_width = resolve_document_sidebars(
        items_by_page,
        page_layouts,
        layout_config,
        margin,
    )

    os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
    with fitz.open(input_pdf) as src_doc, fitz.open() as out_doc:
        for page_index, src_page in enumerate(src_doc):
            page_num = page_index + 1
            src_rect = src_page.rect
            layout = page_layouts.get(page_num, "single")
            is_double = layout == "double"
            page_items = sorted(items_by_page.get(page_num, []), key=item_y)
            lanes = layout_page_sidebars(
                page_items,
                is_double,
                margin,
                default_font,
                max_body_lines,
                font_config,
                layout_config,
                fixed_box_width,
            )
            new_width = src_rect.width + left_width + right_width
            new_height = src_rect.height
            page = out_doc.new_page(width=new_width, height=new_height)

            page.draw_rect(page.rect, color=None, fill=(1, 1, 1))
            content_rect = fitz.Rect(left_width, 0, left_width + src_rect.width, src_rect.height)
            page.show_pdf_page(content_rect, src_doc, page_index)

            if left_width > 0:
                left_rect = fitz.Rect(0, 0, left_width, new_height)
                draw_sidebar_background(page, left_rect, "left")
            else:
                left_rect = None
            if right_width > 0:
                right_rect = fitz.Rect(left_width + src_rect.width, 0, new_width, new_height)
                draw_sidebar_background(page, right_rect, "right")
            else:
                right_rect = None

            draw_items(
                page,
                lanes,
                left_rect,
                right_rect,
                src_rect,
                left_width,
                margin,
                gap,
                default_font,
                min_font,
                max_body_lines,
                font_config,
            )
            page.clean_contents()
        out_doc.save(output_pdf, garbage=4, deflate=True, clean=True)
    return output_pdf


def env_int(name, default):
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def env_float(name, default):
    try:
        return max(1.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def resolve_layout_config(sidebar_width=None):
    base_width = max(120.0, float(sidebar_width or os.getenv("SKIM_SIDEBAR_WIDTH", "270")))
    return {
        "base_sidebar_width": base_width,
        "max_sidebar_width": max(base_width, env_float("SKIM_SIDEBAR_MAX_WIDTH", 520)),
        "width_extra": env_float("SKIM_SIDEBAR_WIDTH_EXTRA", 12),
    }


def sentence_segments(text):
    text = normalize_break_text(text)
    if not text:
        return []

    segments = []
    start = 0
    for index, char in enumerate(text):
        if is_sentence_break(text, index):
            segment = text[start:index + 1].strip()
            if segment:
                segments.append(segment)
            start = index + 1
    tail = text[start:].strip()
    if tail:
        segments.append(tail)
    return segments or [text]


def is_sentence_break(text, index):
    char = text[index]
    if char in "。！？；;!?":
        return True
    if char != ".":
        return False
    prefix = text[max(0, index - 5):index + 1].lower()
    if prefix.endswith(("fig.", "tab.", "eq.", "alg.", "no.", "vs.", "e.g.", "i.e.")):
        return False
    prev_char = text[index - 1] if index > 0 else ""
    next_char = text[index + 1] if index + 1 < len(text) else ""
    if prev_char.isdigit() and next_char.isdigit():
        return False
    if is_numbered_list_marker(text, index):
        return False
    return not next_char or next_char.isspace()


def is_numbered_list_marker(text, index):
    if index <= 0 or not text[index - 1].isdigit():
        return False
    next_char = text[index + 1] if index + 1 < len(text) else ""
    if not next_char.isspace():
        return False

    start = index - 1
    while start > 0 and text[start - 1].isdigit():
        start -= 1
    number_text = text[start:index]
    if len(number_text) > 2:
        return False
    before = text[start - 1] if start > 0 else ""
    return not before or before.isspace() or before in "。！？；;:："


def render_skim_json(doc_ir, skim_data, output_json):
    skim_data = sync_skim_data_with_doc(doc_ir, skim_data)
    payload = {
        "doc": strip_sources(doc_ir),
        "skim": skim_data,
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return output_json


def sync_skim_data_with_doc(doc_ir, skim_data):
    skim_data = dict(skim_data or {})
    by_id = {
        block.get("id"): block
        for block in doc_ir.get("blocks") or []
        if block.get("id")
    }
    order = {block_id: index for index, block_id in enumerate(by_id.keys())}
    merged_owner = merged_continuation_owner_map(doc_ir)
    grouped_items = {}

    for item in skim_data.get("items") or []:
        block_id = item.get("blockId")
        resolved_id = block_id if block_id in by_id else merged_owner.get(block_id)
        if not resolved_id or resolved_id not in by_id:
            continue
        if not should_render_synced_block(by_id[resolved_id]):
            continue
        grouped_items.setdefault(resolved_id, []).append(item)

    synced_items = []
    for block_id, group in sorted(grouped_items.items(), key=lambda pair: order.get(pair[0], 10**9)):
        block = by_id[block_id]
        synced = merged_item_for_block(block_id, group)
        sync_item_structure(synced, block)
        repair_failed_fallback_text(synced, block)
        synced_items.append(synced)
    skim_data["items"] = synced_items
    return skim_data


def merged_continuation_owner_map(doc_ir):
    owner = {}
    for block in doc_ir.get("blocks") or []:
        block_id = block.get("id")
        if not block_id:
            continue
        for merged_id in block.get("mergedContinuationIds") or []:
            owner[merged_id] = block_id
    return owner


def should_render_synced_block(block):
    if block.get("type") == "paragraph" and not block.get("skimEligible", True):
        return False
    return True


def merged_item_for_block(block_id, items):
    preferred = next((item for item in items if item.get("blockId") == block_id), None)
    merged = dict(preferred or items[0])
    merged["blockId"] = block_id
    for key in ["skimText", "sourceText", "translationText"]:
        value = combine_item_texts(items, key)
        if value:
            merged[key] = value
    if len(items) > 1:
        merged["mergedSkimItemIds"] = [item.get("blockId") for item in items if item.get("blockId")]
    return merged


def combine_item_texts(items, key):
    parts = []
    seen = set()
    for item in items:
        text = " ".join(str(item.get(key) or "").split())
        if not text:
            continue
        normalized = text.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        parts.append(text)
    return " ".join(parts)


def sync_item_structure(item, block):
    for key in [
        "type",
        "page",
        "column",
        "bbox",
        "sectionId",
        "sectionTitle",
        "sectionPath",
        "sectionPathText",
        "paragraphIndex",
        "displayLabel",
        "assetPath",
    ]:
        if key in block:
            item[key] = block.get(key)
    item["positionLabel"] = item_position_label(block)


def repair_failed_fallback_text(item, block):
    if not item.get("error"):
        return
    text = " ".join(str(item.get("skimText") or "").split())
    if not text:
        item["skimText"] = localized_failure_text(block)
        return
    if "[truncated]" in text or looks_like_raw_source_fallback(text, block):
        item["skimText"] = localized_failure_text(block)


def looks_like_raw_source_fallback(text, block):
    source = " ".join(str(block.get("text") or block.get("caption") or block.get("latex") or "").split())
    if not source:
        return mostly_ascii(text)
    return source.lower().startswith(text[: min(len(text), 80)].lower()) or mostly_ascii(text)


def mostly_ascii(text):
    chars = [char for char in str(text or "") if not char.isspace()]
    if not chars:
        return False
    ascii_count = sum(1 for char in chars if char.isascii())
    return ascii_count / max(1, len(chars)) > 0.82


def localized_failure_text(block):
    label = item_position_label(block)
    if block.get("type") == "paragraph":
        return f"该段中文伴读生成失败，已保留原文定位：{label}。请重新生成以补齐该段精简句。"
    return f"该对象中文伴读生成失败，已保留原文定位：{label}。请重新生成以补齐解释。"


def item_position_label(block):
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


def strip_sources(doc_ir):
    clean = {}
    for key, value in doc_ir.items():
        if key == "blocks":
            clean[key] = [{k: v for k, v in block.items() if k != "source"} for block in value]
        else:
            clean[key] = value
    return clean


def draw_sidebar_background(page, rect, side):
    fill = (0.985, 0.988, 0.992)
    border = (0.78, 0.8, 0.84)
    page.draw_rect(rect, color=None, fill=fill)
    if side == "left":
        page.draw_line((rect.x1, rect.y0), (rect.x1, rect.y1), color=border, width=0.6)
    else:
        page.draw_line((rect.x0, rect.y0), (rect.x0, rect.y1), color=border, width=0.6)


def resolve_document_sidebars(items_by_page, page_layouts, layout_config, margin):
    has_left = False
    has_right = False
    for page_num, page_items in items_by_page.items():
        is_double = page_layouts.get(page_num, "single") == "double"
        for item in page_items:
            side = side_for_item(item, is_double)
            if side == "left":
                has_left = True
            else:
                has_right = True

    sidebar_width = layout_config["base_sidebar_width"]
    box_width = max(80.0, sidebar_width - margin * 2)
    return (
        sidebar_width if has_left else 0,
        sidebar_width if has_right else 0,
        box_width,
    )


def layout_page_sidebars(items, is_double, margin, font_size, max_body_lines, font_config, layout_config, fixed_box_width):
    lanes = {"left": [], "right": []}
    for item in items:
        side = side_for_item(item, is_double)
        card = build_card_layout(item, margin, font_size, max_body_lines, font_config, layout_config, fixed_box_width)
        if card:
            lanes[side].append(card)
    return lanes


def build_card_layout(item, margin, font_size, max_body_lines, font_config, layout_config, box_width=None):
    text = format_item_text(item)
    if not text:
        return None

    base_box_width = max(80.0, layout_config["base_sidebar_width"] - margin * 2)
    max_box_width = max(base_box_width, layout_config["max_sidebar_width"] - margin * 2)
    if box_width is None:
        box_width = choose_card_box_width(text, base_box_width, max_box_width, font_size, font_config, max_body_lines, layout_config)
    box_width = max(80.0, min(max_box_width, float(box_width)))
    text_width = box_width - card_horizontal_padding() * 2
    lines, overflow = limited_body_lines(text, text_width, font_size, font_config, max_body_lines)
    header_lines = build_header_lines(item, text_width, font_config, header_font_size(font_size))
    return {
        "item": item,
        "text": text,
        "box_width": box_width,
        "text_width": text_width,
        "font_size": font_size,
        "lines": lines,
        "header_lines": header_lines,
        "height": estimate_box_height(lines, header_lines, font_size),
        "overflow": overflow,
    }


def choose_card_box_width(text, base_box_width, max_box_width, font_size, font_config, max_body_lines, layout_config):
    base_text_width = base_box_width - card_horizontal_padding() * 2
    max_lines = max(1, int(max_body_lines or 7))
    segments = sentence_segments(text)
    base_lines = body_lines_for_segments(segments, base_text_width, font_size, font_config)
    if len(base_lines) <= max_lines:
        return base_box_width

    longest_segment_width = max(
        (mixed_text_width(segment, font_size, font_config) for segment in segments),
        default=base_text_width,
    )
    one_segment_box_width = max(base_box_width, min(max_box_width, longest_segment_width + card_horizontal_padding() * 2 + layout_config["width_extra"]))

    max_text_width = max_box_width - card_horizontal_padding() * 2
    if len(body_lines_for_segments(segments, max_text_width, font_size, font_config)) > max_lines:
        return one_segment_box_width

    low = base_box_width
    high = max_box_width
    for _ in range(10):
        mid = (low + high) / 2
        if len(body_lines_for_segments(segments, mid - card_horizontal_padding() * 2, font_size, font_config)) <= max_lines:
            high = mid
        else:
            low = mid
    desired_box_width = high + layout_config["width_extra"]
    return max(base_box_width, min(max_box_width, desired_box_width))


def body_lines_for_width(text, text_width, font_size, font_config):
    return body_lines_for_segments(sentence_segments(text), text_width, font_size, font_config)


def body_lines_for_segments(segments, text_width, font_size, font_config):
    lines = []
    for segment in segments:
        lines.extend(wrap_text(segment, text_width, font_size, font_config))
    return lines or [""]


def limited_body_lines(text, max_width, font_size, font_config, max_lines):
    lines = body_lines_for_width(text, max_width, font_size, font_config)
    max_lines = max(1, int(max_lines or 9))
    overflow = len(lines) > max_lines
    if overflow:
        lines = lines[:max_lines]
        lines[-1] = ellipsize_to_width(lines[-1], max_width, font_size, font_config)
    return lines, overflow


def draw_items(page, lanes, left_rect, right_rect, src_rect, x_offset, margin, gap, default_font, min_font, max_body_lines, font_config):
    sidebars = {"left": left_rect, "right": right_rect}

    for side, lane_items in lanes.items():
        sidebar = sidebars.get(side)
        if sidebar is None:
            continue
        slots = assign_vertical_slots(lane_items, sidebar, margin, gap)
        for card, slot_top, slot_bottom in slots:
            item = card["item"]
            y = y_for_item(item)
            box_width = card["box_width"]
            fitted = fit_card_to_slot(card, max(0, slot_bottom - slot_top), default_font, min_font, max_body_lines, font_config)
            if fitted is None:
                continue
            font_size = fitted["font_size"]
            lines = fitted["lines"]
            header_lines = fitted["header_lines"]
            overflow = fitted["overflow"]
            height = fitted["height"]
            y0 = clamp(y - height / 2, slot_top, slot_bottom - height)

            if side == "left":
                x0 = sidebar.x0 + margin
            else:
                x0 = sidebar.x0 + margin
            align = "left"
            rect = fitz.Rect(x0, y0, x0 + box_width, y0 + height)
            draw_anchor_line(page, rect, item, src_rect, x_offset)
            draw_note_box(page, rect, lines, header_lines, item, font_size, overflow, font_config, align=align)


def assign_vertical_slots(lane_items, sidebar, margin, gap):
    if not lane_items:
        return []
    anchors = [clamp(y_for_item(card["item"]), margin, sidebar.height - margin) for card in lane_items]
    groups = group_nearby_anchors(lane_items, anchors)
    centers = [sum(group["anchors"]) / len(group["anchors"]) for group in groups]
    slots = []
    for group_index, group in enumerate(groups):
        if group_index == 0:
            raw_top = margin
        else:
            raw_top = (centers[group_index - 1] + centers[group_index]) / 2
        if group_index == len(groups) - 1:
            raw_bottom = sidebar.height - margin
        else:
            raw_bottom = (centers[group_index] + centers[group_index + 1]) / 2
        raw_top = max(margin, raw_top)
        raw_bottom = min(sidebar.height - margin, raw_bottom)
        group_slots = split_group_slot(group["cards"], raw_top, raw_bottom, gap)
        slots.extend(group_slots)
    return slots


def group_nearby_anchors(lane_items, anchors):
    threshold = env_float("SKIM_SLOT_GROUP_THRESHOLD", 8)
    groups = []
    for card, anchor in zip(lane_items, anchors):
        if not groups or anchor - groups[-1]["anchors"][-1] > threshold:
            groups.append({"cards": [card], "anchors": [anchor]})
        else:
            groups[-1]["cards"].append(card)
            groups[-1]["anchors"].append(anchor)
    return groups


def split_group_slot(cards, raw_top, raw_bottom, gap):
    height = max(0, raw_bottom - raw_top)
    if not cards:
        return []
    if len(cards) == 1:
        inset = min(gap / 2, max(0, (height - 18) / 2), height * 0.08)
        return [(cards[0], raw_top + inset, raw_bottom - inset)]

    inner_gap = min(gap * 0.35, max(0, (height - 18 * len(cards)) / max(1, len(cards) - 1)))
    available = max(0, height - inner_gap * (len(cards) - 1))
    each_height = available / len(cards) if cards else 0
    slots = []
    top = raw_top
    for card in cards:
        slots.append((card, top, top + each_height))
        top += each_height + inner_gap
    return slots


def fit_card_to_slot(card, slot_height, default_font, min_font, max_body_lines, font_config):
    if slot_height < 12:
        return None
    text = card["text"]
    text_width = card["text_width"]
    item = card["item"]
    preferred_line_cap = dynamic_body_line_cap(item, max_body_lines)
    candidates = []
    for include_header in (True, False):
        fitted = fit_card_variant(
            text,
            text_width,
            slot_height,
            item,
            include_header,
            preferred_line_cap,
            default_font,
            min_font,
            font_config,
        )
        if fitted:
            candidates.append(fitted)
    if not candidates:
        return None

    complete = [candidate for candidate in candidates if not candidate["overflow"]]
    if complete:
        with_header = [candidate for candidate in complete if candidate["header_lines"]]
        if with_header:
            return max(with_header, key=lambda candidate: candidate["font_size"])
        return max(complete, key=lambda candidate: candidate["font_size"])
    return max(
        candidates,
        key=lambda candidate: (
            candidate["visible_score"],
            bool(candidate["header_lines"]),
            -candidate["preferred_penalty"],
            candidate["font_size"],
        ),
    )


def fit_card_variant(text, text_width, slot_height, item, include_header, preferred_line_cap, default_font, min_font, font_config):
    candidates = []
    for font_size in font_steps(default_font, min_font):
        header_lines = build_header_lines(item, text_width, font_config, header_font_size(font_size)) if include_header else []
        capacity = body_line_capacity(slot_height, header_lines, font_size)
        if capacity <= 0:
            continue
        body_limit = capacity
        raw_lines = body_lines_for_width(text, text_width, font_size, font_config)
        overflow = len(raw_lines) > body_limit
        lines = raw_lines[:body_limit]
        if overflow and lines:
            lines[-1] = ellipsize_to_width(lines[-1], text_width, font_size, font_config)
        height = estimate_box_height(lines, header_lines, font_size)
        if height <= slot_height + 0.1:
            candidates.append({
                "font_size": font_size,
                "lines": lines,
                "header_lines": header_lines,
                "height": height,
                "overflow": overflow,
                "visible_score": sum(mixed_len(line) for line in lines),
                "preferred_penalty": max(0, len(lines) - preferred_line_cap),
            })
    if not candidates:
        return None
    complete = [candidate for candidate in candidates if not candidate["overflow"]]
    if complete:
        return max(complete, key=lambda candidate: candidate["font_size"])
    return max(candidates, key=lambda candidate: (candidate["visible_score"], -candidate["preferred_penalty"], candidate["font_size"]))



def font_steps(default_font, min_font):
    steps = []
    font_size = float(default_font)
    min_font = float(min_font)
    while font_size > min_font + 0.01:
        steps.append(round(font_size, 2))
        font_size -= 0.2
    steps.append(round(min_font, 2))
    return steps


def body_line_capacity(slot_height, header_lines, font_size):
    header_height = header_block_height(header_lines, font_size)
    return max(0, int((slot_height - header_height - box_vertical_padding()) / body_line_height(font_size)))


def dynamic_body_line_cap(item, max_body_lines):
    base_cap = max(3, int(max_body_lines or 9))
    bbox = item.get("bbox") or []
    source_height = max(0, float(bbox[3] - bbox[1])) if len(bbox) >= 4 else 0
    item_type = item.get("type")
    if item_type in {"figure", "table", "equation", "algorithm"}:
        if source_height:
            return max(4, min(base_cap + 2, int(source_height / 18) + 4))
        return base_cap + 1
    if source_height:
        return max(3, min(base_cap, int(source_height / 20) + 3))
    return base_cap


def clamp(value, low, high):
    if high < low:
        return low
    return max(low, min(high, value))


def side_for_item(item, has_left_sidebar):
    column = item.get("column") or "single"
    if has_left_sidebar and column == "left":
        return "left"
    return "right"


def format_item_text(item):
    text = " ".join(str(item.get("skimText") or "").split())
    display = item.get("displayLabel") or ""
    if item.get("type") in {"figure", "table", "equation", "algorithm"} and display:
        normalized = normalize_label_prefix(display)
        if not starts_with_label(text, normalized):
            text = f"{display}: {text}"
    return text.strip()


def build_header_lines(item, text_width, font_config, font_size=5.2):
    head = build_header_text(item)
    if not head:
        return []
    return wrap_text(head, text_width, font_size, font_config)[:2]


def build_header_text(item):
    section = " ".join(str(item.get("sectionPathText") or item.get("sectionTitle") or "").split())
    label = str(item.get("displayLabel") or "").strip()
    if item.get("type") == "paragraph":
        head = f"{section} / {label}" if label else section
    else:
        head = f"{section} / {label}" if section and label else (label or section)
    return head.strip()


def draw_note_box(page, rect, lines, header_lines, item, font_size, overflow, font_config, align="left"):
    border = color_for_type(item.get("type"))
    fill = (0.998, 0.998, 0.996)
    page.draw_rect(rect, color=border, fill=fill, width=0.55)
    x = rect.x0 + card_horizontal_padding()
    right_x = rect.x1 - card_horizontal_padding()
    y = rect.y0 + card_top_padding()
    text_width = rect.width - card_horizontal_padding() * 2
    header_size = header_font_size(font_size)
    if header_lines:
        for header in header_lines:
            header = trim_to_width(header, text_width, header_size, font_config)
            draw_aligned_text(page, x, right_x, y + header_size, header, header_size, (0.34, 0.37, 0.43), font_config, align)
            y += header_line_height(header_size)
        page.draw_line((rect.x0 + card_horizontal_padding(), y + 0.6), (rect.x1 - card_horizontal_padding(), y + 0.6), color=(0.86, 0.88, 0.91), width=0.35)
        y += header_divider_gap(font_size)
    line_height = body_line_height(font_size)
    max_lines = max(1, int((rect.y1 - y - card_bottom_padding()) / line_height))
    draw_lines = lines[:max_lines]
    for line in draw_lines:
        line = trim_to_width(line, text_width, font_size, font_config)
        draw_aligned_text(page, x, right_x, y + font_size, line, font_size, (0.10, 0.12, 0.16), font_config, align)
        y += line_height
    if overflow:
        draw_mixed_text(page, rect.x1 - 12, rect.y1 - 4, "...", font_size, (0.45, 0.18, 0.10), font_config)


def resolve_font_config():
    return {
        "latin_fontname": "helv",
        "cjk_fontname": "china-s",
    }


def color_for_type(item_type):
    if item_type == "figure":
        return (0.26, 0.47, 0.74)
    if item_type == "table":
        return (0.24, 0.56, 0.42)
    if item_type == "equation":
        return (0.64, 0.38, 0.18)
    if item_type == "algorithm":
        return (0.46, 0.34, 0.68)
    return (0.68, 0.70, 0.76)


def estimate_box_height(lines, header_lines, font_size):
    header_height = header_block_height(header_lines, font_size)
    return max(12, header_height + len(lines) * body_line_height(font_size) + box_vertical_padding())


def limited_lines(text, max_width, font_size, font_config, max_lines):
    lines = wrap_text(text, max_width, font_size, font_config)
    max_lines = max(1, int(max_lines or 5))
    overflow = len(lines) > max_lines
    if overflow:
        lines = lines[:max_lines]
        lines[-1] = ellipsize_to_width(lines[-1], max_width, font_size, font_config)
    return lines, overflow


def ellipsize_to_width(text, max_width, font_size, font_config):
    suffix = "..."
    base = str(text or "").rstrip()
    while base and mixed_text_width(base + suffix, font_size, font_config) > max_width:
        base = base[:-1].rstrip()
    return (base + suffix) if base else suffix


def header_block_height(header_lines, font_size=5.2):
    if not header_lines:
        return 0
    header_size = header_font_size(font_size)
    return len(header_lines) * header_line_height(header_size) + header_divider_gap(font_size)


def header_font_size(font_size):
    return max(2.0, min(5.2, float(font_size) * 0.82))


def header_line_height(font_size):
    return float(font_size) + 1.1


def header_divider_gap(font_size):
    return max(1.4, min(3.0, float(font_size) * 0.45))


def body_line_height(font_size):
    return float(font_size) + 1.25


def box_vertical_padding():
    return card_top_padding() + card_bottom_padding()


def card_horizontal_padding():
    return env_float("SKIM_CARD_HORIZONTAL_PADDING", 4)


def card_top_padding():
    return env_float("SKIM_CARD_TOP_PADDING", 3)


def card_bottom_padding():
    return env_float("SKIM_CARD_BOTTOM_PADDING", 4)


def normalize_label_prefix(label):
    return " ".join(str(label or "").replace("：", ":").split()).rstrip(":")


def starts_with_label(text, label):
    if not text or not label:
        return False
    normalized = " ".join(text.replace("：", ":").split())
    return normalized.lower().startswith(label.lower())


def draw_anchor_line(page, rect, item, src_rect, x_offset):
    bbox = item.get("bbox") or []
    if len(bbox) < 4:
        return
    anchor_y = y_for_item(item)
    anchor_x = x_offset + (bbox[0] if rect.x0 < x_offset else bbox[2])
    anchor_x = max(x_offset, min(x_offset + src_rect.width, anchor_x))
    box_x = rect.x1 if rect.x0 < x_offset else rect.x0
    color = color_for_type(item.get("type"))
    page.draw_line((box_x, (rect.y0 + rect.y1) / 2), (anchor_x, anchor_y), color=color, width=0.35, dashes="[2 2]")


def avoid_overlap(y0, height, occupied, margin, gap, max_height):
    y0 = max(margin, y0)
    for top, bottom in sorted(occupied):
        if y0 + height + gap <= top:
            break
        if y0 < bottom + gap:
            y0 = bottom + gap
    if y0 + height > max_height:
        y0 = max(margin, max_height - height)
        for top, bottom in sorted(occupied, reverse=True):
            if y0 >= bottom + gap:
                break
            if y0 + height > top:
                y0 = top - height - gap
        y0 = max(margin, y0)
    return y0


def overlaps_any(top, bottom, occupied, gap):
    return any(top < existing_bottom + gap and bottom + gap > existing_top for existing_top, existing_bottom in occupied)


def wrap_text(text, max_width, font_size, font_config):
    text = normalize_break_text(text)
    if not text:
        return [""]
    lines = []
    rest = text
    while rest:
        if mixed_text_width(rest, font_size, font_config) <= max_width:
            lines.append(rest.strip())
            break
        break_at = choose_break(rest, max_width, font_size, font_config)
        if break_at <= 0:
            head, rest = split_to_width(rest, max_width, font_size, font_config)
        else:
            head, rest = rest[:break_at], rest[break_at:]
        head = head.strip()
        rest = rest.lstrip()
        if head:
            lines.append(head)
    return rebalance_short_lines(lines, max_width, font_size, font_config) or [""]


def old_wrap_text(text, max_width, font_size, font_config):
    lines = []
    current = ""
    for token in text_tokens(text):
        candidate = current + token
        if current and mixed_text_width(candidate, font_size, font_config) > max_width:
            lines.append(current.rstrip())
            current = token.lstrip()
            while current and mixed_text_width(current, font_size, font_config) > max_width:
                head, current = split_to_width(current, max_width, font_size, font_config)
                lines.append(head.rstrip())
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())
    return lines or [""]


def normalize_break_text(text):
    text = " ".join(str(text or "").split())
    return text


def choose_break(text, max_width, font_size, font_config):
    limit = 0
    for index in range(1, len(text) + 1):
        if mixed_text_width(text[:index], font_size, font_config) > max_width:
            break
        limit = index
    if limit <= 1:
        return 0

    start = max(1, int(limit * 0.45))
    candidates = []
    for index in range(start, limit + 1):
        prev = text[index - 1]
        next_char = text[index] if index < len(text) else ""
        candidates.append((break_score(prev, next_char, index, limit, text), index))

    candidates.sort(reverse=True)
    best = candidates[0][1]
    if best < len(text) and too_short_line(text[best:]):
        wider = find_wider_break(text, best, limit, max_width, font_size, font_config)
        if wider:
            return wider
    return best


def break_score(prev, next_char, index, limit, text):
    score = 0
    if prev in "。！？；":
        score += 180
    elif prev in "：":
        score += 120
    elif prev == "，":
        score += 95
    elif prev == "、":
        score += 8
    elif prev in ")]）】":
        score += 80
    elif prev.isspace():
        score += 100
    elif next_char.isspace():
        score += 92
    elif is_cjk(prev) and is_cjk(next_char):
        score += 14
    elif is_cjk(prev) != is_cjk(next_char):
        score += 18
    else:
        score += 10

    score -= abs(limit - index) * 0.42
    head = text[:index].strip()
    tail = text[index:].strip()
    if len(head) < 8:
        score -= 80
    if too_short_line(tail):
        score -= 60
    if head and head[-1] in "（([《":
        score -= 80
    if tail and tail[0] in "，。；：、！？)]）】":
        score -= 90
    if ends_inside_ascii_word(text, index):
        score -= 100
    if breaks_ascii_phrase(text, index):
        score -= 120
    return score


def find_wider_break(text, current, limit, max_width, font_size, font_config):
    for index in range(current + 1, min(len(text), limit + 12) + 1):
        if mixed_text_width(text[:index], font_size, font_config) > max_width:
            return 0
        if text[index - 1] in "，。；：、！？ ":
            return index
    return 0


def rebalance_short_lines(lines, max_width, font_size, font_config):
    if len(lines) < 2:
        return lines
    result = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if index + 1 < len(lines) and too_short_line(lines[index + 1]):
            merged = f"{line}{lines[index + 1]}"
            if mixed_text_width(merged, font_size, font_config) <= max_width:
                result.append(merged)
                index += 2
                continue
        result.append(line)
        index += 1
    return result


def too_short_line(text):
    stripped = str(text or "").strip()
    if not stripped:
        return False
    if mixed_len(stripped) <= 7:
        return True
    ascii_words = stripped.split()
    return len(ascii_words) == 1 and stripped.isascii() and len(stripped) <= 22


def mixed_len(text):
    total = 0
    for char in text:
        total += 2 if is_cjk(char) else 1
    return total


def is_cjk(char):
    return "\u4e00" <= char <= "\u9fff"


def ends_inside_ascii_word(text, index):
    if index <= 0 or index >= len(text):
        return False
    return text[index - 1].isascii() and text[index - 1].isalnum() and text[index].isascii() and text[index].isalnum()


def breaks_ascii_phrase(text, index):
    if index <= 0 or index >= len(text):
        return False
    if text[index - 1].isspace():
        left_index = index - 2
        right_index = index
    elif text[index].isspace():
        left_index = index - 1
        right_index = index + 1
    else:
        return False
    if left_index < 0 or right_index >= len(text):
        return False
    return is_ascii_word_char(text[left_index]) and is_ascii_word_char(text[right_index])


def is_ascii_word_char(char):
    return char.isascii() and (char.isalnum() or char in "-_./+%")


def trim_to_width(text, max_width, font_size, font_config):
    result = ""
    for char in text:
        if mixed_text_width(result + char, font_size, font_config) > max_width:
            break
        result += char
    return result


def text_tokens(text):
    tokens = []
    current = ""
    current_ascii = None
    for char in text:
        if char.isspace():
            if current:
                tokens.append(current)
                current = ""
                current_ascii = None
            tokens.append(char)
            continue
        ascii_word = char.isascii() and (char.isalnum() or char in "-_./+%")
        if current and ascii_word == current_ascii:
            current += char
        else:
            if current:
                tokens.append(current)
            current = char
            current_ascii = ascii_word
    if current:
        tokens.append(current)
    return tokens


def split_to_width(text, max_width, font_size, font_config):
    result = ""
    for index, char in enumerate(text):
        if result and mixed_text_width(result + char, font_size, font_config) > max_width:
            return result, text[index:]
        result += char
    return result, ""


def draw_aligned_text(page, left_x, right_x, baseline, text, font_size, color, font_config, align="left"):
    if align == "right":
        width = mixed_text_width(text, font_size, font_config)
        x = max(left_x, right_x - width)
    else:
        x = left_x
    draw_mixed_text(page, x, baseline, text, font_size, color, font_config)


def draw_mixed_text(page, x, baseline, text, font_size, color, font_config):
    cursor = x
    for segment, fontname in font_segments(text, font_config):
        page.insert_text(
            (cursor, baseline),
            segment,
            fontsize=font_size,
            fontname=fontname,
            color=color,
        )
        cursor += fitz.get_text_length(segment, fontname=fontname, fontsize=font_size)


def mixed_text_width(text, font_size, font_config):
    raw_width = sum(
        fitz.get_text_length(segment, fontname=fontname, fontsize=font_size)
        for segment, fontname in font_segments(text, font_config)
    )
    return raw_width * width_safety_factor(text)


def width_safety_factor(text):
    if not text:
        return 1.0
    cjk = sum(1 for char in text if not char.isascii())
    ascii_count = len(text) - cjk
    if cjk and ascii_count:
        return 1.18
    if cjk:
        return 1.12
    return 1.04


def font_segments(text, font_config):
    segments = []
    current = ""
    current_font = None
    for char in text:
        fontname = font_for_char(char, font_config)
        if current and fontname == current_font:
            current += char
        else:
            if current:
                segments.append((current, current_font))
            current = char
            current_font = fontname
    if current:
        segments.append((current, current_font))
    return segments


def font_for_char(char, font_config):
    if char.isascii():
        return font_config["latin_fontname"]
    return font_config["cjk_fontname"]


def item_y(item):
    bbox = item.get("bbox") or [0, 0, 0, 0]
    return (bbox[1], bbox[0])


def y_for_item(item):
    bbox = item.get("bbox") or [0, 0, 0, 0]
    top = float(bbox[1])
    bottom = float(bbox[3])
    if item.get("type") == "paragraph":
        height = max(0.0, bottom - top)
        offset = min(max(height * 0.18, 6.0), 24.0, height / 2 if height else 0.0)
        return top + offset
    return (top + bottom) / 2
