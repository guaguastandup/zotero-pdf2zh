import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import toml

from utils import execute
from utils.config import Config
from utils.deepseek_thinking import normalize_deepseek_extra_data
from utils.deepseek_thinking import prepare_deepseek_runtime_command
from utils.deepseek_thinking import thinking_runtime_policy
from utils.deepseek_thinking import validate_winexe_runtime_if_selected


class DeepSeekThinkingSafetyTest(unittest.TestCase):
    def _config_path(self, root: str, mode: str = "disabled") -> Path:
        path = Path(root) / "config.toml"
        payload = {
            "deepseek_detail": {
                "deepseek_model": "deepseek-v4-flash",
                "deepseek_thinking_mode": mode,
            }
        }
        if mode == "enabled":
            payload["deepseek_detail"]["deepseek_reasoning_effort"] = "high"
        with path.open("w", encoding="utf-8") as handle:
            toml.dump(payload, handle)
        return path

    def test_unsupported_runtime_blocks_both_thinking_modes(self):
        self.assertEqual(thinking_runtime_policy("disabled", False), "block")
        self.assertEqual(thinking_runtime_policy("enabled", False), "block")
        self.assertEqual(thinking_runtime_policy("disabled", True), "pass-flags")
        self.assertEqual(thinking_runtime_policy("enabled", True), "pass-flags")

    def test_old_runtime_cannot_fall_back_when_thinking_is_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._config_path(temp_dir, "disabled")
            cmd = [
                "pdf2zh_next",
                "paper.pdf",
                "--deepseek",
                "--config-file",
                str(config_path),
            ]
            with patch(
                "utils.deepseek_thinking._runtime_supports_thinking",
                return_value=False,
            ):
                with self.assertRaises(ValueError) as caught:
                    prepare_deepseek_runtime_command(cmd, {})

        message = str(caught.exception)
        self.assertIn("思考控制", message)
        self.assertIn("update_packages.py", message)

    def test_saved_enabled_is_respected_without_a_hidden_opt_in_marker(self):
        llm_api = {
            "model": "deepseek-v4-flash",
            "extraData": {
                "deepseek_thinking_mode": "enabled",
                "deepseek_reasoning_effort": "high",
            },
        }
        model = normalize_deepseek_extra_data(llm_api, {})
        self.assertEqual(model, "deepseek-v4-flash")
        self.assertEqual(llm_api["extraData"]["deepseek_thinking_mode"], "enabled")
        self.assertEqual(llm_api["extraData"]["deepseek_reasoning_effort"], "high")

    def test_obsolete_opt_in_marker_is_not_forwarded_to_the_engine(self):
        llm_api = {
            "model": "deepseek-v4-flash",
            "extraData": {
                "deepseek_thinking_mode": "enabled",
                "deepseek_reasoning_effort": "high",
                "deepseek_thinking_explicit_opt_in": "true",
            },
        }
        normalize_deepseek_extra_data(llm_api, {})
        self.assertEqual(llm_api["extraData"]["deepseek_thinking_mode"], "enabled")
        self.assertEqual(llm_api["extraData"]["deepseek_reasoning_effort"], "high")
        self.assertNotIn("deepseek_thinking_explicit_opt_in", llm_api["extraData"])

    def test_unset_mode_defaults_to_disabled_even_if_old_config_enabled_it(self):
        for value in (None, "", "null", "none"):
            with self.subTest(value=value):
                llm_api = {"extraData": {"deepseek_thinking_mode": value}}
                model = normalize_deepseek_extra_data(
                    llm_api,
                    {
                        "deepseek_detail": {
                            "deepseek_model": "deepseek-v4-flash",
                            "deepseek_thinking_mode": "enabled",
                        }
                    },
                )
                self.assertEqual(model, "deepseek-v4-flash")
                self.assertEqual(
                    llm_api["extraData"]["deepseek_thinking_mode"], "disabled"
                )

    def test_non_v4_models_keep_unrelated_parameters_only(self):
        llm_api = {
            "model": "deepseek-chat",
            "extraData": {
                "deepseek_thinking_mode": "enabled",
                "deepseek_reasoning_effort": "max",
                "deepseek_enable_json_mode": True,
            },
        }
        normalize_deepseek_extra_data(llm_api, {})
        self.assertEqual(llm_api["extraData"], {"deepseek_enable_json_mode": True})

    def test_invalid_choices_fail_before_execution(self):
        for extra in (
            {"deepseek_thinking_mode": "auto"},
            {
                "deepseek_thinking_mode": "enabled",
                "deepseek_reasoning_effort": "medium",
            },
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                normalize_deepseek_extra_data(
                    {"model": "deepseek-v4-flash", "extraData": extra}, {}
                )

    def test_supported_runtime_sends_disabled_explicitly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._config_path(temp_dir, "disabled")
            cmd = [
                "pdf2zh_next",
                "paper.pdf",
                "--deepseek",
                "--config-file",
                str(config_path),
            ]
            with patch(
                "utils.deepseek_thinking._runtime_supports_thinking",
                return_value=True,
            ):
                updated = prepare_deepseek_runtime_command(cmd, {})

        pos = updated.index("--deepseek-thinking-mode")
        self.assertEqual(updated[pos + 1], "disabled")
        self.assertNotIn("--deepseek-reasoning-effort", updated)

    def test_supported_runtime_can_execute_explicit_enabled_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._config_path(temp_dir, "enabled")
            cmd = [
                "pdf2zh_next",
                "paper.pdf",
                "--deepseek",
                "--config-file",
                str(config_path),
            ]
            with patch(
                "utils.deepseek_thinking._runtime_supports_thinking",
                return_value=True,
            ):
                updated = prepare_deepseek_runtime_command(cmd, {})

        mode_pos = updated.index("--deepseek-thinking-mode")
        effort_pos = updated.index("--deepseek-reasoning-effort")
        self.assertEqual(updated[mode_pos + 1], "enabled")
        self.assertEqual(updated[effort_pos + 1], "high")

    def test_system_environment_mode_cannot_bypass_cost_guard(self):
        args = SimpleNamespace(enable_venv=False)
        with (
            patch.object(
                execute,
                "prepare_deepseek_runtime_command",
                side_effect=ValueError("DeepSeek cost guard"),
            ),
            patch.object(execute, "_execute_with_pty") as launch,
        ):
            with self.assertRaisesRegex(ValueError, "cost guard"):
                execute.execute_with_progress(
                    ["pdf2zh_next", "paper.pdf", "--deepseek"],
                    None,
                    args,
                    None,
                )

        launch.assert_not_called()

    def test_disabling_thinking_clears_saved_effort_and_obsolete_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._config_path(temp_dir, "enabled")
            request = {
                "engine": "pdf2zh_next",
                "next_service": "deepseek",
                "llm_api": {
                    "model": "deepseek-v4-flash",
                    "extraData": {
                        "deepseek_thinking_mode": "disabled",
                        "deepseek_thinking_explicit_opt_in": "true",
                    },
                },
            }
            with redirect_stdout(StringIO()), patch("sys.argv", ["server.py"]):
                Config(request).update_config_file(path)
            detail = toml.load(path)["deepseek_detail"]
            self.assertEqual(detail["deepseek_thinking_mode"], "disabled")
            self.assertNotIn("deepseek_reasoning_effort", detail)
            self.assertNotIn("deepseek_thinking_explicit_opt_in", detail)

    def test_cli_disabled_overrides_saved_enabled_and_removes_effort(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._config_path(temp_dir, "enabled")
            cmd = [
                "pdf2zh_next",
                "paper.pdf",
                "--deepseek",
                f"--config-file={path}",
                "--deepseek-thinking-mode=disabled",
                "--deepseek-reasoning-effort=max",
            ]
            with patch(
                "utils.deepseek_thinking._runtime_supports_thinking", return_value=True
            ):
                updated = prepare_deepseek_runtime_command(cmd, {})
            self.assertEqual(updated[-2:], ["--deepseek-thinking-mode", "disabled"])
            self.assertFalse(
                any(x.startswith("--deepseek-reasoning-effort") for x in updated)
            )

    def test_old_winexe_cannot_silently_ignore_either_choice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._config_path(temp_dir)
            exe = Path(temp_dir) / "pdf2zh.exe"
            exe.touch()
            for mode in ("disabled", "enabled"):
                with (
                    self.subTest(mode=mode),
                    patch(
                        "sys.argv",
                        [
                            "server.py",
                            "--enable_winexe",
                            "true",
                            "--winexe_path",
                            str(exe),
                        ],
                    ),
                    patch(
                        "utils.deepseek_thinking._runtime_supports_thinking",
                        return_value=False,
                    ),
                    self.assertRaisesRegex(ValueError, "Windows"),
                ):
                    validate_winexe_runtime_if_selected(
                        str(path), "deepseek-v4-flash", mode
                    )

    def test_missing_winexe_uses_the_normal_runtime_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "sys.argv",
                    [
                        "server.py",
                        "--enable_winexe",
                        "true",
                        "--winexe_path",
                        str(Path(temp_dir) / "missing.exe"),
                    ],
                ),
                patch("utils.deepseek_thinking._runtime_supports_thinking") as probe,
            ):
                self.assertTrue(
                    validate_winexe_runtime_if_selected(
                        "unused.toml", "deepseek-v4-flash", "enabled"
                    )
                )
                probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
