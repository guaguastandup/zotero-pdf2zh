import tempfile
import unittest
from pathlib import Path
from utils.log_stream import LogStream, is_loopback


class LogStreamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'server.log'
        self.reader = LogStream(self.path, max_bytes=64, secrets=lambda: ['private-value'])

    def test_missing_and_invalid(self):
        self.assertEqual(self.reader.read(0), dict(text='', offset=0, reset=False, cursor=''))
        for value in (-1, '1', True):
            with self.assertRaises(ValueError):
                self.reader.read(value)

    def test_partial_utf8_line_waits(self):
        self.path.write_bytes('你好'.encode()[:-1])
        self.assertEqual(self.reader.read(0)['offset'], 0)
        with self.path.open('ab') as log:
            log.write('你好'.encode()[-1:] + b'\n')
        result = self.reader.read(0)
        self.assertEqual(result['text'], '你好\n')
        self.assertEqual(result['offset'], 7)

    def test_redacts_and_bounds(self):
        self.path.write_text('api_key=secret\nprivate-value\nBearer abc\nnormal\n', encoding='utf-8')
        result = self.reader.read(0)
        self.assertNotIn('secret', result['text'])
        self.assertNotIn('private-value', result['text'])
        self.assertNotIn('abc', result['text'])
        self.assertIn('normal', result['text'])
        self.path.write_text('x' * 100 + '\nnormal\n', encoding='utf-8')
        result = self.reader.read(0)
        self.assertLessEqual(result['offset'], 64)
        following = self.reader.read(result['offset'])
        self.assertNotIn('xxx', following['text'])

    def test_truncate_and_replace(self):
        self.path.write_text('old\n', encoding='utf-8')
        first = self.reader.read(0)
        self.path.write_text('n\n', encoding='utf-8')
        self.assertTrue(self.reader.read(first['offset'])['reset'])
        self.path.unlink()
        self.path.write_text('new content\n', encoding='utf-8')
        self.assertTrue(self.reader.read(2)['reset'])

    def test_real_file_append_keeps_both_client_cursors(self):
        self.path.write_bytes(b'first\n')
        first = self.reader.read(0)
        other = self.reader.read(0)
        with self.path.open('ab') as log:
            log.write(b'second\n')
            log.flush()
        for cursor in (first['offset'], other['offset']):
            result = self.reader.read(cursor)
            self.assertEqual(result, dict(text='second\n', offset=13, reset=False, cursor=result['cursor']))

    def test_metadata_timestamp_change_does_not_mean_rotation(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import os
        self.path.write_bytes(b'first\nsecond\n')
        stat = self.path.stat()
        changing_stats = [SimpleNamespace(st_dev=stat.st_dev, st_ino=stat.st_ino,
                         st_ctime_ns=stamp, st_size=stat.st_size) for stamp in (1, 2)]
        with patch('os.fstat', side_effect=changing_stats):
            self.reader.read(0)
            result = self.reader.read(6)
        self.assertFalse(result['reset'])
        self.assertEqual(result['text'], 'second\n')

    def test_renamed_rotation_resets_cursor(self):
        self.path.write_bytes(b'old\n')
        first = self.reader.read(0)
        self.path.rename(self.path.with_suffix('.old'))
        self.path.write_bytes(b'new longer record\n')
        self.assertTrue(self.reader.read(first['offset'])['reset'])

    def test_addresses(self):
        for value in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
            self.assertTrue(is_loopback(value))
        for value in ('192.168.0.1', None, 'localhost'):
            self.assertFalse(is_loopback(value))

class LogApiTests(unittest.TestCase):
    def setUp(self):
        # Compile only the handler, keeping tests independent of engine installs.
        import ast
        import re
        from flask import Flask, request, jsonify
        source = (Path(__file__).parents[1] / 'server.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'PDFTranslator')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'get_logs')
        namespace = dict(request=request, jsonify=jsonify, re=re, is_loopback=is_loopback)
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'server.py', 'exec'), namespace)
        from types import SimpleNamespace
        self.reader = SimpleNamespace(read=lambda offset, cursor=None: dict(text='ok\n', offset=offset+3, reset=False))
        self.owner = SimpleNamespace(log_recording_enabled=True, log_stream=self.reader)
        app = Flask(__name__)
        app.add_url_rule('/api/logs', view_func=lambda: namespace['get_logs'](self.owner))
        self.client = app.test_client()

    def test_local_and_parameters(self):
        self.assertEqual(self.client.get('/api/logs?offset=2').json['offset'], 5)
        self.assertEqual(self.client.get('/api/logs?offset=2&cursor=abc').status_code, 200)
        for query in ('offset=-1', 'offset=abc', 'path=x', 'offset=1&offset=2', 'cursor=a&cursor=b'):
            self.assertEqual(self.client.get('/api/logs?' + query).status_code, 400)
        self.assertEqual(self.client.get('/api/logs', environ_base={'REMOTE_ADDR':'192.168.1.3'}).status_code, 403)
        self.owner.log_recording_enabled = False
        self.assertFalse(self.client.get('/api/logs').json['available'])

    def test_secret_loading_failure_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'server.log'
            path.write_bytes(b'confidential-output\n')
            def broken_secrets():
                raise ValueError('malformed credential configuration')
            self.owner.log_stream = LogStream(path, secrets=broken_secrets)
            response = self.client.get('/api/logs?offset=0&cursor=')
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json, {'error': 'Logs unavailable'})
            self.assertNotIn('confidential', response.text)

    def test_fail_closed(self):
        def fail(offset, cursor=None):
            raise RuntimeError('private api key')
        self.reader.read = fail
        response = self.client.get('/api/logs')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private', response.text)

