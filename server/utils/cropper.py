import fitz
import os
import traceback
import shutil
import math

# --- 辅助函数 ---
def _apply_redactions_outside_clip(page, clip_rect):
    """
    物理删除 clip_rect 之外的内容 (Redaction)
    """
    page_rect = page.rect
    redact_rects = []

    # 找出上下左右四个需要删除的矩形区域
    if clip_rect.x0 > page_rect.x0:  # 左侧多余
        redact_rects.append(fitz.Rect(page_rect.x0, page_rect.y0, clip_rect.x0, page_rect.y1))
    if clip_rect.y0 > page_rect.y0:  # 上方多余
        redact_rects.append(fitz.Rect(page_rect.x0, page_rect.y0, page_rect.x1, clip_rect.y0))
    if clip_rect.x1 < page_rect.x1:  # 右侧多余
        redact_rects.append(fitz.Rect(clip_rect.x1, page_rect.y0, page_rect.x1, page_rect.y1))
    if clip_rect.y1 < page_rect.y1:  # 下方多余
        redact_rects.append(fitz.Rect(page_rect.x0, clip_rect.y1, page_rect.x1, page_rect.y1))

    for r_rect in redact_rects:
        page.add_redact_annot(r_rect, fill=None)

    page.apply_redactions(
        graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
        text=fitz.PDF_REDACT_TEXT_REMOVE
    )

def _paste_clipped_page(target_doc, src_doc, page_num, clip_rect, target_rect=None):
    """
    从源文档提取指定页面的 clip_rect 区域，并粘贴到目标文档。
    如果 target_rect 为 None，则创建新页面；
    如果 target_rect 有值，则绘制到目标文档最后一页的指定位置。
    """
    # Keep the source intact and release the temporary document on failure too.
    with fitz.open() as temp_doc:
        temp_doc.insert_pdf(src_doc, from_page=page_num, to_page=page_num)
        temp_page = temp_doc[0]
        if temp_page.rotation:
            temp_page.remove_rotation()
        _apply_redactions_outside_clip(temp_page, clip_rect)
        if target_rect is None:
            new_page = target_doc.new_page(width=clip_rect.width, height=clip_rect.height)
            dest_rect = new_page.rect
        else:
            new_page = target_doc[-1]
            dest_rect = target_rect
        # A blank input page is still a valid page to preserve.
        if temp_page.get_contents():
            new_page.show_pdf_page(dest_rect, temp_doc, 0, clip=clip_rect)
        if target_rect is None:
            new_page.clean_contents()

# --- 主类 ---

