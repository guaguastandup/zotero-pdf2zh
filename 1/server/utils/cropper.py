## server.py v3.0.36
# guaguastandup
# zotero-pdf2zh
from pypdf import PdfWriter, PdfReader
from pypdf.generic import RectangleObject
# from PyMuPDF import fitz  # PyMuPDF
import fitz
import os
import traceback
import shutil

# thanks Grok
def _apply_redactions_outside_clip(page, clip_rect):
    """辅助函数：移除clip_rect外的所有内容，使用redaction永久删除。"""
    page_rect = page.rect  # 页面全矩形
    redact_rects = [] # 计算clip外的矩形（左、上、右、下）
    if clip_rect.x0 > page_rect.x0:  # 左边
        redact_rects.append(fitz.Rect(page_rect.x0, page_rect.y0, clip_rect.x0, page_rect.y1))
    if clip_rect.y0 > page_rect.y0:  # 上边
        redact_rects.append(fitz.Rect(page_rect.x0, page_rect.y0, page_rect.x1, clip_rect.y0))
    if clip_rect.x1 < page_rect.x1:  # 右边
        redact_rects.append(fitz.Rect(clip_rect.x1, page_rect.y0, page_rect.x1, page_rect.y1))
    if clip_rect.y1 < page_rect.y1:  # 下边
        redact_rects.append(fitz.Rect(page_rect.x0, clip_rect.y1, page_rect.x1, page_rect.y1))
    # 添加redaction注解（移除填充以减少大小）
    for r_rect in redact_rects:
        page.add_redact_annot(r_rect, fill=None)  # 无填充，仅移除内容
    # 应用redaction：移除文本、图像、图形（调整参数以优化大小）
    page.apply_redactions(
        # images=fitz.PDF_REDACT_IMAGE_REMOVE,  # 完全移除重叠图像
        graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,  # 移除重叠图形
        text=fitz.PDF_REDACT_TEXT_REMOVE
    )  # 移除重叠文本

