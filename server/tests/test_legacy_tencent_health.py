"""Old pdf2zh must not reuse an incompatible Tencent translation SDK."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from utils import environment_lifecycle as lifecycle


class TencentLegacyHealthTests(unittest.TestCase):
    def test_custom_config_adds_legacy_sdk_constraint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "venv.json"
            path.write_text(json.dumps({
                "pdf2zh": {"uv": {
                    "python_version": "3.12",
                    "packages": ["pdf2zh==1.9.11"],
                }}
            }), encoding="utf-8")
            _, reqs = lifecycle.load_requirements("pdf2zh", "uv", path)
        self.assertIn("tencentcloud-sdk-python-tmt<3.1", reqs)
        self.assertIn(
            "tencentcloud-sdk-python-tmt", lifecycle.VERSION_PACKAGES["pdf2zh"]
        )

    def test_missing_text_translate_request_is_unhealthy(self):
        result = CompletedProcess(
            [], 0, json.dumps({
                "ok": False,
                "reason": "ImportError: cannot import name 'TextTranslateRequest'",
            }), "",
        )
        with patch.object(lifecycle.subprocess, "run", return_value=result) as run:
            healthy, reason = lifecycle.managed_runtime_health(
                "pdf2zh", Path(sys.executable)
            )
        self.assertFalse(healthy)
        self.assertIn("TextTranslateRequest", reason)
        self.assertIn("tencentcloud", run.call_args.args[0][-1])

    def test_real_import_error_gets_actionable_hint(self):
        from utils.error_catalog import classify_error_message

        msg = (
            "ImportError: cannot import name 'TextTranslateRequest' "
            "from 'tencentcloud.tmt.v20180321.models'"
        )
        classified = classify_error_message(msg)
        self.assertEqual(
            classified["errorCode"], "LEGACY_TENCENT_SDK_INCOMPATIBLE"
        )
        self.assertIn("doctor", classified["hint"])

    def test_healthy_import_is_accepted(self):
        result = CompletedProcess([], 0, '{"ok":true,"reason":"ok"}', "")
        with patch.object(lifecycle.subprocess, "run", return_value=result):
            self.assertEqual(
                lifecycle.managed_runtime_health("pdf2zh", Path(sys.executable)),
                (True, "ok"),
            )


if __name__ == "__main__":
    unittest.main()
