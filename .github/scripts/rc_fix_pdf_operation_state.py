from pathlib import Path


def replace_between(text: str, start: str, end: str, replacement: str, *, name: str) -> str:
    start_pos = text.find(start)
    if start_pos < 0:
        raise SystemExit(f"{name}: start marker not found")
    end_pos = text.find(end, start_pos)
    if end_pos < 0:
        raise SystemExit(f"{name}: end marker not found")
    return text[:start_pos] + replacement + text[end_pos:]


# ---------------------------------------------------------------------------
# Cropper: LR/TB is an input layout, never an implicit replacement for the
# requested operation. Callers normalize LR -> TB explicitly when necessary.
# ---------------------------------------------------------------------------
cropper_path = Path("server/utils/cropper.py")
cropper = cropper_path.read_text(encoding="utf-8")

crop_pdf_impl = '''    def crop_pdf(self, config, input_pdf, infile_type, output_pdf, outfile_type):
        print(f"🐲 [Cropper] 开始裁剪PDF: {input_pdf} -> {output_pdf} (模式: {outfile_type})")
        try:
            with fitz.open(input_pdf) as src_doc, fitz.open() as new_doc:
                if len(src_doc) == 0:
                    raise ValueError("输入 PDF 没有页面")

                left_clip, right_clip, w, h = self._get_clips(src_doc[0], config)

                if outfile_type == 'mono-cut':
                    self._process_mono_cut(src_doc, new_doc, left_clip, right_clip)
                elif outfile_type == 'dual-cut':
                    self._process_dual_cut(src_doc, new_doc, left_clip, right_clip, config)
                elif outfile_type == 'crop-compare':
                    self._process_crop_compare(src_doc, new_doc, left_clip, right_clip, w, h, config)
                elif outfile_type == 'origin-cut':
                    self._process_mono_cut(src_doc, new_doc, left_clip, right_clip)
                else:
                    raise ValueError(f"未知的裁剪模式: {outfile_type}")

                if len(new_doc) == 0:
                    raise ValueError(f"PDF 处理没有生成页面: {outfile_type}")
                new_doc.save(output_pdf, garbage=4, deflate=True, clean=True)
                print(f"✅ 处理完成: {output_pdf}")
        except Exception:
            traceback.print_exc()
            raise

'''
cropper = replace_between(
    cropper,
    "    def crop_pdf(self, config, input_pdf, infile_type, output_pdf, outfile_type):\n",
    "    # Mode: LR -> TB",
    crop_pdf_impl,
    name="cropper.crop_pdf",
)

pdf_dual_mode_impl = '''    # -----------------------------------------------------------
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
'''
start = cropper.find("    # -----------------------------------------------------------\n    # Split / Convert (LR -> TB)")
if start < 0:
    raise SystemExit("cropper.pdf_dual_mode: start marker not found")
cropper = cropper[:start] + pdf_dual_mode_impl + "\n"
cropper_path.write_text(cropper, encoding="utf-8")


# ---------------------------------------------------------------------------
# Server: preserve LR/TB in generated filenames and normalize before derived
# operations. crop-compare/compare are terminal products.
# ---------------------------------------------------------------------------
server_path = Path("server/server.py")
server = server_path.read_text(encoding="utf-8")

