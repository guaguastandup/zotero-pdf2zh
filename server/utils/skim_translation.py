import os
import re

import fitz


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
        block_type = block.get("type")
        item = item_by_block.get(block.get("id")) or {}
        if block_type == "title":
            title = clean_md_text(block.get("text"))
            if title:
                level = int(block.get("sectionLevel") or block.get("textLevel") or 2)
                level = max(2, min(level + 1, 4))
                lines.extend([f"{'#' * level} {title}", ""])
            continue

        if block_type == "paragraph":
            translated = clean_md_text(
                item.get("translationText")
                or (item.get("result") or {}).get("translation")
                or block.get("text")
            )
            if translated:
                lines.extend([translated, ""])
            continue

        if block_type in {"figure", "table", "equation"}:
            label = block.get("displayLabel") or block_type
            lines.extend([f"**{label}**", ""])
            image_line = markdown_image_line(block, output_md)
            if image_line:
                lines.extend([image_line, ""])
            caption = clean_md_text(block.get("caption") or block.get("text"))
            if caption:
                lines.extend([f"> {caption}", ""])
            note = clean_md_text(item.get("skimText"))
            if note:
                lines.extend([note, ""])
            if block_type == "equation":
                latex = clean_md_text(block.get("latex"))
                if latex:
                    lines.extend([f"`{latex}`", ""])

    os.makedirs(os.path.dirname(output_md), exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return output_md


def render_translation_pdf(markdown_path, output_pdf):
    with open(markdown_path, "r", encoding="utf-8") as f:
        markdown = f.read()

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    margin_x = 54
    margin_y = 54
    y = margin_y
    max_y = page.rect.height - margin_y

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line:
            y += 6
            continue
        font_size, indent, text = pdf_line_style(line)
        for wrapped in wrap_visual(text, visual_limit_for_font(font_size)):
            if y + font_size + 4 > max_y:
                page = doc.new_page(width=595, height=842)
                y = margin_y
            page.insert_text(
                (margin_x + indent, y),
                wrapped,
                fontsize=font_size,
                fontname="china-s",
                color=(0.08, 0.09, 0.11),
            )
            y += font_size + 4
        y += 2

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
    return " ".join(str(text or "").split())


def pdf_line_style(line):
    stripped = line.strip()
    if stripped.startswith("# "):
        return 16, 0, strip_markdown(stripped[2:])
    if stripped.startswith("## "):
        return 13, 0, strip_markdown(stripped[3:])
    if stripped.startswith("### "):
        return 12, 0, strip_markdown(stripped[4:])
    if stripped.startswith("#### "):
        return 11, 0, strip_markdown(stripped[5:])
    if stripped.startswith("> "):
        return 9, 12, strip_markdown(stripped[2:])
    if stripped.startswith("!["):
        return 8, 12, "[image] " + strip_markdown(stripped)
    return 10, 0, strip_markdown(stripped)


def strip_markdown(text):
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("**", "").replace("`", "")


def visual_limit_for_font(font_size):
    return max(34, int(92 * 10 / max(font_size, 1)))


def wrap_visual(text, limit):
    text = str(text or "")
    if not text:
        return [""]
    lines = []
    current = ""
    current_width = 0
    for char in text:
        char_width = 2 if "\u4e00" <= char <= "\u9fff" else 1
        if current and current_width + char_width > limit:
            lines.append(current.rstrip())
            current = char
            current_width = char_width
        else:
            current += char
            current_width += char_width
    if current:
        lines.append(current.rstrip())
    return lines or [""]
