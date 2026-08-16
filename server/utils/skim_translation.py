import ast
import json
import os
import re
import tempfile
from urllib.parse import unquote

import fitz

from utils.math_text import (
    display_math_from_line,
    is_display_math_line,
    mathtext_lines,
    normalize_latex_for_text,
)

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN_X = 54
MARGIN_Y = 54
TEXT_COLOR = (0.08, 0.09, 0.11)
MUTED_COLOR = (0.33, 0.36, 0.40)
ACCENT_COLOR = (0.13, 0.28, 0.46)
RULE_COLOR = (0.76, 0.80, 0.86)
IMAGE_RENDER_SCALE = 0.8
IMAGE_MAX_WIDTH_RATIO = 0.8
MATH_RENDER_DPI = 180
MATH_RENDER_FONT_SIZE = 18


def render_translation_markdown(doc_ir, skim_data, output_md, target_lang="zh-CN"):
    item_by_block = {
        item.get("blockId"): item
        for item in skim_data.get("items") or []
        if item.get("blockId")
    }
    lines = [
        f"# {doc_ir.get('title') or 'Translated Paper'}",
        "",
        f"> Target language: {target_lang}",
        "",
    ]

    for block in doc_ir.get("blocks") or []:
        if block.get("skipForTranslation"):
            continue
        block_type = block.get("type")
        item = item_by_block.get(block.get("id")) or {}
        if block_type == "title":
            title = clean_readable_md_text(block.get("text"))
            if title:
                level = int(block.get("sectionLevel") or block.get("textLevel") or 2)
                level = max(2, min(level + 1, 4))
                lines.extend([f"{'#' * level} {title}", ""])
            continue

        if block_type == "paragraph":
            translated = clean_readable_md_text(
                item.get("translationText")
                or (item.get("result") or {}).get("translation")
                or block.get("text")
            )
            if translated:
                lines.extend([translated, ""])
            continue

        if block_type in {"figure", "table", "equation", "algorithm", "code"}:
            label = block.get("displayLabel") or ("Code" if block_type == "code" else block_type)
            lines.extend([f"**{label}**", ""])
            image_line = markdown_image_line(block, output_md)
            if image_line:
                lines.extend([image_line, ""])
            caption = clean_readable_md_text(block.get("caption") or block.get("text"))
            if caption:
                lines.extend([f"> {caption}", ""])
            note_lines = markdown_value_lines(item.get("skimText"))
            if note_lines:
                lines.extend(note_lines + [""])
            if block_type == "equation":
                latex = clean_md_text(block.get("latex"))
                if latex and not image_line:
                    lines.extend([f"`{latex}`", ""])
            if block_type in {"algorithm", "code"}:
                algorithm_text = clean_preformatted_md_text(block.get("preformattedText") or block.get("text"))
                if algorithm_text:
                    lines.extend(["```text"])
                    lines.extend(algorithm_text.splitlines())
                    lines.extend(["```", ""])

    os.makedirs(os.path.dirname(output_md), exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return output_md


def render_translation_pdf(markdown_path, output_pdf):
    with open(markdown_path, "r", encoding="utf-8") as f:
        markdown = f.read()

    font_paths = resolve_pdf_fonts()
    regular_font = font_paths["regular"]
    bold_font = font_paths["bold"] or regular_font
    regular = fitz.Font(fontfile=regular_font) if regular_font else fitz.Font(fontname="china-s")
    bold = fitz.Font(fontfile=bold_font) if bold_font else regular

    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    y = MARGIN_Y
    max_y = PAGE_HEIGHT - MARGIN_Y
    text_width = PAGE_WIDTH - (MARGIN_X * 2)

    in_code_block = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            y += 4
            continue
        if in_code_block:
            if not line:
                y += 4
                continue
            page, y = draw_text_block(
                doc,
                page,
                y,
                max_y,
                line,
                style(8.5, 14, line, color=MUTED_COLOR, before=0, after=1, lineheight=1.25, quote=True, preformatted=True),
                regular,
                bold,
                regular_font,
                bold_font,
            )
            continue
        if not line:
            y += 6
            continue
        if is_display_math_line(line):
            page, y = draw_math_block(doc, page, y, max_y, display_math_from_line(line), text_width)
            continue
        image = parse_markdown_image(line, markdown_path)
        if image:
            page, y = draw_image(doc, page, y, max_y, image, text_width)
            continue

        style_info = pdf_line_style(line)
        page, y = draw_text_block(
            doc,
            page,
            y,
            max_y,
            style_info["text"],
            style_info,
            regular,
            bold,
            regular_font,
            bold_font,
        )

    os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
    doc.save(output_pdf, garbage=4, deflate=True, clean=True)
    doc.close()
    return output_pdf


def markdown_image_line(block, output_md):
    asset_path = block.get("assetPath")
    if not asset_path or not os.path.exists(asset_path):
        return ""
    try:
        rel = os.path.relpath(asset_path, os.path.dirname(output_md))
    except ValueError:
        rel = asset_path
    rel = rel.replace("\\", "/")
    label = block.get("displayLabel") or block.get("type") or "image"
    return f"![{label}]({rel})"


def clean_md_text(text):
    value = normalize_value(text)
    if isinstance(value, list):
        return " ".join(clean_md_text(item) for item in value if clean_md_text(item))
    if isinstance(value, dict):
        for key in [
            "translation",
            "compression",
            "skim",
            "summary",
            "overview",
            "explanation",
            "key_message",
            "table_summary",
            "equation_summary",
            "description",
            "raw",
        ]:
            if value.get(key):
                return clean_md_text(value.get(key))
        parts = []
        for key, val in value.items():
            cleaned = clean_md_text(val)
            if cleaned:
                parts.append(f"{key}: {cleaned}")
        return "；".join(parts)
    return " ".join(str(value or "").split())


def clean_readable_md_text(text):
    return normalize_latex_for_text(clean_md_text(text))


def clean_preformatted_md_text(text):
    value = normalize_value(text)
    if isinstance(value, (list, dict)):
        return clean_md_text(value)
    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = raw.replace("```", "'''")
    lines = [re.sub(r"[ \t]+$", "", line) for line in raw.split("\n")]
    compacted = []
    blank_count = 0
    for line in lines:
        if line.strip():
            blank_count = 0
            compacted.append(line)
        else:
            blank_count += 1
            if blank_count <= 1:
                compacted.append("")
    return "\n".join(compacted).strip()


def markdown_value_lines(value):
    normalized = normalize_value(value)
    if isinstance(normalized, list):
        lines = []
        for item in normalized:
            text = clean_readable_md_text(item)
            if text:
                lines.append(f"- {text}")
        return lines
    text = clean_readable_md_text(normalized)
    return [text] if text else []


def pdf_line_style(line):
    stripped = line.strip()
    if stripped.startswith("# "):
        return style(16, 0, strip_markdown(stripped[2:]), bold=True, color=ACCENT_COLOR, before=0, after=10, lineheight=1.25)
    if stripped.startswith("## "):
        return style(13, 0, strip_markdown(stripped[3:]), bold=True, color=ACCENT_COLOR, before=12, after=6, lineheight=1.28)
    if stripped.startswith("### "):
        return style(12, 0, strip_markdown(stripped[4:]), bold=True, color=ACCENT_COLOR, before=10, after=5, lineheight=1.28)
    if stripped.startswith("#### "):
        return style(11, 0, strip_markdown(stripped[5:]), bold=True, color=ACCENT_COLOR, before=8, after=4, lineheight=1.28)
    if stripped.startswith("> "):
        return style(9, 14, strip_markdown(stripped[2:]), color=MUTED_COLOR, before=2, after=4, lineheight=1.42, quote=True)
    if stripped.startswith("- "):
        return style(10, 14, "- " + strip_markdown(stripped[2:]), before=1, after=3, lineheight=1.35)
    if stripped.startswith("!["):
        return style(8, 12, "[image] " + strip_markdown(stripped), color=MUTED_COLOR, before=2, after=4, lineheight=1.32)
    return style(10, 0, strip_markdown(stripped), before=0, after=5, lineheight=1.42)


def style(font_size, indent, text, bold=False, color=TEXT_COLOR, before=0, after=0, lineheight=1.35, quote=False, preformatted=False):
    return {
        "font_size": font_size,
        "indent": indent,
        "text": text,
        "bold": bold,
        "color": color,
        "before": before,
        "after": after,
        "lineheight": lineheight,
        "quote": quote,
        "preformatted": preformatted,
    }


def strip_markdown(text):
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    return normalize_latex_for_text(text)


def resolve_pdf_fonts():
    candidates_regular = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
        r"C:\Windows\Fonts\NotoSerifSC-Regular.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    candidates_bold = [
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\NotoSerifSC-Bold.ttf",
        r"C:\Windows\Fonts\simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    ]
    return {
        "regular": first_existing(candidates_regular),
        "bold": first_existing(candidates_bold),
    }


def first_existing(paths):
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


def draw_text_block(doc, page, y, max_y, text, style_info, regular, bold, regular_font, bold_font):
    text = clean_preformatted_md_text(text) if style_info.get("preformatted") else clean_md_text(text)
    if not style_info.get("preformatted"):
        text = normalize_latex_for_text(text)
    if not text:
        return page, y

    font_size = style_info["font_size"]
    indent = style_info["indent"]
    font = bold if style_info["bold"] else regular
    fontfile = bold_font if style_info["bold"] and bold_font else regular_font
    fontname = "FSkimBold" if style_info["bold"] and fontfile else ("FSkimText" if fontfile else "china-s")
    line_height = max(font_size + 3, font_size * style_info["lineheight"])
    x = MARGIN_X + indent
    max_width = PAGE_WIDTH - MARGIN_X - x

    y += style_info["before"]
    lines = wrap_text_by_width(text, max_width, font, font_size)
    block_height = len(lines) * line_height + style_info["after"]
    if block_height < max_y - MARGIN_Y and y + block_height > max_y:
        page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        y = MARGIN_Y

    for wrapped in lines:
        if y + line_height > max_y:
            page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            y = MARGIN_Y
        if style_info["quote"]:
            page.draw_line(
                (MARGIN_X + 4, y + 1),
                (MARGIN_X + 4, y + line_height - 1),
                color=RULE_COLOR,
                width=1,
            )
        page.insert_text(
            (x, y + font_size),
            wrapped,
            fontsize=font_size,
            fontname=fontname,
            fontfile=fontfile,
            color=style_info["color"],
        )
        y += line_height
    y += style_info["after"]
    return page, y


def draw_math_block(doc, page, y, max_y, latex, max_width):
    images = render_math_images(latex)
    if not images:
        return draw_text_block(
            doc,
            page,
            y,
            max_y,
            normalize_latex_for_text(latex),
            style(10, 14, "", color=TEXT_COLOR, before=2, after=6, lineheight=1.35),
            fitz.Font(fontname="china-s"),
            fitz.Font(fontname="china-s"),
            None,
            None,
        )

    y += 4
    for image in images:
        try:
            pix = fitz.Pixmap(image)
            width, height = pix.width, pix.height
            pix = None
        except Exception:
            continue
        if width <= 0 or height <= 0:
            continue
        display_width = min(width * 72 / MATH_RENDER_DPI, max_width)
        display_height = display_width * height / width
        if y + display_height + 8 > max_y:
            page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            y = MARGIN_Y
        x = MARGIN_X + (max_width - display_width) / 2
        rect = fitz.Rect(x, y, x + display_width, y + display_height)
        page.insert_image(rect, filename=image, keep_proportion=True)
        y += display_height + 4
        try:
            os.remove(image)
        except OSError:
            pass
    return page, y + 4


def render_math_images(latex):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []

    images = []
    for line in mathtext_lines(latex):
        expression = f"${line}$"
        fig = plt.figure(figsize=(8.0, 1.2), dpi=MATH_RENDER_DPI)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        try:
            ax.text(0.02, 0.5, expression, fontsize=MATH_RENDER_FONT_SIZE, va="center", ha="left", color="#111111")
            fd, path = tempfile.mkstemp(prefix="skim_math_", suffix=".png")
            os.close(fd)
            fig.savefig(path, transparent=True, bbox_inches="tight", pad_inches=0.08)
            images.append(path)
        except Exception:
            try:
                os.remove(path)
            except Exception:
                pass
        finally:
            plt.close(fig)
    return images


def wrap_text_by_width(text, max_width, font, font_size):
    tokens = tokenize_for_wrap(text)
    lines = []
    current = ""
    for token in tokens:
        if token == "\n":
            if current.strip():
                lines.append(current.rstrip())
            current = ""
            continue
        candidate = current + token
        if not current or text_width(candidate.rstrip(), font, font_size) <= max_width:
            current = candidate
            continue
        if current.strip():
            lines.append(current.rstrip())
        current = token.lstrip()
        while current and text_width(current.rstrip(), font, font_size) > max_width:
            head, tail = split_token_to_width(current, max_width, font, font_size)
            if head:
                lines.append(head.rstrip())
            current = tail.lstrip()
    if current.strip():
        lines.append(current.rstrip())
    return lines or [""]


def tokenize_for_wrap(text):
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    return re.findall(r"[A-Za-z0-9_./:%+\-]+|[\u4e00-\u9fff]|[^\sA-Za-z0-9_\u4e00-\u9fff]|\s+", normalized)


def text_width(text, font, font_size):
    if not text:
        return 0
    try:
        return font.text_length(text, fontsize=font_size)
    except Exception:
        return len(text) * font_size


def split_token_to_width(token, max_width, font, font_size):
    head = ""
    for char in token:
        candidate = head + char
        if head and text_width(candidate, font, font_size) > max_width:
            return head, token[len(head):]
        head = candidate
    return head, ""


def parse_markdown_image(line, markdown_path):
    match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
    if not match:
        return None
    alt = clean_md_text(match.group(1))
    raw_path = unquote(match.group(2).strip())
    image_path = raw_path
    if not os.path.isabs(image_path):
        image_path = os.path.join(os.path.dirname(markdown_path), image_path)
    image_path = os.path.normpath(image_path)
    return {"alt": alt, "path": image_path}


def draw_image(doc, page, y, max_y, image, max_width):
    image_path = image["path"]
    if not os.path.exists(image_path):
        return draw_text_block(
            doc,
            page,
            y,
            max_y,
            f"[image missing] {image.get('alt') or image_path}",
            style(8, 14, "", color=MUTED_COLOR, after=6),
            fitz.Font(fontname="china-s"),
            fitz.Font(fontname="china-s"),
            None,
            None,
        )

    try:
        pix = fitz.Pixmap(image_path)
        width, height = pix.width, pix.height
        pix = None
    except Exception:
        return page, y

    if width <= 0 or height <= 0:
        return page, y

    display_width = min(width * IMAGE_RENDER_SCALE, max_width * IMAGE_MAX_WIDTH_RATIO)
    display_height = display_width * height / width
    max_height = (PAGE_HEIGHT - MARGIN_Y * 2) * 0.42
    if display_height > max_height:
        display_height = max_height
        display_width = display_height * width / height

    needed = display_height + 12
    if y + needed > max_y:
        page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        y = MARGIN_Y

    x = MARGIN_X + (max_width - display_width) / 2
    rect = fitz.Rect(x, y, x + display_width, y + display_height)
    page.insert_image(rect, filename=image_path, keep_proportion=True)
    y += display_height + 10
    return page, y


def normalize_value(value):
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return value
    parsed = parse_structured_string(value)
    return parsed if parsed is not None else value


def parse_structured_string(value):
    text = str(value or "").strip()
    if not text or text[0] not in "[{":
        return None
    parsers = [
        lambda s: json.loads(s),
        lambda s: json.loads(re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", s)),
        lambda s: ast.literal_eval(s),
    ]
    for parser in parsers:
        try:
            parsed = parser(text)
            if isinstance(parsed, (list, dict)):
                return parsed
        except Exception:
            continue
    extracted = extract_json_string_fields(text)
    if extracted:
        return extracted
    return None


def extract_json_string_fields(text):
    extracted = {}
    for key in [
        "translation",
        "compression",
        "skim",
        "summary",
        "overview",
        "explanation",
        "key_message",
        "table_summary",
        "equation_summary",
        "description",
    ]:
        match = re.search(rf'"{key}"\s*:\s*"((?:\\.|[^"\\])*)"', text, flags=re.S)
        if not match:
            continue
        raw = match.group(1)
        extracted[key] = decode_json_string(raw)
    return extracted


def decode_json_string(raw):
    for candidate in [
        raw,
        re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", raw),
    ]:
        try:
            return json.loads(f'"{candidate}"')
        except Exception:
            continue
    return raw.replace('\\"', '"')
