"""Table switches, engine commands, worker cleanup, and version fallback."""

import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import toml
from utils import table_process, table_runner, table_runtime
from utils.config import Config


class TableModeTests(unittest.TestCase):
    def setUp(self):
        output = redirect_stdout(StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_table_switch_overwrites_previous_persisted_setting(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.toml"
            for enabled, mode, expected_ocr in (
                (False, None, False),
                (True, None, True),
                (True, "fixed", False),
                (True, "preserve", False),
            ):
                with self.subTest(enabled=enabled, mode=mode):
                    path.write_text(
                        "[pdf]\ntranslate_table_text = true\n", encoding="utf-8"
                    )
                    request = {
                        "engine": "pdf2zh_next",
                        "next_service": "openai",
                        "translateTableText": enabled,
                        "tableMode": mode,
                    }
                    Config(request).update_config_file(path)
                    self.assertIs(
                        toml.load(path)["pdf"]["translate_table_text"], expected_ocr
                    )


class TableProcessTests(unittest.TestCase):
    def test_policy_runs_once_in_real_child_and_restores_parent(self):
        server = Path(__file__).resolve().parents[1]
        fixture = server / "tests" / "fixtures" / "table_process_probe.py"
        env = {**os.environ, "PYTHONPATH": str(server)}
        # Always test spawn, even on Linux CI. Fork must not double-install
        # inherited hooks where that start method is available.
        for method in multiprocessing.get_all_start_methods():
            with self.subTest(method=method):
                result = subprocess.run(
                    [sys.executable, str(fixture), method],
                    check=False,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                state = json.loads(result.stdout)
                self.assertEqual(state["mode"], "fixed")
                self.assertEqual(state["installs"], 1)


class TableVersionFallbackTests(unittest.TestCase):
    def test_runner_fallback_enables_native_tables_without_installing_hooks(self):
        for mode in ("fixed", "preserve"):
            for existing_flag in ([], ["--translate-table-text"]):
                with self.subTest(mode=mode, existing_flag=existing_flag):
                    arguments = [
                        "table_runner.py",
                        mode,
                        "paper.pdf",
                        "--config-file",
                        "settings.toml",
                        *existing_flag,
                    ]
                    observed = []

                    def native_cli():
                        observed.extend(sys.argv)
                        return 17

                    entry = SimpleNamespace(
                        group="console_scripts",
                        name="pdf2zh_next",
                        load=lambda: native_cli,
                    )
                    install = Mock(side_effect=AssertionError("unexpected hook"))
                    with (
                        patch.object(sys, "argv", arguments),
                        patch("importlib.metadata.version", return_value="0.7.0"),
                        patch(
                            "importlib.metadata.distribution",
                            return_value=SimpleNamespace(entry_points=[entry]),
                        ),
                        patch.object(
                            table_process, "install_table_process_policy", install
                        ),
                        self.assertLogs(table_runtime.logger, level="WARNING"),
                    ):
                        self.assertEqual(table_runner.main(), 17)
                    install.assert_not_called()
                    self.assertEqual(observed[0], "pdf2zh_next")
                    self.assertEqual(observed.count("--translate-table-text"), 1)
                    self.assertNotIn(mode, observed)
                    self.assertIn("settings.toml", observed)


if __name__ == "__main__":
    unittest.main()
