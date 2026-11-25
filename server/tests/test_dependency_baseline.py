import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from packaging.requirements import Requirement

from utils import environment_lifecycle as lifecycle
from utils.config_migration import migrate_config_file


SERVER = Path(__file__).resolve().parents[1]


class DependencyBaselineTests(unittest.TestCase):
    def test_server_and_new_engine_use_the_same_pymupdf(self):
        server_reqs = {
            req.name.lower(): req
            for line in map(str.strip, (SERVER / "requirements.txt").read_text().splitlines())
            if line and not line.startswith("#")
            for req in [Requirement(line)]
        }
        defaults = json.loads((SERVER / "config/venv.json.example").read_text())
        for tool in ("uv", "conda"):
            requirements = {
                req.name.lower().replace("_", "-"): req
                for req in map(Requirement, defaults["pdf2zh_next"][tool]["packages"])
            }
            for name, version in lifecycle.PDF2ZH_NEXT_BASELINE.items():
                self.assertEqual(str(requirements[name.lower()].specifier), f"=={version}")
            self.assertEqual(
                server_reqs["pymupdf"].specifier,
                requirements["pymupdf"].specifier,
            )
            legacy = next(
                req for req in map(Requirement, defaults["pdf2zh"][tool]["packages"])
                if req.name.lower() == "pymupdf"
            )
            self.assertIn("1.25.2", legacy.specifier)
            self.assertNotIn("1.28.2", legacy.specifier)

    def test_migration_updates_managed_pins_and_preserves_user_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            active = Path(tmp) / "venv.json"
            example = active.with_name("venv.json.example")
            example.write_bytes((SERVER / "config/venv.json.example").read_bytes())
            current = {
                "pdf2zh_next": {"uv": {
                    "python_version": "3.11",
                    "packages": ["pdf2zh-next==2.9.0", "PyMuPDF==2.1", "babeldoc==0.6.0", "my-helper==1.0"],
                }},
                "custom_setting": "keep",
            }
            active.write_text(json.dumps(current))
            with contextlib.redirect_stdout(io.StringIO()):
                migrate_config_file(active)
                first = active.read_bytes()
                migrate_config_file(active)
            self.assertEqual(active.read_bytes(), first)
            migrated = json.loads(first)
            section = migrated["pdf2zh_next"]["uv"]
            self.assertEqual(section["python_version"], "3.11")
            self.assertEqual(migrated["custom_setting"], "keep")
            self.assertIn("my-helper==1.0", section["packages"])
            self.assertIn("pdf2zh_next==2.10.2", section["packages"])
            self.assertIn("BabelDOC==0.7.1", section["packages"])
            self.assertIn("PyMuPDF==1.28.2", section["packages"])
            for obsolete in ("pdf2zh-next==2.9.0", "PyMuPDF==2.1", "babeldoc==0.6.0"):
                self.assertNotIn(obsolete, section["packages"])

    def _prompt(self, versions, state=None, answer="n"):
        with (
            patch.object(lifecycle.sys, "stdin", SimpleNamespace(isatty=lambda: True)),
            patch.object(lifecycle, "_server_cli_bool", return_value=False),
            patch.object(lifecycle, "find_existing_environment", return_value=("conda", Path("env"), Path("python"))),
            patch.object(lifecycle, "server_version_from_source", return_value="4.1.8"),
            patch.object(lifecycle, "read_package_update_state", return_value=state or {}),
            patch.object(lifecycle, "read_versions", return_value=versions),
            patch.object(lifecycle, "runtime_supports_deepseek_thinking", return_value=True),
            patch.object(lifecycle, "write_package_update_state") as write,
            patch.object(lifecycle, "transactional_install_or_update", return_value=(True, "conda", Path("env"))) as install,
            patch("builtins.input", return_value=answer) as ask,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            lifecycle.maybe_prompt_existing_user_update(config_path="custom.json")
        return ask, install, write

    def test_29_is_still_capable_but_old_skip_record_does_not_hide_new_baseline(self):
        self.assertTrue(lifecycle.pdf2zh_next_meets_minimum("2.9.0"))
        ask, install, write = self._prompt(
            {**lifecycle.PDF2ZH_NEXT_BASELINE, "pdf2zh-next": "2.9.0"},
            {"server_version": "4.1.8", "status": "skipped"},
        )
        ask.assert_called_once()
        install.assert_not_called()
        write.assert_called_once_with("4.1.8", "declined")

    def test_matching_combination_needs_no_install(self):
        ask, install, write = self._prompt(dict(lifecycle.PDF2ZH_NEXT_BASELINE))
        ask.assert_not_called()
        install.assert_not_called()
        write.assert_called_once_with("4.1.8", "skipped")

    def test_new_engine_with_wrong_pdf_library_still_prompts(self):
        ask, install, _ = self._prompt({**lifecycle.PDF2ZH_NEXT_BASELINE, "PyMuPDF": "2.1"})
        ask.assert_called_once()
        install.assert_not_called()

    def test_accepting_keeps_the_existing_manager_and_config(self):
        _, install, write = self._prompt({"pdf2zh-next": "2.9.0"}, answer="y")
        install.assert_called_once_with(
            "pdf2zh_next", env_tool="conda", config_path="custom.json",
            preferred_index=None, require_deepseek_thinking=True,
        )
        write.assert_called_once_with("4.1.8", "success")

    def test_decline_is_remembered_for_this_baseline(self):
        ask, install, write = self._prompt(
            {"pdf2zh-next": "2.9.0"},
            {"server_version": "4.1.8", "baseline": lifecycle.PDF2ZH_NEXT_BASELINE, "status": "declined"},
        )
        ask.assert_not_called()
        install.assert_not_called()
        write.assert_not_called()

    def test_state_records_the_dependency_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            with patch.object(lifecycle, "package_update_state_path", return_value=state_path):
                lifecycle.write_package_update_state("4.1.8", "declined")
                state = lifecycle.read_package_update_state()
            self.assertEqual(state["baseline"], lifecycle.PDF2ZH_NEXT_BASELINE)
            self.assertEqual(state["status"], "declined")


if __name__ == "__main__":
    unittest.main()
