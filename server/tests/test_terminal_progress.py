import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from utils.progress_display import TerminalProgress, execute_progress, progress_command
from utils.progress_runner import PREFIX, create_progress_handler
from utils.server_console import LoggedStream


class TerminalProgressTest(unittest.TestCase):
    def test_event_bridge_excludes_nonserializable_result(self):
        output = io.StringIO()
        context, handler = create_progress_handler(None)
        with context, contextlib.redirect_stdout(output):
            handler({'type': 'finish', 'translate_result': object()})
        self.assertEqual(json.loads(output.getvalue()[len(PREFIX):]), {'type': 'finish'})

    def test_carriage_returns_do_not_add_scrolling_lines(self):
        output = io.StringIO()
        display = TerminalProgress(None, output)
        display.update({'type': 'progress_start', 'overall_progress': 12, 'stage': 'Translate Paragraphs'})
        display.update({'type': 'progress_end', 'overall_progress': 85})
        self.assertIn(' 12%', output.getvalue())
        self.assertIn(' 85%', output.getvalue())
        self.assertIn('翻译段落', output.getvalue())
        self.assertIn('\r', output.getvalue())
        self.assertNotIn('\n', output.getvalue())
        display.update({'type': 'finish'})
        display.close()
        self.assertIn('100%', output.getvalue())
        self.assertEqual(output.getvalue().count('\n'), 1)

    def test_progress_does_not_regress_or_claim_early_completion(self):
        display = TerminalProgress(None, io.StringIO())
        for value in [80, 20, float('nan'), 100]:
            display.update({'type': 'progress_end', 'overall_progress': value})
        self.assertEqual(display.percent, 99)
        display.close(failed=True)
        self.assertNotIn('100%', display.stream.getvalue())

    def test_narrow_terminal_does_not_mutate_full_stage(self):
        display = TerminalProgress(None, io.StringIO())
        with patch('utils.progress_terminal.shutil.get_terminal_size', return_value=os.terminal_size((45, 20))):
            display.update({'type': 'progress_start', 'stage': 'Parse PDF and Create Intermediate Representation'})
        self.assertEqual(display.stage, '解析 PDF')

    def test_module_command_keeps_runtime_arguments_and_config(self):
        args = ['--bing', '--config-file', 'path with spaces/config.toml']
        command = [sys.executable, '-I', '-m', 'pdf2zh_next', *args]
        result = progress_command(command, os.environ)
        self.assertEqual(result[0:2], [sys.executable, '-I'])
        self.assertEqual(result[-len(args):], args)
        self.assertTrue(result[3].endswith('progress_runner.py'))
        self.assertIsNone(progress_command(['pdf2zh', 'paper.pdf'], os.environ))

    def test_managed_executable_keeps_its_own_python(self):
        executable = Path(sys.executable).with_name('pdf2zh_next.exe')
        if not executable.exists():
            self.skipTest('managed Windows entry point is unavailable')
        result = progress_command([str(executable), '--bing', 'paper.pdf'], os.environ)
        self.assertEqual(Path(result[0]), Path(sys.executable))
        self.assertEqual(result[-2:], ['--bing', 'paper.pdf'])

    def test_server_logging_preserves_terminal_control_characters(self):
        console, log = io.StringIO(), io.StringIO()
        tee = LoggedStream(console, log, threading.RLock())
        message = '\r翻译 [####------] 40%\r翻译 [##########] 100%\n'
        tee.write(message)
        tee.flush()
        self.assertEqual(console.getvalue(), message)
        self.assertEqual(log.getvalue(), message)

    def test_real_subprocess_events_reach_display_and_task_state(self):
        source = "import json; print('diagnostic'); print('PDF2ZH_PROGRESS '+json.dumps({'type':'progress_update','overall_progress':42,'stage':'Translate Paragraphs'})); print('PDF2ZH_PROGRESS '+json.dumps({'type':'finish'}))"
        output = io.StringIO()
        diagnostics = []
        with contextlib.redirect_stdout(output), patch('utils.progress_terminal.task_manager.update_task') as update:
            execute_progress([sys.executable, '-c', source], os.environ.copy(), 'test-terminal-events', on_output=diagnostics.append)
        self.assertIn(42, [call.args[1]['progress'] for call in update.call_args_list])
        self.assertIn('100%', output.getvalue())
        self.assertNotIn('diagnostic', output.getvalue())
        log = (Path(__file__).resolve().parents[1] / 'work/logs/translation-test-terminal-events.log').read_text(encoding='utf-8')
        self.assertIn('diagnostic', log)
        self.assertIn('diagnostic\n', diagnostics)

    def test_table_reference_wrapper_is_preserved(self):
        command = [sys.executable, '-u', str(Path(__file__).resolve().parents[1] / 'utils/table_runner.py'), 'auto', '--zotero-skip-references', '--bing', 'paper.pdf']
        result = progress_command(command, os.environ)
        index = result.index('--wrapped-script')
        self.assertEqual(result[index + 1:], command[2:])

    def test_wrapped_runner_installs_progress_without_dropping_existing_hooks(self):
        import types
        from utils import progress_runner
        package = types.ModuleType('pdf2zh_next')
        high_level = types.ModuleType('pdf2zh_next.high_level')
        main = types.ModuleType('pdf2zh_next.main')
        main.cli = lambda: self.fail('The wrapped script owns CLI invocation')
        package.high_level = high_level
        modules = {'pdf2zh_next': package, 'pdf2zh_next.high_level': high_level, 'pdf2zh_next.main': main}
        argv = ['progress_runner.py', '--wrapped-script', 'table_runner.py', 'auto', '--bing', 'paper.pdf']
        with patch.dict(sys.modules, modules), patch.object(sys, 'argv', argv), patch.object(progress_runner.runpy, 'run_path') as run:
            progress_runner.main()
            self.assertEqual(sys.argv, ['table_runner.py', 'auto', '--bing', 'paper.pdf'])
            self.assertIs(high_level.create_progress_handler, progress_runner.create_progress_handler)
            run.assert_called_once_with('table_runner.py', run_name='__main__')

    def test_nonzero_exit_is_propagated(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                execute_progress([sys.executable, '-c', 'raise SystemExit(7)'], os.environ.copy(), 'test-terminal-exit')

    def test_structured_error_is_not_success_even_when_cli_exits_zero(self):
        source = "print('PDF2ZH_PROGRESS {\"type\":\"error\",\"error\":\"HTTP 429\"}')"
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 429'):
                execute_progress([sys.executable, '-c', source], os.environ.copy(), 'test-terminal-error')


if __name__ == '__main__':
    unittest.main()
