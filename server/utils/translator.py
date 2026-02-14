## translator.py v3.0.36
# guaguastandup
# zotero-pdf2zh
import os
import re
import sys
import subprocess
import traceback
from collections import deque

from flask import Flask, request, jsonify, send_file
import base64
from pypdf import PdfReader

import runtime
from runtime import pdf2zh, pdf2zh_next, venv, __version__
from utils.venv import VirtualEnvManager
from utils.config import Config
from utils.cropper import Cropper

_VALUE_ERROR_RE = re.compile(r"(?m)^ValueError:\s*(?P<msg>.+)$")


def _make_hidden_startupinfo():
    """SW_HIDE startupinfo: the subprocess inherits a *hidden* console
    instead of having no console at all.  Child processes (e.g. joblib/loky)
    inherit the hidden console automatically — no black-window flashes."""
    if sys.platform != "win32":
        return None, {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si, {}


def _build_winexe_env():
    env = os.environ.copy()
    if os.name != "nt":
        return env

    # Avoid loky physical-core probes that may spawn transient PowerShell
    # windows on some bundled runtimes.
    if "LOKY_MAX_CPU_COUNT" not in env:
        logical_cores = os.cpu_count() or 1
        env["LOKY_MAX_CPU_COUNT"] = str(max(1, logical_cores - 1))
    return env


class PDFTranslator:
    def __init__(self, args):
        self.args = args
        self.app = Flask(__name__)
        if args.enable_venv:
            self.env_manager = VirtualEnvManager(
                runtime.config_path[venv],
                runtime.venv_name,
                args.env_tool,
                args.enable_mirror,
                args.skip_install,
                args.mirror_source,
            )
        self.cropper = Cropper()
        self.setup_routes()

    def setup_routes(self):
        self.app.add_url_rule(
            "/translate", "translate", self.translate, methods=["POST"]
        )
        self.app.add_url_rule("/crop", "crop", self.crop, methods=["POST"])
        self.app.add_url_rule(
            "/crop-compare", "crop-compare", self.crop_compare, methods=["POST"]
        )
        self.app.add_url_rule("/compare", "compare", self.compare, methods=["POST"])
        self.app.add_url_rule(
            "/translatedFile/<filename>", "download", self.download_file
        )
        self.app.add_url_rule("/health", "health", self.health_check, methods=["GET"])

    def health_check(self):
        args = self.args
        engine_ready = True
        if args.packaged_mode:
            engine_ready = bool(args.winexe_path and os.path.exists(args.winexe_path))
        return jsonify(
            {
                "status": "ok",
                "version": __version__,
                "message": "Zotero PDF2zh Server is running",
                "mode": runtime.runtime_mode_label(args),
                "engine_ready": engine_ready,
            }
        ), 200

    def process_request(self):
        data = request.get_json()
        config = Config(data)

        file_content = data.get("fileContent", "")
        if file_content.startswith("data:application/pdf;base64,"):
            file_content = file_content[len("data:application/pdf;base64,") :]

        input_path = os.path.join(runtime.output_folder, data["fileName"])
        with open(input_path, "wb") as f:
            f.write(base64.b64decode(file_content))

        return input_path, config

    def download_file(self, filename):
        try:
            base = os.path.abspath(runtime.output_folder)
            full = os.path.abspath(os.path.join(runtime.output_folder, filename))
            if os.path.commonpath([base, full]) != base:
                return jsonify({"status": "error", "message": "Invalid path"}), 400

            if os.path.exists(full):
                return send_file(full, as_attachment=True)
            return jsonify(
                {"status": "error", "message": f"File not found: {filename}"}
            ), 404
        except Exception as e:
            traceback.print_exc()
            return jsonify({"status": "error", "message": str(e)}), 500

    def translate(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)
            engine = config.engine
            args = self.args
            if infile_type != "origin":
                return jsonify(
                    {
                        "status": "error",
                        "message": "Input file must be an original PDF file.",
                    }
                ), 400
            if engine == pdf2zh:
                if args.packaged_mode:
                    return jsonify(
                        {
                            "status": "error",
                            "message": "packaged_full 模式当前仅支持 pdf2zh_next 引擎，请在插件中切换引擎。",
                        }
                    ), 400
                print("🔍 [Zotero PDF2zh Server] PDF2zh 开始翻译文件...")
                fileList = self.translate_pdf(input_path, config)
                mono_path, dual_path = fileList[0], fileList[1]
                if config.mono_cut:
                    mono_cut_path = self.get_filename_after_process(
                        mono_path, "mono-cut", engine
                    )
                    self.cropper.crop_pdf(
                        config,
                        mono_path,
                        "mono",
                        mono_cut_path,
                        "mono-cut",
                        dualFirst=config.trans_first,
                        engine=engine,
                    )
                    if os.path.exists(mono_cut_path):
                        fileList.append(mono_cut_path)
                if config.dual_cut:
                    dual_cut_path = self.get_filename_after_process(
                        dual_path, "dual-cut", engine
                    )
                    self.cropper.crop_pdf(
                        config,
                        dual_path,
                        "dual",
                        dual_cut_path,
                        "dual-cut",
                        dualFirst=config.trans_first,
                        engine=engine,
                    )
                    if os.path.exists(dual_cut_path):
                        fileList.append(dual_cut_path)
                if config.crop_compare:
                    crop_compare_path = self.get_filename_after_process(
                        dual_path, "crop-compare", engine
                    )
                    self.cropper.crop_pdf(
                        config,
                        dual_path,
                        "dual",
                        crop_compare_path,
                        "crop-compare",
                        dualFirst=config.trans_first,
                        engine=engine,
                    )
                    if os.path.exists(crop_compare_path):
                        fileList.append(crop_compare_path)
                if config.compare and config.babeldoc == False:
                    compare_path = self.get_filename_after_process(
                        dual_path, "compare", engine
                    )
                    self.cropper.merge_pdf(
                        dual_path,
                        compare_path,
                        dualFirst=config.trans_first,
                        engine=engine,
                    )
                    if os.path.exists(compare_path):
                        fileList.append(compare_path)

            elif engine == pdf2zh_next:
                print("🔍 [Zotero PDF2zh Server] PDF2zh_next 开始翻译文件...")
                if config.mono_cut or config.mono:
                    config.no_mono = False
                if (
                    config.dual
                    or config.dual_cut
                    or config.crop_compare
                    or config.compare
                ):
                    config.no_dual = False

                if config.no_dual and config.no_mono:
                    raise ValueError(
                        "⚠️ [Zotero PDF2zh Server] pdf2zh_next 引擎至少需要生成 mono 或 dual 文件, 请检查 no_dual 和 no_mono 配置项"
                    )

                fileList = []
                retList = self.translate_pdf_next(input_path, config)

                if config.no_mono:
                    dual_path = retList[0]
                elif config.no_dual:
                    mono_path = retList[0]
                    fileList.append(mono_path)
                else:
                    mono_path, dual_path = retList[0], retList[1]
                    fileList.append(mono_path)

                if config.dual_cut or config.crop_compare or config.compare:
                    LR_dual_path = dual_path.replace(".dual.pdf", ".LR_dual.pdf")
                    TB_dual_path = dual_path.replace(".dual.pdf", ".TB_dual.pdf")
                    if config.dual_mode == "LR":
                        self.cropper.pdf_dual_mode(dual_path, "LR", "TB")
                        if config.dual:
                            fileList.append(LR_dual_path)
                    elif config.dual_mode == "TB":
                        if os.path.exists(TB_dual_path):
                            os.remove(TB_dual_path)
                        os.rename(dual_path, TB_dual_path)
                        if config.dual:
                            fileList.append(TB_dual_path)
                elif config.dual:
                    fileList.append(dual_path)

                if config.mono_cut:
                    mono_cut_path = self.get_filename_after_process(
                        mono_path, "mono-cut", engine
                    )
                    self.cropper.crop_pdf(
                        config,
                        mono_path,
                        "mono",
                        mono_cut_path,
                        "mono-cut",
                        dualFirst=config.trans_first,
                        engine=engine,
                    )
                    if os.path.exists(mono_cut_path):
                        fileList.append(mono_cut_path)

                if config.dual_cut:
                    dual_cut_path = self.get_filename_after_process(
                        TB_dual_path, "dual-cut", engine
                    )
                    self.cropper.crop_pdf(
                        config,
                        TB_dual_path,
                        "dual",
                        dual_cut_path,
                        "dual-cut",
                        dualFirst=config.trans_first,
                        engine=engine,
                    )
                    if os.path.exists(dual_cut_path):
                        fileList.append(dual_cut_path)

                if config.crop_compare:
                    crop_compare_path = self.get_filename_after_process(
                        TB_dual_path, "crop-compare", engine
                    )
                    self.cropper.crop_pdf(
                        config,
                        TB_dual_path,
                        "dual",
                        crop_compare_path,
                        "crop-compare",
                        dualFirst=config.trans_first,
                        engine=engine,
                    )
                    if os.path.exists(crop_compare_path):
                        fileList.append(crop_compare_path)

                if config.compare:
                    if config.dual_mode == "TB":
                        compare_path = self.get_filename_after_process(
                            TB_dual_path, "compare", engine
                        )
                        self.cropper.merge_pdf(
                            TB_dual_path,
                            compare_path,
                            dualFirst=config.trans_first,
                            engine=engine,
                        )
                        if os.path.exists(compare_path):
                            fileList.append(compare_path)
                    else:
                        print("🐲 无需生成compare文件, 等同于dual文件(Left&Right)")
            else:
                raise ValueError(
                    f"⚠️ [Zotero PDF2zh Server] 输入了不支持的翻译引擎: {engine}, 目前脚本仅支持: pdf2zh/pdf2zh_next"
                )

            fileNameList = [os.path.basename(path) for path in fileList]
            existing = [p for p in fileList if os.path.exists(p)]
            missing = [p for p in fileList if not os.path.exists(p)]

            for m in missing:
                print(f"⚠️ 期望生成但不存在: {m}")
            for f in existing:
                size = os.path.getsize(f)
                print(
                    f"🐲 翻译成功, 生成文件: {f}, 大小为: {size / 1024.0 / 1024.0:.2f} MB"
                )

            if not existing:
                return jsonify(
                    {"status": "error", "message": "操作失败，请查看详细日志。"}
                ), 500

            fileNameList = [os.path.basename(p) for p in existing]
            return jsonify({"status": "success", "fileList": fileNameList}), 200
        except Exception as e:
            return self._handle_exception(e, context="/translate")

    def _handle_exception(self, exc, status_code=500, context=None):
        if context:
            print(f"⚠️ [Zotero PDF2zh Server] {context} Error: {exc}")
        else:
            print(f"⚠️ [Zotero PDF2zh Server] Error: {exc}")
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        info = self._derive_error_info(exc)
        payload = {
            "status": "error",
            "ok": False,
            "message": info["message"],
        }
        error_type = info.get("errorType")
        if error_type:
            payload["errorType"] = error_type
        if isinstance(exc, subprocess.CalledProcessError):
            payload["exitCode"] = exc.returncode
        return jsonify(payload), status_code

    def _derive_error_info(self, exc):
        parts = []
        if isinstance(exc, subprocess.CalledProcessError) and getattr(
            exc, "stderr", None
        ):
            parts.append(exc.stderr)
        formatted = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        if formatted:
            parts.append(formatted)
        blob = "\n".join(part for part in parts if part)

        ve_msg = self._extract_value_error(blob)
        if ve_msg:
            return {
                "errorType": "ValueError",
                "message": ve_msg,
            }

        def _tail_readable(text):
            lines = [ln.rstrip() for ln in text.splitlines()]
            for ln in reversed(lines):
                if not ln:
                    continue
                if ln.startswith(("Traceback", "File ")):
                    continue
                return ln
            return str(exc).strip() or exc.__class__.__name__

        fallback_message = (
            _tail_readable(blob)
            if blob
            else (str(exc).strip() or exc.__class__.__name__)
        )
        return {
            "errorType": exc.__class__.__name__,
            "message": fallback_message,
        }

    @staticmethod
    def _extract_value_error(blob):
        if not blob:
            return None
        if not isinstance(blob, str):
            blob = str(blob)

        matches = list(_VALUE_ERROR_RE.finditer(blob))
        if not matches:
            return None

        match = matches[-1]
        msg = match.group("msg").strip()

        tail_lines = []
        for line in blob[match.end() :].splitlines():
            if not line:
                break
            if line.startswith("Traceback") or _VALUE_ERROR_RE.match(line):
                break
            if line[:1] in (" ", "\t") or line.startswith("^"):
                tail_lines.append(line.strip())
            else:
                break

        if tail_lines:
            msg += " " + " ".join(tail_lines)

        return msg or None

    def crop(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)

            new_type = self.get_filetype_after_crop(input_path)
            if new_type == "unknown":
                return jsonify(
                    {
                        "status": "error",
                        "message": f"Input file is not valid PDF type {infile_type} for crop()",
                    }
                ), 400

            new_path = self.get_filename_after_process(
                input_path, new_type, config.engine
            )
            self.cropper.crop_pdf(
                config,
                input_path,
                infile_type,
                new_path,
                new_type,
                dualFirst=config.trans_first,
                engine=config.engine,
            )

            print(
                f"🔍 [Zotero PDF2zh Server] 开始裁剪文件: {input_path}, {infile_type}, 裁剪类型: {new_type}, {new_path}"
            )

            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                return jsonify({"status": "success", "fileList": [fileName]}), 200
            else:
                return jsonify(
                    {"status": "error", "message": f"Crop failed: {new_path} not found"}
                ), 500
        except Exception as e:
            return self._handle_exception(e, context="/crop")

    def crop_compare(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)
            engine = config.engine

            if infile_type == "origin":
                if engine == pdf2zh or engine != pdf2zh_next:
                    config.engine = "pdf2zh"
                    fileList = self.translate_pdf(input_path, config)
                    dual_path = fileList[1]
                    if not os.path.exists(dual_path):
                        return jsonify(
                            {
                                "status": "error",
                                "message": f"Unable to translate origin file, could not generate: {dual_path}",
                            }
                        ), 500
                    input_path = dual_path

                else:
                    config.dual_mode = "TB"
                    config.no_dual = False
                    config.no_mono = True
                    fileList = self.translate_pdf_next(input_path, config)
                    dual_path = fileList[0]
                    if not os.path.exists(dual_path):
                        return jsonify(
                            {
                                "status": "error",
                                "message": f"Dual file not found: {dual_path}",
                            }
                        ), 500
                    input_path = dual_path

            infile_type = self.get_filetype(input_path)
            new_type = self.get_filetype_after_cropCompare(input_path)
            if new_type == "unknown":
                return jsonify(
                    {
                        "status": "error",
                        "message": f"Input file is not valid PDF type {infile_type} for crop-compare()",
                    }
                ), 400

            new_path = self.get_filename_after_process(input_path, new_type, engine)
            if infile_type == "dual-cut":
                self.cropper.merge_pdf(
                    input_path, new_path, dualFirst=config.trans_first, engine=engine
                )
            else:
                new_path = self.get_filename_after_process(input_path, new_type, engine)
                self.cropper.crop_pdf(
                    config,
                    input_path,
                    infile_type,
                    new_path,
                    new_type,
                    dualFirst=config.trans_first,
                    engine=engine,
                )
            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                size = os.path.getsize(new_path)
                print(
                    f"🐲 双语对照成功(裁剪后拼接), 生成文件: {fileName}, 大小为: {size / 1024.0 / 1024.0:.2f} MB"
                )
                return jsonify({"status": "success", "fileList": [fileName]}), 200
            else:
                return jsonify(
                    {
                        "status": "error",
                        "message": f"Crop-compare failed: {new_path} not found",
                    }
                ), 500
        except Exception as e:
            return self._handle_exception(e, context="/crop-compare")

    def compare(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)
            engine = config.engine
            if infile_type == "origin":
                if engine == pdf2zh or engine != pdf2zh_next:
                    config.engine = "pdf2zh"
                    fileList = self.translate_pdf(input_path, config)
                    dual_path = fileList[1]
                    if not os.path.exists(dual_path):
                        return jsonify(
                            {
                                "status": "error",
                                "message": f"Dual file not found: {dual_path}",
                            }
                        ), 500
                    input_path = dual_path
                    infile_type = self.get_filetype(input_path)
                    new_type = self.get_filetype_after_compare(input_path)
                    if new_type == "unknown":
                        return jsonify(
                            {
                                "status": "error",
                                "message": f"Input file is not valid PDF type {infile_type} for compare()",
                            }
                        ), 400
                    new_path = self.get_filename_after_process(
                        input_path, new_type, engine
                    )
                    self.cropper.merge_pdf(
                        input_path,
                        new_path,
                        dualFirst=config.trans_first,
                        engine=engine,
                    )
                else:
                    config.dual_mode = "LR"
                    config.no_dual = False
                    config.no_mono = True
                    fileList = self.translate_pdf_next(input_path, config)
                    dual_path = fileList[0]
                    if not os.path.exists(dual_path):
                        return jsonify(
                            {
                                "status": "error",
                                "message": f"Dual file not found: {dual_path}",
                            }
                        ), 500
                    new_path = self.get_filename_after_process(
                        input_path, "compare", engine
                    )
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(dual_path, new_path)
            else:
                new_type = self.get_filetype_after_compare(input_path)
                if new_type == "unknown":
                    return jsonify(
                        {
                            "status": "error",
                            "message": f"Input file is not valid PDF type {infile_type} for compare()",
                        }
                    ), 400
                new_path = self.get_filename_after_process(input_path, new_type, engine)
                self.cropper.merge_pdf(
                    input_path, new_path, dualFirst=config.trans_first, engine=engine
                )
            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                print(
                    f"🐲 双语对照成功, 生成文件: {fileName}, 大小为: {os.path.getsize(new_path) / 1024.0 / 1024.0:.2f} MB"
                )
                return jsonify({"status": "success", "fileList": [fileName]}), 200
            else:
                return jsonify(
                    {
                        "status": "error",
                        "message": f"Compare failed: {new_path} not found",
                    }
                ), 500
        except Exception as e:
            return self._handle_exception(e, context="/compare")

    def get_filetype(self, path):
        if "mono.pdf" in path:
            return "mono"
        elif "dual.pdf" in path:
            return "dual"
        elif "dual-cut.pdf" in path:
            return "dual-cut"
        elif "mono-cut.pdf" in path:
            return "mono-cut"
        elif "crop-compare.pdf" in path:
            return "crop-compare"
        elif "compare.pdf" in path:
            return "compare"
        elif "cut.pdf" in path:
            return "origin-cut"
        return "origin"

    def get_filetype_after_crop(self, path):
        filetype = self.get_filetype(path)
        print(f"🔍 [Zotero PDF2zh Server] 获取文件类型: {filetype} from {path}")
        if filetype == "origin":
            return "origin-cut"
        elif filetype == "mono":
            return "mono-cut"
        elif filetype == "dual":
            return "dual-cut"
        return "unknown"

    def get_filetype_after_cropCompare(self, path):
        filetype = self.get_filetype(path)
        if filetype == "origin" or filetype == "dual" or filetype == "dual-cut":
            return "crop-compare"
        return "unknown"

    def get_filetype_after_compare(self, path):
        filetype = self.get_filetype(path)
        if filetype == "origin" or filetype == "dual":
            return "compare"
        return "unknown"

    def get_filename_after_process(self, inpath, outtype, engine):
        if engine == pdf2zh or engine != pdf2zh_next:
            intype = self.get_filetype(inpath)
            if intype == "origin":
                if outtype == "origin-cut":
                    return inpath.replace(".pdf", "-cut.pdf")
                return inpath.replace(".pdf", f"-{outtype}.pdf")
            return inpath.replace(f"{intype}.pdf", f"{outtype}.pdf")
        else:
            intype = self.get_filetype(inpath)
            if intype == "origin":
                if outtype == "origin-cut":
                    return inpath.replace(".pdf", ".cut.pdf")
                return inpath.replace(".pdf", f".{outtype}.pdf")
            return inpath.replace(f"{intype}.pdf", f"{outtype}.pdf")

    def translate_pdf(self, input_path, config):
        args = self.args
        config.update_config_file(runtime.config_path[pdf2zh])
        if config.targetLang == "zh-CN":
            config.targetLang = "zh"
        if config.sourceLang == "zh-CN":
            config.sourceLang = "zh"
        cmd = [
            pdf2zh,
            input_path,
            "--t",
            str(config.thread_num),
            "--output",
            str(runtime.output_folder),
            "--service",
            str(config.service),
            "--lang-in",
            str(config.sourceLang),
            "--lang-out",
            str(config.targetLang),
            "--config",
            str(runtime.config_path[pdf2zh]),
        ]

        if config.skip_last_pages and config.skip_last_pages > 0:
            end = len(PdfReader(input_path).pages) - config.skip_last_pages
            cmd.append("-p " + str(1) + "-" + str(end))
        if config.skip_font_subsets:
            cmd.append("--skip-subset-fonts")
        if config.babeldoc:
            print(
                "🔍 [Zotero PDF2zh Server] 不推荐使用pdf2zh 1.x + babeldoc, 如有需要，请考虑直接使用pdf2zh_next"
            )
            cmd.append("--babeldoc")
        try:
            if args.enable_venv:
                self.env_manager.execute_in_env(cmd)
            else:
                subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"⚠️ 翻译失败, 错误信息: {e}, 尝试跳过字体子集化, 重新渲染\n")
            cmd.append("--skip-subset-fonts")
            if args.enable_venv:
                self.env_manager.execute_in_env(cmd)
            else:
                subprocess.run(cmd, check=True)
        fileName = os.path.basename(input_path).replace(".pdf", "")
        if config.babeldoc:
            output_path_mono = os.path.join(
                runtime.output_folder, f"{fileName}.{config.targetLang}.mono.pdf"
            )
            output_path_dual = os.path.join(
                runtime.output_folder, f"{fileName}.{config.targetLang}.dual.pdf"
            )
        else:
            output_path_mono = os.path.join(
                runtime.output_folder, f"{fileName}-mono.pdf"
            )
            output_path_dual = os.path.join(
                runtime.output_folder, f"{fileName}-dual.pdf"
            )
        output_files = [output_path_mono, output_path_dual]
        for f in output_files:
            if not os.path.exists(f):
                print(f"⚠️ 未找到期望生成的文件: {f}")
                continue
            size = os.path.getsize(f)
            print(
                f"🐲 pdf2zh 翻译成功, 生成文件: {f}, 大小为: {size / 1024.0 / 1024.0:.2f} MB"
            )
        return output_files

    def translate_pdf_next(self, input_path, config):
        args = self.args
        service_map = {
            "ModelScope": "modelscope",
            "openailiked": "openaicompatible",
            "tencent": "tencentmechinetranslation",
            "silicon": "siliconflow",
            "qwen-mt": "qwenmt",
            "AliyunDashScope": "aliyundashscope",
        }
        if config.service in service_map:
            config.service = service_map[config.service]
        config.update_config_file(runtime.config_path[pdf2zh_next])

        cmd = [
            pdf2zh_next,
            input_path,
            "--" + config.service,
            "--qps",
            str(config.qps),
            "--output",
            str(runtime.output_folder),
            "--lang-in",
            str(config.sourceLang),
            "--lang-out",
            str(config.targetLang),
            "--config-file",
            str(runtime.config_path[pdf2zh_next]),
        ]
        if config.no_watermark:
            cmd.extend(["--watermark-output-mode", "no_watermark"])
        else:
            cmd.extend(["--watermark-output-mode", "watermarked"])
        if config.skip_last_pages and config.skip_last_pages > 0:
            end = len(PdfReader(input_path).pages) - config.skip_last_pages
            cmd.extend(["--pages", f"{1}-{end}"])
        if config.no_dual:
            cmd.append("--no-dual")
        if config.no_mono:
            cmd.append("--no-mono")
        if config.trans_first:
            cmd.append("--dual-translate-first")
        if config.skip_clean:
            cmd.append("--skip-clean")
        if config.disable_rich_text_translate:
            cmd.append("--disable-rich-text-translate")
        if config.enhance_compatibility:
            cmd.append("--enhance-compatibility")
        if config.save_auto_extracted_glossary:
            cmd.append("--save-auto-extracted-glossary")
        if config.disable_glossary:
            cmd.append("--no-auto-extract-glossary")
        if config.dual_mode == "TB":
            cmd.append("--use-alternating-pages-dual")
        if config.translate_table_text:
            cmd.append("--translate-table-text")
        if config.ocr:
            cmd.append("--ocr-workaround")
        if config.auto_ocr:
            cmd.append("--auto-enable-ocr-workaround")
        if config.font_family and config.font_family in [
            "serif",
            "sans-serif",
            "script",
        ]:
            cmd.extend(["--primary-font-family", config.font_family])
        if config.pool_size and config.pool_size > 1:
            cmd.extend(["--pool-max-worker", str(config.pool_size)])

        fileName = os.path.basename(input_path).replace(".pdf", "")
        no_watermark_mono = os.path.join(
            runtime.output_folder,
            f"{fileName}.no_watermark.{config.targetLang}.mono.pdf",
        )
        no_watermark_dual = os.path.join(
            runtime.output_folder,
            f"{fileName}.no_watermark.{config.targetLang}.dual.pdf",
        )
        watermark_mono = os.path.join(
            runtime.output_folder, f"{fileName}.{config.targetLang}.mono.pdf"
        )
        watermark_dual = os.path.join(
            runtime.output_folder, f"{fileName}.{config.targetLang}.dual.pdf"
        )

        output_path = []
        if config.no_watermark:
            if not config.no_mono:
                output_path.append(no_watermark_mono)
            if not config.no_dual:
                output_path.append(no_watermark_dual)
        else:
            if not config.no_mono:
                output_path.append(watermark_mono)
            if not config.no_dual:
                output_path.append(watermark_dual)

        if args.packaged_mode and not os.path.exists(args.winexe_path):
            raise FileNotFoundError(
                f"packaged_full 模式下未找到内置引擎: {args.winexe_path}"
            )

        if args.packaged_mode:
            args.winexe_attach_console = False

        if args.enable_winexe and os.path.exists(args.winexe_path):
            cmd = [f"{args.winexe_path}"] + cmd[1:]
            cmd = [
                os.path.normpath(arg)
                if os.path.isfile(arg) or os.path.isdir(arg)
                else arg
                for arg in cmd
            ]
            exe_dir = os.path.dirname(args.winexe_path)
            child_env = _build_winexe_env()

            print(f"🔧 [winexe] winexe_attach_console={args.winexe_attach_console}")

            if args.winexe_attach_console:
                print("🚀 [winexe] mode=attach-console")
                print(f"📁 [winexe] cwd={exe_dir}")

                safe_cmd = []
                for i, arg in enumerate(cmd):
                    if i > 0 and any(
                        sensitive in cmd[i - 1].lower()
                        for sensitive in ["key", "token", "secret", "password"]
                    ):
                        safe_cmd.append("***")
                    else:
                        safe_cmd.append(arg)
                print(f"⚡ [winexe] cmd={' '.join(safe_cmd)}")

                def quick_visibility_check():
                    try:
                        print("🔍 [预检] 检查exe输出可见性...")
                        test_cmd = [cmd[0], "--help"]
                        test_result = subprocess.run(
                            test_cmd,
                            shell=False,
                            cwd=exe_dir,
                            timeout=23,
                            capture_output=True,
                            text=True,
                        )

                        has_output = bool(
                            test_result.stdout.strip() or test_result.stderr.strip()
                        )

                        if not has_output:
                            print(
                                "\n⚠️ [预检结果] 23秒内未检测到控制台输出，可能为GUI/无控制台子系统或会自行新建控制台窗口"
                            )
                            print(
                                "   若需无黑窗 + 实时日志，建议使用console版exe或回到uv/venv"
                            )
                            print("   " + "=" * 60 + "\n")
                        else:
                            print(f"✅ [预检结果] 检测到控制台输出")

                        return has_output

                    except subprocess.TimeoutExpired:
                        print("\n⚠️ [预检结果] exe响应超时，可能为GUI程序")
                        print("   " + "=" * 60 + "\n")
                        return False
                    except Exception as e:
                        print(f"⚠️ [预检结果] 检查失败: {e}")
                        print("   " + "=" * 60 + "\n")
                        return False

                quick_visibility_check()

                print("🔍 [winexe] 开始执行（预期在当前终端显示实时日志）...")
                process = subprocess.Popen(
                    cmd,
                    shell=False,
                    cwd=exe_dir,
                    env=child_env,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )

                stderr_lines = []
                if process.stderr:
                    for line in process.stderr:
                        stderr_lines.append(line)
                        sys.stderr.write(line)
                        sys.stderr.flush()
                    process.stderr.close()

                return_code = process.wait()
                if return_code != 0:
                    stderr_text = "".join(stderr_lines)
                    value_error = self._extract_value_error(stderr_text)
                    if value_error:
                        raise ValueError(value_error)
                    print(f"❌ pdf2zh.exe 执行失败，退出码: {return_code}")
                    print("   操作失败，请查看详细日志。")
                    raise RuntimeError(f"pdf2zh.exe 执行失败，退出码: {return_code}")

            else:
                print("🔇 [winexe] mode=silent (hidden console)")
                si, extra_kwargs = _make_hidden_startupinfo()
                process = subprocess.Popen(
                    cmd,
                    shell=False,
                    cwd=exe_dir,
                    env=child_env,
                    startupinfo=si,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    **extra_kwargs,
                )
                output_tail = deque(maxlen=4000)
                if process.stdout:
                    for line in process.stdout:
                        output_tail.append(line)
                        sys.stdout.write(line)
                        sys.stdout.flush()
                    process.stdout.close()

                return_code = process.wait()
                output_text = "".join(output_tail)
                if return_code != 0:
                    value_error = self._extract_value_error(output_text)
                    if value_error:
                        raise ValueError(value_error)
                    raise RuntimeError(
                        f"pdf2zh.exe 退出码 {return_code}\noutput(tail):\n{output_text}"
                    )
        elif args.enable_venv:
            self.env_manager.execute_in_env(cmd)
        else:
            subprocess.run(cmd, check=True)
        existing = [p for p in output_path if os.path.exists(p)]

        for f in existing:
            size = os.path.getsize(f)
            print(
                f"🐲 pdf2zh_next 翻译成功, 生成文件: {f}, 大小为: {size / 1024.0 / 1024.0:.2f} MB"
            )

        if not existing:
            raise RuntimeError("操作失败，请查看详细日志。")

        return existing

    def run(self, port, debug=False):
        self.app.run(host="0.0.0.0", port=port, debug=debug)
