"""Provider switches must not inherit fields or credentials from another job."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import toml
from utils.config import Config


class RequestConfigTest(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(redirect_stdout(StringIO()))

    def config(self, engine='pdf2zh_next', name='Research Gateway', extra=None, **kwargs):
        api = dict(apiType='openai-compatible', configMode='replace', apiUrl='https://example.test/v1',
                   apiKey='test-key', model='test-model', extraData=extra or {})
        api.update(kwargs)
        return Config(dict(engine=engine, service=name, next_service=name, llm_api=api))

    def source(self, engine):
        path = Path(self.directory) / ('settings.json' if engine == 'pdf2zh' else 'settings.toml')
        if engine == 'pdf2zh':
            data = {'translators': [{'name': 'openailiked', 'envs': {'OPENAILIKED_API_KEY': 'old-secret', 'old_field': 3}}]}
            path.write_text(json.dumps(data))
        else:
            path.write_text(toml.dumps({'openaicompatible_detail': {
                'openai_compatible_api_key': 'old-secret', 'openai_compatible_timeout': 99,
                'openai_compatible_enable_json_mode': True, 'old_field': 3}}))
        return path

    def provider(self, path, engine):
        if engine == 'pdf2zh':
            return json.loads(Path(path).read_text())['translators'][0]['envs']
        return toml.load(path)['openaicompatible_detail']

    def test_five_extra_fields_then_two_and_then_empty(self):
        for engine in ('pdf2zh', 'pdf2zh_next'):
            with self.subTest(engine=engine):
                path = self.source(engine)
                first = {f'field{i}': i for i in range(5)}
                self.config(engine, extra=first).update_config_file(path)
                self.config(engine, extra={'field0': False, 'field1': 0}).update_config_file(path)
                detail = self.provider(path, engine)
                self.assertIs(detail['field0'], False)
                self.assertEqual(detail['field1'], 0)
                for key in ('field2', 'field3', 'field4', 'old_field', 'openai_compatible_timeout', 'openai_compatible_enable_json_mode'):
                    self.assertNotIn(key, detail)
                self.config(engine, extra={}).update_config_file(path)
                self.assertFalse(any(key.startswith('field') for key in self.provider(path, engine)))

    def test_empty_key_does_not_reuse_saved_credential(self):
        for engine in ('pdf2zh', 'pdf2zh_next'):
            path = self.source(engine)
            key = 'OPENAILIKED_API_KEY' if engine == 'pdf2zh' else 'openai_compatible_api_key'
            config = self.config(engine, apiKey='')
            self.assertIsNone(config.detect_saved_credential_reuse(path))
            with config.runtime_config_file(path) as runtime:
                self.assertEqual(self.provider(runtime, engine)[key], '')

    def test_builtin_provider_replaces_optional_fields_too(self):
        path = Path(self.directory) / 'openai.toml'
        path.write_text(toml.dumps({'openai_detail': {'openai_api_key': 'old-secret',
            'openai_temperature': 0.8, 'openai_send_temprature': True, 'openai_enable_json_mode': True}}))
        config = Config({'engine': 'pdf2zh_next', 'next_service': 'openai', 'llm_api': {
            'configMode': 'replace', 'apiKey': 'new-key', 'model': 'model', 'extraData': {}}})
        config.update_config_file(path)
        self.assertEqual(toml.load(path)['openai_detail'], {'openai_api_key': 'new-key', 'openai_model': 'model', 'openai_base_url': ''})

    def test_parallel_jobs_keep_independent_settings_and_cleanup(self):
        for engine in ('pdf2zh', 'pdf2zh_next'):
            path = self.source(engine)
            before = path.read_bytes()
            barrier = Barrier(2)
            def job(name):
                config = self.config(engine, name=name, apiKey=name)
                with config.runtime_config_file(path) as runtime:
                    barrier.wait(timeout=5)
                    contents = Path(runtime).read_text()
                    self.assertIn(name, contents)
                    other = 'secret-b' if name == 'secret-a' else 'secret-a'
                    self.assertNotIn(other, contents)
                    return runtime
            with ThreadPoolExecutor(max_workers=2) as executor:
                paths = list(executor.map(job, ['secret-a', 'secret-b']))
            self.assertNotEqual(*paths)
            self.assertTrue(all(not Path(p).exists() for p in paths))
            self.assertEqual(path.read_bytes(), before)

    def test_failed_engine_still_cleans_private_config(self):
        path = self.source('pdf2zh_next')
        with self.assertRaises(RuntimeError):
            with self.config().runtime_config_file(path) as runtime:
                raise RuntimeError('engine failure')
        self.assertFalse(Path(runtime).exists())

    def test_legacy_partial_request_preserves_manually_saved_defaults(self):
        path = self.source('pdf2zh_next')
        config = Config({'engine': 'pdf2zh_next', 'next_service': 'openailiked'})
        with config.runtime_config_file(path) as runtime:
            self.assertEqual(self.provider(runtime, 'pdf2zh_next')['openai_compatible_api_key'], 'old-secret')
            self.assertEqual(self.provider(runtime, 'pdf2zh_next')['openai_compatible_timeout'], 99)

    def test_unknown_name_requires_explicit_interface(self):
        with self.assertRaises(ValueError):
            Config({'engine': 'pdf2zh_next', 'next_service': 'misspelled-service'})
        self.assertEqual(self.config().engine_service, 'openaicompatible')
        self.assertEqual(self.config('pdf2zh').engine_service, 'openailiked')

    def test_runtime_settings_are_accepted_by_real_next_engine(self):
        profile = Path(self.directory)
        expanduser = Path.expanduser
        with patch.object(Path, 'home', return_value=profile), patch.object(
            Path, 'expanduser', lambda path: profile / str(path)[2:]
            if str(path).startswith('~/') else expanduser(path)
        ):
            try:
                from pdf2zh_next.config.translate_engine_model import OpenAICompatibleSettings
                from babeldoc.translator.cache import db
            except ImportError:
                self.skipTest("pdf2zh-next integration runtime is not installed")
        self.addCleanup(db.close)
        path = self.source('pdf2zh_next')
        config = self.config(extra={'openai_compatible_enable_json_mode': False})
        with config.runtime_config_file(path) as runtime:
            settings = OpenAICompatibleSettings(**self.provider(runtime, 'pdf2zh_next'))
            settings.validate_settings()
            self.assertEqual(settings.openai_compatible_api_key, 'test-key')
            self.assertEqual(settings.openai_compatible_model, 'test-model')
            self.assertIs(settings.openai_compatible_enable_json_mode, False)
            self.assertIsNone(settings.openai_compatible_timeout)

    def test_null_credentials_are_cleared_and_invalid_field_types_fail_early(self):
        path = self.source('pdf2zh_next')
        with self.config(apiKey=None).runtime_config_file(path) as runtime:
            self.assertEqual(self.provider(runtime, 'pdf2zh_next')['openai_compatible_api_key'], '')
        with self.assertRaisesRegex(ValueError, 'apiKey'):
            self.config(apiKey=123)

    def test_normal_translation_entry_uses_private_config_until_engine_returns(self):
        import server
        from types import SimpleNamespace
        path = self.source('pdf2zh_next')
        config = self.config()
        captured = []
        translator = server.PDFTranslator.__new__(server.PDFTranslator)
        def execute(command, *args):
            runtime = command[command.index('--config-file') + 1]
            captured.append(runtime)
            self.assertTrue(Path(runtime).is_file())
            self.assertIn('--openaicompatible', command)
            for kind in ('mono', 'dual'):
                Path(self.directory, f'paper.no_watermark.zh-CN.{kind}.pdf').write_bytes(b'%PDF-test')
        with patch.object(server, 'config_path', {'pdf2zh_next': str(path)}), \
                patch.object(server, 'output_folder', self.directory), \
                patch.object(server, 'args', SimpleNamespace(enable_winexe=False, enable_venv=False), create=True), \
                patch.object(server, 'execute_with_progress', side_effect=execute):
            result = translator.translate_pdf_next('paper.pdf', config)
        self.assertTrue(result)
        self.assertEqual(len(captured), 1)
        self.assertFalse(Path(captured[0]).exists())
