"""Exercise the real installed engine, replacing only the outbound API client."""

import importlib.util
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import toml

from utils.config import Config
from utils.deepseek_thinking import prepare_deepseek_runtime_command


@unittest.skipUnless(
    importlib.util.find_spec("pdf2zh_next"),
    "Requires the full pdf2zh_next dependency baseline (installed in CI)",
)
class DeepSeekBaselineIntegrationTest(unittest.TestCase):
    def test_plugin_choices_reach_the_upstream_api_request(self):
        # Upstream initializes its cache database while importing. Keep both
        # packages' config/cache files out of the developer's real profile.
        profile = Path(self.enterContext(tempfile.TemporaryDirectory()))
        expanduser = Path.expanduser
        self.enterContext(patch.dict(os.environ))
        with (
            patch.object(Path, "home", return_value=profile),
            patch.object(
                Path,
                "expanduser",
                lambda path: (
                    profile / str(path)[2:]
                    if str(path).startswith("~/")
                    else expanduser(path)
                ),
            ),
        ):
            from pdf2zh_next.config.model import SettingsModel
            from pdf2zh_next.config.translate_engine_model import DeepSeekSettings
            from pdf2zh_next.translator.translator_impl.openai import OpenAITranslator
            from babeldoc.translator.cache import db
        self.addCleanup(db.close)

        cases = (
            ({}, "disabled", None),
            (
                {
                    "deepseek_thinking_mode": "disabled",
                    "deepseek_reasoning_effort": "max",
                },
                "disabled",
                None,
            ),
            ({"deepseek_thinking_mode": "enabled"}, "enabled", "high"),
            (
                {
                    "deepseek_thinking_mode": "enabled",
                    "deepseek_reasoning_effort": "max",
                },
                "enabled",
                "max",
            ),
        )
        for extra, mode, effort in cases:
            with (
                self.subTest(mode=mode, effort=effort),
                tempfile.TemporaryDirectory() as tmp,
            ):
                config_path = Path(tmp) / "config.toml"
                # A previous request enabled maximum thinking. Check that a new
                # request can disable it without inheriting stale parameters.
                config_path.write_text(
                    toml.dumps(
                        {
                            "deepseek_detail": {
                                "deepseek_model": "deepseek-v4-pro",
                                "deepseek_thinking_mode": "enabled",
                                "deepseek_reasoning_effort": "max",
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                request = {
                    "engine": "pdf2zh_next",
                    "next_service": "deepseek",
                    "llm_api": {
                        "model": "deepseek-v4-flash",
                        "apiKey": "test-key",
                        "extraData": extra,
                    },
                }
                cmd = [
                    sys.executable,
                    "-m",
                    "pdf2zh_next",
                    "paper.pdf",
                    "--deepseek",
                    "--config-file",
                    str(config_path),
                ]
                with redirect_stdout(StringIO()), patch("sys.argv", ["server.py"]):
                    Config(request).update_config_file(config_path)
                    prepared = prepare_deepseek_runtime_command(cmd)
                self.assertEqual(
                    prepared[prepared.index("--deepseek-thinking-mode") + 1], mode
                )

                engine_settings = DeepSeekSettings(
                    **toml.load(config_path)["deepseek_detail"]
                )
                engine_settings.validate_settings()
                settings = SettingsModel(
                    translate_engine_settings=engine_settings.transform()
                )
                create = Mock(
                    return_value=SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content="translated")
                            )
                        ],
                        usage=None,
                    )
                )
                client = SimpleNamespace(
                    chat=SimpleNamespace(completions=SimpleNamespace(create=create))
                )
                with (
                    patch(
                        "pdf2zh_next.translator.translator_impl.openai.openai.OpenAI",
                        return_value=client,
                    ),
                    patch("pdf2zh_next.translator.translator_impl.openai.httpx.Client"),
                ):
                    translator = OpenAITranslator(settings, Mock())
                    self.assertEqual(translator.do_translate("hello"), "translated")
                create.assert_called_once()
                payload = create.call_args.kwargs
                self.assertEqual(payload["model"], "deepseek-v4-flash")
                self.assertEqual(payload["extra_body"], {"thinking": {"type": mode}})
                if effort:
                    self.assertEqual(payload["reasoning_effort"], effort)
                else:
                    self.assertNotIn("reasoning_effort", payload)


if __name__ == "__main__":
    unittest.main()
