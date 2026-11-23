"""Exercise concurrent same-name uploads, real post-processing, and download protocol."""
import base64
import contextlib
import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
import pymupdf as fitz
import server
from utils.config import Config
from utils.cropper import Cropper
from utils.task_manager import TaskManager


def pdf_bytes(label):
    with fitz.open() as doc:
        doc.new_page(width=600, height=800).insert_text((40, 80), label)
        return doc.tobytes()


class JobFileTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(patch.object(server, 'output_folder', str(self.root)))
        self.manager = TaskManager()
        self.manager._delayed_remove = lambda _id: None
        self.enterContext(patch.object(server, 'task_manager', self.manager))
        self.translator = server.PDFTranslator.__new__(server.PDFTranslator)
        self.translator.cropper = Cropper()
        self.app = Flask(__name__)

    def request(self, label='FIRST', **extra):
        return dict(engine='pdf2zh', fileName='paper.pdf', fileContent=base64.b64encode(pdf_bytes(label)).decode(), **extra)

    def test_concurrent_same_filename_keeps_input_and_downloads_independent(self):
        barrier = Barrier(2)
        def job(label):
            with self.app.test_request_context('/translate', json=self.request(label)):
                path, config = self.translator.process_request()
                try:
                    barrier.wait(timeout=5)
                    with fitz.open(path) as doc:
                        self.assertIn(label, doc[0].get_text())
                    output = Path(config.output_dir) / 'paper-mono.pdf'
                    output.write_bytes(pdf_bytes(label))
                    return path, self.translator._success_files_payload([str(output)], config)
                finally:
                    self.translator._cleanup_job_files(config)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(job, ['FIRST', 'SECOND']))
        self.assertNotEqual(results[0][0], results[1][0])
        self.assertNotEqual(results[0][1]['fileList'], results[1][1]['fileList'])
        for (source, payload), label in zip(results, ('FIRST', 'SECOND')):
            self.assertFalse(Path(source).exists())
            name = payload['fileList'][0]
            self.assertNotIn('/', name)  # Old clients still download flat names.
            self.assertTrue(name.endswith('-mono.pdf'))
            with self.app.test_request_context('/translatedFile/' + name):
                response = self.translator.download_file(name)
                response.direct_passthrough = False
                with fitz.open(stream=response.get_data(), filetype='pdf') as doc:
                    self.assertIn(label, doc[0].get_text())
                response.close()
        self.assertFalse(list(self.root.glob('.job-*')))

    def test_requested_glossary_survives_workspace_cleanup(self):
        with self.app.test_request_context('/translate', json=self.request(saveGlossary=True)):
            _, config = self.translator.process_request()
            pdf = Path(config.output_dir) / 'paper-mono.pdf'
            pdf.write_bytes(pdf_bytes('RESULT'))
            csv = Path(config.output_dir) / 'paper.zh.glossary.csv'
            csv.write_text('source,target\nexample,示例\n')
            payload = self.translator._success_files_payload([str(pdf)], config)
            self.translator._cleanup_job_files(config)
        self.assertEqual(len(payload['fileList']), 1)
        glossaries = list(self.root.glob('*.glossary.csv'))
        self.assertEqual(len(glossaries), 1)
        self.assertIn('示例', glossaries[0].read_text())

    def test_crop_route_publishes_and_cleans_workspace(self):
        with self.app.test_request_context('/crop', json=self.request()):
            response, status = self.translator.crop()
        self.assertEqual(status, 200)
        payload = response.get_json()
        self.assertEqual(len(payload['fileList']), 1)
        self.assertTrue(Path(payload['filePaths'][0]).is_file())
        self.assertFalse(list(self.root.glob('.job-*')))

    def test_invalid_operation_and_failed_worker_cleanup(self):
        data = self.request()
        data['fileName'] = 'paper.cut.pdf'
        with self.app.test_request_context('/crop', json=data):
            _, status = self.translator.crop()
        self.assertEqual(status, 400)
        self.assertFalse(list(self.root.glob('.job-*')))
        for asynchronous in (False, True):
            with self.app.test_request_context('/translate', json=self.request(asyncJob=asynchronous)):
                _, config = self.translator.process_request()
                workdir = Path(config.output_dir)
                def fail():
                    raise RuntimeError('synthetic engine failure')
                response, _ = self.translator._start_accepted_job('test', {}, fail, '/translate', config=config)
            if asynchronous:
                import time
                deadline = time.monotonic() + 3
                while workdir.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
            self.assertFalse(workdir.exists())

    def test_sync_and_async_translate_routes_keep_results_after_cleanup(self):
        import time
        for asynchronous in (False, True):
            def translate(input_path, config, task_id):
                with fitz.open(input_path) as doc:
                    self.assertIn('COMPLETE', doc[0].get_text())
                outputs = []
                for kind in ('mono', 'dual'):
                    path = Path(config.output_dir) / f'paper-{kind}.pdf'
                    path.write_bytes(pdf_bytes(kind))
                    outputs.append(str(path))
                return outputs
            with self.subTest(asynchronous=asynchronous), patch.object(self.translator, 'translate_pdf', side_effect=translate):
                with self.app.test_request_context('/translate', json=self.request('COMPLETE', asyncJob=asynchronous)):
                    response, status = self.translator.translate()
                self.assertEqual(status, 200)
                payload = response.get_json()
                if asynchronous:
                    self.assertEqual(payload['status'], 'accepted')
                    deadline = time.monotonic() + 3
                    task = self.manager.get_task(payload['taskId'])
                    while not task['finished'] and time.monotonic() < deadline:
                        time.sleep(0.01)
                        task = self.manager.get_task(payload['taskId'])
                    payload = task['result']
                self.assertEqual(payload['status'], 'success')
                self.assertEqual(len(payload['filePaths']), 2)
                self.assertTrue(all(Path(path).is_file() for path in payload['filePaths']))
        # Completion is reported just before worker cleanup; wait for teardown.
        deadline = time.monotonic() + 3
        while list(self.root.glob('.job-*')) and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(list(self.root.glob('.job-*')))

    def test_failed_job_keeps_generated_pdf_for_recovery_without_reporting_success(self):
        with self.app.test_request_context('/translate', json=self.request()):
            _, config = self.translator.process_request()
            def fail_after_output():
                (Path(config.output_dir) / 'paper-mono.pdf').write_bytes(pdf_bytes('RECOVERABLE'))
                raise RuntimeError('dual generation failed')
            response, status = self.translator._start_accepted_job('partial', {}, fail_after_output, '/translate', config=config)
        self.assertEqual(status, 500)
        self.assertEqual(response.get_json()['status'], 'error')
        outputs = list(self.root.glob('*.pdf'))
        self.assertEqual(len(outputs), 1)
        with fitz.open(outputs[0]) as doc:
            self.assertIn('RECOVERABLE', doc[0].get_text())
        self.assertFalse(list(self.root.glob('.job-*')))

    def test_failed_publication_preserves_files_in_workspace_for_recovery(self):
        with self.app.test_request_context('/translate', json=self.request()):
            _, config = self.translator.process_request()
        output = Path(config.output_dir) / 'paper-mono.pdf'
        output.write_bytes(pdf_bytes('KEEP_ME'))
        with patch('utils.job_files.os.replace', side_effect=OSError('destination unavailable')):
            self.translator._cleanup_job_files(config)
        self.assertTrue(output.is_file())
        self.translator._cleanup_job_files(config)
        self.assertFalse(Path(config.output_dir).exists())
        self.assertEqual(len(list(self.root.glob('*.pdf'))), 1)

    def test_invalid_base64_is_rejected_without_a_workspace(self):
        data = self.request()
        data['fileContent'] = 'not a valid base64!'
        with self.app.test_request_context('/translate', json=data):
            with self.assertRaisesRegex(ValueError, 'Invalid PDF content'):
                self.translator.process_request()
        self.assertFalse(list(self.root.glob('.job-*')))

    def test_engines_refuse_partial_output_before_positional_consumers(self):
        self.enterContext(patch.object(server, 'args', SimpleNamespace(enable_winexe=False, enable_venv=False), create=True))
        for engine in ('pdf2zh', 'pdf2zh_next'):
            config = Config(dict(engine=engine, next_service='openai'))
            config.output_dir = str(self.root)
            def execute(command, *args):
                directory = Path(command[command.index('--output') + 1])
                name = 'paper-mono.pdf' if engine == 'pdf2zh' else 'paper.no_watermark.zh-CN.mono.pdf'
                (directory / name).write_bytes(pdf_bytes('ONLY_MONO'))
            with self.subTest(engine=engine), patch.object(server, 'execute_with_progress', side_effect=execute):
                with self.assertRaisesRegex(RuntimeError, '输出不完整.*dual'):
                    if engine == 'pdf2zh':
                        self.translator._translate_pdf('paper.pdf', config, None, 'unused.json')
                    else:
                        self.translator._translate_pdf_next('paper.pdf', config, None, None, 'unused.toml')

    def test_next_crop_compare_does_not_reverse_the_engines_page_order_twice(self):
        self.enterContext(patch.object(server, 'args', SimpleNamespace(enable_winexe=False, enable_venv=False), create=True))
        for translated_first, enhance in ((False, False), (True, False), (False, True)):
            config = Config(dict(engine='pdf2zh_next', next_service='openai', transFirst=translated_first,
                                 enhanceCompatibility=enhance, dualMode='TB', noMono=True))
            config.output_dir = str(self.root)
            def execute(command, *args):
                order = ['TRANSLATED', 'ORIGINAL'] if '--dual-translate-first' in command or '--enhance-compatibility' in command else ['ORIGINAL', 'TRANSLATED']
                with fitz.open() as doc:
                    for label in order:
                        doc.new_page(width=600, height=800).insert_text((90, 180), label)
                    doc.save(self.root / 'paper.no_watermark.zh-CN.dual.pdf')
            with self.subTest(translated_first=translated_first, enhance=enhance), patch.object(server, 'execute_with_progress', side_effect=execute):
                files = self.translator._translate_pdf_next('paper.pdf', config, None, None, 'unused.toml')
                output = self.root / 'crop-compare.pdf'
                self.translator.cropper.crop_pdf(config, files[0], 'dual', str(output), 'crop-compare')
                with fitz.open(output) as doc:
                    original_x = doc[0].search_for('ORIGINAL')[0].x0
                    translated_x = doc[0].search_for('TRANSLATED')[0].x0
                    self.assertEqual(translated_x < original_x, translated_first)

    def test_legacy_compare_converts_alternating_pages_despite_next_lr_preference(self):
        source = self.root / 'paper-dual.pdf'
        with fitz.open() as doc:
            doc.new_page(width=600, height=800).insert_text((40, 80), 'FIRST')
            doc.new_page(width=600, height=800).insert_text((40, 80), 'SECOND')
            doc.save(source)
        config = Config(dict(engine='pdf2zh', dualMode='LR'))
        result = self.translator._execute_compare_job('legacy', str(source), config, 'pdf2zh', 'dual')
        with fitz.open(result['filePaths'][0]) as doc:
            self.assertEqual(len(doc), 1)
            self.assertEqual(doc[0].rect.width, 1200)
            self.assertIn('FIRST', doc[0].get_text())
            self.assertIn('SECOND', doc[0].get_text())
