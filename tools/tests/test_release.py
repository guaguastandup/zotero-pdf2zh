"""Exercise commit/publish boundaries in disposable repositories; never publish."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from package_server import REQUIRED


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        subprocess.run(['git', 'init', '-q', '-b', 'test-branch', str(self.root)], check=True)
        for name in REQUIRED:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        shutil.copytree(TOOLS, self.root / 'tools', ignore=shutil.ignore_patterns('__pycache__'))
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        scanner = self.bin / 'gitleaks'
        scanner.write_text('#!' + sys.executable + '\nimport os,sys\nsys.exit(int(os.environ.get("FAKE_SCAN_RESULT", "0")))\n')
        scanner.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'GIT_AUTHOR_NAME': 'Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
                    'GIT_COMMITTER_NAME': 'Fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'}
        self.git('add', 'server', 'tools')
        self.git('commit', '-qm', 'initial')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, env=self.env, text=True).strip()

    def release(self, *args):
        return subprocess.run([sys.executable, 'tools/release.py', *args], cwd=self.root,
                              env=self.env, capture_output=True, text=True)

    def test_prepare_does_not_commit_or_remove_private_files(self):
        private = self.root / 'server/.env'
        private.write_text('private sentinel')
        head = self.git('rev-parse', 'HEAD')
        result = self.release()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertEqual(private.read_text(), 'private sentinel')
        self.assertTrue((self.root / 'dist/server.zip').exists())

    def test_commit_includes_new_explicit_source_in_archive(self):
        import zipfile
        source = self.root / 'server/utils/new.py'
        source.parent.mkdir(exist_ok=True)
        source.write_text('# fixture')
        result = self.release('--commit-message', 'selected change', '--paths', 'server/utils/new.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'selected change')
        with zipfile.ZipFile(self.root / 'dist/server.zip') as archive:
            self.assertIn('server/utils/new.py', archive.namelist())
        self.assertEqual(self.git('tag', '--list'), '')

    def test_scan_failure_prevents_commit(self):
        self.env['FAKE_SCAN_RESULT'] = '1'
        head = self.git('rev-parse', 'HEAD')
        result = self.release('--commit-message', 'blocked', '--paths', 'server/server.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertEqual(self.git('diff', '--cached', '--name-only'), '')

    def test_staged_changes_and_private_paths_are_rejected(self):
        private = self.root / 'server/.env'
        private.write_text('private sentinel')
        result = self.release('--commit-message', 'blocked', '--paths', 'server/.env')
        self.assertNotEqual(result.returncode, 0)
        self.git('add', 'server/.env')
        result = self.release()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('staged changes', result.stderr)

    def test_publish_rejects_feature_branch_before_network_or_tag(self):
        result = self.release('--publish')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('only from main', result.stderr)
        self.assertEqual(self.git('tag', '--list'), '')
