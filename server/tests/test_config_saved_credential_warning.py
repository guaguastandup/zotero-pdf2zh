"""Saved credential reuse: 插件未下发 API Key 时 server 必须给出提示。

背景：update_config_file() 会保留请求里缺省的字段，于是用户在插件里删掉 Key
之后，server 仍会用磁盘上的旧 Key 请求付费 API，而日志和插件界面都看不出这点。
"""

import json
import os
import tempfile
import unittest

import toml

from utils.config import Config


def next_request(**overrides):
    data = {
        "engine": "pdf2zh_next",
        "service": "deepseek",
        "next_service": "deepseek",
        "sourceLang": "en",
        "targetLang": "zh-CN",
        "mono": True,
        "dual": False,
    }
    data.update(overrides)
    return data


class SavedCredentialWarningTests(unittest.TestCase):
    def write_config(self, text, suffix=".toml"):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=suffix, delete=False, encoding="utf-8"
        )
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_warns_when_plugin_sends_no_key_but_config_keeps_one(self):
        path = self.write_config(
            "[deepseek_detail]\n"
            'deepseek_api_key = "sk-live-123456"\n'
            'deepseek_model = "deepseek-chat"\n'
        )

        config = Config(next_request())
        warning = config.detect_saved_credential_reuse(path)

        self.assertIsNotNone(warning)
        self.assertIn("deepseek", warning)
        self.assertIn("********3456", warning)
        self.assertNotIn("sk-live-123456", warning)
        self.assertEqual(config.warnings, [warning])

    def test_no_warning_when_plugin_provides_the_key(self):
        path = self.write_config(
            "[deepseek_detail]\n" 'deepseek_api_key = "sk-saved-123456"\n'
        )

        config = Config(
            next_request(llm_api={"apiKey": "sk-plugin-abcdef", "model": "m"})
        )

        self.assertIsNone(config.detect_saved_credential_reuse(path))
        self.assertEqual(config.warnings, [])

    def test_no_warning_when_saved_key_is_placeholder(self):
        for placeholder in ('"null"', '"none"', '""'):
            with self.subTest(placeholder=placeholder):
                path = self.write_config(
                    "[deepseek_detail]\n"
                    f"deepseek_api_key = {placeholder}\n"
                )
                config = Config(next_request())
                self.assertIsNone(config.detect_saved_credential_reuse(path))
                self.assertEqual(config.warnings, [])

    def test_no_warning_for_service_without_api_key(self):
        path = self.write_config("[bing_detail]\n")
        config = Config(next_request(service="bing", next_service="bing"))
        self.assertIsNone(config.detect_saved_credential_reuse(path))

    def test_pdf2zh_engine_reads_translators_json(self):
        path = self.write_config(
            json.dumps(
                {
                    "translators": [
                        {"name": "openai", "envs": {"OPENAI_API_KEY": "sk-json-7788"}}
                    ]
                }
            ),
            suffix=".json",
        )
        config = Config(
            {"engine": "pdf2zh", "service": "openai", "sourceLang": "en"}
        )

        warning = config.detect_saved_credential_reuse(path)

        self.assertIsNotNone(warning)
        self.assertIn("openai", warning)
        self.assertIn("********7788", warning)

    def test_missing_config_file_is_not_an_error(self):
        config = Config(next_request())
        self.assertIsNone(
            config.detect_saved_credential_reuse("/nonexistent/config.toml")
        )


if __name__ == "__main__":
    unittest.main()