translate_post = '''                # Canonicalize every pdf2zh_next dual output so later operations
                # can recover its layout even after the file is attached to Zotero
                # and uploaded again in a separate request.
                primary_dual_path = None
                LR_dual_path = None
                TB_dual_path = None
                if not config.no_dual:
                    primary_dual_path = self._canonicalize_pdf2zh_next_dual(dual_path, config.dual_mode)
                    if config.dual_mode == 'LR':
                        LR_dual_path = primary_dual_path
                        if config.dual_cut or config.crop_compare:
                            _, TB_dual_path = self.cropper.pdf_dual_mode(primary_dual_path, 'LR', 'TB')
                    else:
                        TB_dual_path = primary_dual_path

                    if config.dual:
                        fileList.append(primary_dual_path)

                if config.mono_cut:
                    mono_cut_path = self.get_filename_after_process(mono_path, 'mono-cut', engine)
                    self.cropper.crop_pdf(config, mono_path, 'mono', mono_cut_path, 'mono-cut')
                    addFileList(fileList, mono_cut_path)

                if config.dual_cut:
                    if not TB_dual_path:
                        raise ValueError("dual-cut 需要 TB dual 输入，但未能准备该布局。")
                    dual_cut_path = self.get_filename_after_process(TB_dual_path, 'dual-cut', engine)
                    self.cropper.crop_pdf(config, TB_dual_path, 'dual', dual_cut_path, 'dual-cut')
                    addFileList(fileList, dual_cut_path)

                if config.crop_compare:
                    if not TB_dual_path:
                        raise ValueError("crop-compare 需要 TB dual 输入，但未能准备该布局。")
                    crop_compare_path = self.get_filename_after_process(TB_dual_path, 'crop-compare', engine)
                    self.cropper.crop_pdf(config, TB_dual_path, 'dual', crop_compare_path, 'crop-compare')
                    addFileList(fileList, crop_compare_path)

                if config.compare:
                    if config.dual_mode == 'LR':
                        if not LR_dual_path:
                            raise ValueError("compare 需要 LR dual 输入，但未能准备该布局。")
                        compare_path = self.get_filename_after_process(LR_dual_path, 'compare', engine)
                        if os.path.exists(compare_path):
                            os.remove(compare_path)
                        shutil.copyfile(LR_dual_path, compare_path)
                        addFileList(fileList, compare_path)
                    else:
                        if not TB_dual_path:
                            raise ValueError("compare 需要 TB dual 输入，但未能准备该布局。")
                        compare_path = self.get_filename_after_process(TB_dual_path, 'compare', engine)
                        self.cropper.merge_pdf(TB_dual_path, compare_path)
                        addFileList(fileList, compare_path)
'''
server = replace_between(
    server,
    "                if config.dual_cut or config.crop_compare or config.compare:\n",
    "            else:\n                raise ValueError(f\"⚠️ [Zotero PDF2zh Server] 输入了不支持的翻译引擎",
    translate_post,
    name="server.translate pdf2zh_next postprocess",
)

crop_impl = '''    # 裁剪 /crop
    def crop(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)

            if infile_type == 'dual' and self.get_dual_mode(input_path, config.dual_mode) == 'LR':
                _, new_path = self.cropper.pdf_dual_mode(input_path, 'LR', 'TB')
                if os.path.exists(new_path):
                    return jsonify({'status': 'success', 'fileList': [os.path.basename(new_path)]}), 200
                return jsonify({'status': 'error', 'message': f'Crop LR->TB failed: {new_path} not found'}), 500

            new_type = self.get_filetype_after_crop(input_path)
            if new_type == 'unknown':
                return jsonify({
                    'status': 'error',
                    'errorType': 'InvalidPDFOperation',
                    'message': f'当前 PDF 类型 {infile_type} 不能再次执行裁剪。请选择原文、mono 或 dual 文件。'
                }), 400

            new_path = self.get_filename_after_process(input_path, new_type, config.engine)
            self.cropper.crop_pdf(config, input_path, infile_type, new_path, new_type)
            print(f"🔍 [Zotero PDF2zh Server] 开始裁剪文件: {input_path}, {infile_type}, 裁剪类型: {new_type}, {new_path}")

            if os.path.exists(new_path):
                return jsonify({'status': 'success', 'fileList': [os.path.basename(new_path)]}), 200
            return jsonify({'status': 'error', 'message': f'Crop failed: {new_path} not found'}), 500
        except Exception as e:
            return self._handle_exception(e, context='/crop')

'''
server = replace_between(
    server,
    "    # 裁剪 /crop\n    def crop(self):\n",
    "    def crop_compare(self):\n",
    crop_impl,
    name="server.crop",
)

