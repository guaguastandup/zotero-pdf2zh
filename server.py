import os
import threading
import uuid
from flask import Flask, request, jsonify, send_file
import base64
import subprocess
from pypdf import PdfWriter, PdfReader
from pypdf.generic import RectangleObject
import sys
from typing import Dict

services = [
    'bing', 'google', 'deepl', 'deeplx', 'ollama', 'xinference',
    'openai', 'azure-openai', 'zhipu', 'ModelScope', 'silicon',
    'gemini', 'azure', 'tencent', 'dify', 'anythingllm', 'argos',
    'grok', 'groq', 'deepseek', 'openailiked', 'qwen-mt'
]

class PDFTranslator:
    DEFAULT_CONFIG = {
        'port': 8888, 'engine': 'pdf2zh', 'service': 'bing', 'threadNum': 4,
        'outputPath': './translated/', 'configPath': './config.json',
        'sourceLang': 'en', 'targetLang': 'zh'
    }

    def __init__(self):
        self.app = Flask(__name__)
        self.tasks: Dict[str, dict] = {}  # 任务状态存储：{task_id: {status, result, error}}
        self.setup_routes()

    def setup_routes(self):
        self.app.add_url_rule('/submitTask', 'submit_task', self.submit_task, methods=['POST'])
        self.app.add_url_rule('/taskStatus/<task_id>', 'task_status', self.task_status)
        self.app.add_url_rule('/translate', 'translate', self.translate, methods=['POST'])
        self.app.add_url_rule('/cut', 'cut', self.cut_pdf, methods=['POST'])
        self.app.add_url_rule('/compare', 'compare', self.compare, methods=['POST'])
        self.app.add_url_rule('/translatedFile/<filename>', 'download', self.download_file)

    class Config:
        def __init__(self, data):
            self.threads = data.get('threadNum') or PDFTranslator.DEFAULT_CONFIG['threadNum']
            self.service = data.get('service') or PDFTranslator.DEFAULT_CONFIG['service']
            self.engine = data.get('engine') or PDFTranslator.DEFAULT_CONFIG['engine']
            self.outputPath = data.get('outputPath') or PDFTranslator.DEFAULT_CONFIG['outputPath']
            self.configPath = data.get('configPath') or PDFTranslator.DEFAULT_CONFIG['configPath']
            self.sourceLang = data.get('sourceLang') or PDFTranslator.DEFAULT_CONFIG['sourceLang']
            self.targetLang = data.get('targetLang') or PDFTranslator.DEFAULT_CONFIG['targetLang']
            self.babeldoc = data.get('babeldoc', False)
            self.mono_cut = data.get('mono_cut', False)
            self.dual_cut = data.get('dual_cut', False)
            self.compare = data.get('compare', False)

            self.outputPath = self.get_abs_path(self.outputPath)
            self.configPath = self.get_abs_path(self.configPath)
            os.makedirs(self.outputPath, exist_ok=True)

            if self.engine not in ['pdf2zh', 'EbookTranslator'] and self.engine in services:
                self.engine = 'pdf2zh'
                print("[Warning - Zotero设置]: 请在Zotero设置面板中重新设置翻译engine参数为pdf2zh")
            print("[config]: ", self.__dict__)

        @staticmethod
        def get_abs_path(path):
            return path if os.path.isabs(path) else os.path.abspath(path)

    def process_request(self):
        data = request.get_json()
        config = self.Config(data)
        self.translated_dir = config.outputPath
        
        file_content = data.get('fileContent', '')
        if file_content.startswith('data:application/pdf;base64,'):
            file_content = file_content[len('data:application/pdf;base64,'):]
        
        input_path = os.path.join(config.outputPath, data['fileName'])
        with open(input_path, 'wb') as f:
            f.write(base64.b64decode(file_content))
        
        return input_path, config

    def translate_pdf(self, input_path, config):
        base_name = os.path.basename(input_path).replace('.pdf', '')
        output_files = {
            'mono': os.path.join(config.outputPath, f"{base_name}-mono.pdf"),
            'dual': os.path.join(config.outputPath, f"{base_name}-dual.pdf")
        }
        cmd = [
            config.engine, input_path, '--t', str(config.threads),
            '--output', config.outputPath, '--service', config.service,
            '--lang-in', config.sourceLang, '--lang-out', config.targetLang,
            '--config', config.configPath
        ]
        if config.babeldoc:
            cmd.append('--babeldoc')
        subprocess.run(cmd, check=True)
        if config.babeldoc:
            os.rename(os.path.join(config.outputPath, f"{base_name}.{config.targetLang}.mono.pdf"), output_files['mono'])
            os.rename(os.path.join(config.outputPath, f"{base_name}.{config.targetLang}.dual.pdf"), output_files['dual'])
        return output_files['mono'], output_files['dual']

    def split_pdf(self, input_pdf, output_pdf, compare=False, babeldoc=False):
        # 原有逻辑保持不变
        writer = PdfWriter()
        if ('dual' in input_pdf or compare) and not babeldoc:
            readers = [PdfReader(input_pdf) for _ in range(4)]
            for i in range(0, len(readers[0].pages), 2):
                original_media_box = readers[0].pages[i].mediabox
                width = original_media_box.width
                height = original_media_box.height
                left_page_1 = readers[0].pages[i]
                for box in ['mediabox', 'cropbox', 'bleedbox', 'trimbox', 'artbox']:
                    setattr(left_page_1, box, RectangleObject((0, 0, width/2, height)))
                left_page_2 = readers[1].pages[i+1]
                for box in ['mediabox', 'cropbox', 'bleedbox', 'trimbox', 'artbox']:
                    setattr(left_page_2, box, RectangleObject((0, 0, width/2, height)))
                right_page_1 = readers[2].pages[i]
                for box in ['mediabox', 'cropbox', 'bleedbox', 'trimbox', 'artbox']:
                    setattr(right_page_1, box, RectangleObject((width/2, 0, width, height)))
                right_page_2 = readers[3].pages[i+1]
                for box in ['mediabox', 'cropbox', 'bleedbox', 'trimbox', 'artbox']:
                    setattr(right_page_2, box, RectangleObject((width/2, 0, width, height)))
                if compare:
                    blank_page_1 = writer.add_blank_page(width, height)
                    blank_page_1.merge_transformed_page(left_page_1, (1, 0, 0, 1, 0, 0))
                    blank_page_1.merge_transformed_page(left_page_2, (1, 0, 0, 1, width / 2, 0))
                    blank_page_2 = writer.add_blank_page(width, height)
                    blank_page_2.merge_transformed_page(right_page_1, (1, 0, 0, 1, -width / 2, 0))
                    blank_page_2.merge_transformed_page(right_page_2, (1, 0, 0, 1, 0, 0))
                else:
                    writer.add_page(left_page_1)
                    writer.add_page(left_page_2)
                    writer.add_page(right_page_1)
                    writer.add_page(right_page_2)
        else:
            readers = [PdfReader(input_pdf) for _ in range(2)]
            for i in range(len(readers[0].pages)):
                page = readers[0].pages[i]
                original_media_box = page.mediabox
                width = original_media_box.width
                height = original_media_box.height
                left_page = readers[0].pages[i]
                left_page.mediabox = RectangleObject((0, 0, width / 2, height))
                right_page = readers[1].pages[i]
                right_page.mediabox = RectangleObject((width / 2, 0, width, height))
                writer.add_page(left_page)
                writer.add_page(right_page)

        with open(output_pdf, "wb") as output_file:
            writer.write(output_file)

    def submit_task(self):
        print("\n########## submitting task ##########")
        try:
            input_path, config = self.process_request()
            task_id = str(uuid.uuid4())  # 生成唯一任务 ID
            self.tasks[task_id] = {"status": "pending", "result": None, "error": None}

            # 在后台线程中执行翻译任务
            def run_task():
                try:
                    mono, dual = self.translate_pdf(input_path, config)
                    processed_files = [mono, dual]
                    if config.mono_cut:
                        output = mono.replace('-mono.pdf', '-mono-cut.pdf')
                        self.split_pdf(mono, output)
                        processed_files.append(output)
                    if config.dual_cut:
                        output = dual.replace('-dual.pdf', '-dual-cut.pdf')
                        self.split_pdf(dual, output, False, config.babeldoc)
                        processed_files.append(output)
                    if not config.babeldoc and config.compare:
                        output = dual.replace('-dual.pdf', '-compare.pdf')
                        self.split_pdf(dual, output, compare=True, babeldoc=False)
                        processed_files.append(output)
                    self.tasks[task_id] = {"status": "completed", "result": processed_files, "error": None}
                except Exception as e:
                    self.tasks[task_id] = {"status": "failed", "result": None, "error": str(e)}
                    print(f"[task {task_id} error]: ", e)

            threading.Thread(target=run_task).start()
            return jsonify({"status": "success", "taskId": task_id, "message": "Task submitted"}), 200
        except Exception as e:
            print("[submit task error]: ", e)
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def task_status(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            return jsonify({"status": "error", "message": "Task not found"}), 404
        return jsonify({
            "status": task["status"],
            "taskId": task_id,
            "result": task["result"] if task["status"] == "completed" else None,
            "error": task["error"] if task["status"] == "failed" else None
        }), 200
    
    def translate(self):
        print("\n########## translating ##########")
        try:
            input_path, config = self.process_request()
            mono, dual = self.translate_pdf(input_path, config)
            processed_files = []
            if config.mono_cut == True or config.mono_cut == "true":
                output = mono.replace('-mono.pdf', '-mono-cut.pdf')
                self.split_pdf(mono, output)
                processed_files.append(output)
            if config.dual_cut == True or config.dual_cut == "true":
                output = dual.replace('-dual.pdf', '-dual-cut.pdf')
                self.split_pdf(dual, output, False, config.babeldoc == True or config.babeldoc == "true")
                processed_files.append(output)
            if config.babeldoc == False or config.babeldoc == "false":
                if config.compare == True or config.compare == "true":
                    output = dual.replace('-dual.pdf', '-compare.pdf')
                    self.split_pdf(dual, output, compare=True, babeldoc=False)
                    processed_files.append(output)
            return jsonify({'status': 'success', 'processed': processed_files}), 200
        
        except Exception as e:
            print("[translate error]: ", e)
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def cut_pdf(self):
        print("\n########## cutting ##########")
        try:
            input_path, config = self.process_request()
            output_path = input_path.replace('.pdf', '-cut.pdf')
            self.split_pdf(input_path, output_path) # 保留原逻辑
            return jsonify({'status': 'success', 'path': output_path}), 200
        except Exception as e:
            print("[cut error]: ", e)
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def compare(self):
        print("\n########## compare ##########")
        try:
            input_path, config = self.process_request()
            if 'mono' in input_path:
                raise Exception('Please provide dual PDF or origial PDF for dual-comparison')
            if not 'dual' in input_path:
                _, dual = self.translate_pdf(input_path, config)
                input_path = dual
            output_path = input_path.replace('-dual.pdf', '-compare.pdf')
            self.split_pdf(input_path, output_path, compare=True)
            return jsonify({'status': 'success', 'path': output_path}), 200
        except Exception as e:
            print("[compare error]: ", e)
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def download_file(self, filename):
        file_path = os.path.join(self.translated_dir, filename)
        return send_file(file_path, as_attachment=True) if os.path.exists(file_path) else ('File not found', 404)

    def run(self):
        port = int(sys.argv[1]) if len(sys.argv) > 1 else self.DEFAULT_CONFIG['port']
        self.app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    translator = PDFTranslator()
    translator.run()