class Cropper():
    def __init__(self):
        pass
    
    # very prefect!
    def crop_pdf(self, config, input_pdf, infile_type, output_pdf, outfile_type, dualFirst=True, engine="pdf2zh"):
        w_offset = config.pdf_w_offset   # 左右边距
        h_offset = config.pdf_h_offset   # 上下边距
        r = config.pdf_offset_ratio      # 偏移比例
        src_doc = fitz.open(input_pdf)  # 打开输入PDF
        new_doc = fitz.open()
        mediabox = src_doc[0].mediabox
        w = mediabox.width
        h = mediabox.height
        half_w = w / 2

        left_clip = fitz.Rect(w_offset, h_offset, half_w + w_offset / r, h - h_offset)
        right_clip = fitz.Rect(half_w - w_offset / r, h_offset, w - w_offset, h - h_offset) 
        clip_rects = [left_clip, right_clip]

        # 创建源文档的完整拷贝，避免多次拷贝单个页面
        temp_src_doc = fitz.open()
        temp_src_doc.insert_pdf(src_doc)

        if infile_type == 'mono' or infile_type == 'origin':
            for page_num in range(len(temp_src_doc)):
                # 为每个页面创建一个临时拷贝（仅一次），然后为每个栏分别处理redaction
                temp_page_doc_base = fitz.open()
                temp_page_doc_base.insert_pdf(temp_src_doc, from_page=page_num, to_page=page_num)
                for clip_rect in clip_rects:
                    # 由于redaction是破坏性的，为每个栏拷贝base
                    temp_page_doc = fitz.open()
                    temp_page_doc.insert_pdf(temp_page_doc_base)
                    temp_page = temp_page_doc[0]
                    _apply_redactions_outside_clip(temp_page, clip_rect)
                    # 创建新页面：直接切分为上页（左栏）和下页（右栏）
                    new_page = new_doc.new_page(width=clip_rect.width, height=clip_rect.height)
                    new_page.show_pdf_page(new_page.rect, temp_page_doc, 0, clip=clip_rect)
                    new_page.clean_contents()
                    temp_page_doc.close()
                temp_page_doc_base.close()

        elif infile_type == 'dual':
            if len(temp_src_doc) % 2 != 0:
                raise ValueError("❗️ PDF page number is not even, cropping skipped.")

            for i in range(0, len(temp_src_doc), 2):
                odd_page_num = i
                even_page_num = i + 1
                if engine == "pdf2zh" and dualFirst == True:
                    odd_page_num = i + 1
                    even_page_num = i
                # 为奇数页和偶数页各创建一个base拷贝
                odd_base_doc = fitz.open()
                odd_base_doc.insert_pdf(temp_src_doc, from_page=odd_page_num, to_page=odd_page_num)
                even_base_doc = fitz.open()
                even_base_doc.insert_pdf(temp_src_doc, from_page=even_page_num, to_page=even_page_num)
                for clip_rect in clip_rects:
                    if outfile_type == 'crop-compare':  # 左右拼接
                        new_page = new_doc.new_page(width=w, height=h - 2 * h_offset)
                        target_left_rect = fitz.Rect(0, 0, w / 2, h - 2 * h_offset)
                        target_right_rect = fitz.Rect(w / 2, 0, w, h - 2 * h_offset)
                        # 处理奇数页（原文）
                        odd_temp_doc = fitz.open()
                        odd_temp_doc.insert_pdf(odd_base_doc)
                        odd_temp_page = odd_temp_doc[0]
                        _apply_redactions_outside_clip(odd_temp_page, clip_rect)
                        new_page.show_pdf_page(target_left_rect, odd_temp_doc, 0, clip=clip_rect)
                        odd_temp_doc.close()
                        # 处理偶数页（翻译）
                        even_temp_doc = fitz.open()
                        even_temp_doc.insert_pdf(even_base_doc)
                        even_temp_page = even_temp_doc[0]
                        _apply_redactions_outside_clip(even_temp_page, clip_rect)
                        new_page.show_pdf_page(target_right_rect, even_temp_doc, 0, clip=clip_rect)
                        even_temp_doc.close()
                        new_page.clean_contents()
                    elif outfile_type == 'dual-cut':
                        # 对于每个栏：原文半页 -> 对应翻译半页
                        # 处理原文
                        odd_temp_doc = fitz.open()
                        odd_temp_doc.insert_pdf(odd_base_doc)
                        odd_temp_page = odd_temp_doc[0]
                        _apply_redactions_outside_clip(odd_temp_page, clip_rect)
                        odd_new_page = new_doc.new_page(width=clip_rect.width, height=clip_rect.height)
                        odd_new_page.show_pdf_page(odd_new_page.rect, odd_temp_doc, 0, clip=clip_rect)
                        odd_new_page.clean_contents()
                        odd_temp_doc.close()
                        # 处理翻译
                        even_temp_doc = fitz.open()
                        even_temp_doc.insert_pdf(even_base_doc)
                        even_temp_page = even_temp_doc[0]
                        _apply_redactions_outside_clip(even_temp_page, clip_rect)
                        even_new_page = new_doc.new_page(width=clip_rect.width, height=clip_rect.height)
                        even_new_page.show_pdf_page(even_new_page.rect, even_temp_doc, 0, clip=clip_rect)
                        even_new_page.clean_contents()
                        even_temp_doc.close()
                odd_base_doc.close()
                even_base_doc.close()
        temp_src_doc.close()
        # 保存时优化大小：垃圾回收、压缩、清理
        new_doc.save(output_pdf, garbage=4, deflate=True, clean=True, deflate_images=True, deflate_fonts=True)
        new_doc.close()
        src_doc.close()
        print(f"✅ 处理完成，新PDF保存为 {output_pdf}. 已移除隐藏文本，并优化文件大小。")
    
    def pdf_dual_mode(self, dual_path, from_mode, to_mode):
        LR_dual_path = dual_path.replace('dual.pdf', f'LR_dual.pdf')
        TB_dual_path = dual_path.replace('dual.pdf', f'TB_dual.pdf')
        if from_mode == 'TB' and to_mode == 'LR':
            shutil.copyfile(dual_path, TB_dual_path) 
            self.merge_pdf(TB_dual_path, LR_dual_path)
        elif from_mode == 'LR' and to_mode == 'TB':
            shutil.copyfile(dual_path, LR_dual_path)
            self.split_pdf(LR_dual_path, TB_dual_path)
        return LR_dual_path, TB_dual_path

    def split_pdf(self, input_path, output_path):
        print(f"🐲 开始拆分PDF: {input_path} 到 {output_path}")
        src_doc = fitz.open(input_path)  # 打开输入PDF
        new_doc = fitz.open()
        mediabox = src_doc[0].mediabox
        w = mediabox.width
        h = mediabox.height
        half_w = w / 2

        left_clip = fitz.Rect(0, 0, half_w, h)
        right_clip = fitz.Rect(half_w, 0, w, h)
        clip_rects = [left_clip, right_clip]

        # 创建源文档的完整拷贝，避免多次拷贝单个页面
        temp_src_doc = fitz.open()
        temp_src_doc.insert_pdf(src_doc)
        for page_num in range(len(temp_src_doc)):
            # 为每个页面创建一个临时拷贝（仅一次），然后为每个栏分别处理redaction
            temp_page_doc_base = fitz.open()
            temp_page_doc_base.insert_pdf(temp_src_doc, from_page=page_num, to_page=page_num)
            for clip_rect in clip_rects:
                # 由于redaction是破坏性的，为每个栏拷贝base
                temp_page_doc = fitz.open()
                temp_page_doc.insert_pdf(temp_page_doc_base)
                temp_page = temp_page_doc[0]
                _apply_redactions_outside_clip(temp_page, clip_rect)
                # 创建新页面：直接切分为上页（左栏）和下页（右栏）
                new_page = new_doc.new_page(width=clip_rect.width, height=clip_rect.height)
                new_page.show_pdf_page(new_page.rect, temp_page_doc, 0, clip=clip_rect)
                new_page.clean_contents()
                temp_page_doc.close()
            temp_page_doc_base.close()
        temp_src_doc.close()
        new_doc.save(output_path, garbage=4, deflate=True, clean=True, deflate_images=True, deflate_fonts=True)
        new_doc.close()
        src_doc.close()
        print(f"✅ 处理完成，新PDF保存为 {output_path}. 已移除隐藏文本，并优化文件大小。")

    def merge_pdf(self, input_path, output_path, dualFirst=True, engine="pdf2zh"):
        if len(fitz.open(input_path)) % 2 != 0:
            print(f"❌ [Zotero PDF2zh Server] merge_pdf Error: PDF page number is not even, merging skipped.")
            return None
        print(f"🐲 开始合并PDF: {input_path} 和 {output_path}")
        try:
            dual_pdf = fitz.open(input_path)
            output_pdf = fitz.open()
            for page_num in range(0, dual_pdf.page_count, 2):
                left_page = dual_pdf[page_num]
                right_page = dual_pdf[page_num+1]
                if engine=="pdf2zh" and dualFirst==True:
                    left_page = dual_pdf[page_num+1]
                    right_page = dual_pdf[page_num]
                # 获取页面尺寸
                left_rect = left_page.rect
                right_rect = right_page.rect
                # 创建新页面，宽度是双语页面的两倍（并排显示）
                new_page = output_pdf.new_page(width=(left_rect.width + right_rect.width), height=left_rect.height)
                # 将双语页面绘制在左侧
                if engine=="pdf2zh" and dualFirst==True:
                    new_page.show_pdf_page(fitz.Rect(0, 0, left_rect.width, left_rect.height), dual_pdf, page_num + 1)
                    new_page.show_pdf_page(fitz.Rect(left_rect.width, 0, left_rect.width + right_rect.width, right_rect.height), dual_pdf, page_num)
                else:
                    new_page.show_pdf_page(fitz.Rect(0, 0, left_rect.width, left_rect.height), dual_pdf, page_num)
                    new_page.show_pdf_page(fitz.Rect(left_rect.width, 0, left_rect.width + right_rect.width, right_rect.height), dual_pdf, page_num + 1)
            output_pdf.save(output_path, garbage=4, deflate=True)
            output_pdf.close()
            dual_pdf.close()
            print(f"🐲 合并成功，生成文件: {output_path}, 大小为: {os.path.getsize(output_path)/1024.0/1024.0:.2f} MB")
        except Exception as e:
            traceback.print_exc()
            print(f"❌ [Zotero PDF2zh Server] merge_pdf Error: {e}")
        return output_path