crop_compare_impl = '''    def crop_compare(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)
            engine = config.engine

            if infile_type == 'crop-compare':
                return jsonify({
                    'status': 'error',
                    'errorType': 'InvalidPDFOperation',
                    'message': '该 PDF 已经是“裁剪后双语对照”结果，无需再次执行 crop-compare。请选择原文或 dual 附件。'
                }), 409

            if infile_type == 'origin':
                if engine == pdf2zh or engine != pdf2zh_next:
                    config.engine = 'pdf2zh'
                    fileList = self.translate_pdf(input_path, config)
                    input_path = fileList[1]
                    if not os.path.exists(input_path):
                        return jsonify({'status': 'error', 'message': f'Dual file not found: {input_path}'}), 500
                else:
                    # crop-compare internally requires alternating-page TB dual.
                    config.dual_mode = 'TB'
                    config.no_dual = False
                    config.no_mono = True
                    fileList = self.translate_pdf_next(input_path, config)
                    input_path = fileList[0]
                    if not os.path.exists(input_path):
                        return jsonify({'status': 'error', 'message': f'Dual file not found: {input_path}'}), 500

            infile_type = self.get_filetype(input_path)
            if infile_type == 'dual-cut':
                new_path = self.get_filename_after_process(input_path, 'crop-compare', engine)
                self.cropper.merge_pdf(input_path, new_path)
            elif infile_type == 'dual':
                source_path = input_path
                if self.get_dual_mode(input_path, config.dual_mode) == 'LR':
                    _, source_path = self.cropper.pdf_dual_mode(input_path, 'LR', 'TB')
                new_path = self.get_filename_after_process(input_path, 'crop-compare', engine)
                self.cropper.crop_pdf(config, source_path, 'dual', new_path, 'crop-compare')
            else:
                return jsonify({
                    'status': 'error',
                    'errorType': 'InvalidPDFOperation',
                    'message': f'当前 PDF 类型 {infile_type} 不能执行 crop-compare。请选择原文、dual 或 dual-cut 文件。'
                }), 400

            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                size = os.path.getsize(new_path)
                print(f"🐲 双语对照成功(裁剪后拼接), 生成文件: {fileName}, 大小为: {size/1024.0/1024.0:.2f} MB")
                return jsonify({'status': 'success', 'fileList': [fileName]}), 200
            return jsonify({'status': 'error', 'message': f'Crop-compare failed: {new_path} not found'}), 500
        except Exception as e:
            return self._handle_exception(e, context='/crop-compare')

'''
server = replace_between(
    server,
    "    def crop_compare(self):\n",
    "    # /compare\n",
    crop_compare_impl,
    name="server.crop_compare",
)

