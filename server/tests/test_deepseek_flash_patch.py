"""No-API tests for DeepSeek Flash thinking and version compatibility."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import toml

from utils import deepseek_flash_patch, deepseek_thinking, table_runner
from utils.table_runtime import prepare_table_runtime_command


class DeepSeekFlashTests(unittest.TestCase):
    def test_deepseek_flash_control_is_explicit_and_not_an_alias(self):
        self.assertTrue(deepseek_thinking.is_deepseek_flash_model("deepseek-flash"))
        self.assertTrue(deepseek_thinking.is_deepseek_thinking_model("deepseek-v4-pro"))
        self.assertFalse(deepseek_thinking.is_deepseek_thinking_model("deepseek-chat"))
        self.assertFalse(deepseek_thinking.is_deepseek_flash_model("deepseek-flash-custom"))
        user = {"model": "deepseek-flash", "extraData": {}}
        self.assertEqual(
            deepseek_thinking.normalize_deepseek_extra_data(user, {}),
            "deepseek-flash",
        )
        self.assertEqual(user["extraData"]["deepseek_thinking_mode"], "disabled")

    def _prepare(self, available):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config.write_text(
                toml.dumps({"deepseek_detail": {
                    "deepseek_model": "deepseek-flash",
                    "deepseek_thinking_mode": "disabled",
                }}), encoding="utf-8",
            )
            command = ["pdf2zh_next", "paper.pdf", "--deepseek",
                       "--config-file", str(config)]
            with patch.object(
                deepseek_thinking, "_runtime_supports_thinking",
                return_value=available,
            ), redirect_stdout(io.StringIO()):
                return deepseek_thinking.prepare_deepseek_runtime_command(command)

    def test_runtime_adds_explicit_disabled_flag_and_patch(self):
        result = self._prepare(True)
        self.assertEqual(
            result[result.index("--deepseek-thinking-mode") + 1], "disabled"
        )
        self.assertIn(deepseek_thinking.FLASH_PATCH_FLAG, result)
        self.assertNotIn("--deepseek-model", result)

    def test_unsupported_runtime_blocks_before_api(self):
        with self.assertRaisesRegex(ValueError, "调用 API 前停止"):
            self._prepare(False)

    def test_python_runner_honors_flash_only_and_combined_modes(self):
        legacy = [sys.executable, "-m", "pdf2zh_next"]
        self.assertIs(prepare_table_runtime_command(legacy), legacy)
        cmd = legacy + [
            "paper.pdf", "--deepseek", deepseek_thinking.FLASH_PATCH_FLAG,
        ]
        wrapped = prepare_table_runtime_command(cmd)
        self.assertEqual(wrapped[:2], [sys.executable, "-u"])
        self.assertEqual(
            wrapped[3:5], ["none", deepseek_thinking.FLASH_PATCH_FLAG]
        )
        combined = prepare_table_runtime_command(
            cmd + ["--zotero-table-mode", "fixed", "--zotero-reference-skip"]
        )
        self.assertEqual(
            combined[3:6],
            ["fixed", "--zotero-reference-skip", deepseek_thinking.FLASH_PATCH_FLAG],
        )

    def test_standalone_exe_is_refused_before_api(self):
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / "pdf2zh.exe"
            exe.touch()
            with (
                patch.object(sys, "argv", [
                    "server.py", "--enable_winexe", "true",
                    "--winexe_path", str(exe),
                ]),
                self.assertRaisesRegex(ValueError, "Windows 独立 EXE"),
            ):
                deepseek_thinking.validate_winexe_runtime_if_selected(
                    "config.toml", "deepseek-flash", "disabled",
                )

    def test_runner_removes_private_flag_and_restores_hook(self):
        calls = []

        def install():
            calls.append("install")
            return lambda: calls.append("restore")

        def run_entry():
            self.assertNotIn(deepseek_thinking.FLASH_PATCH_FLAG, sys.argv)
            calls.append("entry")
            return 0

        entry = SimpleNamespace(
            group="console_scripts", name="pdf2zh_next", load=lambda: run_entry
        )
        with (
            patch.object(sys, "argv", [
                "table_runner.py", "none", deepseek_thinking.FLASH_PATCH_FLAG,
                "paper.pdf", "--deepseek",
            ]),
            patch(
                "utils.deepseek_flash_patch.install_deepseek_flash_patch",
                side_effect=install,
            ),
            patch(
                "importlib.metadata.distribution",
                return_value=SimpleNamespace(entry_points=[entry]),
            ),
        ):
            self.assertEqual(table_runner.main(), 0)
        self.assertEqual(calls, ["install", "entry", "restore"])


class RealTransformTests(unittest.TestCase):
    def test_upstream_2_9_0_transform_disabled_enabled_and_restored(self):
        try:
            from pdf2zh_next.config.translate_engine_model import DeepSeekSettings
        except ImportError as exc:
            self.skipTest(f"real upstream wheel not installed: {exc}")

        original = DeepSeekSettings.transform

        def settings(mode):
            return DeepSeekSettings(
                deepseek_api_key="no-network-test-key",
                deepseek_model="deepseek-flash",
                deepseek_thinking_mode=mode,
                deepseek_reasoning_effort="max" if mode == "enabled" else None,
            )

        self.assertIsNone(settings("disabled").transform()._openai_extra_body)
        with patch.object(deepseek_flash_patch, "version", return_value="2.9.0"):
            restore = deepseek_flash_patch.install_deepseek_flash_patch()
            try:
                disabled = settings("disabled").transform()
                self.assertEqual(disabled.openai_model, "deepseek-flash")
                self.assertEqual(
                    disabled._openai_extra_body, {"thinking": {"type": "disabled"}}
                )
                self.assertFalse(disabled.openai_send_reasoning_effort)

                enabled = settings("enabled").transform()
                self.assertEqual(
                    enabled._openai_extra_body, {"thinking": {"type": "enabled"}}
                )
                self.assertTrue(enabled.openai_send_reasoning_effort)
                self.assertEqual(enabled.openai_reasoning_effort, "max")

                legacy = DeepSeekSettings(
                    deepseek_api_key="no-network-test-key",
                    deepseek_model="deepseek-v4-pro",
                    deepseek_thinking_mode="disabled",
                ).transform()
                self.assertEqual(
                    legacy._openai_extra_body, {"thinking": {"type": "disabled"}}
                )
                with self.assertRaisesRegex(RuntimeError, "重复安装"):
                    deepseek_flash_patch.install_deepseek_flash_patch()
            finally:
                restore()
        self.assertIs(DeepSeekSettings.transform, original)
        self.assertIsNone(settings("disabled").transform()._openai_extra_body)

    def test_unknown_version_fails_closed(self):
        with patch.object(deepseek_flash_patch, "version", return_value="2.9.1"):
            with self.assertRaisesRegex(RuntimeError, "尚未验证"):
                deepseek_flash_patch.install_deepseek_flash_patch()


if __name__ == "__main__":
    unittest.main()
