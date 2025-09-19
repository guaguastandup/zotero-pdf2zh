## server.py v3.0.17
# guaguastandup
# zotero-pdf2zh
import os
from flask import Flask, request, jsonify, send_file
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
import sys  # NEW: 用于退出脚本
import re   # NEW: 用于解析版本号
import urllib.request # NEW: 用于下载文件
import zipfile # NEW: 用于解压文件
import tempfile # 引入tempfile来处理临时目录
import io

# NEW: 定义当前脚本版本  
# 修复了Ocr的问题, 更新了readme
# 添加了新的预热方法
__version__ = "3.0.27" 

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
            self.env_manager = VirtualEnvManager(config_path[venv], venv_name, args.env_tool, args.enable_mirror, args.skip_install)
        self.cropper = Cropper()
        self.setup_routes()

    def setup_routes(self):
        self.app.add_url_rule('/translate', 'translate', self.translate, methods=['POST'])
        self.app.add_url_rule('/crop', 'crop', self.crop, methods=['POST']) 
        self.app.add_url_rule('/crop-compare', 'crop-compare', self.crop_compare, methods=['POST']) 
        self.app.add_url_rule('/compare', 'compare', self.compare, methods=['POST'])
        self.app.add_url_rule('/translatedFile/<filename>', 'download', self.download_file)

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
    def download_file(self, filename):
        try:
            base = os.path.abspath(output_folder)
            full = os.path.abspath(os.path.join(output_folder, filename))
            # 防止目录穿越
            if os.path.commonpath([base, full]) != base:
                return jsonify({'status': 'error', 'message': 'Invalid path'}), 400

            if os.path.exists(full):
                return send_file(full, as_attachment=True)
            # 新增：不存在时明确返回 404，而不是什么都不返回
            return jsonify({'status': 'error', 'message': f'File not found: {filename}'}), 404
        except Exception as e:
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    ############################# 核心逻辑 #############################
    # 翻译 /translate
    def translate(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)
            engine = config.engine
            if infile_type != 'origin':
                return jsonify({'status': 'error', 'message': 'Input file must be an original PDF file.'}), 400
            if engine == pdf2zh:
                print("🔍 [Zotero PDF2zh Server] PDF2zh 开始翻译文件...")
                fileList = self.translate_pdf(input_path, config)
                mono_path, dual_path = fileList[0], fileList[1]
                if config.mono_cut:
                    mono_cut_path = self.get_filename_after_process(mono_path, 'mono-cut', engine)
                    self.cropper.crop_pdf(config, mono_path, 'mono', mono_cut_path, 'mono-cut', dualFirst=config.trans_first, engine=engine)
                    if os.path.exists(mono_cut_path):
                        fileList.append(mono_cut_path)
                if config.dual_cut:
                    dual_cut_path = self.get_filename_after_process(dual_path, 'dual-cut', engine)
                    self.cropper.crop_pdf(config, dual_path, 'dual', dual_cut_path, 'dual-cut', dualFirst=config.trans_first, engine=engine)
                    if os.path.exists(dual_cut_path):
                        fileList.append(dual_cut_path)
                if config.crop_compare:
                    crop_compare_path = self.get_filename_after_process(dual_path, 'crop-compare', engine)
                    self.cropper.crop_pdf(config, dual_path, 'dual', crop_compare_path, 'crop-compare', dualFirst=config.trans_first, engine=engine)
                    if os.path.exists(crop_compare_path):
                        fileList.append(crop_compare_path)
                if config.compare and config.babeldoc == False: # babeldoc不支持compare
                    compare_path = self.get_filename_after_process(dual_path, 'compare', engine)
                    self.cropper.merge_pdf(dual_path, compare_path, dualFirst=config.trans_first, engine=engine)
                    if os.path.exists(compare_path):
                        fileList.append(compare_path)
                
            elif engine == pdf2zh_next:
                print("🔍 [Zotero PDF2zh Server] PDF2zh_next 开始翻译文件...")
                if config.mono_cut or config.mono:
                    config.no_mono = False
                if config.dual or config.dual_cut or config.crop_compare or config.compare:
                    config.no_dual = False

                if config.no_dual and config.no_mono:
                    raise ValueError("⚠️ [Zotero PDF2zh Server] pdf2zh_next 引擎至少需要生成 mono 或 dual 文件, 请检查 no_dual 和 no_mono 配置项")

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
                    LR_dual_path = dual_path.replace('.dual.pdf', '.LR_dual.pdf')
                    TB_dual_path = dual_path.replace('.dual.pdf', '.TB_dual.pdf')
                    if config.dual_mode == 'LR':
                        self.cropper.pdf_dual_mode(dual_path, 'LR', 'TB')
                        if config.dual:
                            fileList.append(LR_dual_path)
                    elif config.dual_mode == 'TB':
                        os.rename(dual_path, TB_dual_path)
                        if config.dual:
                            fileList.append(TB_dual_path)
                elif config.dual:
                    fileList.append(dual_path)

                if config.mono_cut:
                    mono_cut_path = self.get_filename_after_process(mono_path, 'mono-cut', engine)
                    self.cropper.crop_pdf(config, mono_path, 'mono', mono_cut_path, 'mono-cut', dualFirst=config.trans_first, engine=engine)
                    if os.path.exists(mono_cut_path):
                        fileList.append(mono_cut_path)

                if config.dual_cut: # use TB_dual_path
                    dual_cut_path = self.get_filename_after_process(TB_dual_path, 'dual-cut', engine)
                    self.cropper.crop_pdf(config, TB_dual_path, 'dual', dual_cut_path, 'dual-cut', dualFirst=config.trans_first, engine=engine)
                    if os.path.exists(dual_cut_path):
                        fileList.append(dual_cut_path)

                if config.crop_compare: # use TB_dual_path
                    crop_compare_path = self.get_filename_after_process(TB_dual_path, 'crop-compare', engine)
                    self.cropper.crop_pdf(config, TB_dual_path, 'dual', crop_compare_path, 'crop-compare', dualFirst=config.trans_first, engine=engine)
                    if os.path.exists(crop_compare_path):
                        fileList.append(crop_compare_path)

                if config.compare: # use TB_dual_path
                    if config.dual_mode == 'TB':
                        compare_path = self.get_filename_after_process(TB_dual_path, 'compare', engine)
                        self.cropper.merge_pdf(TB_dual_path, compare_path, dualFirst=config.trans_first, engine=engine)
                        if os.path.exists(compare_path):
                            fileList.append(compare_path)
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
                return jsonify({'status': 'error', 'message': '操作失败，请查看详细日志。'}), 500

            fileNameList = [os.path.basename(p) for p in existing]
            return jsonify({'status': 'success', 'fileList': fileNameList}), 200
        except Exception as e:
            print(f"❌ [Zotero PDF2zh Server] /translate Error: {e}\n")
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # 裁剪 /crop
    def crop(self):
        try:
            input_path, config = self.process_request()
            infile_type = self.get_filetype(input_path)

            new_type = self.get_filetype_after_crop(input_path)
            if new_type == 'unknown':
                return jsonify({'status': 'error', 'message': f'Input file is not valid PDF type {infile_type} for crop()'}), 400

            new_path = self.get_filename_after_process(input_path, new_type, config.engine)
            self.cropper.crop_pdf(config, input_path, infile_type, new_path, new_type, dualFirst=config.trans_first, engine=config.engine)

            print(f"🔍 [Zotero PDF2zh Server] 开始裁剪文件: {input_path}, {infile_type}, 裁剪类型: {new_type}, {new_path}")
            
            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                return jsonify({'status': 'success', 'fileList': [fileName]}), 200
            else:
                return jsonify({'status': 'error', 'message': f'Crop failed: {new_path} not found'}), 500
        except Exception as e:
            traceback.print_exc()
            print(f"❌ [Zotero PDF2zh Server] /crop Error: {e}\n")
            return jsonify({'status': 'error', 'message': str(e)}), 500

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
                self.cropper.merge_pdf(input_path, new_path, dualFirst=config.trans_first, engine=engine)
            else:
                new_path = self.get_filename_after_process(input_path, new_type, engine)
                self.cropper.crop_pdf(config, input_path, infile_type, new_path, new_type, dualFirst=config.trans_first, engine=engine)
            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                size = os.path.getsize(new_path)
                print(f"🐲 双语对照成功(裁剪后拼接), 生成文件: {fileName}, 大小为: {size/1024.0/1024.0:.2f} MB")
                return jsonify({'status': 'success', 'fileList': [fileName]}), 200
            else:
                return jsonify({'status': 'error', 'message': f'Crop-compare failed: {new_path} not found'}), 500
        except Exception as e:
            traceback.print_exc()
            print(f"❌ [Zotero PDF2zh Server] /crop-compare Error: {e}\n")
            return jsonify({'status': 'error', 'message': str(e)}), 500

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
                    self.cropper.merge_pdf(input_path, new_path, dualFirst=config.trans_first, engine=engine)
                else:
                    config.dual_mode = 'LR' # 直接生成dualMode为LR的文件, 就是Compare模式
                    config.no_dual = False
                    config.no_mono = True
                    fileList = self.translate_pdf_next(input_path, config)
                    dual_path = fileList[0]
                    if not os.path.exists(dual_path):
                        return jsonify({'status': 'error', 'message': f'Dual file not found: {dual_path}'}), 500
                    new_path = self.get_filename_after_process(input_path, 'compare', engine)
                    os.rename(dual_path, new_path) # 直接将dual文件重命名为compare文件
            else:
                new_type = self.get_filetype_after_compare(input_path)
                if new_type == 'unknown':
                    return jsonify({'status': 'error', 'message': f'Input file is not valid PDF type {infile_type} for compare()'}), 400
                new_path = self.get_filename_after_process(input_path, new_type, engine)
                self.cropper.merge_pdf(input_path, new_path, dualFirst=config.trans_first, engine=engine)
            if os.path.exists(new_path):
                fileName = os.path.basename(new_path)
                print(f"🐲 双语对照成功, 生成文件: {fileName}, 大小为: {os.path.getsize(new_path)/1024.0/1024.0:.2f} MB")
                return jsonify({'status': 'success', 'fileList': [fileName]}), 200
            else:
                return jsonify({'status': 'error', 'message': f'Compare failed: {new_path} not found'}), 500
        except Exception as e:
            traceback.print_exc()
            print(f"❌ [Zotero PDF2zh Server] /compare Error: {e}\n")
            return jsonify({'status': 'error', 'message': str(e)}), 500

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

    def translate_pdf(self, input_path, config):
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
            print("🔍 [Zotero PDF2zh Server] 不推荐使用pdf2zh 1.x + babeldoc, 如有需要，请考虑直接使用pdf2zh_next")
            cmd.append('--babeldoc')
        try:
            if args.enable_venv:
                self.env_manager.execute_in_env(cmd)
            else:
                subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"⚠️ 翻译失败, 错误信息: {e}, 尝试跳过字体子集化, 重新渲染\n")
            cmd.append('--skip-subset-fonts')
            if args.enable_venv:
                self.env_manager.execute_in_env(cmd)
            else:
                subprocess.run(cmd, check=True)
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
    
    def translate_pdf_next(self, input_path, config):
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
        # TODO: 术语表的地址
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
                r = subprocess.run(
                    cmd,
                    shell=False,
                    cwd=exe_dir
                    # 不使用creationflags，允许控制台窗口显示
                    # 不捕获stdout/stderr，继承父进程的标准输出/错误流
                )

                if r.returncode != 0:
                    print(f"❌ pdf2zh.exe 执行失败，退出码: {r.returncode}")
                    print("   操作失败，请查看详细日志。")
                    raise RuntimeError(f"pdf2zh.exe 执行失败，退出码: {r.returncode}")

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
                    raise RuntimeError(f"pdf2zh.exe 退出码 {r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        elif args.enable_venv:
            self.env_manager.execute_in_env(cmd)
        else:
            subprocess.run(cmd, check=True)
        existing = [p for p in output_path if os.path.exists(p)]

        for f in existing:
            size = os.path.getsize(f)
            print(f"🐲 pdf2zh_next 翻译成功, 生成文件: {f}, 大小为: {size/1024.0/1024.0:.2f} MB")

        if not existing:
            raise RuntimeError("操作失败，请查看详细日志。")

        return existing

    def run(self, port, debug=False):
        # print(f"🔍 [温馨提示] 如果遇到Network Error错误，请检查Zotero插件设置中的Python Server IP端口号是否与此处端口号一致: {port}, 并检查端口是否开放.")
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
# ######################### NEW: 自动更新模块 ############################
# ================================================================================

def get_xpi_info_from_repo(owner, repo, branch='main', expected_version=None):
    """
    根据已知的命名规则直接构造 Zotero PDF 2 ZH 插件的下载链接。
    命名规则：zotero-pdf-2-zh-v{expected_version}.xpi
    """
    if not expected_version:
        print("  - ⚠️ 未提供版本号，无法构造插件下载链接。")
        return None, None
    try:
        # 构造文件名
        target_filename = f"zotero-pdf-2-zh-v{expected_version}.xpi"
        # 构造 GitHub raw 文件下载链接
        download_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{target_filename}"
        print(f"  - 构造插件下载链接: {download_url}")
        # 可选：验证链接是否有效
        with urllib.request.urlopen(download_url, timeout=1000) as response:
            if response.status == 200:
                print(f"  - 成功验证插件: {target_filename}")
                return download_url, target_filename
            else:
                print(f"  - ⚠️ 无法访问插件文件，状态码: {response.status}")
                return None, None
    except Exception as e:
        print(f"  - ⚠️ 无法获取插件文件 (可能是网络问题或文件不存在): {e}")
        return None, None

def smart_file_sync(source_dir, target_dir, stats, backup_dir, updated_files, new_files, exclude_dirs=None):
    """
    智能文件同步：比较文件内容，只更新真正改变的文件。同时备份受影响的文件，并跟踪更新和新增。
    
    Args:
        source_dir: 新版本的文件夹路径
        target_dir: 目标文件夹路径  
        stats: 统计信息字典 {'updated': 0, 'new': 0, 'preserved': 0, 'unchanged': 0}
        backup_dir: 备份目录，用于存储将被更新的文件的备份
        updated_files: 列表，用于跟踪更新的文件相对路径
        new_files: 列表，用于跟踪新增的文件相对路径
        exclude_dirs (list, optional): 需要完全跳过的目录名列表。 Defaults to None.
    """
    if exclude_dirs is None:
        exclude_dirs = []

    for root, dirs, files in os.walk(source_dir):
        # <<< 优化点 1: 在遍历时，从 dirs 列表中移除需要排除的目录 >>>
        # 这样 os.walk 就不会进入这些目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        # 计算相对路径
        rel_dir = os.path.relpath(root, source_dir)
        target_root = os.path.join(target_dir, rel_dir) if rel_dir != '.' else target_dir
        
        # 确保目标目录存在
        os.makedirs(target_root, exist_ok=True)
        
        # 同步文件
        for file in files:
            source_file = os.path.join(root, file)
            target_file = os.path.join(target_root, file)
            rel_file_path = os.path.join(rel_dir, file) if rel_dir != '.' else file
            
            if os.path.exists(target_file): # 比较文件内容
                try:
                    with open(source_file, 'rb') as sf, open(target_file, 'rb') as tf:
                        source_content = sf.read()
                        target_content = tf.read()
                    
                    if source_content != target_content:
                        # 文件内容不同，需要更新：先备份原文件
                        backup_file = os.path.join(backup_dir, rel_file_path)
                        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                        shutil.copy2(target_file, backup_file)
                        # 更新
                        shutil.copy2(source_file, target_file)
                        print(f"    ✓ 更新: {rel_file_path}")
                        stats['updated'] += 1
                        updated_files.append(rel_file_path)
                    else:
                        # 文件内容相同，无需更新
                        print(f"    ≡ 跳过: {rel_file_path} (内容相同)")
                        stats['unchanged'] += 1
                except Exception as e:
                    # 比较出错时，保守地更新文件：先备份
                    backup_file = os.path.join(backup_dir, rel_file_path)
                    os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                    shutil.copy2(target_file, backup_file)
                    shutil.copy2(source_file, target_file)
                    print(f"    ⚠️ 比较失败，强制更新: {rel_file_path} ({e})")
                    stats['updated'] += 1
                    updated_files.append(rel_file_path)
            else:
                # 新文件
                shutil.copy2(source_file, target_file)
                print(f"    + 新增: {rel_file_path}")
                stats['new'] += 1
                new_files.append(rel_file_path)

def count_preserved_files(source_dir, target_dir, stats, exclude_dirs=None):
    # 统计保留的用户文件（在target中存在但source中不存在的文件）
    if exclude_dirs is None:
        exclude_dirs = []

    for root, dirs, files in os.walk(target_dir):
        # <<< 优化点 2: 同样地，在统计保留文件时也跳过排除目录 >>>
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        rel_dir = os.path.relpath(root, target_dir)
        source_root = os.path.join(source_dir, rel_dir) if rel_dir != '.' else source_dir
        
        for file in files:
            source_file = os.path.join(source_root, file)
            if not os.path.exists(source_file):
                rel_file_path = os.path.join(rel_dir, file) if rel_dir != '.' else file
                print(f"    ◆ 保留: {rel_file_path} (用户文件)")
                stats['preserved'] += 1

def perform_update_optimized(expected_version=None):
    # 优化的更新逻辑：结合智能同步和临时目录的优点，使用针对性备份避免操作无关目录（如虚拟环境）。
    print("🚀 [自动更新] 开始更新 (智能同步模式)...请稍候。")
    owner, repo = 'guaguastandup', 'zotero-pdf2zh'
    project_root = os.path.dirname(root_path)
    print(f"   - 项目根目录: {project_root}")
    print(f"   - 当前服务目录: {root_path}")
    
    # <<< 优化点 3: 定义一个排除列表，包含虚拟环境和常见的缓存目录 >>>
    # 这是保护虚拟环境的关键
    EXCLUDE_DIRECTORIES = ['zotero-pdf2zh-next-venv', 'zotero-pdf2zh-venv']
    print(f"   - 🛡️ 更新将自动忽略以下目录: {EXCLUDE_DIRECTORIES}")

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(project_root, f"server_backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)
    
    zip_filename = f"server_{expected_version or 'latest'}.zip"
    server_zip_path = os.path.join(project_root, zip_filename)
    
    stats = {'updated': 0, 'new': 0, 'preserved': 0, 'unchanged': 0}
    updated_files = []
    new_files = []
    
    try:
        # --- 步骤 1: 下载文件 ---
        xpi_url, xpi_filename = get_xpi_info_from_repo(owner, repo, 'main', expected_version)
        if xpi_url and xpi_filename:
            xpi_save_path = os.path.join(project_root, xpi_filename)
            print(f"  - 正在下载插件文件 ({xpi_filename})...")
            if os.path.exists(xpi_save_path): 
                os.remove(xpi_save_path)
            urllib.request.urlretrieve(xpi_url, xpi_save_path)
            print("  - ✅ 插件文件下载完成, 请将新版本插件安装到Zotero中")
        else:
            print("  - ⚠️ 未找到合适的插件文件，跳过插件下载。")
        
        server_zip_url = f"https://github.com/{owner}/{repo}/raw/main/server.zip"
        print(f"  - 正在下载服务端文件 ({zip_filename})...")
        urllib.request.urlretrieve(server_zip_url, server_zip_path)
        print("  - ✅ 服务端文件下载完成")

        # --- 步骤 2: 使用临时目录解压并智能同步 ---
        print("  - 正在解压并同步新版本...")
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(server_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            new_server_path = os.path.join(temp_dir, 'server')
            if not os.path.exists(new_server_path):
                new_server_path = temp_dir
            
            print("    - 开始智能文件同步:")
            # <<< 优化点 4: 将排除列表传递给同步函数 >>>
            smart_file_sync(new_server_path, root_path, stats, backup_path, updated_files, new_files, exclude_dirs=EXCLUDE_DIRECTORIES)
            # <<< 优化点 5: 将排除列表传递给统计函数 >>>
            count_preserved_files(new_server_path, root_path, stats, exclude_dirs=EXCLUDE_DIRECTORIES)

        # --- 步骤 3 & 4 & 回滚逻辑: (这部分代码无需改动，保持原样) ---
        print(f"\n📊 同步统计报告:")
        print(f"    - 📝 更新的文件: {stats['updated']}")
        print(f"    - ➕ 新增的文件: {stats['new']}")  
        print(f"    - ◆ 保留的文件: {stats['preserved']}")
        print(f"    - ≡ 跳过的文件: {stats['unchanged']} (内容相同)")
        print(f"    - 📁 总处理文件: {sum(stats.values())}")

        print("  - 正在清理临时文件...")
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
        os.remove(server_zip_path)
        print("  - ✅ 清理完成")

        print(f"\n✅ 更新成功！")
        if xpi_filename:
            print(f"   - 📦 最新的插件文件 '{xpi_filename}' 已下载到项目主目录")
            print("   - 🔄 请将插件文件重新安装到Zotero中")
        print("   - 🚀 请重新启动 server.py 脚本以应用新版本")
        print("   - 🛡️ 您的配置文件和虚拟环境已安全保留")

    except Exception as e:
        print(f"\n❌ 更新失败: {e}")    
        print("  - 正在尝试从备份回滚...")
        try:
            for rel_path in updated_files:
                backup_file = os.path.join(backup_path, rel_path)
                target_file = os.path.join(root_path, rel_path)
                if os.path.exists(backup_file):
                    shutil.copy2(backup_file, target_file)
                    print(f"    - 回滚更新: {rel_path}")
            
            for rel_path in new_files:
                target_file = os.path.join(root_path, rel_path)
                if os.path.exists(target_file):
                    os.remove(target_file)
                    print(f"    - 回滚新增: {rel_path}")

            print("  - ✅ [自动更新] 已成功回滚到更新前的状态")
        except Exception as rollback_error:
            print(f"  - ❌ [自动更新] 回滚失败: {rollback_error}")
            print(f"  - 💾 [自动更新] 备份文件保留在: {backup_path}")

    finally:
        if os.path.exists(server_zip_path):
            os.remove(server_zip_path)
        sys.exit()

def check_for_updates(): # 从 GitHub 检查是否有新版本。如果存在，则返回(本地版本, 远程版本)，否则返回None。
    print("🔍 [自动更新] 正在检查更新...")
    remote_script_url = "https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/server/server.py"
    try:
        with urllib.request.urlopen(remote_script_url, timeout=60) as response:
            remote_content = response.read().decode('utf-8')
        match = re.search(r'__version__\s*=\s*["\'](.+?)["\']', remote_content)
        if not match:
            print("⚠️ [自动更新] 无法在远程文件中找到版本信息, 已跳过.\n")
            return None
        remote_version = match.group(1)
        local_version = __version__
        if tuple(map(int, remote_version.split('.'))) > tuple(map(int, local_version.split('.'))):
            return local_version, remote_version
        else:
            print("✅ [自动更新] 您的程序已是最新版本.\n")
            return None
    except Exception as e:
        print(f"⚠️ [自动更新] 检查更新失败 (可能是网络问题)，已跳过。错误: {e}\n")
        return None

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
    parser.add_argument('--debug', type=str2bool, default=False, help='Enable debug mode')
    parser.add_argument('--enable_winexe', type=str2bool, default=False, help='使用pdf2zh_next Windows可执行文件运行脚本, 仅限Windows系统')
    parser.add_argument('--enable_mirror', type=str2bool, default=True, help='启用下载镜像加速, 仅限中国大陆用户')
    parser.add_argument('--winexe_path', type=str, default='./pdf2zh-v2.6.3-BabelDOC-v0.5.7-win64/pdf2zh/pdf2zh.exe', help='Windows可执行文件的路径')
    parser.add_argument('--winexe_attach_console', type=str2bool, default=True, help='Winexe模式是否尝试附着父控制台显示实时日志 (默认True)')
    parser.add_argument('--skip_install', type=str2bool, default=True, help='跳过虚拟环境中的安装')
    args = parser.parse_args()
    print(f"🚀 启动参数: {args}\n")
    print("💡 如果您来自网络上的视频教程/文字教程, 并且在执行中遇到问题, 请优先阅读【本项目主页】, 以获得最准确的安装信息: \ngithub: https://github.com/guaguastandup/zotero-pdf2zh\ngitee: https://gitee.com/guaguastandup/zotero-pdf2zh")
    print("💡 另外, 常见问题文档: https://docs.qq.com/markdown/DU0RPQU1vaEV6UXJC")
    print("💡 如遇到无法解决的问题请加入QQ群: 897867369, 提问前您需要先阅读本项目指南和常见问题文档, 确认是新问题后再提问. 另外，提问时必须将本终端完整的信息复制到txt文件中并截图zotero插件设置, 一并发送到群里, 以便更好地得到帮助, 感谢配合!\n")

    # 启动时自动检查更新
    if args.check_update:
        update_info = check_for_updates()
        if update_info:
            local_v, remote_v = update_info
            print(f"🎉 发现新版本！当前版本: {local_v}, 最新版本: {remote_v}, 新增AliyunDashScope与ClaudeCode翻译服务支持, 修复Ocr选项不生效的Bug.")
            try:
                answer = input("是否要立即更新? (y/n): ").lower()
            except (EOFError, KeyboardInterrupt):
                answer = 'n'
                print("\n无法获取用户输入，已自动取消更新。")
            
            if answer in ['y', 'yes']:
                perform_update_optimized(expected_version=remote_v)  # 使用优化版本
            else:
                print("👌 已取消更新。")
    
    print("🏠 当前路径: ", root_path)
    print("🏠 当前版本: ", __version__)
    # 正常的启动流程
    prepare_path()
    translator = PDFTranslator(args)
    translator.run(args.port, debug=args.debug)