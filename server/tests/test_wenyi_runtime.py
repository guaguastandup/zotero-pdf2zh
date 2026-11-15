"""Offline host paths, launcher and lifecycle checks without a real BabelDOC."""

import os
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import wenyi_runner
from utils.wenyi_paths import WenyiPaths
from utils.wenyi_runtime import ManagedWenyiRuntime


class WenyiRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manager = Mock()
        self.manager.get_python_and_env.return_value = (Path(sys.executable), dict(os.environ))
        self.runtime = ManagedWenyiRuntime(
            self.manager,
            self.root / "runtime",
            session_root=self.root / "sessions",
            cache_root=self.root / "assets",
            startup_timeout=3,
        )
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
        self.assertEqual(command[:2], [sys.executable, "-I"])
        self.assertEqual(Path(command[2]).name, "wenyi_runner.py")
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
            self.assertEqual(
                results[0][1].get("NO_PROXY"),
                self.manager.get_python_and_env.return_value[1].get("NO_PROXY"),
            )
            self.assertEqual(
                self.environments[0]["WENYI_BABELDOC_STATE_DIR"], str(self.root / "sessions")
            )
            self.assertEqual(
                self.environments[0]["ZOTERO_WENYI_CACHE_DIR"], str(self.root / "assets")
            )
            self.assertEqual(
                os.environ.get("ZOTERO_WENYI_CACHE_DIR"),
                self.manager.get_python_and_env.return_value[1].get("ZOTERO_WENYI_CACHE_DIR"),
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
            self.assertEqual(
                self.environments[0]["WENYI_BABELDOC_STATE_DIR"],
                self.environments[1]["WENYI_BABELDOC_STATE_DIR"],
            )
            self.assertEqual(
                self.environments[0]["ZOTERO_WENYI_CACHE_DIR"],
                self.environments[1]["ZOTERO_WENYI_CACHE_DIR"],
            )
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


class WenyiPathsTests(unittest.TestCase):
    def test_explicit_roots_override_environment_without_creating_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch.dict(os.environ, {"ZOTERO_WENYI_DATA_DIR": str(root / "ambient")}):
                paths = WenyiPaths.resolve(root / "data", root / "assets")
            self.assertEqual(paths.data, root / "data")
            self.assertEqual(paths.cache, root / "assets")
            self.assertFalse(paths.data.exists())
            self.assertFalse(paths.cache.exists())

    def test_environment_and_default_cache_belong_to_selected_data_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch.dict(
                os.environ,
                {"ZOTERO_WENYI_DATA_DIR": str(root), "ZOTERO_WENYI_CACHE_DIR": ""},
            ):
                paths = WenyiPaths.resolve()
            self.assertEqual(paths.data, root)
            self.assertEqual(paths.cache, root / "cache")
            self.assertEqual(paths.tasks, root / "tasks")
            self.assertEqual(paths.sessions, root / "bridge" / "sessions")
            self.assertEqual(paths.runtime, root / "runtime")

    def test_cache_cannot_overlap_non_disposable_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "data"
            for cache in (
                data,
                data.parent,
                data / "bridge",
                data / "bridge" / "sessions" / "assets",
                data / "translations",
                data / "tasks",
                data / "runtime",
            ):
                with self.subTest(cache=cache), self.assertRaisesRegex(ValueError, "overlap"):
                    WenyiPaths.resolve(data, cache)

    def test_server_supplies_selected_roots_without_creating_them_or_starting_runtime(self):
        import server

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            arguments = SimpleNamespace(
                enable_venv=True,
                env_tool="uv",
                enable_mirror=False,
                skip_install=True,
                mirror_source=None,
                wenyi_data_dir=root / "data",
                wenyi_cache_dir=root / "assets",
            )
            with (
                patch.object(server, "VirtualEnvManager"),
                patch.object(server, "ManagedWenyiRuntime") as runtime,
            ):
                translator = server.PDFTranslator(arguments)
            self.assertEqual(translator.wenyi.task_root, root / "data" / "tasks")
            self.assertEqual(translator.wenyi.state_root, root / "data" / "translations")
            self.assertEqual(translator.wenyi.cache_root, root / "assets")
            self.assertEqual(runtime.call_args.args[1], root / "data" / "runtime")
            self.assertEqual(
                runtime.call_args.kwargs["session_root"], root / "data" / "bridge" / "sessions"
            )
            self.assertEqual(runtime.call_args.kwargs["cache_root"], root / "assets")
            runtime.return_value.prepare.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])

    def test_platform_defaults_are_plugin_specific_and_not_installation_relative(self):
        with tempfile.TemporaryDirectory() as temporary:
            # Resolve Windows short-path aliases and use a native absolute path
            # with a drive, rather than assuming POSIX-rooted fixture strings.
            profile = Path(temporary).resolve() / "profile"
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("utils.wenyi_paths.Path.home", return_value=profile),
            ):
                for platform, expected in (
                    ("linux", ".local/share/zotero-pdf2zh/wenyi"),
                    ("darwin", "Library/Application Support/zotero-pdf2zh/wenyi"),
                    ("win32", "AppData/Local/zotero-pdf2zh/wenyi"),
                ):
                    with (
                        self.subTest(platform=platform),
                        patch("utils.wenyi_paths.sys.platform", platform),
                    ):
                        self.assertEqual(WenyiPaths.resolve().data, profile / expected)


class WenyiRunnerTests(unittest.TestCase):
    def test_missing_current_connection_fails_before_importing_cli(self):
        with patch.dict(os.environ, {wenyi_runner.BRIDGE_ENV: ""}):
            with self.assertRaisesRegex(SystemExit, "current HTTP"):
                wenyi_runner.main()

    def test_old_installation_is_actionable_and_never_falls_back_to_saved_port(self):
        with (
            patch.dict(os.environ, {wenyi_runner.BRIDGE_ENV: "http://127.0.0.1:12345"}),
            patch.dict(sys.modules, {"wenyi_core.pdf_bridge.connection": None}),
        ):
            with self.assertRaisesRegex(SystemExit, r"Update wenyi-cli.*--wenyi-python"):
                wenyi_runner.main()

    def test_spawned_bridge_worker_configures_the_same_dedicated_asset_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "assets"
            babeldoc = types.ModuleType("babeldoc")
            const = types.ModuleType("babeldoc.const")
            babeldoc.const = const
            with (
                patch.dict(sys.modules, {"babeldoc": babeldoc, "babeldoc.const": const}),
                patch.dict(os.environ, {"ZOTERO_WENYI_CACHE_DIR": str(cache)}),
                patch("sys.stdout"),
            ):
                # multiprocessing spawn replays the entry module as __mp_main__.
                runpy.run_path(
                    str(Path(__file__).parents[1] / "utils" / "wenyi_bridge.py"),
                    run_name="__mp_main__",
                )
                self.assertEqual(const.CACHE_FOLDER, cache)
                self.assertEqual(const.TIKTOKEN_CACHE_FOLDER, cache / "tiktoken")
                self.assertEqual(os.environ["TIKTOKEN_CACHE_DIR"], str(cache / "tiktoken"))
                self.assertTrue((cache / "tiktoken").is_dir())


if __name__ == "__main__":
    unittest.main()