class Cropper():
    def __init__(self):
        pass

    def _get_clips(self, page, config):
        """计算左栏和右栏的裁剪矩形"""
        w, h = page.rect.width, page.rect.height
        half_w = w / 2

        w_offset = config.pdf_w_offset
        h_offset = config.pdf_h_offset
        r = config.pdf_offset_ratio

        if not all(math.isfinite(v) for v in (w_offset, h_offset, r)) or r <= 0 or w_offset < 0 or h_offset < 0:
            raise ValueError("裁剪边距必须为非负有限值，裁剪比例必须大于 0。")

        # 定义裁剪区域 (左栏 L, 右栏 R)
        left_clip = fitz.Rect(w_offset, h_offset, half_w + w_offset / r, h - h_offset)
        right_clip = fitz.Rect(half_w - w_offset / r, h_offset, w - w_offset, h - h_offset)

        left_clip &= page.rect
        right_clip &= page.rect
        if left_clip.is_empty or right_clip.is_empty:
            raise ValueError("裁剪边距超过页面尺寸，请减小裁剪边距。")
        return left_clip, right_clip, w, h

    def crop_pdf(self, config, input_pdf, infile_type, output_pdf, outfile_type):
        print(f"🐲 [Cropper] 开始裁剪PDF: {input_pdf} -> {output_pdf} (模式: {outfile_type})")
        try:
            with fitz.open(input_pdf) as src_doc, fitz.open() as new_doc:
                if len(src_doc) == 0:
                    raise ValueError("输入 PDF 没有页面")

                if outfile_type == 'mono-cut':
                    self._process_mono_cut(src_doc, new_doc, config)
                elif outfile_type == 'dual-cut':
                    self._process_dual_cut(src_doc, new_doc, config)
                elif outfile_type == 'crop-compare':
                    self._process_crop_compare(src_doc, new_doc, config)
                elif outfile_type == 'origin-cut':
                    self._process_mono_cut(src_doc, new_doc, config)
                else:
                    raise ValueError(f"未知的裁剪模式: {outfile_type}")

                if len(new_doc) == 0:
                    raise ValueError(f"PDF 处理没有生成页面: {outfile_type}")
                new_doc.save(output_pdf, garbage=4, deflate=True, clean=True)
                print(f"✅ 处理完成: {output_pdf}")
        except Exception:
            traceback.print_exc()
            raise

    # Mode: LR -> TB (将宽页拆分成两张窄页)
    # 输入: LR_dual (P1 = [Trans | Origin])
    # 输出: TB_dual (P1 = Trans, P2 = Origin)
    def _process_LR_to_TB(self, src_doc, new_doc):
        for page_num, page in enumerate(src_doc):
            w, h = page.rect.width, page.rect.height
            _paste_clipped_page(new_doc, src_doc, page_num, fitz.Rect(0, 0, w / 2, h))
            _paste_clipped_page(new_doc, src_doc, page_num, fitz.Rect(w / 2, 0, w, h))

    def _process_mono_cut(self, src_doc, new_doc, config):
        for page_num, page in enumerate(src_doc):
            for clip in self._get_clips(page, config)[:2]:
                _paste_clipped_page(new_doc, src_doc, page_num, clip)

    def _process_dual_cut(self, src_doc, new_doc, config):
        for i in range(0, len(src_doc), 2):
            pair = list(range(i, min(i + 2, len(src_doc))))
            clips = {p: self._get_clips(src_doc[p], config)[:2] for p in pair}
            for column in (0, 1):
                for p in pair:
                    _paste_clipped_page(new_doc, src_doc, p, clips[p][column])

    def _process_crop_compare(self, src_doc, new_doc, config):
        trans_first = getattr(config, 'trans_first', True)
        source_first = getattr(config, 'dual_source_trans_first', None)
        for i in range(0, len(src_doc), 2):
            pair = list(range(i, min(i + 2, len(src_doc))))
            # Preserve an unpaired trailing page on the left, matching compare.
            # Newly generated next-engine PDFs already encode their order.
            # Existing uploads have no reliable order metadata: preserve them.
            if len(pair) == 2 and source_first is not None and source_first != trans_first:
                pair.reverse()
            clips = {p: self._get_clips(src_doc[p], config) for p in pair}
            widths = [clips[p][2] / 2 for p in pair]
            if len(pair) == 1:
                widths.append(widths[0])
            final_h = max(clips[p][0].height for p in pair)
            for column in (0, 1):
                new_doc.new_page(width=sum(widths), height=final_h)
                x = 0
                for p, width in zip(pair, widths):
                    dest = fitz.Rect(x, 0, x + width, clips[p][column].height)
                    _paste_clipped_page(new_doc, src_doc, p, clips[p][column], dest)
                    x += width
                new_doc[-1].clean_contents()

    # -----------------------------------------------------------
    # Merge / Compare (TB -> LR)
    # -----------------------------------------------------------
    def merge_pdf(self, input_path, output_path, trans_first=True):
        """
        实现 'compare' 模式：将 TB_dual 转换为 LR_dual
        修复：奇数页时，最后一页单独放在左侧，右侧留白
        trans_first=False 时原文在左 (#290)。
        """
        print(f"🐲 开始合并(Compare): {input_path} -> {output_path}")
        dual_pdf = output_pdf = None
        try:
            dual_pdf = fitz.open(input_path)
            output_pdf = fitz.open()

            total_pages = len(dual_pdf)

            # 修改循环范围，确保能取到最后一页 (如果总数是5，range就是 0, 2, 4)
            for i in range(0, total_pages, 2):
                p_trans_idx = i
                p_orig_idx = i + 1

                page_trans = dual_pdf[p_trans_idx]
                rect_trans = page_trans.rect

                # --- 情况 1: 存在右侧页 (成对) ---
                if p_orig_idx < total_pages:
                    page_orig = dual_pdf[p_orig_idx]
                    rect_orig = page_orig.rect

                    new_w = rect_trans.width + rect_orig.width
                    new_h = max(rect_trans.height, rect_orig.height)

                    new_page = output_pdf.new_page(width=new_w, height=new_h)

                    p_left_idx = p_trans_idx if trans_first else p_orig_idx
                    p_right_idx = p_orig_idx if trans_first else p_trans_idx
                    left_size = dual_pdf[p_left_idx].rect
                    right_size = dual_pdf[p_right_idx].rect
                    rect_left = fitz.Rect(0, 0, left_size.width, left_size.height)
                    rect_right = fitz.Rect(left_size.width, 0, new_w, right_size.height)
                    if dual_pdf[p_left_idx].get_contents():
                        new_page.show_pdf_page(rect_left, dual_pdf, p_left_idx)
                    if dual_pdf[p_right_idx].get_contents():
                        new_page.show_pdf_page(rect_right, dual_pdf, p_right_idx)

                # --- 情况 2: 最后一页落单 (奇数页) ---
                else:
                    # 策略：为了阅读体验一致，依然创建双倍宽度的画布
                    # 左侧放内容，右侧留白
                    new_w = rect_trans.width * 2
                    new_h = rect_trans.height

                    new_page = output_pdf.new_page(width=new_w, height=new_h)

                    rect_left = fitz.Rect(0, 0, rect_trans.width, rect_trans.height)

                    if page_trans.get_contents():
                        new_page.show_pdf_page(rect_left, dual_pdf, p_trans_idx)
                    # print(f"ℹ️ 处理奇数尾页: 第 {p_trans_idx + 1} 页")

            output_pdf.save(output_path, garbage=4, deflate=True)
            print(f"✅ 合并成功: {output_path}")

            return output_path
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"PDF 合并失败: {input_path} -> {output_path}") from e
        finally:
            if output_pdf is not None:
                output_pdf.close()
            if dual_pdf is not None:
                dual_pdf.close()

    # -----------------------------------------------------------
    # Split / Convert (LR <-> TB)
    # -----------------------------------------------------------
    @staticmethod
    def _dual_variant_paths(dual_path):
        path = str(dual_path)
        for suffix in ('.LR_dual.pdf', '.TB_dual.pdf', '.dual.pdf'):
            if path.endswith(suffix):
                base = path[:-len(suffix)]
                break
        else:
            base, _ = os.path.splitext(path)
        return base + '.LR_dual.pdf', base + '.TB_dual.pdf'

    def pdf_dual_mode(self, dual_path, from_mode, to_mode):
        """Convert a pdf2zh_next dual file between LR and alternating-page TB.

        The input may already use the canonical ``.LR_dual.pdf`` or
        ``.TB_dual.pdf`` suffix.  Do not derive paths with a blind string
        replacement because that previously produced names such as
        ``.LR_LR_dual.pdf``.
        """
        from_mode = str(from_mode or '').upper()
        to_mode = str(to_mode or '').upper()
        LR_dual_path, TB_dual_path = self._dual_variant_paths(dual_path)

        if from_mode == to_mode:
            target = LR_dual_path if to_mode == 'LR' else TB_dual_path
            if os.path.abspath(str(dual_path)) != os.path.abspath(target):
                if os.path.exists(target):
                    os.remove(target)
                shutil.copyfile(dual_path, target)
            return LR_dual_path, TB_dual_path

        if from_mode == 'TB' and to_mode == 'LR':
            source = str(dual_path) if str(dual_path).endswith('.TB_dual.pdf') else TB_dual_path
            if not os.path.exists(source):
                if not os.path.exists(dual_path):
                    raise FileNotFoundError(f"TB dual 输入不存在: {dual_path}")
                if os.path.abspath(str(dual_path)) != os.path.abspath(TB_dual_path):
                    shutil.copyfile(dual_path, TB_dual_path)
                source = TB_dual_path
            self.merge_pdf(source, LR_dual_path)
            return LR_dual_path, TB_dual_path

        if from_mode == 'LR' and to_mode == 'TB':
            source = str(dual_path) if str(dual_path).endswith('.LR_dual.pdf') else LR_dual_path
            if not os.path.exists(source):
                if not os.path.exists(dual_path):
                    raise FileNotFoundError(f"LR dual 输入不存在: {dual_path}")
                if os.path.abspath(str(dual_path)) != os.path.abspath(LR_dual_path):
                    shutil.copyfile(dual_path, LR_dual_path)
                source = LR_dual_path

            print(f"🐲 开始拆分(LR->TB): {source} -> {TB_dual_path}")
            with fitz.open(source) as src_doc, fitz.open() as new_doc:
                self._process_LR_to_TB(src_doc, new_doc)
                if len(new_doc) == 0:
                    raise ValueError("LR -> TB 没有生成页面")
                if os.path.exists(TB_dual_path):
                    os.remove(TB_dual_path)
                new_doc.save(TB_dual_path, garbage=4, deflate=True)
            print(f"✅ 拆分成功: {TB_dual_path}")
            return LR_dual_path, TB_dual_path

        raise ValueError(f"不支持的 dual 布局转换: {from_mode} -> {to_mode}")

