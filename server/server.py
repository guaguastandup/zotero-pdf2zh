## server.py v4.0.0
# guaguastandup
# zotero-pdf2zh
import os
from flask import Flask, request, jsonify, send_file, Response
import base64
import subprocess
import json, toml
import shutil
from pypdf import PdfReader
from utils.venv import VirtualEnvManager
from utils.config import Config
from utils.cropper import Cropper
import traceback
import argparse
import sys  # 用于退出脚本
import re   # 用于解析版本号和提取错误信息
import io
import socket  # 用于端口检查
import time    # 用于 SSE 推送间隔
import uuid    # 用于生成任务唯一标识
from datetime import datetime  # 用于记录任务开始/结束时间
# 导入自动更新模块
from utils.auto_update import check_for_updates, perform_update_optimized
# 导入任务管理器（用于 index.html 前端进度显示）
from utils.task_manager import task_manager
# 导入带进度解析的命令执行器
from utils.execute import execute_with_progress

_VALUE_ERROR_RE = re.compile(r'(?m)^ValueError:\s*(?P<msg>.+)$')

# 准备修改为4.0.0
__version__ = "4.0.3" 
update_log = "新增进度显示页面; 修复部分bug; 新增插件文档; 优化插件端项目配置等; 修复windows端终端进度条显示(暂不支持多任务进度显示), 优化html端"

############# config file #########
pdf2zh      = 'pdf2zh'
pdf2zh_next = 'pdf2zh_next'
venv        = 'venv' 

# TODO: 强制设置标准输出和标准错误的编码为 UTF-8
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Windows 下防止子进程弹出控制台窗口
if sys.platform == 'win32':
    CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    CREATE_NO_WINDOW = 0

# 所有系统: 获取当前脚本server.py所在的路径
root_path     = os.path.dirname(os.path.abspath(__file__))
config_folder = os.path.join(root_path, 'config')
output_folder = os.path.join(root_path, 'translated')
config_path = { # 配置文件路径
    pdf2zh:      os.path.join(config_folder, 'config.json'),
    pdf2zh_next: os.path.join(config_folder, 'config.toml'),
    venv:        os.path.join(config_folder, 'venv.json'),
}

######### venv config #########
venv_name = { # venv名称
    pdf2zh:      'zotero-pdf2zh-venv',
    pdf2zh_next: 'zotero-pdf2zh-next-venv',
}

default_env_tool = 'uv' # 默认使用uv管理venv
enable_venv = True