compare_impl = '''    # /compare
    def compare(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)
            engine = config.engine

            if infile_type == 'compare':
                return jsonify({
                    'status': 'error',
                    'errorType': 'InvalidPDFOperation',
                    'message': '该 PDF 已经是双语对照结果，无需再次执行 compare。请选择原文或 dual 附件。'
                }), 409

            if infile_type == 'origin':
                if engine == pdf2zh or engine != pdf2zh_next:
                    config.engine = 'pdf2zh'
                    fileList = self.translate_pdf(input_path, config)
                    input_path = fileList[1]
                    if not os.path.exists(input_path):
                        return jsonify({'status': 'error', 'message': f'Dual file not found: {input_path}'}), 500
                else:
                    config.dual_mode = 'LR'
                    config.no_dual = False
                    config.no_mono = True
                    fileList = self.translate_pdf_next(input_path, config)
                    dual_path = fileList[0]
                    if not os.path.exists(dual_path):
                        return jsonify({'status': 'error', 'message': f'Dual file not found: {dual_path}'}), 500
                    new_path = self.get_filename_after_process(input_path, 'compare', engine)
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(dual_path, new_path)
                    return jsonify({'status': 'success', 'fileList': [os.path.basename(new_path)]}), 200

            infile_type = self.get_filetype(input_path)
            if infile_type != 'dual':
                return jsonify({
                    'status': 'error',
                    'errorType': 'InvalidPDFOperation',
                    'message': f'当前 PDF 类型 {infile_type} 不能执行 compare。请选择原文或 dual 文件。'
                }), 400

            new_path = self.get_filename_after_process(input_path, 'compare', engine)
            if self.get_dual_mode(input_path, config.dual_mode) == 'LR':
                if os.path.exists(new_path):
                    os.remove(new_path)
                shutil.copyfile(input_path, new_path)
            else:
                self.cropper.merge_pdf(input_path, new_path)

            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                print(f"🐲 双语对照成功, 生成文件: {fileName}, 大小为: {os.path.getsize(new_path)/1024.0/1024.0:.2f} MB")
                return jsonify({'status': 'success', 'fileList': [fileName]}), 200
            return jsonify({'status': 'error', 'message': f'Compare failed: {new_path} not found'}), 500
        except Exception as e:
            return self._handle_exception(e, context='/compare')

'''
server = replace_between(
    server,
    "    # /compare\n    def compare(self):\n",
    "    def get_filetype(self, path):\n",
    compare_impl,
    name="server.compare",
)

filetype_impl = '''    def get_filetype(self, path):
        name = os.path.basename(str(path))
        # Check terminal/specific suffixes before generic dual/mono markers.
        if 'crop-compare.pdf' in name:
            return 'crop-compare'
        if 'dual-cut.pdf' in name:
            return 'dual-cut'
        if 'mono-cut.pdf' in name:
            return 'mono-cut'
        if 'compare.pdf' in name:
            return 'compare'
        if name.endswith('.LR_dual.pdf') or name.endswith('.TB_dual.pdf') or 'dual.pdf' in name:
            return 'dual'
        if 'mono.pdf' in name:
            return 'mono'
        if 'cut.pdf' in name:
            return 'origin-cut'
        return 'origin'

    def get_dual_mode(self, path, fallback='TB'):
        name = os.path.basename(str(path))
        if name.endswith('.LR_dual.pdf'):
            return 'LR'
        if name.endswith('.TB_dual.pdf'):
            return 'TB'
        mode = str(fallback or 'TB').upper()
        return mode if mode in {'LR', 'TB'} else 'TB'

    def _canonicalize_pdf2zh_next_dual(self, dual_path, mode):
        if not dual_path or not os.path.exists(dual_path):
            raise FileNotFoundError(f"Dual file not found: {dual_path}")
        mode = 'LR' if str(mode).upper() == 'LR' else 'TB'
        path = str(dual_path)
        if path.endswith('.LR_dual.pdf') or path.endswith('.TB_dual.pdf'):
            current = self.get_dual_mode(path)
            if current == mode:
                return path
            lr_path, tb_path = self.cropper.pdf_dual_mode(path, current, mode)
            return lr_path if mode == 'LR' else tb_path
        if path.endswith('.dual.pdf'):
            target = path[:-len('.dual.pdf')] + f'.{mode}_dual.pdf'
        else:
            target = path[:-4] + f'.{mode}_dual.pdf' if path.endswith('.pdf') else path + f'.{mode}_dual.pdf'
        if os.path.exists(target):
            os.remove(target)
        os.replace(path, target)
        return target

    def get_filetype_after_crop(self, path):
        filetype = self.get_filetype(path)
        print(f"🔍 [Zotero PDF2zh Server] 获取文件类型: {filetype} from {path}")
        if filetype == 'origin':
            return 'origin-cut'
        if filetype == 'mono':
            return 'mono-cut'
        if filetype == 'dual':
            return 'dual-cut'
        return 'unknown'

    def get_filetype_after_cropCompare(self, path):
        filetype = self.get_filetype(path)
        if filetype in {'origin', 'dual', 'dual-cut'}:
            return 'crop-compare'
        return 'unknown'

    def get_filetype_after_compare(self, path):
        filetype = self.get_filetype(path)
        if filetype in {'origin', 'dual'}:
            return 'compare'
        return 'unknown'

    def get_filename_after_process(self, inpath, outtype, engine):
        inpath = str(inpath)
        intype = self.get_filetype(inpath)
        if intype == 'dual':
            # Remove the layout marker from derived terminal products.
            for suffix in ('.LR_dual.pdf', '.TB_dual.pdf'):
                if inpath.endswith(suffix):
                    base = inpath[:-len(suffix)]
                    return base + (f'-{outtype}.pdf' if engine == pdf2zh else f'.{outtype}.pdf')

        if engine == pdf2zh or engine != pdf2zh_next:
            if intype == 'origin':
                if outtype == 'origin-cut':
                    return inpath.replace('.pdf', '-cut.pdf')
                return inpath.replace('.pdf', f'-{outtype}.pdf')
            return inpath.replace(f'{intype}.pdf', f'{outtype}.pdf')

        if intype == 'origin':
            if outtype == 'origin-cut':
                return inpath.replace('.pdf', '.cut.pdf')
            return inpath.replace('.pdf', f'.{outtype}.pdf')
        return inpath.replace(f'{intype}.pdf', f'{outtype}.pdf')

'''
server = replace_between(
    server,
    "    def get_filetype(self, path):\n",
    "    def translate_pdf(self, input_path, config, task_id=None):\n",
    filetype_impl,
    name="server.filetype helpers",
)
server_path.write_text(server, encoding="utf-8")


