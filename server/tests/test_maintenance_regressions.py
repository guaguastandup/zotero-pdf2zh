import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import fitz
from utils import execute, environment_lifecycle as lifecycle
from utils.venv import VirtualEnvManager
from utils.cropper import Cropper
from utils.config import Config

# Load actual server methods without starting Flask or installing environments.
source = Path(__file__).parents[1] / 'server.py'
tree = ast.parse(source.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PDFTranslator')
selected = {'translate_pdf', 'translate_pdf_next', 'get_filetype', 'get_filename_after_process'}
namespace = dict(os=os, subprocess=subprocess, pdf2zh='pdf2zh', pdf2zh_next='pdf2zh_next',
                 config_path={'pdf2zh': 'unused', 'pdf2zh_next': 'unused'},
                 output_folder='output', args=SimpleNamespace(enable_venv=False),
                 pdf2zh_next_service_aliases={})
methods = ast.ClassDef(name='Translator', bases=[], keywords=[], body=[n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in selected], decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[methods], type_ignores=[])), str(source), 'exec'), namespace)

class MaintenanceTests(unittest.TestCase):
    def test_utf8_invalid_bytes_do_not_stall_and_split_characters_survive(self):
        for raw in (b'hello\x80next', b'hello\xed\xa0\x80next', '中文进度'.encode()):
            for split in range(len(raw) + 1):
                a, pending = execute._decode_pty_utf8(raw[:split], b'')
                b, pending = execute._decode_pty_utf8(raw[split:], pending)
                self.assertEqual(a+b, raw.decode('utf8', errors='replace'))
                self.assertEqual(pending, b'')
        pending = b''
        for _ in range(100):
            text, pending = execute._decode_pty_utf8(b'\x80progress 5/17\r', pending)
            self.assertIn('progress 5/17', text)
            self.assertLessEqual(len(pending), 3)

    def test_tqdm_is_not_overwritten_by_legacy(self):
        with patch.object(execute.task_manager, 'update_task') as update:
            execute._parse_progress(' 17%| 17/100 [00:03] Running 0/1', 'task')
        self.assertEqual(update.call_count, 1)
        self.assertEqual(update.call_args.args[1]['progress'], 17)

    def test_engine_selection_uses_invocation_not_paths(self):
        manager = VirtualEnvManager.__new__(VirtualEnvManager)
        manager.is_windows = False
        manager.curr_envtool = 'uv'
        manager.ensure_env = Mock(return_value=True)
        with tempfile.TemporaryDirectory() as tmp:
            manager._existing = Mock(return_value=('uv', Path(tmp), Path(tmp)/'bin/python'))
            for command, engine, arguments in (
                (['pdf2zh', '/pdf2zh_next/Paper.PDF'], 'pdf2zh', ['/pdf2zh_next/Paper.PDF']),
                ([r'C:\tools\pdf2zh_next.exe', 'paper.pdf'], 'pdf2zh_next', ['paper.pdf']),
                (['python3', '-u', '-m', 'pdf2zh_next', 'paper.pdf'], 'pdf2zh_next', ['paper.pdf']),
            ):
                result, env = manager._resolved_command(command)
                manager.ensure_env.assert_called_with(engine)
                self.assertEqual(result, [str(Path(tmp)/'bin/python'), '-u', '-m', engine, *arguments])

    def test_existing_custom_configs_receive_bitstring_constraint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'venv.json'
            data = {engine: {tool: {'packages': [engine]} for tool in ('uv','conda')} for engine in lifecycle.ENGINE_ENV_NAMES}
            path.write_text(json.dumps(data))
            before = path.read_bytes()
            for engine in data:
                for tool in data[engine]:
                    _, packages = lifecycle.load_requirements(engine, tool, path)
                    self.assertIn('bitstring>=4.3.0,<5', packages)
            self.assertEqual(path.read_bytes(), before)

    def test_existing_health_check_rejects_bitstring_5_but_keeps_old_engine(self):
        manager = VirtualEnvManager.__new__(VirtualEnvManager)
        manager.config_path = None
        def run(command, **kwargs):
            code = command[-1]
            for bitstring, success in [('4.3.1', True), ('5.0.0', False)]:
                with patch('importlib.metadata.version', side_effect=lambda name: bitstring if name == 'bitstring' else '1.0.0'):
                    if success:
                        exec(code, {})
                    else:
                        with self.assertRaises(AssertionError): exec(code, {})
            return SimpleNamespace(returncode=0)
        with patch('utils.venv.subprocess.run', side_effect=run), patch('utils.venv.managed_runtime_health', return_value=(True,'ok')):
            self.assertTrue(manager._requirements_ok('pdf2zh_next', 'uv', Path(sys.executable)))

    def test_merge_failure_closes_documents_and_propagates(self):
        cropper = Cropper.__new__(Cropper)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'input.pdf'
            with fitz.open() as doc:
                page = doc.new_page(); page.insert_text((30,30),'test'); doc.save(source)
            opened = []
            real_open = fitz.open
            def track(*args, **kwargs):
                doc = real_open(*args, **kwargs); opened.append(doc); return doc
            with patch('utils.cropper.fitz.open', side_effect=track):
                with self.assertRaises(RuntimeError): cropper.merge_pdf(source, Path(tmp)/'missing/output.pdf')
            self.assertTrue(all(doc.is_closed for doc in opened))
            with patch.object(cropper, 'merge_pdf', side_effect=RuntimeError('merge failed')):
                with self.assertRaisesRegex(RuntimeError, 'merge failed'): cropper.pdf_dual_mode(source, 'TB', 'LR')

    def test_odd_page_merge_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp)/'input.pdf', Path(tmp)/'output.pdf'
            with fitz.open() as doc:
                for i in range(3): doc.new_page().insert_text((30,30),str(i))
                doc.save(source)
            Cropper.__new__(Cropper).merge_pdf(source, target)
            with fitz.open(target) as result: self.assertEqual(len(result), 2)

    def test_pdf_names_preserve_directory_and_embedded_suffix(self):
        translator = namespace['Translator']()
        for name in ('Paper.PDF','Paper.PdF','a.pdf.pdf'):
            path = '/tmp/folder.pdf/'+name
            stem = os.path.splitext(path)[0]
            for engine, separator in [('pdf2zh','-'),('pdf2zh_next','.')]:
                self.assertEqual(translator.get_filename_after_process(path,'origin-cut',engine), stem+separator+'cut.pdf')

    def test_skip_all_pages_fails_before_subprocess_for_both_engines(self):
        translator = namespace['Translator']()
        config = SimpleNamespace(service='openai', update_config_file=lambda _: None,
            targetLang='en', sourceLang='en', thread_num=1, skip_last_pages=3,
            qps=1, no_watermark=True)
        namespace['PdfReader'] = lambda _: SimpleNamespace(pages=[1,2,3])
        namespace['execute_with_progress'] = Mock()
        for method in (translator.translate_pdf, translator.translate_pdf_next):
            with self.assertRaisesRegex(ValueError,'skip_last_pages'): method('paper.pdf',config)
        namespace['execute_with_progress'].assert_not_called()

    def test_legacy_output_names_and_page_arguments(self):
        translator = namespace['Translator']()
        config = SimpleNamespace(service='openai', update_config_file=lambda _: None,
            targetLang='en', sourceLang='en', thread_num=1, skip_last_pages=1,
            skip_font_subsets=False, babeldoc=False)
        namespace['PdfReader'] = lambda _: SimpleNamespace(pages=[1,2,3])
        namespace['execute_with_progress'] = Mock()
        for name in ('Paper.PDF','a.pdf.pdf'):
            with patch('os.path.isfile', return_value=True):
                paths = translator.translate_pdf(name,config)
            self.assertEqual(paths[0], 'output/'+os.path.splitext(name)[0]+'-mono.pdf')
        cmd = namespace['execute_with_progress'].call_args.args[0]
        self.assertEqual(cmd[cmd.index('-p')+1], '1-2')

    def test_next_output_names_accept_mixed_case(self):
        translator = namespace['Translator']()
        namespace['args'] = SimpleNamespace(enable_venv=False, enable_winexe=False)
        namespace['execute_with_progress'] = Mock()
        for name in ('Paper.PDF', 'a.pdf.pdf'):
            with contextlib.redirect_stdout(io.StringIO()):
                config = Config({'engine':'pdf2zh_next', 'service':'openai'})
            config.update_config_file = lambda _: None
            with patch('os.path.exists', return_value=True), patch('os.path.getsize', return_value=100):
                paths = translator.translate_pdf_next(name, config)
            self.assertTrue(paths)
            self.assertTrue(all(os.path.basename(p).startswith(os.path.splitext(name)[0]+'.') for p in paths))

    def test_legacy_blank_fields_preserve_saved_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'config.json'
            original={'translators':[{'name':'openai','envs':{'OPENAI_API_KEY':'test-secret','OPENAI_MODEL':'saved-model'}}]}
            path.write_text(json.dumps(original))
            with contextlib.redirect_stdout(io.StringIO()):
                config=Config({'engine':'pdf2zh','service':'openai','llm_api':{}})
                config.update_config_file(path)
            values=json.loads(path.read_text())['translators'][0]['envs']
            self.assertEqual(values['OPENAI_API_KEY'],'test-secret')
            self.assertEqual(values['OPENAI_MODEL'],'saved-model')

    def test_font_update_without_service_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, font=Path(tmp)/'config.json', Path(tmp)/'font.ttf'
            path.write_text('{"translators": []}');font.touch()
            with contextlib.redirect_stdout(io.StringIO()):
                config=Config({'engine':'pdf2zh','service':'unknown','fontFile':str(font)})
                config.update_config_file(path)
            self.assertEqual(json.loads(path.read_text())['NOTO_FONT_PATH'],str(font))

if __name__ == '__main__': unittest.main()
