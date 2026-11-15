"""Keep private Wenyi runtime data out of releases and source synchronization."""

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import auto_update

PRIVATE_DIRECTORIES = ("zotero-wenyi-venv", "wenyi-runtime", "wenyi-tasks")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class WenyiDistributionTests(unittest.TestCase):
    def test_release_workflow_uses_whitelist_packer(self):
        """release.yml 必须走 pack_server.py 白名单, 不得回退到 zip 黑名单。"""
        text = (
            REPOSITORY_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("pack_server.py", text)
        self.assertNotIn("zip -r server.zip server", text)

    def test_pack_server_whitelist_excludes_wenyi_data_and_tests(self):
        """白名单 = git 跟踪文件; 运行时私有目录与 server/tests 天然不进包。

        真跑一次打包验证, 而不是解析 workflow 文本: 打包逻辑本身才是
        防线的本体(黑名单时代的教训: 排除清单漏一项就全量泄漏)。
        """
        result = subprocess.run(
            ["git", "ls-files", "--", "server"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertTrue(tracked)
        for name in PRIVATE_DIRECTORIES:
            self.assertFalse(
                any(
                    f == f"server/{name}" or f.startswith(f"server/{name}/")
                    for f in tracked
                ),
                f"{name} 不应被 git 跟踪",
            )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "server.zip"
            subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY_ROOT / "pack_server.py"),
                    "--output",
                    str(output),
                ],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
        self.assertIn("server/server.py", names)
        self.assertFalse(
            any(name.startswith("server/tests/") for name in names), "server/tests 不应进包"
        )
        for name in PRIVATE_DIRECTORIES:
            self.assertFalse(
                any(f"server/{name}/" in entry for entry in names),
                f"{name} 不应进包",
            )

    def test_source_update_preserves_wenyi_environment_sessions_and_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "server"
            target.mkdir()
            (target / "server.py").write_text('__version__ = "1.0.0"\n')
            for name in PRIVATE_DIRECTORIES:
                private = target / name
                private.mkdir()
                (private / "private-sentinel").write_text("original local data")
            release = root / "fixture.zip"
            with zipfile.ZipFile(release, "w") as archive:
                archive.writestr("server/server.py", '__version__ = "9.9.9"\n')
                for name in PRIVATE_DIRECTORIES:
                    archive.writestr(f"server/{name}/private-sentinel", "must not overwrite")

            def download(_urls, destination, _label):
                shutil.copyfile(release, destination)

            with (
                patch.object(auto_update, "get_xpi_info_from_repo", return_value=([], None)),
                patch.object(auto_update, "_download_first", side_effect=download),
                self.assertRaises(SystemExit) as stopped,
            ):
                auto_update.perform_update_optimized(str(target), "1.0.0", "9.9.9")
            self.assertEqual(stopped.exception.code, 0)
            self.assertIn("9.9.9", (target / "server.py").read_text())
            for name in PRIVATE_DIRECTORIES:
                self.assertEqual(
                    (target / name / "private-sentinel").read_text(), "original local data"
                )


if __name__ == "__main__":
    unittest.main()
