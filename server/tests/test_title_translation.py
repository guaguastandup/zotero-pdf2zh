import concurrent.futures
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from utils.title_translation import (
    TitleTranslationError, TitleTranslator, prepare_request, run_worker, validate_result,
)


def request(**changes):
    return dict(title='Attention Is All You Need', engine='pdf2zh_next',
                next_service='openailiked', targetLang='zh-CN', sourceLang='en', **changes)


class TitleRequestTests(unittest.TestCase):
    def test_uses_selected_profile_without_stale_settings(self):
        saved = {'openaicompatible_detail': {
            'openai_compatible_api_key': 'old-secret',
            'openai_compatible_model': 'old-model',
            'openai_compatible_temperature': '0.9',
        }}
        resolved = prepare_request(request(llm_api={
            'apiKey': 'new-secret', 'model': 'new-model', 'apiUrl': 'http://localhost/v1',
            'extraData': {'openai_compatible_send_temperature': 'false', 'unrelated': 'value'},
        }), saved)
        self.assertEqual(resolved['service'], 'openaicompatible')
        self.assertEqual(resolved['detail']['openai_compatible_api_key'], 'new-secret')
        self.assertNotIn('openai_compatible_temperature', resolved['detail'])
        self.assertNotIn('unrelated', resolved['detail'])
        self.assertEqual(saved['openaicompatible_detail']['openai_compatible_api_key'], 'old-secret')
        self.assertEqual(prepare_request(request(), saved)['detail']['openai_compatible_model'], 'old-model')

    def test_invalid_and_unsupported_requests_do_not_select_another_service(self):
        for data, code in [
            (None, 'invalid_request'), ({**request(), 'title': ''}, 'invalid_request'),
            ({**request(), 'title': 'x' * 1201}, 'invalid_request'),
            ({**request(), 'engine': 'pdf2zh'}, 'unsupported_engine'),
            ({**request(), 'next_service': 'bing'}, 'unsupported_service'),
        ]:
            with self.subTest(code=code), self.assertRaises(TitleTranslationError) as error:
                prepare_request(data)
            self.assertEqual(error.exception.code, code)

    def test_chinese_output_validation(self):
        r = prepare_request(request())
        self.assertEqual(validate_result('  注意力\n就是全部所需  ', r), '注意力 就是全部所需')
        for value in ('', None, 'Attention Is All You Need', '注意力の研究', '中' * 1201):
            with self.assertRaises(TitleTranslationError):
                validate_result(value, r)
        self.assertEqual(validate_result('Titre traduit', {**r, 'targetLang': 'fr'}), 'Titre traduit')


class TitleCacheTests(unittest.TestCase):
    def test_concurrent_requests_share_work_and_config_changes_invalidate(self):
        calls = []
        entered, release = threading.Event(), threading.Event()
        def worker(r, *_):
            calls.append(r)
            entered.set()
            release.wait(2)
            return '注意力就是全部所需'
        translator = TitleTranslator(worker=worker, max_entries=2)
        r = prepare_request(request())
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(translator.translate, r, 'python', 'runtime')
            self.assertTrue(entered.wait(1))
            b = pool.submit(translator.translate, r, 'python', 'runtime')
            release.set()
            self.assertEqual(a.result(), b.result())
        translator.translate(r, 'python', 'runtime')
        self.assertEqual(len(calls), 1)
        for updated in ({**r, 'title': 'New title'}, {**r, 'targetLang': 'zh-TW'},
                        {**r, 'detail': {'apiKey': 'changed'}}):
            translator.translate(updated, 'python', 'runtime')
        self.assertEqual(len(calls), 4)
        self.assertLessEqual(len(translator.cache), 2)

    def test_failed_requests_are_not_cached_and_expired_entries_refresh(self):
        calls = []
        def worker(*_):
            calls.append(1)
            if len(calls) == 1:
                raise TitleTranslationError('timeout')
            return '中文标题'
        translator = TitleTranslator(worker=worker, ttl=-1)
        r = prepare_request(request())
        with self.assertRaises(TitleTranslationError):
            translator.translate(r, 'python', 'runtime')
        translator.translate(r, 'python', 'runtime')
        translator.translate(r, 'python', 'runtime')
        self.assertEqual(len(calls), 3)
        self.assertEqual(translator.pending, {})


class TitleEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.server = server

    def setUp(self):
        self.arguments = SimpleNamespace(enable_venv=False, enable_winexe=False, env_tool='auto')
        self.args_patch = patch.object(self.server, 'args', self.arguments, create=True)
        self.args_patch.start()
        self.addCleanup(self.args_patch.stop)
        self.translator = self.server.PDFTranslator(self.arguments)
        self.translator.title_translator = TitleTranslator(worker=lambda *_: '注意力就是全部所需')
        self.client = self.translator.app.test_client()

    def test_route_and_capability(self):
        health = self.client.get('/health').get_json()
        self.assertIn('openaicompatible', health['titleTranslation']['services'])
        response = self.client.post('/translateTitle', json=request(llm_api={}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['title'], '注意力就是全部所需')

    def test_old_engine_and_failure_are_explicit_and_do_not_expose_errors(self):
        response = self.client.post('/translateTitle', json={**request(), 'engine': 'pdf2zh'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'unsupported_engine')
        with patch.object(self.translator.title_translator, 'translate', side_effect=RuntimeError('secret-key')):
            response = self.client.post('/translateTitle', json=request(llm_api={}))
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('secret-key', response.get_data(as_text=True))


@unittest.skipUnless(os.environ.get('PDF2ZH_TITLE_TEST_PYTHON'), 'Set PDF2ZH_TITLE_TEST_PYTHON to test the installed engine')
class NativeTitleWorkerTests(unittest.TestCase):
    def test_native_engine_uses_title_only_and_selected_openai_profile(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append((self.path, self.headers.get('Authorization'), body))
                data = json.dumps({'id': 'test', 'object': 'chat.completion',
                    'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {
                        'role': 'assistant', 'content': '注意力就是全部所需'}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as root:
                for service in ('openailiked', 'openai'):
                    data = {**request(), 'next_service': service, 'llm_api': {
                        'apiKey': 'test-secret', 'apiUrl': f'http://127.0.0.1:{server.server_port}/v1',
                        'model': 'selected-model', 'extraData': {},
                    }}
                    title = run_worker(prepare_request(data), os.environ['PDF2ZH_TITLE_TEST_PYTHON'], root)
                    self.assertEqual(title, '注意力就是全部所需')
                self.assertEqual(list(Path(root).iterdir()), [])
            self.assertEqual(len(calls), 2)
            for path, auth, body in calls:
                self.assertEqual(path, '/v1/chat/completions')
                self.assertEqual(auth, 'Bearer test-secret')
                self.assertEqual(body['model'], 'selected-model')
                self.assertIn('Attention Is All You Need', body['messages'][0]['content'])
                self.assertIn('zh-CN', body['messages'][0]['content'])
                self.assertNotIn('Hello', body['messages'][0]['content'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_real_subprocess_deadline_and_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            start = time.monotonic()
            with self.assertRaises(TitleTranslationError) as error:
                run_worker(prepare_request(request()), os.environ['PDF2ZH_TITLE_TEST_PYTHON'], root, timeout=0.01)
            self.assertEqual(error.exception.code, 'timeout')
            self.assertLess(time.monotonic() - start, 3)
            self.assertEqual(list(Path(root).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
