"""Keep private Wenyi runtime data out of releases and source synchronization."""

import shlex
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
    @unittest.skipUnless(shutil.which("zip"), "Release ZIP checks require the zip command")
    def test_ci_and_release_zip_commands_exclude_wenyi_data(self):
        for workflow in ("ci.yml", "release.yml"):
            with self.subTest(workflow=workflow), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "server"
                source.mkdir()
                (source / "server.py").write_text("# synthetic server\n")
                for name in PRIVATE_DIRECTORIES:
                    private = source / name
                    private.mkdir()
                    (private / "private-sentinel").write_text("must not be packaged")
                lines = (
                    (REPOSITORY_ROOT / ".github" / "workflows" / workflow).read_text().splitlines()
                )
                start = next(i for i, line in enumerate(lines) if line.strip().startswith("zip -"))
                command = []
                for line in lines[start:]:
                    command.append(line.strip().removesuffix("\\"))
                    if not line.endswith("\\"):
                        break
                arguments = shlex.split(" ".join(command))
                arguments[2] = str(root / "server.zip")
                subprocess.run(arguments, cwd=root, check=True, capture_output=True)
                with zipfile.ZipFile(root / "server.zip") as archive:
                    names = archive.namelist()
                self.assertIn("server/server.py", names)
                self.assertFalse(any("private-sentinel" in name for name in names), names)

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
