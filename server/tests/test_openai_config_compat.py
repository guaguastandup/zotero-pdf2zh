import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import toml

from utils.config import Config


def _request(extra_data=None):
    return {
        "engine": "pdf2zh_next",
        "next_service": "openai",
        "llm_api": {
            "apiKey": "",
            "apiUrl": "",
            "model": "",
            "extraData": extra_data or {},
        },
    }


def _write_config(path, openai_detail):
    with path.open("w", encoding="utf-8") as config_file:
        toml.dump(
            {
                "translation": {},
                "pdf": {},
                "openai_detail": openai_detail,
            },
            config_file,
        )


def _update_config(path, extra_data=None):
    with redirect_stdout(StringIO()):
        Config(_request(extra_data)).update_config_file(path)


class OpenAIConfigCompatibilityTest(unittest.TestCase):
    def test_saved_upstream_key_survives_requests_that_omit_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            _write_config(
                path,
                {
                    "translate_engine_type": "openai",
                    "support_llm": "yes",
                    "openai_send_temprature": True,
                },
            )

            _update_config(path)
            _update_config(path)

            detail = toml.load(path)["openai_detail"]
            self.assertIs(detail["openai_send_temprature"], True)
            self.assertNotIn("openai_send_temperature", detail)

    def test_old_correctly_spelled_alias_is_migrated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            _write_config(
                path,
                {
                    "translate_engine_type": "openai",
                    "support_llm": "yes",
                    "openai_send_temperature": True,
                },
            )

            _update_config(path)

            detail = toml.load(path)["openai_detail"]
            self.assertIs(detail["openai_send_temprature"], True)
            self.assertNotIn("openai_send_temperature", detail)

    def test_old_plugin_extra_data_alias_is_migrated_and_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            _write_config(
                path,
                {
                    "translate_engine_type": "openai",
                    "support_llm": "yes",
                },
            )

            _update_config(path, {"openai_send_temperature": False})
            _update_config(path)

            detail = toml.load(path)["openai_detail"]
            self.assertIs(detail["openai_send_temprature"], False)
            self.assertNotIn("openai_send_temperature", detail)


if __name__ == "__main__":
    unittest.main()
