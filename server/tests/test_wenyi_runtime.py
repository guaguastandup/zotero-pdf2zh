"""Offline lifecycle checks with a real, tiny HTTP child instead of BabelDOC."""

import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.wenyi_runtime import ManagedWenyiRuntime


class WenyiRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manager = Mock()
        self.manager.get_python_and_env.return_value = (Path(sys.executable), dict(os.environ))
        self.runtime = ManagedWenyiRuntime(self.manager, self.root, startup_timeout=3)
        self.addCleanup(self.runtime.close)

    def fake_children(self):
        original = subprocess.Popen
        self.children = []
        self.commands = []
        self.environments = []

        def start(command, **kwargs):
            self.commands.append(command)
            self.environments.append(kwargs["env"])
            self.assertEqual(command[:2], [sys.executable, "-I"])
            self.assertEqual(Path(command[2]).name, "wenyi_bridge.py")
            process = original(
                [sys.executable, "-I", str(Path(__file__).with_name("fake_wenyi_bridge.py"))],
                **kwargs,
            )
            self.children.append(process)
            return process

        return patch("utils.wenyi_runtime.subprocess.Popen", side_effect=start)

    def test_external_bridge_is_never_started_or_stopped(self):
        self.runtime.external_bridge_url = "http://127.0.0.1:8765"
        with patch("utils.wenyi_runtime.subprocess.Popen") as start:
            command, _, url = self.runtime.prepare()
            self.runtime.close()
        start.assert_not_called()
        self.assertEqual(command, [sys.executable, "-I", "-m", "wenyi_cli"])
        self.assertEqual(url, "http://127.0.0.1:8765")

    def test_failed_environment_never_falls_back_to_path_or_starts_bridge(self):
        self.manager.get_python_and_env.side_effect = RuntimeError("Install failed")
        with patch("utils.wenyi_runtime.subprocess.Popen") as start:
            with self.assertRaisesRegex(RuntimeError, "Install failed"):
                self.runtime.prepare()
        start.assert_not_called()

    @unittest.skipIf(os.name == "nt", "The tiny owner-pipe fixture uses POSIX pipe reads")
    def test_lazy_single_bridge_is_shared_by_concurrent_tasks_and_closed(self):
        self.assertFalse(self.root.joinpath("bridge.log").exists())
        self.manager.get_python_and_env.return_value[1].update(
            {"DEEPSEEK_API_KEY": "fake-test-credential", "HTTP_PROXY": "http://127.0.0.1:1"}
        )
        with self.fake_children():
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: self.runtime.prepare(), range(4)))
            self.assertEqual(len(self.children), 1)
            self.assertEqual(len({result[2] for result in results}), 1)
            self.assertNotEqual(results[0][2], "http://127.0.0.1:8765")
            self.assertNotIn("DEEPSEEK_API_KEY", self.environments[0])
            self.assertEqual(results[0][1]["DEEPSEEK_API_KEY"], "fake-test-credential")
            self.assertIn("127.0.0.1", results[0][1]["NO_PROXY"])
            self.assertEqual(
                self.environments[0]["WENYI_BABELDOC_STATE_DIR"], str(self.root / "sessions")
            )
            self.runtime.close()
            self.assertIsNotNone(self.children[0].poll())

    @unittest.skipIf(os.name == "nt", "The tiny owner-pipe fixture uses POSIX pipe reads")
    def test_bridge_crash_is_restarted_without_touching_pdf2zh(self):
        with self.fake_children():
            self.runtime.prepare()
            self.children[0].terminate()
            self.children[0].wait(timeout=3)
            self.runtime.prepare()
            self.assertEqual(len(self.children), 2)
            self.assertIsNone(self.children[1].poll())
        self.assertTrue(
            all(call.args == ("wenyi",) for call in self.manager.get_python_and_env.call_args_list)
        )

    @unittest.skipIf(os.name == "nt", "The tiny owner-pipe fixture uses POSIX pipe reads")
    def test_failed_or_timed_out_start_is_cleaned_up_and_can_be_retried(self):
        for mode in ("exit", "invalid", "stall"):
            with self.subTest(mode=mode):
                self.manager.get_python_and_env.return_value[1]["WENYI_BRIDGE_TEST_MODE"] = mode
                self.runtime.startup_timeout = 0.2 if mode == "stall" else 3
                with self.fake_children():
                    with self.assertRaisesRegex(RuntimeError, "bridge.log"):
                        self.runtime.prepare()
                    self.assertIsNotNone(self.children[-1].poll())
        self.manager.get_python_and_env.return_value[1].pop("WENYI_BRIDGE_TEST_MODE")
        with self.fake_children():
            self.runtime.prepare()
            self.assertIsNone(self.children[0].poll())


if __name__ == "__main__":
    unittest.main()