PORT = 8890     # 默认端口号
class PDFTranslator:
    def __init__(self, args):
        self.app = Flask(__name__)
        if args.enable_venv:
            self.env_manager = VirtualEnvManager(config_path[venv], venv_name, args.env_tool, args.enable_mirror, args.skip_install, args.mirror_source)
        self.cropper = Cropper()
        self.setup_routes()

    def setup_routes(self):
        # 新增：首页路由 - 提供 index.html 前端进度监控页面
        self.app.add_url_rule('/', 'index', self.index)

        self.app.add_url_rule('/translate', 'translate', self.translate, methods=['POST'])
        self.app.add_url_rule('/crop', 'crop', self.crop, methods=['POST'])
        self.app.add_url_rule('/crop-compare', 'crop-compare', self.crop_compare, methods=['POST'])
        self.app.add_url_rule('/compare', 'compare', self.compare, methods=['POST'])
        self.app.add_url_rule('/translatedFile/<filename>', 'download', self.download_file)

        # 新增：健康检查端点 - 用于检查服务器状态
        self.app.add_url_rule('/health', 'health', self.health_check)
        # 新增：SSE 端点 - 实时推送翻译进度给 index.html 前端
        self.app.add_url_rule('/events', 'events', self.events)
        # 新增：历史记录 API - 供 index.html 前端获取翻译历史
        self.app.add_url_rule('/api/history', 'history', self.get_history)
        # 新增：配置信息 API - 供 index.html 前端显示当前服务配置
        self.app.add_url_rule('/api/config', 'config', self.get_config)
        # 新增：favicon 路由
        self.app.add_url_rule('/favicon.svg', 'favicon', self.favicon)
        # 新增：提示音音频路由
        self.app.add_url_rule('/bo.mp3', 'notification_sound', self.notification_sound)

    ##################################################################
    # 健康检查端点 /health - 检查服务器状态
    # 返回JSON格式的服务器状态信息，包括状态码、版本号和消息
    ##################################################################
    def health_check(self):
        return jsonify({
            'status': 'ok',
            'version': __version__,
            'message': 'PDF2zh Server is running'
        }), 200

    ##################################################################
    # 首页路由 / - 提供 index.html 前端进度监控页面
    ##################################################################
    def index(self):
        try:
            index_path = os.path.join(root_path, 'index.html')
            if os.path.exists(index_path):
                return send_file(index_path)
            else:
                return jsonify({'status': 'error', 'message': 'index.html not found'}), 404
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    ##################################################################
    # SSE (Server-Sent Events) 端点 /events - 实时推送翻译进度给前端
    # index.html 通过 EventSource('/events') 接收数据
    ##################################################################
    def events(self):
        def generate():
            while True:
                try:
                    tasks_data = {
                        'type': 'tasks',
                        'data': task_manager.get_active_tasks_list()
                    }
                    yield f"data: {json.dumps(tasks_data)}\n\n"
                    time.sleep(1)  # 每秒推送一次
                except GeneratorExit:
                    break
        return Response(generate(), mimetype='text/event-stream')

    ##################################################################
    # 历史记录 API /api/history - 供 index.html 前端获取翻译历史
    ##################################################################
    def get_history(self):
        return jsonify({'status': 'success', 'history': task_manager.get_history()})

    ##################################################################
    # 配置信息 API /api/config - 供 index.html 前端显示当前服务配置
    ##################################################################
    def get_config(self):
        config_info = {
            'version': __version__,
            'port': args.port,
            'enable_venv': args.enable_venv,
            'env_tool': args.env_tool,
            'enable_mirror': args.enable_mirror,
            'mirror_source': args.mirror_source if args.enable_mirror else '-',
            'skip_install': args.skip_install,
            'enable_winexe': args.enable_winexe,
        }
        return jsonify({'status': 'success', 'config': config_info})

    ##################################################################
    # Favicon 路由
    ##################################################################
    def favicon(self):
        favicon_path = os.path.join(root_path, 'favicon.svg')
        if os.path.exists(favicon_path):
            return send_file(favicon_path, mimetype='image/svg+xml')
        return '', 404

    ##################################################################
    # 提示音音频路由
    ##################################################################
    def notification_sound(self):
        sound_path = os.path.join(root_path, 'bo.mp3')
        if os.path.exists(sound_path):
            return send_file(sound_path, mimetype='audio/mpeg')
        return '', 404

    ##################################################################
    def process_request(self):
        data = request.get_json() # 获取请求的data
        config = Config(data)
        
        file_content = data.get('fileContent', '')
        if file_content.startswith('data:application/pdf;base64,'):
            file_content = file_content[len('data:application/pdf;base64,'):]

        input_path = os.path.join(output_folder, data['fileName'])
        with open(input_path, 'wb') as f:
            f.write(base64.b64decode(file_content))
        
        # input_path表示保存的pdf源文件路径
        return input_path, config

    # 下载文件 /translatedFile/<filename>
    # 支持 ?preview=true 参数用于 index.html 的在线预览功能
    def download_file(self, filename):
        try:
            base = os.path.abspath(output_folder)
            full = os.path.abspath(os.path.join(output_folder, filename))
            # 防止目录穿越
            if os.path.commonpath([base, full]) != base:
                return jsonify({'status': 'error', 'message': 'Invalid path'}), 400

            if os.path.exists(full):
                # 如果 preview=true，则以内联方式返回（用于浏览器内预览）
                is_preview = request.args.get('preview') == 'true'
                return send_file(full, as_attachment=not is_preview)
            # 新增：不存在时明确返回 404，而不是什么都不返回
            return jsonify({'status': 'error', 'message': f'File not found: {filename}'}), 404
        except Exception as e:
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    ############################# 核心逻辑 #############################
    # 翻译 /translate
    def translate(self):
        # 生成任务ID并记录开始时间（用于 index.html 前端进度显示）
        task_id = str(uuid.uuid4())
        start_time = datetime.now()

        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)
            engine = config.engine

            # 构建当前翻译的配置摘要（供 index.html 前端展示，不含敏感信息）
            output_types = []
            if config.mono: output_types.append('mono')
            if config.dual: output_types.append('dual')
            if config.mono_cut: output_types.append('mono-cut')
            if config.dual_cut: output_types.append('dual-cut')
            if config.compare: output_types.append('compare')
            if config.crop_compare: output_types.append('crop-compare')
            config_summary = {
                'sourceLang': config.sourceLang,
                'targetLang': config.targetLang,
                'outputTypes': output_types,
            }
            if engine == pdf2zh:
                config_summary['threadNum'] = config.thread_num
                config_summary['babeldoc'] = config.babeldoc
            elif engine == pdf2zh_next:
                config_summary['qps'] = config.qps
                config_summary['dualMode'] = config.dual_mode  # LR/LT 模式
                config_summary['noWatermark'] = config.no_watermark
                config_summary['ocr'] = config.ocr or config.auto_ocr
                config_summary['poolSize'] = config.pool_size

            # 添加通用配置参数
            if config.skip_last_pages and config.skip_last_pages > 0:
                config_summary['skipLastPages'] = config.skip_last_pages
            if config.no_watermark:
                config_summary['noWatermark'] = config.no_watermark

            # 注册任务到 task_manager（前端通过 SSE /events 接收此数据）
            # 获取模型名称，对于免费服务使用友好的显示名称
            model_name = config.llm_api.get('model', '')
            service = config.service

            # 为免费服务设置友好的显示名称
            if not model_name or model_name == '':
                if service == 'siliconflowfree':
                    model_name = 'siliconflowfree (免费服务)'
                elif service == 'bing':
                    model_name = 'Bing 翻译'
                elif service == 'google':
                    model_name = 'Google 翻译'
                else:
                    model_name = f'{service} (默认模型)'

            task_manager.add_task(task_id, {
                'taskId': task_id,
                'active': True,
                'fileName': os.path.basename(input_path),
                'engine': engine,
                'service': config.service,
                'modelName': model_name,  # 添加模型名称
                'startTime': start_time.isoformat(),
                'progress': 0,
                'status': '开始翻译',
                'message': '正在初始化...',
                'config': config_summary
            })

            # 辅助函数：仅当文件存在时添加到列表
            def addFileList(fileList, filePath):
                if os.path.exists(filePath):
                    fileList.append(filePath)

            if infile_type != 'origin':
                return jsonify({'status': 'error', 'message': 'Input file must be an original PDF file.'}), 400
            if engine == pdf2zh:
                print("🔍 [Zotero PDF2zh Server] PDF2zh 开始翻译文件...")
                fileList = self.translate_pdf(input_path, config, task_id)
                mono_path, dual_path = fileList[0], fileList[1]
                if config.mono_cut:
                    mono_cut_path = self.get_filename_after_process(mono_path, 'mono-cut', engine)
                    self.cropper.crop_pdf(config, mono_path, 'mono', mono_cut_path, 'mono-cut')
                    addFileList(fileList, mono_cut_path)
                if config.dual_cut:
                    dual_cut_path = self.get_filename_after_process(dual_path, 'dual-cut', engine)
                    self.cropper.crop_pdf(config, dual_path, 'dual', dual_cut_path, 'dual-cut')
                    addFileList(fileList, dual_cut_path)
                if config.crop_compare:
                    crop_compare_path = self.get_filename_after_process(dual_path, 'crop-compare', engine)
                    self.cropper.crop_pdf(config, dual_path, 'dual', crop_compare_path, 'crop-compare')
                    addFileList(fileList, crop_compare_path)
                if config.compare and config.babeldoc == False: # babeldoc不支持compare
                    compare_path = self.get_filename_after_process(dual_path, 'compare', engine)
                    self.cropper.merge_pdf(dual_path, compare_path)
                    addFileList(fileList, compare_path)
                
            elif engine == pdf2zh_next:
                print("🔍 [Zotero PDF2zh Server] PDF2zh_next 开始翻译文件...")
                if config.mono_cut or config.mono:
                    config.no_mono = False
                if config.dual or config.dual_cut or config.crop_compare or config.compare:
                    config.no_dual = False

                if config.no_dual and config.no_mono:
                    raise ValueError("⚠️ [Zotero PDF2zh Server] pdf2zh_next 引擎至少需要生成 mono 或 dual 文件, 请检查 no_dual 和 no_mono 配置项")

                fileList = []
                retList = self.translate_pdf_next(input_path, config, task_id)

                if config.no_mono:
                    dual_path = retList[0]
                elif config.no_dual:
                    mono_path = retList[0]
                    fileList.append(mono_path)
                else:
                    mono_path, dual_path = retList[0], retList[1]
                    fileList.append(mono_path)
                
                if config.dual_cut or config.crop_compare or config.compare:
                    LR_dual_path = dual_path.replace('.dual.pdf', '.LR_dual.pdf')
                    TB_dual_path = dual_path.replace('.dual.pdf', '.TB_dual.pdf')
                    if config.dual_mode == 'LR':
                        self.cropper.pdf_dual_mode(dual_path, 'LR', 'TB')
                        if config.dual:
                            fileList.append(LR_dual_path)
                    elif config.dual_mode == 'TB':
                        if os.path.exists(TB_dual_path):
                            os.remove(TB_dual_path)
                        os.rename(dual_path, TB_dual_path)
                        if config.dual:
                            fileList.append(TB_dual_path)
                elif config.dual:
                    fileList.append(dual_path)

                if config.mono_cut:
                    mono_cut_path = self.get_filename_after_process(mono_path, 'mono-cut', engine)
                    self.cropper.crop_pdf(config, mono_path, 'mono', mono_cut_path, 'mono-cut')
                    addFileList(fileList, mono_cut_path)

                if config.dual_cut: # use TB_dual_path
                    dual_cut_path = self.get_filename_after_process(TB_dual_path, 'dual-cut', engine)
                    self.cropper.crop_pdf(config, TB_dual_path, 'dual', dual_cut_path, 'dual-cut')
                    addFileList(fileList, dual_cut_path)

                if config.crop_compare: # use TB_dual_path
                    crop_compare_path = self.get_filename_after_process(TB_dual_path, 'crop-compare', engine)
                    self.cropper.crop_pdf(config, TB_dual_path, 'dual', crop_compare_path, 'crop-compare')
                    addFileList(fileList, crop_compare_path)

                if config.compare: # use TB_dual_path
                    if config.dual_mode == 'TB':
                        compare_path = self.get_filename_after_process(TB_dual_path, 'compare', engine)
                        self.cropper.merge_pdf(TB_dual_path, compare_path)
                        addFileList(fileList, compare_path)
                    else:
                        print("🐲 无需生成compare文件, 等同于dual文件(Left&Right)")
            else:
                raise ValueError(f"⚠️ [Zotero PDF2zh Server] 输入了不支持的翻译引擎: {engine}, 目前脚本仅支持: pdf2zh/pdf2zh_next")
            
            fileNameList = [os.path.basename(path) for path in fileList]
            existing = [p for p in fileList if os.path.exists(p)]
            missing  = [p for p in fileList if not os.path.exists(p)]

            for m in missing:
                print(f"⚠️ 期望生成但不存在: {m}")
            for f in existing:
                size = os.path.getsize(f)
                print(f"🐲 翻译成功, 生成文件: {f}, 大小为: {size/1024.0/1024.0:.2f} MB")

            if not existing:
                # 更新任务状态为失败（前端会显示失败状态）
                task_manager.complete_task(task_id, 'failed', '操作失败，请查看详细日志。', error='无文件生成')
                return jsonify({'status': 'error', 'message': '操作失败，请查看详细日志。'}), 500

            fileNameList = [os.path.basename(p) for p in existing]
            # 更新任务状态为成功（前端会显示成功状态和生成的文件列表）
            task_manager.complete_task(
                task_id,
                'success',
                f'成功生成 {len(existing)} 个文件',
                file_list=fileNameList
            )
            return jsonify({'status': 'success', 'fileList': fileNameList}), 200
        except Exception as e:
            # 更新任务状态为失败
            task_manager.complete_task(task_id, 'failed', str(e), error=str(e))
            return self._handle_exception(e, context='/translate')

    def _handle_exception(self, exc, status_code=500, context=None):
        if context:
            print(f"⚠️ [Zotero PDF2zh Server] {context} Error: {exc}")
        else:
            print(f"⚠️ [Zotero PDF2zh Server] Error: {exc}")
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        info = self._derive_error_info(exc)
        payload = {
            'status': 'error',
            'ok': False,
            'message': info['message'],
        }
        error_type = info.get('errorType')
        if error_type:
            payload['errorType'] = error_type
        if isinstance(exc, subprocess.CalledProcessError):
            payload['exitCode'] = exc.returncode
        return jsonify(payload), status_code

    def _derive_error_info(self, exc):
        parts = []
        if isinstance(exc, subprocess.CalledProcessError) and getattr(exc, 'stderr', None):
            parts.append(exc.stderr)
        formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if formatted:
            parts.append(formatted)
        blob = '\n'.join(part for part in parts if part)

        ve_msg = self._extract_value_error(blob)
        if ve_msg:
            return {
                'errorType': 'ValueError',
                'message': ve_msg,
            }

        def _tail_readable(text):
            lines = [ln.rstrip() for ln in text.splitlines()]
            for ln in reversed(lines):
                if not ln:
                    continue
                if ln.startswith(('Traceback', 'File ')):
                    continue
                return ln
            return str(exc).strip() or exc.__class__.__name__

        fallback_message = _tail_readable(blob) if blob else (str(exc).strip() or exc.__class__.__name__)
        return {
            'errorType': exc.__class__.__name__,
            'message': fallback_message,
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
        msg = match.group('msg').strip()

        tail_lines = []
        for line in blob[match.end():].splitlines():
            if not line:
                break
            if line.startswith('Traceback') or _VALUE_ERROR_RE.match(line):
                break
            if line[:1] in (' ', '\t') or line.startswith('^'):
                tail_lines.append(line.strip())
            else:
                break

        if tail_lines:
            msg += ' ' + ' '.join(tail_lines)

        return msg or None

    # 裁剪 /crop
    def crop(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)

            # --- 优化 LR_dual 处理逻辑 (Start) ---
            # 如果输入文件名包含 LR_dual.pdf，强制视为 LR -> TB 的转换请求
            # 输出类型应保持为 'dual' (具体为 TB_dual)，而不是 'dual-cut'
            if 'LR_dual.pdf' in input_path:
                infile_type = 'LR_dual'
                new_type = 'dual' # 逻辑上依然是dual，只是变成了TB排版
                new_path = input_path.replace('LR_dual.pdf', 'TB_dual.pdf')

                print(f"🔍 [Zotero PDF2zh Server] 检测到 LR_dual 输入，执行 Split (LR -> TB) 操作: {input_path} -> {new_path}")

                # 调用 cropper (cropper内已包含针对 LR_dual 的检测逻辑，会执行 Split 操作)
                self.cropper.crop_pdf(config, input_path, infile_type, new_path, new_type)

                if os.path.exists(new_path):
                    fileName = os.path.basename(new_path)
                    return jsonify({'status': 'success', 'fileList': [fileName]}), 200
                else:
                    return jsonify({'status': 'error', 'message': f'Crop LR->TB failed: {new_path} not found'}), 500
            # --- 优化 LR_dual 处理逻辑 (End) ---

            # 常规逻辑 (mono -> mono-cut, dual -> dual-cut 等)
            new_type = self.get_filetype_after_crop(input_path)
            if new_type == 'unknown':
                return jsonify({'status': 'error', 'message': f'Input file is not valid PDF type {infile_type} for crop()'}), 400

            new_path = self.get_filename_after_process(input_path, new_type, config.engine)
            self.cropper.crop_pdf(config, input_path, infile_type, new_path, new_type)

            print(f"🔍 [Zotero PDF2zh Server] 开始裁剪文件: {input_path}, {infile_type}, 裁剪类型: {new_type}, {new_path}")

            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                return jsonify({'status': 'success', 'fileList': [fileName]}), 200
            else:
                return jsonify({'status': 'error', 'message': f'Crop failed: {new_path} not found'}), 500
        except Exception as e:
            return self._handle_exception(e, context='/crop')

    def crop_compare(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)
            engine = config.engine

            if infile_type == 'origin':
                if engine == pdf2zh or engine != pdf2zh_next: # 默认为pdf2zh
                    config.engine = 'pdf2zh'
                    fileList = self.translate_pdf(input_path, config)
                    dual_path = fileList[1] # 会生成mono和dual文件
                    if not os.path.exists(dual_path):
                        return jsonify({'status': 'error', 'message': f'Unable to translate origin file, could not generate: {dual_path}'}), 500
                    input_path = dual_path # crop_compare输入的是dual路径的文件

                else: # pdf2zh_next
                    config.dual_mode = 'TB'
                    config.no_dual = False
                    config.no_mono = True
                    fileList = self.translate_pdf_next(input_path, config)
                    dual_path = fileList[0] # 仅生成dual文件
                    if not os.path.exists(dual_path):
                        return jsonify({'status': 'error', 'message': f'Dual file not found: {dual_path}'}), 500
                    input_path = dual_path

            infile_type = self.get_filetype(input_path)
            new_type = self.get_filetype_after_cropCompare(input_path)
            if new_type == 'unknown':
                return jsonify({'status': 'error', 'message': f'Input file is not valid PDF type {infile_type} for crop-compare()'}), 400
            
            new_path = self.get_filename_after_process(input_path, new_type, engine)
            if infile_type == 'dual-cut':
                self.cropper.merge_pdf(input_path, new_path)
            else:
                new_path = self.get_filename_after_process(input_path, new_type, engine)
                self.cropper.crop_pdf(config, input_path, infile_type, new_path, new_type)
            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                size = os.path.getsize(new_path)
                print(f"🐲 双语对照成功(裁剪后拼接), 生成文件: {fileName}, 大小为: {size/1024.0/1024.0:.2f} MB")
                return jsonify({'status': 'success', 'fileList': [fileName]}), 200
            else:
                return jsonify({'status': 'error', 'message': f'Crop-compare failed: {new_path} not found'}), 500
        except Exception as e:
            return self._handle_exception(e, context='/crop-compare')

    # /compare
    def compare(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)
            engine = config.engine
            if infile_type == 'origin': 
                if engine == pdf2zh or engine != pdf2zh_next:
                    config.engine = 'pdf2zh'
                    fileList = self.translate_pdf(input_path, config)
                    dual_path = fileList[1]
                    if not os.path.exists(dual_path):
                        return jsonify({'status': 'error', 'message': f'Dual file not found: {dual_path}'}), 500
                    input_path = dual_path
                    infile_type = self.get_filetype(input_path)
                    new_type = self.get_filetype_after_compare(input_path)
                    if new_type == 'unknown':
                        return jsonify({'status': 'error', 'message': f'Input file is not valid PDF type {infile_type} for compare()'}), 400
                    new_path = self.get_filename_after_process(input_path, new_type, engine)
                    self.cropper.merge_pdf(input_path, new_path)
                else:
                    config.dual_mode = 'LR' # 直接生成dualMode为LR的文件, 就是Compare模式
                    config.no_dual = False
                    config.no_mono = True
                    fileList = self.translate_pdf_next(input_path, config)
                    dual_path = fileList[0]
                    if not os.path.exists(dual_path):
                        return jsonify({'status': 'error', 'message': f'Dual file not found: {dual_path}'}), 500
                    new_path = self.get_filename_after_process(input_path, 'compare', engine)
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(dual_path, new_path) # 直接将dual文件重命名为compare文件
            else:
                new_type = self.get_filetype_after_compare(input_path)
                if new_type == 'unknown':
                    return jsonify({'status': 'error', 'message': f'Input file is not valid PDF type {infile_type} for compare()'}), 400
                new_path = self.get_filename_after_process(input_path, new_type, engine)
                self.cropper.merge_pdf(input_path, new_path)
            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                print(f"🐲 双语对照成功, 生成文件: {fileName}, 大小为: {os.path.getsize(new_path)/1024.0/1024.0:.2f} MB")
                return jsonify({'status': 'success', 'fileList': [fileName]}), 200
            else:
                return jsonify({'status': 'error', 'message': f'Compare failed: {new_path} not found'}), 500
        except Exception as e:
            return self._handle_exception(e, context='/compare')

    def get_filetype(self, path):
        if 'mono.pdf' in path:
            return 'mono'
        elif 'dual.pdf' in path:
            return 'dual'
        elif 'dual-cut.pdf' in path:
            return 'dual-cut'
        elif 'mono-cut.pdf' in path:
            return 'mono-cut'
        elif 'crop-compare.pdf' in path: # 裁剪后才merge
            return 'crop-compare'  
        elif 'compare.pdf' in path:      # 无需裁剪, 直接merge
            return 'compare'
        elif 'cut.pdf' in path:
            return 'origin-cut'
        return 'origin'

    def get_filetype_after_crop(self, path):
        filetype = self.get_filetype(path)
        print(f"🔍 [Zotero PDF2zh Server] 获取文件类型: {filetype} from {path}")
        if filetype == 'origin':
            return 'origin-cut'
        elif filetype == 'mono':
            return 'mono-cut'
        elif filetype == 'dual':
            return 'dual-cut'
        return 'unknown'

    def get_filetype_after_cropCompare(self, path):
        filetype = self.get_filetype(path)
        if filetype == 'origin' or filetype == 'dual' or filetype == 'dual-cut':
            return 'crop-compare'
        return 'unknown'

    def get_filetype_after_compare(self, path):
        filetype = self.get_filetype(path)
        if filetype == 'origin' or filetype == 'dual':
            return 'compare'
        return 'unknown'
        
    def get_filename_after_process(self, inpath, outtype, engine):
        if engine == pdf2zh or engine != pdf2zh_next:
            intype = self.get_filetype(inpath)
            if intype == 'origin':
                if outtype == 'origin-cut':
                    return inpath.replace('.pdf', '-cut.pdf')
                return inpath.replace('.pdf', f'-{outtype}.pdf')
            return inpath.replace(f'{intype}.pdf', f'{outtype}.pdf')
        else:
            intype = self.get_filetype(inpath)
            if intype == 'origin':
                if outtype == 'origin-cut':
                    return inpath.replace('.pdf', '.cut.pdf')
                return inpath.replace('.pdf', f'.{outtype}.pdf')
            return inpath.replace(f'{intype}.pdf', f'{outtype}.pdf')

    def translate_pdf(self, input_path, config, task_id=None):
        # TODO: 如果翻译失败了, 自动执行跳过字体子集化, 并且显示生成的文件的大小
        config.update_config_file(config_path[pdf2zh])
        if config.targetLang == 'zh-CN': # TOFIX, pdf2zh 1.x converter没有通过
            config.targetLang = 'zh'
        if config.sourceLang == 'zh-CN': # TOFIX, pdf2zh 1.x converter没有通过
            config.sourceLang = 'zh'
        cmd = [
            pdf2zh, 
            input_path, 
            '--t', str(config.thread_num),
            '--output', str(output_folder),
            '--service', str(config.service),
            '--lang-in', str(config.sourceLang),
            '--lang-out', str(config.targetLang),
            '--config', str(config_path[pdf2zh]), # 使用默认的config path路径
        ]

        if config.skip_last_pages and config.skip_last_pages > 0:
            end = len(PdfReader(input_path).pages) - config.skip_last_pages
            cmd.append('-p '+str(1)+'-'+str(end))
        if config.skip_font_subsets:
            cmd.append('--skip-subset-fonts')
        if config.babeldoc:
            print("🔍 [Zotero PDF2zh Server] 目前不推荐使用pdf2zh 1.x + babeldoc, 如有需要，请直接使用pdf2zh_next")
            cmd.append('--babeldoc')
        try:
            # 使用 execute_with_progress 替代原来的 execute_in_env / subprocess.run
            # 实时解析子进程输出中的进度信息并更新 task_manager
            execute_with_progress(cmd, task_id, args, self.env_manager if args.enable_venv else None)
        except subprocess.CalledProcessError as e:
            print(f"⚠️ 翻译失败, 错误信息: {e}, 尝试跳过字体子集化, 重新渲染\n")
            cmd.append('--skip-subset-fonts')
            execute_with_progress(cmd, task_id, args, self.env_manager if args.enable_venv else None)
        fileName = os.path.basename(input_path).replace('.pdf', '')
        if config.babeldoc:
            output_path_mono = os.path.join(output_folder, f"{fileName}.{config.targetLang}.mono.pdf")
            output_path_dual = os.path.join(output_folder, f"{fileName}.{config.targetLang}.dual.pdf")
        else:
            output_path_mono = os.path.join(output_folder, f"{fileName}-mono.pdf")
            output_path_dual = os.path.join(output_folder, f"{fileName}-dual.pdf")
        output_files = [output_path_mono, output_path_dual]
        for f in output_files: # 显示生成
            if not os.path.exists(f):
                print(f"⚠️ 未找到期望生成的文件: {f}")
                continue
            size = os.path.getsize(f)
            print(f"🐲 pdf2zh 翻译成功, 生成文件: {f}, 大小为: {size/1024.0/1024.0:.2f} MB")
        return output_files
    
    def translate_pdf_next(self, input_path, config, task_id=None):
        service_map = {
            'ModelScope': 'modelscope',
            'openailiked': 'openaicompatible',
            'tencent': 'tencentmechinetranslation',
            'silicon': 'siliconflow',
            'qwen-mt': 'qwenmt',
            "AliyunDashScope": "aliyundashscope"
        }
        if config.service in service_map:
            config.service = service_map[config.service]
        config.update_config_file(config_path[pdf2zh_next])

        cmd = [
            pdf2zh_next,
            input_path,
            '--' + config.service,
            '--qps', str(config.qps),
            '--output', str(output_folder),
            '--lang-in', str(config.sourceLang),
            '--lang-out', str(config.targetLang),
            '--config-file', str(config_path[pdf2zh_next]), # 使用默认的config path路径
        ]
        # TODO: 增加术语表的地址
        if config.no_watermark:
            cmd.extend(['--watermark-output-mode', 'no_watermark'])
        else:
            cmd.extend(['--watermark-output-mode', 'watermarked'])
        if config.skip_last_pages and config.skip_last_pages > 0:
            end = len(PdfReader(input_path).pages) - config.skip_last_pages
            cmd.extend(['--pages', f'{1}-{end}'])
        if config.no_dual:
            cmd.append('--no-dual')
        if config.no_mono:
            cmd.append('--no-mono')
        if config.trans_first:
            cmd.append('--dual-translate-first')
        if config.skip_clean:
            cmd.append('--skip-clean')
        if config.disable_rich_text_translate:
            cmd.append('--disable-rich-text-translate')
        if config.enhance_compatibility:
            cmd.append('--enhance-compatibility')
        if config.save_auto_extracted_glossary:
            cmd.append('--save-auto-extracted-glossary')
        if config.disable_glossary:
            cmd.append('--no-auto-extract-glossary')
        if config.dual_mode == 'TB': # TB or LR, LR是defualt的
            cmd.append('--use-alternating-pages-dual')
        if config.translate_table_text:
            cmd.append('--translate-table-text')
        if config.ocr:
            cmd.append('--ocr-workaround')
        if config.auto_ocr:
            cmd.append('--auto-enable-ocr-workaround')
        if config.font_family and config.font_family in ['serif', 'sans-serif', 'script']:
            cmd.extend(['--primary-font-family', config.font_family])
        if config.pool_size and config.pool_size > 1:
            cmd.extend(['--pool-max-worker', str(config.pool_size)])

        fileName = os.path.basename(input_path).replace('.pdf', '')
        no_watermark_mono = os.path.join(output_folder, f"{fileName}.no_watermark.{config.targetLang}.mono.pdf")
        no_watermark_dual = os.path.join(output_folder, f"{fileName}.no_watermark.{config.targetLang}.dual.pdf")
        watermark_mono = os.path.join(output_folder, f"{fileName}.{config.targetLang}.mono.pdf")
        watermark_dual = os.path.join(output_folder, f"{fileName}.{config.targetLang}.dual.pdf")

        output_path = []
        if config.no_watermark: # 无水印
            if not config.no_mono:
                output_path.append(no_watermark_mono)
            if not config.no_dual:
                output_path.append(no_watermark_dual)
        else: # 有水印
            if not config.no_mono:
                output_path.append(watermark_mono)
            if not config.no_dual:
                output_path.append(watermark_dual)

        if args.enable_winexe and os.path.exists(args.winexe_path):
            cmd = [f"{args.winexe_path}"] + cmd[1:]  # Windows可执行文件
            # 将所有是路径的字段, 改为os.path.normpath
            cmd = [os.path.normpath(arg) if os.path.isfile(arg) or os.path.isdir(arg) else arg for arg in cmd]
            # 设置工作目录为 exe 所在目录，确保相对路径解析正确
            exe_dir = os.path.dirname(args.winexe_path)

            # 打印开关状态
            print(f"🔧 [winexe] winexe_attach_console={args.winexe_attach_console}")

            if args.winexe_attach_console:

                # 附着父控制台模式
                print("🚀 [winexe] mode=attach-console")
                print(f"📁 [winexe] cwd={exe_dir}")

                # 隐藏敏感信息后的命令显示
                safe_cmd = []
                for i, arg in enumerate(cmd):
                    if i > 0 and any(sensitive in cmd[i-1].lower() for sensitive in ['key', 'token', 'secret', 'password']):
                        safe_cmd.append('***')
                    else:
                        safe_cmd.append(arg)
                print(f"⚡ [winexe] cmd={' '.join(safe_cmd)}")

                # 23秒可见性预检
                def quick_visibility_check():
                    try:
                        print("🔍 [预检] 检查exe输出可见性...")
                        test_cmd = [cmd[0], '--help']
                        test_result = subprocess.run(
                            test_cmd,
                            shell=False,
                            cwd=exe_dir,
                            timeout=23,
                            capture_output=True,
                            text=True
                        )

                        # 检查是否有输出
                        has_output = bool(test_result.stdout.strip() or test_result.stderr.strip())

                        if not has_output:
                            print("\n⚠️ [预检结果] 23秒内未检测到控制台输出，可能为GUI/无控制台子系统或会自行新建控制台窗口")
                            print("   若需无黑窗 + 实时日志，建议使用console版exe或回到uv/venv")
                            print("   " + "="*60 + "\n")
                        else:
                            print(f"✅ [预检结果] 检测到控制台输出")

                        return has_output

                    except subprocess.TimeoutExpired:
                        print("\n⚠️ [预检结果] exe响应超时，可能为GUI程序")
                        print("   " + "="*60 + "\n")
                        return False
                    except Exception as e:
                        print(f"⚠️ [预检结果] 检查失败: {e}")
                        print("   " + "="*60 + "\n")
                        return False

                # 执行预检
                quick_visibility_check()

                # 执行主命令 - 附着父控制台
                print("🔍 [winexe] 开始执行（预期在当前终端显示实时日志）...")
                process = subprocess.Popen(
                    cmd,
                    shell=False,
                    cwd=exe_dir,
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
                    stderr_text = ''.join(stderr_lines)
                    value_error = self._extract_value_error(stderr_text)
                    if value_error:
                        raise ValueError(value_error)
                    print(f"❌ pdf2zh.exe 执行失败，退出码: {return_code}")
                    print("   操作失败，请查看详细日志。")
                    raise RuntimeError(f"pdf2zh.exe 执行失败，退出码: {return_code}")

            else:
                # 回退模式：静默模式（旧行为）
                print("🔇 [winexe] mode=silent")
                r = subprocess.run(
                    cmd,
                    shell=False,
                    cwd=exe_dir,
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8"
                )
                if r.returncode != 0:
                    value_error = self._extract_value_error(r.stderr or '')
                    if value_error:
                        raise ValueError(value_error)
                    raise RuntimeError(f"pdf2zh.exe 退出码 {r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        elif args.enable_venv:
            # 使用 execute_with_progress 替代原来的 execute_in_env
            # 实时解析子进程输出中的进度信息并更新 task_manager
            execute_with_progress(cmd, task_id, args, self.env_manager)
        else:
            execute_with_progress(cmd, task_id, args, None)
        existing = [p for p in output_path if os.path.exists(p)]

        for f in existing:
            size = os.path.getsize(f)
            print(f"🐲 pdf2zh_next 翻译成功, 生成文件: {f}, 大小为: {size/1024.0/1024.0:.2f} MB")

        if not existing:
            raise RuntimeError("操作失败，请查看详细日志。")

        return existing

    def run(self, port, debug=False):
        # print(f"🔍 [温馨提示] 如果遇到Network Error错误，请检查Zotero插件设置中的Python Server IP端口号是否与此处端口号一致: {port}, 并检查端口是否开放.")
        print(f"🌐 Server将启动在: http://localhost:{port}")
        print(f"📊 翻译进度监控页面: http://localhost:{port}/")
        print(f"💡 健康检查端点: http://localhost:{port}/health")
        self.app.run(host='0.0.0.0', port=port, debug=debug)

def prepare_path():
    print("🔍 [配置文件] 检查文件路径中...")
    # output folder
    os.makedirs(output_folder, exist_ok=True)
    # config file 路径和格式检查
    for (_, path) in config_path.items():
        # if not os.path.exists(path):
        #     example_file = os.path.join(config_folder, os.path.basename(path) + '.example')
        #     if os.path.exists(example_file):
        #         shutil.copyfile(example_file, path)
        # 因为需要修复toml文件中的一些问题, 需要让example文件直接覆盖config文件
        example_file = os.path.join(config_folder, os.path.basename(path) + '.example')
        if os.path.exists(example_file):
            # TOCHECK: 是否是直接覆盖, 是否会引发报错?
            if os.path.exists(path):
                print(f"⚠️ [配置文件] 发现旧的配置文件 {path}, 为了确保配置文件格式正确, 将使用 {example_file} 覆盖旧的配置文件.")
            else:
                print(f"🔍 [配置文件] 发现缺失的配置文件 {path}, 将使用 {example_file} 作为初始配置文件.")
            shutil.copyfile(example_file, path)
        # 检查文件格式
        try:
            if path.endswith('.json'):
                with open(path, 'r', encoding='utf-8') as f:  # Specify UTF-8 encoding
                    json.load(f)
            elif path.endswith('.toml'):
                with open(path, 'r', encoding='utf-8') as f:  # Specify UTF-8 encoding
                    toml.load(f)
        except Exception as e:
            traceback.print_exc()
            print(f"⚠️ [配置文件] {path} 文件格式错误, 请检查文件格式并尝试删除非.example文件后重试! 错误信息: {e}\n")
    print("✅ [配置文件] 文件路径检查完成\n")

# ================================================================================
# ######################### 主程序入口 ############################
# ================================================================================

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', '1', 'y'):
        return True
    elif v.lower() in ('no', 'false', 'f', '0', 'n'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser() 
    parser.add_argument('--port', type=int, default=PORT, help='Port to run the server on')

    parser.add_argument('--enable_venv', type=str2bool, default=enable_venv, help='脚本自动开启虚拟环境')
    parser.add_argument('--env_tool', type=str, default=default_env_tool, help='虚拟环境管理工具, 默认使用 uv')
    parser.add_argument('--check_update', type=str2bool, default=True, help='启动时检查更新')
    parser.add_argument('--update_source', type=str, default='gitee', help='更新源设置为gitee或github, 默认为gitee')
    parser.add_argument('--debug', type=str2bool, default=False, help='Enable debug mode')
    parser.add_argument('--enable_winexe', type=str2bool, default=False, help='使用pdf2zh_next Windows可执行文件运行脚本, 仅限Windows系统')
    parser.add_argument('--enable_mirror', type=str2bool, default=True, help='启用下载镜像加速, 仅限中国大陆用户')
    parser.add_argument('--mirror_source', type=str, default='https://mirrors.ustc.edu.cn/pypi/simple', help='自定义您的PyPI镜像源, 仅限中国大陆用户')
    parser.add_argument('--winexe_path', type=str, default='./pdf2zh-v2.6.3-BabelDOC-v0.5.7-win64/pdf2zh/pdf2zh.exe', help='Windows可执行文件的路径')
    parser.add_argument('--winexe_attach_console', type=str2bool, default=True, help='Winexe模式是否尝试附着父控制台显示实时日志 (默认True)')
    parser.add_argument('--skip_install', type=str2bool, default=False, help='跳过虚拟环境中的安装')
    args = parser.parse_args()
    # 2. 打印提示信息
    print("\n===== 💡提示💡 =====")
    print("如果您遇到问题......")
    print("1️⃣ 请阅读本项目的【github主页】, 这里有最准确的信息")
    print("    · 🤖 github: https://github.com/guaguastandup/zotero-pdf2zh")
    print("    · 🤖 如果国内无法访问github, 请移步: gitee: https://gitee.com/guaguastandup/zotero-pdf2zh\n")

    print("2️⃣ 加入zotero-pdf2zh插件QQ群: 请在github主页查看最新群号, 入群口令: github")
    print("    · 【提问前】您需要先确保已经阅读过本项目主页的教程以及常见问题汇总")
    print("    · 【提问时】您必须将本终端输出的所有信息复制到txt文件中, 并截图您的zotero插件设置, 一并发送到群里, 否则您将不会得到回复, 感谢配合!\n")

    print("\n==== 🌍翻译期间请勿关闭此窗口🌍 =====\n")

    # 3. 打印启动参数
    print("🚀 启动参数:", args, "\n")
    print("🏠 当前版本: ", __version__)
    print("🏠 当前路径: ", root_path, "\n")

    # 4. 环境检查（端口、目录权限、Python版本、虚拟环境）
    print("🔍 开始环境检查...")
    all_checks_passed = True

    # 4.1 端口检查
    print("\n--- 网络端口检查 ---")
    port = args.port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print(f"🔍 检查端口 {port} 是否被占用...")
        if s.connect_ex(('localhost', port)) == 0:
            print(f"❌ 端口 {port} 已被占用！")
            print("\n💡 解决方案:")
            print("   1. 选择其他端口启动: python server.py --port XXXX")
            print("   2. 或在Zotero插件设置中修改Server IP端口号")
            print(f"   3. 或停止占用端口 {port} 的其他程序")
            all_checks_passed = False
        else:
            print(f"✅ 端口 {port} 可用")

    # 4.2 目录权限检查
    print("\n--- 目录权限检查 ---")
    required_dirs = [
        ('translated', '翻译输出目录'),
        ('config', '配置文件目录')
    ]

    for dir_name, description in required_dirs:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path):
            print(f"⚠️  {description} ({dir_name}) 不存在，尝试创建...")
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"✅ {description} 创建成功: {dir_path}")
            except Exception as e:
                print(f"❌ 无法创建 {description}: {e}")
                print(f"\n💡 解决方案:")
                print(f"   1. 手动创建 {dir_name} 文件夹")
                print(f"   2. 检查当前用户是否有创建目录的权限")
                print(f"   3. 尝试以管理员身份运行（Windows: 右键'以管理员身份运行'）")
                all_checks_passed = False
        else:
            # 检查写入权限
            if not os.access(dir_path, os.W_OK):
                print(f"❌ {description} ({dir_name}) 没有写入权限！")
                print(f"\n💡 解决方案:")
                print(f"   1. 检查 {dir_name} 文件夹的权限设置")
                print(f"   2. 在Windows中: 右键文件夹 -> 属性 -> 安全 -> 编辑权限")
                print(f"   3. 在Linux/Mac中: chmod 755 {dir_path}")
                all_checks_passed = False
            else:
                print(f"✅ {description} ({dir_name}) 权限正常")

    # 4.3 Python版本检查
    print("\n--- Python环境检查 ---")
    print(f"🐍 Python版本: {sys.version}")
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 8):
        print(f"❌ Python版本过低！需要 Python 3.8 或更高版本")
        print(f"💡 解决方案:")
        print(f"   1. 安装 Python 3.8 或更高版本")
        print(f"   2. 从 python.org 下载最新版 Python")
        all_checks_passed = False
    else:
        print(f"✅ Python版本符合要求")

    # 4.4 虚拟环境检查
    if args.enable_venv:
        print("\n--- 虚拟环境检查 ---")

        # 根据虚拟环境管理工具确定环境名称
        env_tool = args.env_tool  # 'uv' or 'conda'
        env_suffix = '-venv' if env_tool == 'uv' else '-venv'

        # 检查两个翻译引擎的虚拟环境
        venv_pdf2zh = os.path.join(root_path, f'zotero-pdf2zh{env_suffix}')
        venv_pdf2zh_next = os.path.join(root_path, f'zotero-pdf2zh-next{env_suffix}')

        print(f"🔧 虚拟环境工具: {env_tool}")
        print(f"📁 pdf2zh环境: {venv_pdf2zh}")
        print(f"📁 pdf2zh_next环境: {venv_pdf2zh_next}")

        pdf2zh_exists = os.path.exists(venv_pdf2zh)
        pdf2zh_next_exists = os.path.exists(venv_pdf2zh_next)

        if pdf2zh_exists and pdf2zh_next_exists:
            print(f"✅ 两个翻译引擎的虚拟环境都已存在")
        elif pdf2zh_exists or pdf2zh_next_exists:
            which_exists = "pdf2zh" if pdf2zh_exists else "pdf2zh_next"
            print(f"⚠️  仅 {which_exists} 虚拟环境存在")
            print(f"💡 提示: 使用 {which_exists} 引擎翻译时会自动安装缺失的环境")
        else:
            print(f"⚠️  虚拟环境不存在，将在首次翻译时自动安装")
            print(f"💡 提示:")
            print(f"   - 首次运行会自动下载并安装依赖包")
            print(f"   - 安装过程可能需要几分钟，请耐心等待")

    # 检查总结
    print("\n" + "="*60)
    if all_checks_passed:
        print("✅ 所有检查通过！Server准备启动...")
    else:
        print("❌ 部分检查未通过，可能影响Server正常运行")
        print("\n⚠️  您可以选择:")
        print("   1. 根据上述提示修复问题后重新启动")
        print("   2. 忽略警告继续运行（可能遇到错误）")

        user_input = input("\n是否继续启动？(y/n): ").strip().lower()
        if user_input != 'y':
            print("👋 已取消启动，请修复问题后重试")
            sys.exit(0)

    print("="*60 + "\n")
    print("💡 请保持此窗口开启，翻译期间请勿关闭\n")

    # 5. 启动时自动检查更新
    if args.check_update:
        print("🔍 开始检查更新...")
        update_info = check_for_updates(__version__, args.update_source)
        if update_info:
            local_v, remote_v = update_info
            print(f"🎉 发现新版本！当前版本: {local_v}, 最新版本: {remote_v}")
            try:
                answer = input("是否要立即更新? (y/n): ").lower()
            except (EOFError, KeyboardInterrupt):
                answer = 'n'
                print("\n无法获取用户输入，已自动取消更新。")

            if answer in ['y', 'yes']:
                perform_update_optimized(root_path, __version__, expected_version=remote_v, update_source=args.update_source)
            else:
                print("👌 已取消更新。")

    # 6. 正常启动流程
    prepare_path()
    translator = PDFTranslator(args)
    translator.run(args.port, debug=args.debug)