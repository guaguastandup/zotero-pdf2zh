"""Clear saved credential tests: plugin deletion must wipe the server-side key."""

import json
import os
import tempfile
import unittest

import toml

from utils.config import (
    clear_saved_credential,
    pdf2zh,
    pdf2zh_next,
)


class ClearSavedCredentialTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        for name in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, name))
        os.rmdir(self.tmpdir)

    def write_toml(self, data):
        path = os.path.join(self.tmpdir, "config.toml")
        with open(path, "w", encoding="utf-8") as f:
            toml.dump(data, f)
        return path

    def write_json(self, data):
        path = os.path.join(self.tmpdir, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return path

    def test_clears_deepseek_key_in_toml(self):
        path = self.write_toml(
            {
                "deepseek_detail": {
                    "deepseek_api_key": "sk-live-1234",
                    "deepseek_model": "deepseek-chat",
                },
                "translation": {"lang_out": "zh-CN"},
            }
        )

        self.assertTrue(clear_saved_credential(path, pdf2zh_next, "deepseek"))

        with open(path, "r", encoding="utf-8") as f:
            data = toml.load(f)
        self.assertEqual(data["deepseek_detail"]["deepseek_api_key"], "null")
        self.assertEqual(data["deepseek_detail"]["deepseek_model"], "deepseek-chat")
        self.assertEqual(data["translation"]["lang_out"], "zh-CN")

    def test_placeholder_key_is_noop(self):
        path = self.write_toml({"deepseek_detail": {"deepseek_api_key": "null"}})

        self.assertFalse(clear_saved_credential(path, pdf2zh_next, "deepseek"))

        with open(path, "r", encoding="utf-8") as f:
            data = toml.load(f)
        self.assertEqual(data["deepseek_detail"]["deepseek_api_key"], "null")

    def test_missing_service_section_is_noop(self):
        path = self.write_toml({"openai_detail": {"openai_api_key": "sk-openai"}})

        self.assertFalse(clear_saved_credential(path, pdf2zh_next, "deepseek"))

        with open(path, "r", encoding="utf-8") as f:
            data = toml.load(f)
        self.assertEqual(data["openai_detail"]["openai_api_key"], "sk-openai")

    def test_resolves_service_alias(self):
        path = self.write_toml(
            {"siliconflow_detail": {"siliconflow_api_key": "sk-silicon"}}
        )

        self.assertTrue(clear_saved_credential(path, pdf2zh_next, "silicon"))

        with open(path, "r", encoding="utf-8") as f:
            data = toml.load(f)
        self.assertEqual(data["siliconflow_detail"]["siliconflow_api_key"], "null")

    def test_clears_openai_key_in_json(self):
        path = self.write_json(
            {
                "translators": [
                    {
                        "name": "openai",
                        "envs": {
                            "OPENAI_API_KEY": "sk-openai",
                            "OPENAI_MODEL": "gpt-4o",
                        },
                    }
                ]
            }
        )

        self.assertTrue(clear_saved_credential(path, pdf2zh, "openai"))

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["translators"][0]["envs"]["OPENAI_API_KEY"], "")
        self.assertEqual(data["translators"][0]["envs"]["OPENAI_MODEL"], "gpt-4o")

    def test_service_without_api_key_mapping_is_noop(self):
        path = self.write_json(
            {"translators": [{"name": "bing", "envs": {"BING_HOST": "x"}}]}
        )

        self.assertFalse(clear_saved_credential(path, pdf2zh, "bing"))

    def test_missing_file_is_noop(self):
        self.assertFalse(
            clear_saved_credential(
                os.path.join(self.tmpdir, "nope.toml"), pdf2zh_next, "deepseek"
            )
        )

    def test_unknown_engine_is_noop(self):
        path = self.write_toml({"deepseek_detail": {"deepseek_api_key": "sk-x"}})

        self.assertFalse(clear_saved_credential(path, "unknown", "deepseek"))


if __name__ == "__main__":
    unittest.main()
