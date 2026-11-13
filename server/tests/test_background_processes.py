"""No process may create a console for a Windows background server."""
import ast
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from utils import startup, environment_lifecycle, execute, venv


class BackgroundProcessTests(unittest.TestCase):
    def test_process_options_only_hide_windows_background_children(self):
        for platform, argv, expected in [
            ('win32', ['server.py', '--non-interactive'], {'creationflags': 0x08000000}),
            ('win32', ['server.py'], {}),
            ('linux', ['server.py', '--non-interactive'], {}),
        ]:
            with self.subTest(platform=platform, argv=argv), patch.object(sys, 'platform', platform), patch.object(sys, 'argv', argv):
                self.assertEqual(startup.background_subprocess_options(), expected)
                self.assertIs(startup.subprocess_stdout(), sys.stdout if expected else None)

    def test_every_server_child_launch_applies_console_policy(self):
        root = Path(__file__).resolve().parents[1]
        for path in [root / 'server.py', *(root / 'utils').glob('*.py')]:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for call in ast.walk(tree):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == 'subprocess' and call.func.attr in {'Popen', 'run', 'call', 'check_output', 'check_call'}):
                    continue
                with self.subTest(file=path.name, line=call.lineno):
                    # The standalone executable silent branch already hides its
                    # console in interactive mode; preserve that existing policy.
                    if any(item.arg == 'creationflags' for item in call.keywords):
                        continue
                    self.assertTrue(any(item.arg is None and isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == 'background_subprocess_options' for item in call.keywords))

    def test_environment_discovery_child_uses_background_options(self):
        with patch.object(sys, 'platform', 'win32'), patch.object(sys, 'argv', ['server.py', '--non-interactive']), patch.object(environment_lifecycle.shutil, 'which', return_value='conda'), patch.object(environment_lifecycle.subprocess, 'run', return_value=Mock(stdout='{}')) as run:
            self.assertEqual(environment_lifecycle._conda_info(), {})
            self.assertEqual(run.call_args.kwargs['creationflags'], 0x08000000)

    def test_venv_translation_child_uses_background_log_stream(self):
        manager = venv.VirtualEnvManager.__new__(venv.VirtualEnvManager)
        manager.get_command_and_env = Mock(return_value=(['python', 'engine'], {}))
        child = Mock(stderr=io.StringIO(''))
        child.wait.return_value = 0
        with patch.object(sys, 'platform', 'win32'), patch.object(sys, 'argv', ['server.py', '--non-interactive']), patch.object(venv.subprocess, 'Popen', return_value=child) as popen:
            manager.execute_in_env(['engine'])
            self.assertEqual(popen.call_args.kwargs['creationflags'], 0x08000000)
            self.assertIs(popen.call_args.kwargs['stdout'], sys.stdout)

    def test_progress_translation_child_uses_background_log_stream(self):
        child = Mock(stderr=io.BytesIO())
        child.wait.return_value = 0
        with patch.object(sys, 'platform', 'win32'), patch.object(sys, 'argv', ['server.py', '--non-interactive']), patch.object(execute.subprocess, 'Popen', return_value=child) as popen, patch.object(execute.threading, 'Thread'):
            execute._execute_with_inherit(['python', 'engine'], {}, None, 80)
            self.assertEqual(popen.call_args.kwargs['creationflags'], 0x08000000)
            self.assertIs(popen.call_args.kwargs['stdout'], sys.stdout)

class CommandLoggingTests(unittest.TestCase):
    def test_redacts_separate_and_equals_secret_arguments(self):
        command = ['python', '--openai-api-key', 'fixture-secret-one', '--api_key=fixture-secret-two', '--access-token', 'fixture-secret-three', '--password=fixture-secret-four', '--model', 'model-name']
        expected = ['python', '--openai-api-key', '***', '--api_key=***', '--access-token', '***', '--password=***', '--model', 'model-name']
        self.assertEqual(startup.safe_command(command), expected)
        self.assertEqual(command[2], 'fixture-secret-one')

    def test_venv_failed_command_logs_and_exception_do_not_contain_key(self):
        manager = venv.VirtualEnvManager.__new__(venv.VirtualEnvManager)
        command = ['python', '--provider-api-key', 'fixture-sensitive-value']
        manager.get_command_and_env = Mock(return_value=(command, {}))
        child = Mock(stderr=io.StringIO(''))
        child.wait.return_value = 1
        output = io.StringIO()
        from contextlib import redirect_stdout
        with patch.object(venv.subprocess, 'Popen', return_value=child) as popen, redirect_stdout(output):
            with self.assertRaises(venv.subprocess.CalledProcessError) as raised:
                manager.execute_in_env(command)
        self.assertNotIn('fixture-sensitive-value', output.getvalue())
        self.assertNotIn('fixture-sensitive-value', str(raised.exception))
        self.assertEqual(popen.call_args.args[0], command)

    def test_progress_command_logs_and_exception_do_not_contain_key(self):
        command = ['python', '--provider-api-key=fixture-sensitive-value']
        output = io.StringIO()
        from contextlib import redirect_stdout
        from types import SimpleNamespace
        with patch.object(sys, 'platform', 'win32'), patch.object(execute, 'prepare_deepseek_runtime_command', side_effect=lambda cmd, env: cmd), patch.object(execute, 'prepare_table_runtime_command', side_effect=lambda cmd: cmd), patch.object(execute, '_execute_with_inherit') as run, redirect_stdout(output):
            execute.execute_with_progress(command, None, SimpleNamespace(enable_venv=False), None)
        self.assertNotIn('fixture-sensitive-value', output.getvalue())
        self.assertEqual(run.call_args.args[0], command)
        child = Mock(stderr=io.BytesIO())
        child.wait.return_value = 1
        with patch.object(execute.subprocess, 'Popen', return_value=child), patch.object(execute.threading, 'Thread'):
            with self.assertRaises(execute.subprocess.CalledProcessError) as raised:
                execute._execute_with_inherit(command, {}, None, 80)
        self.assertNotIn('fixture-sensitive-value', str(raised.exception))

class PackageManagerLoggingTests(unittest.TestCase):
    def test_background_installer_output_goes_to_log(self):
        with patch.object(sys, 'platform', 'win32'), patch.object(sys, 'argv', ['server.py', '--non-interactive']), patch.object(environment_lifecycle, '_build_install_command', return_value=['uv', 'pip', 'install', 'fixture-package']), patch.object(environment_lifecycle.subprocess, 'run') as run:
            self.assertTrue(environment_lifecycle._run_install('uv', Path('fixture-python'), ['fixture-package'], ['https://example.invalid/simple']))
            self.assertEqual(run.call_args.kwargs['creationflags'], 0x08000000)
            self.assertIs(run.call_args.kwargs['stdout'], sys.stdout)
            self.assertIs(run.call_args.kwargs['stderr'], sys.stdout)
