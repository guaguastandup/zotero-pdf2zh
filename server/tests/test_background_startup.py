"""Offline regressions for launching the server without a terminal."""
import ast
import contextlib
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from utils import environment_lifecycle as lifecycle

SERVER = Path(__file__).resolve().parents[1]


class BackgroundStartupTests(unittest.TestCase):
    def test_background_initializes_streams_and_cwd_and_appends_log(self):
        from utils.startup import configure_background
        old_cwd = os.getcwd()
        self.addCleanup(os.chdir, old_cwd)
        with tempfile.TemporaryDirectory() as temp:
            logfile = Path(temp) / 'logs' / 'server.log'
            logfile.parent.mkdir()
            logfile.write_text('previous run\n', encoding='utf-8')
            with patch.object(sys, 'stdin', None), patch.object(sys, 'stdout', None), patch.object(sys, 'stderr', None):
                configure_background(['--non-interactive', '--log-file', str(logfile)], SERVER)
                streams = (sys.stdin, sys.stdout, sys.stderr)
                try:
                    print('后台日志')
                    sys.stderr.write('failure detail\n')
                    self.assertEqual(sys.stdin.read(), '')
                    self.assertEqual(Path.cwd(), SERVER)
                finally:
                    for stream in set(streams):
                        stream.close()
            self.assertEqual(logfile.read_text(encoding='utf-8'), 'previous run\n后台日志\nfailure detail\n')

    def test_interactive_launch_preserves_streams_and_directory(self):
        from utils.startup import configure_background
        original = (sys.stdin, sys.stdout, sys.stderr, Path.cwd())
        configure_background([], SERVER)
        self.assertEqual((sys.stdin, sys.stdout, sys.stderr, Path.cwd()), original)

    def test_missing_dependency_without_console_is_logged_and_exits(self):
        # Force a predictable import failure without depending on which optional
        # packages happen to be installed in the test interpreter.
        probe = '''
import builtins, runpy, sys
script, logfile = sys.argv[1:]
sys.path.insert(0, str(__import__('pathlib').Path(script).parent))
sys.argv = [script, '--non-interactive', '--log-file', logfile]
real_import = builtins.__import__
def checked_import(name, *args, **kwargs):
    if name == 'flask':
        raise ImportError('offline startup dependency failure')
    return real_import(name, *args, **kwargs)
builtins.__import__ = checked_import
sys.stdin = sys.stdout = sys.stderr = None
runpy.run_path(script, run_name='__main__')
'''
        with tempfile.TemporaryDirectory() as temp:
            logfile = Path(temp) / 'startup.log'
            result = subprocess.run(
                [sys.executable, '-c', probe, str(SERVER / 'server.py'), str(logfile)],
                cwd=temp, capture_output=True, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('offline startup dependency failure', logfile.read_text(encoding='utf-8'))

    def run_startup(self, argv, occupied=False):
        # Execute the real entry point with external operations stubbed.
        source = ast.parse((SERVER / 'server.py').read_text(encoding='utf-8'))
        body = next(node.body for node in source.body if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'" and any(isinstance(child, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'parser' for target in child.targets) for child in node.body))
        import argparse
        env = dict(argparse=argparse, sys=sys, os=os, socket=socket,
                   PORT=8890, enable_venv=True, default_env_tool='auto',
                   str2bool=lambda value: value.lower() == 'true',
                   root_path=str(SERVER), __version__='test',
                   pdf2zh='pdf2zh', pdf2zh_next='pdf2zh_next',
                   find_existing_environment=Mock(return_value=None),
                   fetch_and_show_notices=Mock(), check_for_updates=Mock(return_value=('1','2')),
                   prepare_path=Mock(), PDFTranslator=Mock())
        sock = Mock()
        sock.__enter__ = Mock(return_value=sock)
        sock.__exit__ = Mock(return_value=False)
        sock.connect_ex.return_value = 0 if occupied else 1
        with patch.object(sys, 'argv', ['server.py', *argv]), patch('socket.socket', return_value=sock), patch('builtins.input', side_effect=AssertionError('must not prompt')), contextlib.redirect_stdout(io.StringIO()):
            exec(compile(ast.Module(body=body, type_ignores=[]), str(SERVER / 'server.py'), 'exec'), env)
        return env

    def test_failed_checks_exit_nonzero_without_prompt(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_startup(['--non-interactive'], occupied=True)
        self.assertEqual(raised.exception.code, 1)

    def test_background_skips_network_update_and_starts_server(self):
        env = self.run_startup(['--non-interactive'])
        env['fetch_and_show_notices'].assert_not_called()
        env['check_for_updates'].assert_not_called()
        env['PDFTranslator'].return_value.run.assert_called_once_with('127.0.0.1', 8890, debug=False)

    def test_background_never_prompts_for_engine_update_even_with_tty(self):
        with patch.object(sys, 'argv', ['server.py', '--non-interactive']), patch.object(sys.stdin, 'isatty', return_value=True), patch.object(lifecycle, 'find_existing_environment', side_effect=AssertionError('must skip before discovery')):
            lifecycle.maybe_prompt_existing_user_update()