# ---------------------------------------------------------------------------
# Plugin: reject invalid state transitions before upload/request. This avoids
# ugly server errors and duplicate terminal attachments.
# ---------------------------------------------------------------------------
helper_path = Path("plugin/src/modules/pdf2zhHelper.ts")
helper = helper_path.read_text(encoding="utf-8")
if 'import { getString } from "../utils/locale";' not in helper:
    helper = helper.replace(
        'import { getPref } from "../utils/prefs";\n',
        'import { getPref } from "../utils/prefs";\nimport { getString } from "../utils/locale";\n',
        1,
    )

old_progress = '''        // 新增了显示处理进度窗口\n        const progressWindow = new ztoolkit.ProgressWindow(\n            "PDF处理",\n        ).createLine({\n            text: "正在处理PDF文件...",\n            type: "default",\n            progress: 0,\n        });\n        progressWindow.show();\n\n        const tasks: Array<{\n'''
if old_progress not in helper:
    raise SystemExit("pdf2zhHelper: progress block not found")
helper = helper.replace(old_progress, '        const tasks: Array<{\n', 1)

old_task = '''                const fileName = PathUtils.filename(filepath);\n                const config = this.getServerConfig();\n                tasks.push({\n'''
new_task = '''                const fileName = PathUtils.filename(filepath);\n                const inputType = this.getFileType(fileName);\n                const operationError = this.getOperationValidationError(\n                    endpoint,\n                    inputType,\n                );\n                if (operationError) {\n                    throw new Error(operationError);\n                }\n                const config = this.getServerConfig();\n                tasks.push({\n'''
if old_task not in helper:
    raise SystemExit("pdf2zhHelper: task block not found")
helper = helper.replace(old_task, new_task, 1)

marker = '''        const fileProcessor = FileProcessor.getInstance();\n'''
progress_after_validation = '''        if (tasks.length === 0) {\n            return;\n        }\n\n        const progressWindow = new ztoolkit.ProgressWindow(\n            getString("operation-progress-title"),\n        ).createLine({\n            text: getString("operation-progress-processing"),\n            type: "default",\n            progress: 0,\n        });\n        progressWindow.show();\n\n        const fileProcessor = FileProcessor.getInstance();\n'''
if marker not in helper:
    raise SystemExit("pdf2zhHelper: fileProcessor marker not found")
