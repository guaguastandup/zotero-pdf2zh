"""Managed Wenyi environments never reuse PDF2zh or ambient Python packages."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import environment_lifecycle as lifecycle
from utils.config_migration import _merge_defaults
from utils.package_network import IndexProbeResult
from utils.venv import VirtualEnvManager


class WenyiEnvironmentTests(unittest.TestCase):
    def test_latest_packages_use_one_dedicated_environment(self):
        self.assertEqual(lifecycle.ENGINE_ENV_NAMES.get("wenyi"), "zotero-wenyi-venv")
        for tool in ("uv", "conda"):
            python, requirements = lifecycle.load_requirements("wenyi", tool)
            self.assertEqual(python, "3.12")
            self.assertEqual(
                requirements,
                [
                    "wenyi-cli",
                    "wenyi-core",
                    "wenyi-babeldoc-bridge",
                ],
            )

    def test_config_migration_removes_old_wenyi_pins_and_preserves_extras(self):
        defaults = lifecycle.load_environment_config()
        old = {"pdf2zh_next": {"uv": {"packages": ["my-helper==1"]}}}
        merged = _merge_defaults(defaults, old)
        self.assertIn("wenyi", merged)
        for tool in ("uv", "conda"):
            merged["wenyi"][tool]["packages"] = [
                "wenyi-cli==1.4.1",
                "wenyi_core==1.4.1",
                "wenyi-babeldoc-bridge==0.1.4",
                "my-helper==1",
            ]
        refreshed = _merge_defaults(defaults, merged)
        for tool in ("uv", "conda"):
            with self.subTest(tool=tool):
                packages = refreshed["wenyi"][tool]["packages"]
                self.assertEqual(
                    packages,
                    ["wenyi-cli", "wenyi-core", "wenyi-babeldoc-bridge", "my-helper==1"],
                )
        self.assertEqual(_merge_defaults(defaults, refreshed), refreshed)

    def test_install_and_update_resolve_latest_only_for_wenyi(self):
        source = IndexProbeResult("PyPI", "https://pypi.org/simple", "wenyi-cli", True)
        for engine in lifecycle.ENGINE_ENV_NAMES:
            for tool in ("uv", "conda"):
                for mode in ("new", "update", "repair"):
                    existing = (
                        None if mode == "new" else (tool, Path(sys.prefix), Path(sys.executable))
                    )
                    with (
                        self.subTest(engine=engine, tool=tool, mode=mode),
                        contextlib.redirect_stdout(io.StringIO()),
                        patch.object(lifecycle, "find_existing_environment", return_value=existing),
                        patch.object(lifecycle.shutil, "which", return_value=tool),
                        patch.object(lifecycle, "_cleanup_legacy_sidecar_environments"),
                        patch.object(
                            lifecycle,
                            "_ensure_canonical_environment",
                            return_value=(Path(sys.prefix), Path(sys.executable)),
                        ),
                        patch.object(lifecycle, "read_versions", return_value={}),
                        patch.object(
                            lifecycle, "managed_runtime_health", return_value=(True, "ok")
                        ),
                        patch.object(lifecycle, "probe_indexes", return_value=[source]),
                        patch.object(lifecycle, "_pip_supports_dry_run", return_value=True),
                        patch.object(
                            lifecycle, "validate_environment", return_value=True
                        ) as validate,
                        patch.object(
                            lifecycle.subprocess, "run", return_value=Mock(returncode=0)
                        ) as run,
                    ):
                        success, selected, _ = lifecycle.transactional_install_or_update(
                            engine, env_tool=tool, force_reinstall=(mode == "repair")
                        )
                        self.assertTrue(success)
                        self.assertEqual(selected, tool)
                        validate.assert_called_once()
                        self.assertEqual(run.call_count, 2)
                        preflight, install = [call.args[0] for call in run.call_args_list]
                        self.assertIn("--dry-run", preflight)
                        self.assertNotIn("--dry-run", install)
                        for command in (preflight, install):
                            self.assertEqual("--upgrade" in command, engine == "wenyi")
                            self.assertNotIn("--pre", command)
                        reinstall = "--reinstall" if tool == "uv" else "--force-reinstall"
                        self.assertEqual(reinstall in install, mode == "repair")

    def test_discovery_only_looks_for_the_wenyi_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("zotero-pdf2zh-venv", "zotero-pdf2zh-next-venv"):
                python = root / name / "bin" / "python"
                python.parent.mkdir(parents=True)
                python.touch()
            with (
                patch.object(lifecycle, "SERVER_ROOT", root),
                patch.object(lifecycle.platform, "system", return_value="Linux"),
            ):
                self.assertIsNone(lifecycle.find_existing_environment("wenyi", "uv"))
                python = root / "zotero-wenyi-venv" / "bin" / "python"
                python.parent.mkdir(parents=True)
                python.touch()
                self.assertEqual(
                    lifecycle.find_existing_environment("wenyi", "uv"),
                    ("uv", python.parent.parent, python),
                )

    def test_command_environment_uses_engine_cache_not_current_engine(self):
        for system, tool, relative_python in (
            ("Linux", "uv", "bin/python"),
            ("Windows", "uv", "Scripts/python.exe"),
            ("Windows", "conda", "python.exe"),
        ):
            with (
                self.subTest(system=system, tool=tool),
                patch.object(lifecycle.platform, "system", return_value=system),
                tempfile.TemporaryDirectory() as directory,
            ):
                manager = VirtualEnvManager("missing.json", None, "auto", skip_install=True)
                root = Path(directory)
                python = root / relative_python
                python.parent.mkdir(parents=True, exist_ok=True)
                python.touch()
                manager.ensured_env["wenyi"] = (tool, "zotero-wenyi-venv", str(root))
                manager.curr_envtool = "conda" if tool == "uv" else "uv"
                manager.curr_env_path = "/another-engine"
                with (
                    patch.object(manager, "ensure_env", return_value=True),
                    patch.dict(os.environ, {"PYTHONPATH": "/system", "PYTHONHOME": "/system"}),
                ):
                    actual, environment = manager.get_python_and_env("wenyi")
                self.assertEqual(actual, python)
                self.assertNotIn("PYTHONPATH", environment)
                self.assertNotIn("PYTHONHOME", environment)
                self.assertEqual(environment["PYTHONNOUSERSITE"], "1")
                self.assertEqual(environment["PATH"].split(os.pathsep)[0], str(python.parent))

    def test_existing_wenyi_must_pass_runtime_validation(self):
        manager = VirtualEnvManager("missing.json", None, "uv", skip_install=True)
        with patch("utils.venv.validate_environment", return_value=False) as validate:
            self.assertFalse(manager._requirements_ok("wenyi", "uv", Path(sys.executable)))
        self.assertEqual(validate.call_args.args[0], "wenyi")
        self.assertEqual(
            validate.call_args.args[2], ["wenyi-cli", "wenyi-core", "wenyi-babeldoc-bridge"]
        )

    def test_healthy_wenyi_is_reused_without_checking_for_updates(self):
        manager = VirtualEnvManager("missing.json", None, "uv", skip_install=True)
        existing = ("uv", Path(sys.prefix), Path(sys.executable))
        with (
            patch.object(manager, "_existing", return_value=existing),
            patch("utils.venv.validate_environment", return_value=True) as validate,
            patch.object(manager, "install_packages") as install,
        ):
            self.assertTrue(manager.ensure_env("wenyi"))
        validate.assert_called_once()
        install.assert_not_called()

    def test_empty_wenyi_requirements_cannot_disable_runtime_validation(self):
        manager = VirtualEnvManager("missing.json", None, "uv", skip_install=True)
        with (
            patch("utils.venv.load_requirements", return_value=("3.12", [])),
            patch("utils.venv.validate_environment") as validate,
        ):
            self.assertFalse(manager._requirements_ok("wenyi", "uv", Path(sys.executable)))
        validate.assert_not_called()

    def test_skip_install_does_not_accept_an_incompatible_wenyi_environment(self):
        manager = VirtualEnvManager("missing.json", None, "uv", skip_install=True)
        existing = ("uv", Path("/managed/wenyi"), Path("/managed/wenyi/bin/python"))
        with (
            patch.object(manager, "_existing", return_value=existing),
            patch.object(manager, "_requirements_ok", return_value=False),
            patch.object(manager, "install_packages") as install,
        ):
            self.assertFalse(manager.ensure_env("wenyi"))
        install.assert_not_called()

    def test_wenyi_validation_never_looks_for_pdf2zh_executables(self):
        with (
            patch.object(lifecycle, "managed_runtime_health", return_value=(True, "ok")),
            patch.object(lifecycle, "check_runtime_dependencies", return_value=True),
            patch.object(lifecycle.subprocess, "run") as run,
            patch.object(lifecycle.Path, "exists", return_value=False),
        ):
            run.return_value.returncode = 0
            self.assertTrue(
                lifecycle.validate_environment("wenyi", Path(sys.executable), ["wenyi-cli"])
            )

    def test_update_and_diagnostics_accept_wenyi(self):
        import manage_packages
        import update_packages

        with (
            patch.object(sys, "argv", ["update_packages.py", "--engine", "wenyi"]),
            patch.object(
                update_packages, "transactional_install_or_update", return_value=(True, "uv", None)
            ) as install,
        ):
            self.assertEqual(update_packages.main(), 0)
        self.assertEqual(install.call_args.args, ("wenyi",))
        self.assertEqual(manage_packages.PRIMARY_PACKAGES["wenyi"], "wenyi-cli")
        self.assertIn("wenyi", manage_packages._engines("all"))

    def test_server_defaults_to_lazy_managed_runtime_but_keeps_manual_override(self):
        from types import SimpleNamespace
        import server

        with (
            patch.object(server, "VirtualEnvManager") as manager,
            patch.object(server, "ManagedWenyiRuntime") as runtime,
        ):
            arguments = SimpleNamespace(
                enable_venv=True,
                env_tool="uv",
                enable_mirror=False,
                skip_install=False,
                mirror_source=None,
            )
            translator = server.PDFTranslator(arguments)
            self.assertIs(translator.wenyi.runtime, runtime.return_value)
            self.assertEqual(runtime.call_args.args[0], manager.return_value)
            manager.return_value.get_python_and_env.assert_not_called()
            runtime.return_value.prepare.assert_not_called()
            arguments.wenyi_executable = "/manual/wenyi"
            manual = server.PDFTranslator(arguments)
            self.assertIsNone(manual.wenyi.runtime)
            self.assertEqual(manual.wenyi.executable, "/manual/wenyi")
            runtime.assert_called_once()

    def test_server_shutdown_closes_the_owned_runtime(self):
        from types import SimpleNamespace
        import server

        translator = server.PDFTranslator(SimpleNamespace(enable_venv=False))
        translator.wenyi = Mock()
        with patch.object(translator.app, "run", side_effect=RuntimeError("Stopped")):
            with self.assertRaisesRegex(RuntimeError, "Stopped"):
                translator.run("127.0.0.1", 0)
        translator.wenyi.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
