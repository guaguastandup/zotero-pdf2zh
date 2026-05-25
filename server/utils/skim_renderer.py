import json
import os

import fitz


class SkimRenderError(RuntimeError):
    pass


def render_skim_pdf(input_pdf, doc_ir, skim_data, output_pdf, sidebar_width=None):
    sidebar_width = float(sidebar_width or os.getenv("SKIM_SIDEBAR_WIDTH", "300"))
    margin = 12
    gap = 9
    min_font = 5.4
    default_font = 6.5
    max_body_lines = env_int("SKIM_CARD_MAX_LINES", 5)
    font_config = resolve_font_config()

    items_by_page = {}
    for item in skim_data.get("items") or []:
        if item.get("skimText"):
            items_by_page.setdefault(int(item.get("page") or 1), []).append(item)

    page_layouts = {int(p["page"]): p.get("layout", "single") for p in doc_ir.get("pages") or []}

    os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
    with fitz.open(input_pdf) as src_doc, fitz.open() as out_doc:
        for page_index, src_page in enumerate(src_doc):
            page_num = page_index + 1
            src_rect = src_page.rect
            layout = page_layouts.get(page_num, "single")
            is_double = layout == "double"
            left_width = sidebar_width if is_double else 0
            right_width = sidebar_width
            new_width = src_rect.width + left_width + right_width
            new_height = src_rect.height
            page = out_doc.new_page(width=new_width, height=new_height)

            page.draw_rect(page.rect, color=None, fill=(1, 1, 1))
            content_rect = fitz.Rect(left_width, 0, left_width + src_rect.width, src_rect.height)
            page.show_pdf_page(content_rect, src_doc, page_index)

            if is_double:
                left_rect = fitz.Rect(0, 0, left_width, new_height)
                draw_sidebar_background(page, left_rect, "left")
            else:
                left_rect = None
            right_rect = fitz.Rect(left_width + src_rect.width, 0, new_width, new_height)
            draw_sidebar_background(page, right_rect, "right")

            page_items = sorted(items_by_page.get(page_num, []), key=item_y)
            draw_items(
                page,
                page_items,
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


def render_skim_json(doc_ir, skim_data, output_json):
    payload = {
        "doc": strip_sources(doc_ir),
        "skim": skim_data,
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return output_json


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


def draw_items(page, items, left_rect, right_rect, src_rect, x_offset, margin, gap, default_font, min_font, max_body_lines, font_config):
    lanes = {"left": [], "right": []}
    for item in items:
        side = side_for_item(item, left_rect is not None)
        target = left_rect if side == "left" else right_rect
        if target is None:
            target = right_rect
            side = "right"
        lanes[side].append((item, target))

    for side, lane_items in lanes.items():
        occupied = []
        for item, sidebar in lane_items:
            text = format_item_text(item)
            if not text:
                continue
            y = y_for_item(item)
            box_width = sidebar.width - margin * 2
            text_width = box_width - 10
            font_size = default_font
            lines, overflow = limited_lines(text, text_width, font_size, font_config, max_body_lines)
            header_lines = build_header_lines(item, text_width, font_config)
            height = estimate_box_height(lines, header_lines, font_size)
            max_height = sidebar.height - margin
            y0 = max(margin, y - height / 2)
            y0 = avoid_overlap(y0, height, occupied, margin, gap, max_height)
            if y0 + height > max_height:
                font_size = min_font
                lines, overflow = limited_lines(text, text_width, font_size, font_config, max_body_lines)
                header_lines = build_header_lines(item, text_width, font_config)
                height = estimate_box_height(lines, header_lines, font_size)
                y0 = avoid_overlap(max(margin, y - height / 2), height, occupied, margin, gap, max_height)
            if y0 + height > max_height:
                header_height = header_block_height(header_lines)
                available = min(max_body_lines, max(1, int((max_height - y0 - header_height - 8) / (font_size + 1.7))))
                lines = lines[:available]
                if lines:
                    lines[-1] = ellipsize_to_width(lines[-1], text_width, font_size, font_config)
                height = estimate_box_height(lines, header_lines, font_size)
                overflow = True
                item["overflow"] = True

            x0 = sidebar.x0 + margin
            rect = fitz.Rect(x0, y0, x0 + box_width, min(max_height, y0 + height))
            if overlaps_any(rect.y0, rect.y1, occupied, gap):
                continue
            draw_anchor_line(page, rect, item, src_rect, x_offset)
            draw_note_box(page, rect, lines, header_lines, item, font_size, overflow, font_config)
            occupied.append((rect.y0, rect.y1))


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


def build_header_lines(item, text_width, font_config):
    section = " ".join(str(item.get("sectionPathText") or item.get("sectionTitle") or "").split())
    label = str(item.get("displayLabel") or "").strip()
    if item.get("type") == "paragraph":
        head = f"{section} / {label}" if label else section
    else:
        head = f"{section} / {label}" if section and label else (label or section)
    if not head:
        return []
    return wrap_text(head, text_width, 5.3, font_config)[:2]


def draw_note_box(page, rect, lines, header_lines, item, font_size, overflow, font_config):
    border = color_for_type(item.get("type"))
    fill = (0.998, 0.998, 0.996)
    page.draw_rect(rect, color=border, fill=fill, width=0.55)
    x = rect.x0 + 5
    y = rect.y0 + 4
    text_width = rect.width - 10
    if header_lines:
        for header in header_lines:
            header = trim_to_width(header, text_width, 5.2, font_config)
            draw_mixed_text(page, x, y + 5.2, header, 5.2, (0.34, 0.37, 0.43), font_config)
            y += 6.4
        page.draw_line((rect.x0 + 4, y + 0.8), (rect.x1 - 4, y + 0.8), color=(0.86, 0.88, 0.91), width=0.35)
        y += 3.2
    line_height = font_size + 1.7
    max_lines = max(1, int((rect.y1 - y - 4) / line_height))
    draw_lines = lines[:max_lines]
    for line in draw_lines:
        line = trim_to_width(line, text_width, font_size, font_config)
        draw_mixed_text(page, x, y + font_size, line, font_size, (0.10, 0.12, 0.16), font_config)
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
    header_height = header_block_height(header_lines)
    return max(14, header_height + len(lines) * (font_size + 1.7) + 8)


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


def header_block_height(header_lines):
    if not header_lines:
        return 0
    return len(header_lines) * 6.4 + 4


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

    start = max(1, int(limit * 0.58))
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
        score += 100
    elif prev in "：":
        score += 58
    elif prev in "，、":
        score += 28
    elif prev in ")]）】":
        score += 70
    elif prev.isspace():
        score += 62
    elif next_char.isspace():
        score += 58
    elif is_cjk(prev) and is_cjk(next_char):
        score += 36
    elif is_cjk(prev) != is_cjk(next_char):
        score += 24
    else:
        score += 10

    score -= abs(limit - index) * 0.65
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
    return (float(bbox[1]) + float(bbox[3])) / 2
