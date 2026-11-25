import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('package_server', Path(__file__).resolve().parents[1] / 'package_server.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def test_private_files_are_excluded_even_if_tracked_and_local_data_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            private = ['server/.env', 'server/.env.production', 'server/config/config.json',
                       'server/config/config.toml', 'server/translated/private.pdf',
                       'server/utils/__pycache__/cache.pyc', 'server/wenyi-tasks/key.json',
                       'server/custom-config.yaml', 'server/tests/private.pdf',
                       'server/zotero-pdf2zh-next-venv/lib/private.py',
                       'server/private.cmd', 'server/utils/private.ps1',
                       'server/utils/local/pdf2zh-service.ps1']
            public = sorted(package.REQUIRED | {
                'server/utils/helper.py', 'server/utils/pdf2zh-service.ps1',
                'server/启动-pdf2zh.cmd', 'server/停止-pdf2zh.cmd',
            })
            for name in private + public:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('fixture-content')
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            untracked = root / 'server/utils/local.py'
            untracked.write_text('private-untracked')
            output = root / 'dist/server.zip'
            package.build(root, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), set(public))
            for name in private:
                self.assertEqual((root / name).read_text(), 'fixture-content')
            self.assertTrue(untracked.exists())

    def test_missing_required_file_fails_without_overwriting_existing_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            output = root / 'server.zip'
            output.write_bytes(b'old-archive')
            with self.assertRaises(ValueError):
                package.build(root, output)
            self.assertEqual(output.read_bytes(), b'old-archive')

    def test_hidden_nested_files_are_never_allowed(self):
        for name in ['server/utils/.secret.py', 'server/utils/.cache/helper.py',
                     'server/utils/__pycache__/helper.py', 'server/config/.env.example']:
            self.assertFalse(package.allowed(name), name)
