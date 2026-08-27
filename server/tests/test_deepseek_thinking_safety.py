import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import toml

from utils import execute
from utils.deepseek_thinking import THINKING_EXPLICIT_OPT_IN_FIELD
from utils.deepseek_thinking import normalize_deepseek_extra_data
from utils.deepseek_thinking import prepare_deepseek_runtime_command
from utils.deepseek_thinking import thinking_runtime_policy


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
        self.assertIn("2.9.0", message)
        self.assertIn("高额费用", message)

    def test_saved_enabled_without_current_opt_in_is_forced_disabled(self):
        llm_api = {
            "model": "deepseek-v4-flash",
            "extraData": {
                "deepseek_thinking_mode": "enabled",
                "deepseek_reasoning_effort": "high",
            },
        }
        model = normalize_deepseek_extra_data(llm_api, {})
        self.assertEqual(model, "deepseek-v4-flash")
        self.assertEqual(llm_api["extraData"]["deepseek_thinking_mode"], "disabled")
        self.assertNotIn("deepseek_reasoning_effort", llm_api["extraData"])
        self.assertNotIn(THINKING_EXPLICIT_OPT_IN_FIELD, llm_api["extraData"])

    def test_explicit_plugin_opt_in_allows_thinking_and_is_consumed(self):
        llm_api = {
            "model": "deepseek-v4-flash",
            "extraData": {
                "deepseek_thinking_mode": "enabled",
                "deepseek_reasoning_effort": "high",
                THINKING_EXPLICIT_OPT_IN_FIELD: "true",
            },
        }
        normalize_deepseek_extra_data(llm_api, {})
        self.assertEqual(llm_api["extraData"]["deepseek_thinking_mode"], "enabled")
        self.assertEqual(llm_api["extraData"]["deepseek_reasoning_effort"], "high")
        self.assertNotIn(THINKING_EXPLICIT_OPT_IN_FIELD, llm_api["extraData"])

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

    def test_editor_migration_and_opt_in_are_cost_safe(self):
        script = Path(
            "plugin/addon/content/llmApiEditorEnhancements.js"
        ).read_text(encoding="utf-8")
        migration = script.split("function migrateLegacyDeepSeekModel()", 1)[1].split(
            'document.addEventListener("DOMContentLoaded"', 1
        )[0]
        self.assertIn(
            'setExtraSelectValue("deepseek_thinking_mode", "disabled")', migration
        )
        self.assertNotIn(
            'setExtraSelectValue("deepseek_thinking_mode", "enabled")', migration
        )
        self.assertIn("deepseek_thinking_explicit_opt_in", script)
        self.assertIn('document.addEventListener("change"', script)
        self.assertIn('key !== "deepseek_thinking_mode"', script)
        self.assertIn('target.value === "enabled"', script)


if __name__ == "__main__":
    unittest.main()