class ConcurrentLogTests(unittest.TestCase):
    def test_concurrent_cursors_and_failed_secret_loading(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'server.log'
            path.write_bytes(b'hello\n')
            reader = LogStream(path)
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(reader.read, [0] * 20))
            self.assertTrue(all(result == dict(text='hello\n', offset=6, reset=False, cursor=result['cursor']) for result in results))
            def fail():
                raise ValueError('secret config malformed')
            reader.secrets = fail
            with self.assertRaises(ValueError):
                reader.read(0)


class SignedCursorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'server.log'
        self.path.write_bytes(b'old\n')
        self.reader = LogStream(self.path)

    def poll(self, previous, reader=None):
        return (reader or self.reader).read(previous['offset'], previous['cursor'])

    def test_two_clients_across_rotation(self):
        a = self.reader.read(0)
        b = self.reader.read(0)
        self.path.rename(self.path.with_suffix('.old'))
        self.path.write_bytes(b'new longer\n')
        for previous in (a, b):
            result = self.poll(previous)
            self.assertTrue(result['reset'])
            self.assertEqual(result['text'], 'new longer\n')
            self.assertFalse(self.poll(result)['reset'])

    def test_truncate_regrow_and_restart(self):
        old = self.reader.read(0)
        self.path.write_bytes(b'replaced and longer\n')
        result = self.poll(old)
        self.assertTrue(result['reset'])
        self.assertIn('replaced', result['text'])
        self.assertTrue(self.poll(result, LogStream(self.path))['reset'])

    def test_empty_initial_cursor_is_not_rotation(self):
        result = self.reader.read(0, '')
        self.assertFalse(result['reset'])
        self.assertEqual(result['text'], 'old\n')
        self.assertTrue(self.reader.read(result['offset'], '')['reset'])

    def test_append_and_invalid_token(self):
        previous = self.reader.read(0)
        with self.path.open('ab') as output:
            output.write(b'next\n')
        result = self.poll(previous)
        self.assertFalse(result['reset'])
        self.assertEqual(result['text'], 'next\n')
        self.assertTrue(self.reader.read(result['offset'], 'invalid')['reset'])
        self.path.unlink()
        self.assertEqual(self.poll(result)['cursor'], '')
