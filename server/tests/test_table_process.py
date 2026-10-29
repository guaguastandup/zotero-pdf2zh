import json
import multiprocessing
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from utils import table_process


class TableProcessTests(unittest.TestCase):
    def test_worker_restores_policy_when_native_translation_raises(self):
        restore = Mock()
        native = Mock(side_effect=RuntimeError("translation failed"))
        engine = SimpleNamespace(_translate_wrapper=native)
        with (
            patch.dict(
                sys.modules, {"pdf2zh_next": SimpleNamespace(high_level=engine)}
            ),
            patch.object(table_process, "install_table_policy", return_value=restore),
            self.assertRaisesRegex(RuntimeError, "translation failed"),
        ):
            table_process._run_table_worker("fixed", "input.pdf")
        native.assert_called_once_with("input.pdf")
        restore.assert_called_once_with()

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


if __name__ == "__main__":
    unittest.main()
