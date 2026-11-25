"""Offline checks: no daemon, image downloads or user configuration changes."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from utils import update_interaction as interaction

ROOT = Path(__file__).resolve().parents[2]


class UpdateInteractionTests(unittest.TestCase):
    def test_container_never_prompts_even_with_tty(self):
        with patch.dict(os.environ, {'ZOTERO_PDF2ZH_CONTAINER': '1'}), \
                patch.object(interaction.sys, 'stdin') as stdin, \
                patch('builtins.input', side_effect=AssertionError('must not prompt')), \
                contextlib.redirect_stdout(io.StringIO()):
            stdin.isatty.return_value = True
            self.assertFalse(interaction.can_prompt_for_update())
            self.assertFalse(interaction.source_update_requested())

    def test_noninteractive_service_never_prompts(self):
        with patch.object(interaction, 'is_container', return_value=False), \
                patch.object(interaction.sys, 'stdin', None), \
                patch('builtins.input', side_effect=AssertionError('must not prompt')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(interaction.source_update_requested())

    def test_desktop_still_respects_explicit_answer(self):
        with patch.object(interaction, 'is_container', return_value=False), \
                patch.object(interaction.sys, 'stdin') as stdin:
            stdin.isatty.return_value = True
            for answer, expected in [('y', True), (' YES ', True), ('n', False)]:
                with patch('builtins.input', return_value=answer):
                    self.assertEqual(interaction.source_update_requested(), expected)


@unittest.skipIf(os.name == 'nt', 'POSIX script fixture')
class DockerUpdateCommandTests(unittest.TestCase):
    def run_update(self, mode='server', fail=''):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / 'docker'
            fake.write_text('#!/bin/sh\necho "$*" >> "$UPDATE_TEST_LOG"\ncase "$*" in\n  *"$UPDATE_TEST_FAIL"*) if [ -n "$UPDATE_TEST_FAIL" ]; then exit 9; fi ;;\nesac\n')
            fake.chmod(0o755)
            log = root / 'commands'
            result = subprocess.run(['sh', str(ROOT / 'docker/update.sh'), mode],
                env={**os.environ, 'PATH': f'{root}:{os.environ.get("PATH", "")}',
                     'UPDATE_TEST_LOG': str(log), 'UPDATE_TEST_FAIL': fail},
                capture_output=True, text=True)
            return result, log.read_text().splitlines() if log.exists() else []

    def test_default_updates_server_without_pulling_engine(self):
        result, commands = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('compose build --pull --no-cache pdf2zh-server', commands)
        self.assertIn('compose up -d --no-deps --no-build pdf2zh-server', commands)
        self.assertFalse(any('compose run' in cmd for cmd in commands))
        self.assertFalse(any(' down' in cmd or 'prune' in cmd for cmd in commands))

    def test_all_resolves_engine_from_compose_and_pulls_before_restart(self):
        result, commands = self.run_update('all')
        self.assertEqual(result.returncode, 0, result.stderr)
        pull = next(i for i, cmd in enumerate(commands) if 'compose run' in cmd)
        restart = next(i for i, cmd in enumerate(commands) if 'compose up' in cmd)
        self.assertLess(pull, restart)
        self.assertIn('ZOTERO_PDF2ZH_FROM_IMAGE', commands[pull])
        self.assertIn('--rm -T --no-deps', commands[pull])

    def test_build_or_pull_failure_does_not_restart_running_service(self):
        for failure in ('compose build', 'compose run'):
            result, commands = self.run_update('all', failure)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(any('compose up' in cmd for cmd in commands))

    def test_invalid_option_runs_no_docker_command(self):
        result, commands = self.run_update('wrong')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(commands, [])

class UpdatePolicyTests(unittest.TestCase):
    def test_legacy_false_wins_over_explicit_mode(self):
        for args in [['--check_update=False', '--update-mode=notify'],
                     ['--check_update', 'false', '--update-mode', 'prompt'],
                     ['--check_update=f', '--update-mode=notify']]:
            self.assertEqual(interaction.update_mode(args), 'off')
        self.assertEqual(interaction.update_mode([]), 'prompt')
        self.assertEqual(interaction.update_mode(['--update-mode', 'notify']), 'notify')

    def test_notify_and_off_never_prompt_on_desktop(self):
        for mode in ['notify', 'off']:
            with patch.object(interaction.sys, 'argv', ['server.py', '--update-mode', mode]), \
                    patch.object(interaction, 'is_container', return_value=False), \
                    patch.object(interaction.sys, 'stdin') as stdin, \
                    patch('builtins.input', side_effect=AssertionError('must not prompt')), \
                    contextlib.redirect_stdout(io.StringIO()):
                stdin.isatty.return_value = True
                self.assertFalse(interaction.can_prompt_for_update())
                self.assertFalse(interaction.source_update_requested())

class DockerSharedTemporaryFilesTests(unittest.TestCase):
    def test_config_and_glossary_use_shared_tmpdir_and_are_cleaned(self):
        # A fresh process exercises tempfile's TMPDIR selection before caching it.
        code = '''
from pathlib import Path
import os
from utils.config import Config
from utils.glossary_upload import temporary_glossary
root = Path(os.environ['TMPDIR'])
source = root / 'source.json'
source.write_text('{"translators": []}')
config = Config({'engine': 'pdf2zh', 'service': 'google'})
with config.runtime_config_file(str(source)) as path:
    config_path = Path(path)
    assert config_path.is_relative_to(root)
    assert config_path.is_file()
    with temporary_glossary('source,target\\nhello,world\\n') as glossary:
        glossary_path = Path(glossary)
        assert glossary_path.is_relative_to(root)
        assert 'hello' in glossary_path.read_text(encoding='utf-8-sig')
    assert not glossary_path.exists()
assert not config_path.exists()
assert source.exists()
'''
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([interaction.sys.executable, '-c', code],
                cwd=ROOT / 'server', env={**os.environ, 'TMPDIR': directory, 'PYTHONIOENCODING': 'utf-8'},
                capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
        dockerfile = (ROOT / 'docker/Dockerfile').read_text(encoding='utf-8')
        self.assertIn('mkdir -p /app/server/translated /app/server/config/.tmp', dockerfile)
        self.assertIn('export TMPDIR=/app/server/config/.tmp', dockerfile)

@unittest.skipIf(os.name == 'nt', 'Container shell fixture requires POSIX')
class DockerPublishedServerCompatibilityTests(unittest.TestCase):
    def test_old_and_new_server_archives_receive_supported_update_flags(self):
        import json
        import shlex
        dockerfile = (ROOT / 'docker/Dockerfile').read_text(encoding='utf-8')
        line = next(line for line in dockerfile.splitlines() if line.strip().startswith("'update_option="))
        primary = shlex.split(line.strip().removesuffix('\\'))[0]
        alternate = next(line for line in (ROOT / 'docker2/Dockerfile').read_text(encoding='utf-8').splitlines() if line.startswith('CMD '))
        command = json.loads(alternate[4:])
        self.assertEqual(command[:2], ['sh', '-c'])
        for entrypoint in (primary, command[2]):
            for supports_notify in (True, False):
                with self.subTest(supports_notify=supports_notify), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / 'server.py'
                    source.write_text('--update-mode' if supports_notify else '--check_update')
                    fake = root / 'python'
                    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
                    fake.chmod(0o755)
                    result = subprocess.run(['sh', '-c', entrypoint.replace('/app/server/server.py', shlex.quote(str(source)))],
                        env={**os.environ, 'PATH': f'{root}:{os.environ.get("PATH", "")}'},
                        text=True, capture_output=True, check=True)
                    flags = result.stdout.splitlines()
                    self.assertIn('--update-mode=notify' if supports_notify else '--check_update=False', flags)
                    self.assertNotIn('--check_update=False' if supports_notify else '--update-mode=notify', flags)