helper = helper.replace(marker, progress_after_validation, 1)

validation_method = '''    static getOperationValidationError(\n        endpoint: string,\n        inputType: string,\n    ): string | null {\n        const allowed: Record<string, string[]> = {\n            translate: [PDFType.ORIGIN],\n            crop: [PDFType.ORIGIN, PDFType.MONO, PDFType.DUAL],\n            compare: [PDFType.ORIGIN, PDFType.DUAL],\n            "crop-compare": [PDFType.ORIGIN, PDFType.DUAL, PDFType.DUAL_CUT],\n        };\n\n        if (endpoint === "crop-compare" && inputType === PDFType.CROP_COMPARE) {\n            return getString("operation-error-crop-compare-terminal");\n        }\n        if (endpoint === "compare" && inputType === PDFType.COMPARE) {\n            return getString("operation-error-compare-terminal");\n        }\n        const accepted = allowed[endpoint];\n        if (!accepted || accepted.includes(inputType)) {\n            return null;\n        }\n        const key =\n            endpoint === "translate"\n                ? "operation-error-translate"\n                : endpoint === "crop"\n                  ? "operation-error-crop"\n                  : endpoint === "compare"\n                    ? "operation-error-compare"\n                    : "operation-error-crop-compare";\n        return getString(key);\n    }\n\n'''
insert_marker = '    // 处理单个文件\n'
if insert_marker not in helper:
    raise SystemExit("pdf2zhHelper: method insertion marker not found")
helper = helper.replace(insert_marker, validation_method + insert_marker, 1)
helper_path.write_text(helper, encoding="utf-8")


# Locale messages for operation-state validation.
locale_additions = {
    Path("plugin/addon/locale/zh-CN/addon.ftl"): '''\n\noperation-progress-title = PDF处理\noperation-progress-processing = 正在处理PDF文件...\noperation-error-translate = “翻译 PDF”只支持原始 PDF。请选择原文附件或论文条目。\noperation-error-crop = 当前文件不能再次裁剪。请选择原文、mono 或 dual 附件。\noperation-error-compare = 当前文件不能执行“双语对照”。请选择原文或 dual 附件。\noperation-error-crop-compare = 当前文件不能执行“双语对照（裁剪）”。请选择原文、dual 或 dual-cut 附件。\noperation-error-crop-compare-terminal = 该 PDF 已经是“双语对照（裁剪）”结果，无需再次处理。请选择原文或 dual 附件。\noperation-error-compare-terminal = 该 PDF 已经是“双语对照”结果，无需再次处理。请选择原文或 dual 附件。\n''',
    Path("plugin/addon/locale/en-US/addon.ftl"): '''\n\noperation-progress-title = PDF Processing\noperation-progress-processing = Processing PDF...\noperation-error-translate = “Translate PDF” only accepts an original PDF. Select the original attachment or its parent item.\noperation-error-crop = This file cannot be cropped again. Select an original, mono, or dual attachment.\noperation-error-compare = This file cannot be used for Bilingual Compare. Select an original or dual attachment.\noperation-error-crop-compare = This file cannot be used for Cropped Bilingual Compare. Select an original, dual, or dual-cut attachment.\noperation-error-crop-compare-terminal = This PDF is already a Cropped Bilingual Compare result. Select the original or a dual attachment instead.\noperation-error-compare-terminal = This PDF is already a Bilingual Compare result. Select the original or a dual attachment instead.\n''',
}
for path, addition in locale_additions.items():
    text = path.read_text(encoding="utf-8")
    if "operation-error-crop-compare-terminal" not in text:
        text = text.rstrip() + addition + "\n"
        path.write_text(text, encoding="utf-8")
