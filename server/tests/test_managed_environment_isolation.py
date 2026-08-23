import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from utils import execute
from utils.environment_lifecycle import _build_install_command
from utils.environment_lifecycle import managed_python_env
from utils.environment_lifecycle import managed_runtime_health
from utils.environment_lifecycle import runtime_supports_deepseek_thinking
from utils.environment_lifecycle import transactional_install_or_update
from utils.venv import VirtualEnvManager


class ManagedEnvironmentIsolationTest(unittest.TestCase):
    def test_python_path_pollution_is_removed_without_losing_other_settings(self):
        source = {
            "PATH": "managed-bin;system-bin",
            "PYTHONPATH": r"C:\python3.11.4\Lib\site-packages",
            "PYTHONHOME": r"C:\python3.11.4",
            "PythonPath": r"C:\another-global-site-packages",
            "HTTPS_PROXY": "http://127.0.0.1:7890",
            "CUDA_VISIBLE_DEVICES": "0",
        }

        isolated = managed_python_env(source)

        self.assertNotIn("PYTHONPATH", isolated)
        self.assertNotIn("PYTHONHOME", isolated)
        self.assertNotIn("PythonPath", isolated)
        self.assertEqual(isolated["PYTHONNOUSERSITE"], "1")
        self.assertEqual(isolated["PATH"], source["PATH"])
        self.assertEqual(isolated["HTTPS_PROXY"], source["HTTPS_PROXY"])
        self.assertEqual(isolated["CUDA_VISIBLE_DEVICES"], "0")
        self.assertIn("PYTHONPATH", source, "the caller's mapping must not be mutated")

    def test_health_probe_ignores_ambient_pythonpath(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake = Path(temp_dir)
            (fake / "pydantic.py").write_text("raise RuntimeError('polluted')\n")
            core = fake / "pydantic_core"
            core.mkdir()
            (core / "__init__.py").write_text("# missing native extension\n")

            with patch.dict(os.environ, {"PYTHONPATH": str(fake)}, clear=False):
                healthy, reason = managed_runtime_health(
                    "pdf2zh_next", Path(sys.executable)
                )

        self.assertTrue(healthy, reason)

    def test_repair_reinstalls_only_after_a_managed_environment_is_unhealthy(self):
        names = {
            "pdf2zh": "zotero-pdf2zh-venv",
            "pdf2zh_next": "zotero-pdf2zh-next-venv",
        }
        manager = VirtualEnvManager("missing.json", names, "uv", skip_install=True)
        manager.skip_install = False
        existing = ("uv", Path("/tmp/managed"), Path(sys.executable))
        manager._existing = lambda engine, tool: existing
        manager._requirements_ok = lambda engine, tool, python: False
        calls = []
        manager.install_packages = lambda *args, **kwargs: calls.append(
            (args, kwargs)
        ) or True

        self.assertTrue(manager.ensure_env("pdf2zh_next"))
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][1]["force_reinstall"], True)

    def test_reinstall_flags_are_manager_specific(self):
        uv = _build_install_command(
            "uv",
            Path("python"),
            ["pdf2zh-next"],
            "https://pypi.org/simple",
            dry_run=False,
            reinstall=True,
        )
        with patch("utils.environment_lifecycle._pip_supports_dry_run", return_value=True):
            conda = _build_install_command(
                "conda",
                Path("python"),
                ["pdf2zh-next"],
                "https://pypi.org/simple",
                dry_run=False,
                reinstall=True,
            )

        self.assertIn("--reinstall", uv)
        self.assertIn("--force-reinstall", conda)
        self.assertIn("-I", conda)

    def test_manual_update_reinstalls_an_existing_broken_runtime(self):
        existing = ("uv", Path("/tmp/managed"), Path(sys.executable))
        with (
            patch(
                "utils.environment_lifecycle.find_existing_environment",
                return_value=existing,
            ),
            patch(
                "utils.environment_lifecycle.load_requirements",
                return_value=("3.12", ["pdf2zh-next>=2.9.0,<3.0.0"]),
            ),
            patch("utils.environment_lifecycle._cleanup_legacy_sidecar_environments"),
            patch(
                "utils.environment_lifecycle.managed_runtime_health",
                return_value=(False, "missing _pydantic_core"),
            ),
            patch("utils.environment_lifecycle.read_versions", return_value={}),
            patch(
                "utils.environment_lifecycle.choose_install_sources",
                return_value=["https://pypi.org/simple"],
            ),
            patch("utils.environment_lifecycle._run_install", return_value=True) as install,
            patch("utils.environment_lifecycle.validate_environment", return_value=True),
        ):
            success, selected, env_dir = transactional_install_or_update(
                "pdf2zh_next", env_tool="uv"
            )

        self.assertTrue(success)
        self.assertEqual(selected, "uv")
        self.assertEqual(env_dir, existing[1])
        self.assertIs(install.call_args.kwargs["reinstall"], True)

    def test_static_capability_probe_only_isolates_managed_mode(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout='{"supported": true}',
            stderr="",
        )
        with patch(
            "utils.environment_lifecycle.subprocess.run", return_value=completed
        ) as run:
            self.assertTrue(
                runtime_supports_deepseek_thinking(
                    Path("python"),
                    env={"PYTHONPATH": "intentional-system-path"},
                    isolated=False,
                )
            )
            system_call = run.call_args

            self.assertTrue(
                runtime_supports_deepseek_thinking(
                    Path("python"),
                    env={"PYTHONPATH": "polluted", "PATH": "managed-bin"},
                    isolated=True,
                )
            )
            managed_call = run.call_args

        self.assertNotIn("-I", system_call.args[0])
        self.assertEqual(
            system_call.kwargs["env"]["PYTHONPATH"], "intentional-system-path"
        )
        self.assertIn("-I", managed_call.args[0])
        self.assertNotIn("PYTHONPATH", managed_call.kwargs["env"])

    def test_system_mode_keeps_ambient_python_settings(self):
        captured = {}

        def capture(_cmd, env, _task_id, _cols, _rows):
            captured.update(env)

        args = SimpleNamespace(enable_venv=False)
        with (
            patch.dict(
                os.environ,
                {"PYTHONPATH": "intentional-system-path", "PYTHONHOME": "system-home"},
                clear=False,
            ),
            patch.object(
                execute,
                "prepare_deepseek_runtime_command",
                side_effect=lambda cmd, env: cmd,
            ),
            patch.object(execute, "_execute_with_pty", side_effect=capture),
        ):
            execute.execute_with_progress(["python", "-V"], None, args, None)

        self.assertEqual(captured["PYTHONPATH"], "intentional-system-path")
        self.assertEqual(captured["PYTHONHOME"], "system-home")

    def test_managed_mode_removes_ambient_python_settings(self):
        captured = {}

        class Manager:
            @staticmethod
            def get_command_and_env(cmd):
                return cmd, {
                    **os.environ,
                    "PYTHONPATH": "polluted",
                    "PYTHONHOME": "polluted-home",
                    "PATH": "managed-bin",
                }

        def capture(_cmd, env, _task_id, _cols, _rows):
            captured.update(env)

        args = SimpleNamespace(enable_venv=True)
        with (
            patch.object(
                execute,
                "prepare_deepseek_runtime_command",
                side_effect=lambda cmd, env: cmd,
            ),
            patch.object(execute, "_execute_with_pty", side_effect=capture),
        ):
            execute.execute_with_progress(
                ["pdf2zh_next", "paper.pdf"], None, args, Manager()
            )

        self.assertNotIn("PYTHONPATH", captured)
        self.assertNotIn("PYTHONHOME", captured)
        self.assertEqual(captured["PYTHONNOUSERSITE"], "1")
        self.assertEqual(captured["PATH"], "managed-bin")


if __name__ == "__main__":
    unittest.main()
