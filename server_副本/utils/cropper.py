import fitz
import os
import traceback
import shutil

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
    # 1. 临时文档处理原页，防止污染
    temp_doc = fitz.open()
    temp_doc.insert_pdf(src_doc, from_page=page_num, to_page=page_num)
    temp_page = temp_doc[0]

    # 2. 物理裁剪
    _apply_redactions_outside_clip(temp_page, clip_rect)

    # 3. 确定目标页面和位置
    if target_rect is None:
        # 创建新页面，大小等于裁剪框
        new_page = target_doc.new_page(width=clip_rect.width, height=clip_rect.height)
        dest_rect = new_page.rect
    else:
        # 使用当前最后一页
        new_page = target_doc[-1]
        dest_rect = target_rect

    # 4. 绘制 (show_pdf_page 会自动缩放内容以适应 dest_rect)
    new_page.show_pdf_page(dest_rect, temp_doc, 0, clip=clip_rect)

    if target_rect is None:
        new_page.clean_contents()

    temp_doc.close()

# --- 主类 ---

class Cropper():
    def __init__(self):
        pass

    def _get_clips(self, page, config):
        """计算左栏和右栏的裁剪矩形"""
        mediabox = page.mediabox
        w, h = mediabox.width, mediabox.height
        half_w = w / 2

        w_offset = config.pdf_w_offset
        h_offset = config.pdf_h_offset
        r = config.pdf_offset_ratio

        # 定义裁剪区域 (左栏 L, 右栏 R)
        left_clip = fitz.Rect(w_offset, h_offset, half_w + w_offset / r, h - h_offset)
        right_clip = fitz.Rect(half_w - w_offset / r, h_offset, w - w_offset, h - h_offset)

        return left_clip, right_clip, w, h

    def crop_pdf(self, config, input_pdf, infile_type, output_pdf, outfile_type):
        print(f"🐲 [Cropper] 开始裁剪PDF: {input_pdf} -> {output_pdf} (模式: {outfile_type})")
        try:
            with fitz.open(input_pdf) as src_doc, fitz.open() as new_doc:
                # --- 核心修改逻辑 Start ---
                # 判断是否为 LR_dual (左右对照) 格式
                is_LR_input = 'LR_dual' in input_pdf or (infile_type and 'LR' in infile_type)
                if is_LR_input:
                    print(f"🔄 检测到 LR_dual 输入，执行 Split (LR -> TB) 操作...")
                    self._process_LR_to_TB(src_doc, new_doc)
                # --- 核心修改逻辑 End ---

                else:
                    # 常规处理：计算裁剪区域
                    left_clip, right_clip, w, h = self._get_clips(src_doc[0], config)

                    # 根据目标类型分发处理逻辑
                    if outfile_type == 'mono-cut':
                        self._process_mono_cut(src_doc, new_doc, left_clip, right_clip)

                    elif outfile_type == 'dual-cut':
                        self._process_dual_cut(src_doc, new_doc, left_clip, right_clip, config)

                    elif outfile_type == 'crop-compare':
                        self._process_crop_compare(src_doc, new_doc, left_clip, right_clip, w, h, config)

                    elif outfile_type == 'origin-cut':
                        self._process_mono_cut(src_doc, new_doc, left_clip, right_clip)

                    else:
                        print(f"⚠️ 未知的裁剪模式: {outfile_type}")
                        return

                # 保存文件
                new_doc.save(output_pdf, garbage=4, deflate=True, clean=True)
                print(f"✅ 处理完成: {output_pdf}")

        except Exception as e:
            traceback.print_exc()

    # Mode: LR -> TB (将宽页拆分成两张窄页)
    # 输入: LR_dual (P1 = [Trans | Origin])
    # 输出: TB_dual (P1 = Trans, P2 = Origin)
    def _process_LR_to_TB(self, src_doc, new_doc):
        # 获取页面尺寸
        page = src_doc[0]
        w, h = page.rect.width, page.rect.height
        half_w = w / 2

        # 定义左半边和右半边的矩形
        rect_l = fitz.Rect(0, 0, half_w, h)
        rect_r = fitz.Rect(half_w, 0, w, h)

        for page_num in range(len(src_doc)):
            # 1. 提取左半边 (Trans) -> 新的一页
            _paste_clipped_page(new_doc, src_doc, page_num, rect_l)

            # 2. 提取右半边 (Origin) -> 新的一页
            _paste_clipped_page(new_doc, src_doc, page_num, rect_r)

    # Mode 1: mono-cut (一分为二，拼成长条)
    # Page 1 -> [P1-L, P1-R]
    def _process_mono_cut(self, src_doc, new_doc, left_clip, right_clip):
        for page_num in range(len(src_doc)):
            # 先左后右
            _paste_clipped_page(new_doc, src_doc, page_num, left_clip)
            _paste_clipped_page(new_doc, src_doc, page_num, right_clip)

    # Mode 2: dual-cut (双语交叉切割)
    # 输入: Dual PDF (TB模式，P1=Trans, P2=Origin)
    # 输出: [P1-L, P2-L, P1-R, P2-R] (左栏对照，右栏对照)
    def _process_dual_cut(self, src_doc, new_doc, left_clip, right_clip, config):
        if len(src_doc) % 2 != 0:
            print("⚠️ [Warning] dual-cut 模式输入页数不是偶数，最后一张可能被忽略。")

        for i in range(0, len(src_doc) // 2 * 2, 2):
            p_trans = i
            p_orig = i + 1

            # 1. Trans-Left
            _paste_clipped_page(new_doc, src_doc, p_trans, left_clip)
            # 2. Origin-Left
            _paste_clipped_page(new_doc, src_doc, p_orig, left_clip)
            # 3. Trans-Right
            _paste_clipped_page(new_doc, src_doc, p_trans, right_clip)
            # 4. Origin-Right
            _paste_clipped_page(new_doc, src_doc, p_orig, right_clip)

    # Mode 3: crop-compare (裁剪后拼接)
    # 输入: Dual PDF (TB模式, P1=Trans, P2=Origin)
    # 输出: 宽页
    def _process_crop_compare(self, src_doc, new_doc, left_clip, right_clip, w, h, config):
        h_offset = config.pdf_h_offset

        # 为了简单，我们创建一个原宽度的页面
        final_w = w
        final_h = left_clip.height

        for i in range(0, len(src_doc) // 2 * 2, 2):
            p_trans = i
            p_orig = i + 1

            # --- 新页 1: 左栏对照 (Trans-L + Orig-L) ---
            new_page_1 = new_doc.new_page(width=final_w, height=final_h)
            rect_left_half = fitz.Rect(0, 0, final_w/2, final_h)
            rect_right_half = fitz.Rect(final_w/2, 0, final_w, final_h)

            _paste_clipped_page(new_doc, src_doc, p_trans, left_clip, rect_left_half)
            _paste_clipped_page(new_doc, src_doc, p_orig, left_clip, rect_right_half)
            new_page_1.clean_contents()

            # --- 新页 2: 右栏对照 (Trans-R + Orig-R) ---
            new_page_2 = new_doc.new_page(width=final_w, height=final_h)

            _paste_clipped_page(new_doc, src_doc, p_trans, right_clip, rect_left_half)
            _paste_clipped_page(new_doc, src_doc, p_orig, right_clip, rect_right_half)
            new_page_2.clean_contents()

    # -----------------------------------------------------------
    # Merge / Compare (TB -> LR)
    # -----------------------------------------------------------
    def merge_pdf(self, input_path, output_path):
        """
        实现 'compare' 模式：将 TB_dual 转换为 LR_dual
        修复：奇数页时，最后一页单独放在左侧，右侧留白
        """
        print(f"🐲 开始合并(Compare): {input_path} -> {output_path}")
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

                    rect_left = fitz.Rect(0, 0, rect_trans.width, rect_trans.height)
                    # 右侧矩形从左侧宽度结束处开始
                    rect_right = fitz.Rect(rect_trans.width, 0, new_w, rect_orig.height)

                    new_page.show_pdf_page(rect_left, dual_pdf, p_trans_idx)
                    new_page.show_pdf_page(rect_right, dual_pdf, p_orig_idx)

                # --- 情况 2: 最后一页落单 (奇数页) ---
                else:
                    # 策略：为了阅读体验一致，依然创建双倍宽度的画布
                    # 左侧放内容，右侧留白
                    new_w = rect_trans.width * 2
                    new_h = rect_trans.height

                    new_page = output_pdf.new_page(width=new_w, height=new_h)

                    rect_left = fitz.Rect(0, 0, rect_trans.width, rect_trans.height)

                    new_page.show_pdf_page(rect_left, dual_pdf, p_trans_idx)
                    # print(f"ℹ️ 处理奇数尾页: 第 {p_trans_idx + 1} 页")

            output_pdf.save(output_path, garbage=4, deflate=True)
            print(f"✅ 合并成功: {output_path}")

            output_pdf.close()
            dual_pdf.close()
            return output_path
        except Exception as e:
            traceback.print_exc()
            return None

    # -----------------------------------------------------------
    # Split / Convert (LR -> TB) - 工具方法，保留以兼容外部调用
    # -----------------------------------------------------------
    def pdf_dual_mode(self, dual_path, from_mode, to_mode):
        """
        工具方法：在 LR (左右对照) 和 TB (上下对照) 之间转换
        """
        LR_dual_path = dual_path.replace('dual.pdf', 'LR_dual.pdf')
        TB_dual_path = dual_path.replace('dual.pdf', 'TB_dual.pdf')

        # TB -> LR
        if from_mode == 'TB' and to_mode == 'LR':
            if not os.path.exists(TB_dual_path) and os.path.exists(dual_path):
                shutil.copyfile(dual_path, TB_dual_path)
            self.merge_pdf(TB_dual_path, LR_dual_path)
            return LR_dual_path, TB_dual_path

        # LR -> TB
        elif from_mode == 'LR' and to_mode == 'TB':
            print(f"🐲 开始拆分(LR->TB): {LR_dual_path} -> {TB_dual_path}")
            if not os.path.exists(LR_dual_path) and os.path.exists(dual_path):
                shutil.copyfile(dual_path, LR_dual_path)

            src_doc = fitz.open(LR_dual_path)
            new_doc = fitz.open()

            # 使用新抽取的逻辑
            self._process_LR_to_TB(src_doc, new_doc)

            new_doc.save(TB_dual_path, garbage=4, deflate=True)
            new_doc.close()
            src_doc.close()
            print(f"✅ 拆分成功: {TB_dual_path}")
            return LR_dual_path, TB_dual_path

        return dual_path, dual_path
