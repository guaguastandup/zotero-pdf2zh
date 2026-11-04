"""Isolated protocol and Flask tests using synthetic PDFs and an offline fake CLI."""

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pypdf import PdfWriter
from utils.config import Config
from utils.wenyi import WenyiAdapter

import server


class WenyiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.task_id = str(uuid4())
        self.adapter = WenyiAdapter(self.root / "tasks", self.root / "published", timeout=5)
        self.source = self.adapter.workspace(self.task_id) / "论文 with spaces.pdf"
        pdf = PdfWriter()
        pdf.add_blank_page(width=300, height=400)
        pdf.write(self.source)
        self.config = Config({"engine": "wenyi", "sourceLang": "en", "targetLang": "zh-CN"})
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fake-test-credential"}).start()
        patch("utils.wenyi.shutil.which", return_value=sys.executable).start()
        original_popen = subprocess.Popen

        def child(command, **kwargs):
            self.command = command
            self.child = original_popen(
                [sys.executable, str(Path(__file__).with_name("fake_wenyi.py")), *command[1:]],
                **kwargs,
            )
            return self.child

        patch("utils.wenyi.subprocess.Popen", side_effect=child).start()

    def translate(self):
        self.frames = []
        return self.adapter.translate(self.source, self.config, self.task_id, self.frames.append)

    def test_real_child_receipt_and_atomic_publication(self):
        files = self.translate()
        self.assertEqual(len(files), 1)
        self.assertTrue(Path(files[0]).name.endswith(".zh.mono.pdf"))
        self.assertEqual(Path(files[0]).read_bytes(), self.source.read_bytes())
        self.assertTrue(self.frames)
        self.assertLess(self.frames[-1]["progress"], 100)
        self.assertNotIn("fake-test-credential", repr(self.command))
        settings = json.loads((self.source.parent / "config.yaml").read_text())
        self.assertEqual(settings["llm"], {"preset": "deepseek"})
        self.assertEqual(settings["pipeline"]["pdf_backend"], "babeldoc")
        self.assertEqual(settings["language"]["target"], "zh")
        self.assertNotIn("fake-test-credential", json.dumps(settings))
        self.assertEqual(list(self.adapter.output_root.glob(".wenyi-*")), [])

    def test_native_options_reach_all_model_tiers_and_pipeline(self):
        self.config = Config(
            {
                "engine": "wenyi",
                "wenyi": {
                    "pipeline": {
                        "book_understanding": False,
                        "translation_mode": "standard",
                        "polish": False,
                        "review": False,
                    },
                    "model": {"thinking": False, "reasoning_effort": "max"},
                },
            }
        )
        self.translate()
        settings = json.loads((self.source.parent / "config.yaml").read_text())
        self.assertEqual(settings["pipeline"]["translation_mode"], "standard")
        self.assertIs(settings["pipeline"]["polish"], False)
        self.assertIs(settings["pipeline"]["review"], False)
        self.assertIs(settings["pipeline"]["book_understanding"], False)
        self.assertNotIn("providers", settings["llm"])
        for tier in ("strong", "cheap", "fast"):
            model = settings["llm"]["models"][f"default_{tier}"]
            self.assertEqual(model["model"], "deepseek-flash")
            self.assertEqual(model["provider"], "default")
            self.assertEqual(model["options"], {"thinking": False, "reasoning_effort": "max"})

    def test_invalid_wenyi_options_fail_before_starting_process(self):
        for options in (
            None,
            [],
            {"apiKey": "must-not-forward"},
            {"model": {"deepseek_thinking_mode": "enabled"}},
            {"model": {"thinking": "false"}},
            {"model": {"reasoning_effort": "ultra"}},
            {"model": {"extra_body": {"anything": True}}},
            {"pipeline": {"polish": "false"}},
            {"pipeline": {"translation_mode": True}},
            {"pipeline": {"translation_mode": "best_of_five"}},
            {"pipeline": {"translation_mode": "best_of_three", "polish": False}},
            {"pipeline": {"pdf_backend": "mineru"}},
            {"provider": {"base_url": "http://untrusted.invalid"}},
            {"provider": {"max_concurrency": 6}},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                Config({"engine": "wenyi", "wenyi": options})
        self.assertFalse(hasattr(self, "child"))

    def test_legacy_engines_ignore_wenyi_options(self):
        self.assertEqual(
            Config({"engine": "pdf2zh_next", "wenyi": {"unsupported": True}}).engine,
            "pdf2zh_next",
        )

    def test_mismatched_or_missing_results_never_publish_a_file(self):
        for mode in (
            "exit",
            "no-result",
            "wrong-run",
            "wrong-source",
            "wrong-path",
            "bad-hash",
            "failed-receipt",
            "invalid-pdf",
        ):
            with self.subTest(mode=mode), patch.dict(os.environ, {"WENYI_TEST_MODE": mode}):
                task_id = str(uuid4())
                source = self.adapter.workspace(task_id) / "paper.pdf"
                source.write_bytes(self.source.read_bytes())
                with self.assertRaises((RuntimeError, ValueError)):
                    self.adapter.translate(source, self.config, task_id, lambda _: None)
                self.assertFalse(self.adapter.output_root.exists())

    def test_timeout_terminates_child_and_preserves_checkpoints(self):
        self.adapter.timeout = 0.05
        with patch.dict(os.environ, {"WENYI_TEST_MODE": "stall"}):
            with self.assertRaisesRegex(TimeoutError, "checkpoints"):
                self.translate()
        self.assertIsNotNone(self.child.poll())
        self.assertTrue(self.source.exists())
        self.assertFalse(self.adapter.output_root.exists())

    def test_second_invocation_cannot_reuse_old_receipts(self):
        self.translate()
        with self.assertRaisesRegex(ValueError, "twice"):
            self.translate()

    def test_missing_credentials_fail_before_starting_process(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
                self.translate()
        self.assertFalse(hasattr(self, "child"))

    def test_unsupported_options_and_languages_fail_before_starting_process(self):
        for changes in (
            {"dual": True},
            {"mono": False},
            {"no_mono": True},
            {"mono_cut": True},
            {"ocr": True},
            {"auto_ocr": True},
            {"only_include_translated_page": True},
            {"skip_last_pages": 2},
            {"targetLang": "auto"},
            {"targetLang": "pl"},
            {"targetLang": "en"},
        ):
            with self.subTest(changes=changes):
                config = Config({"engine": "wenyi"})
                config.sourceLang = "en"
                for key, value in changes.items():
                    setattr(config, key, value)
                with self.assertRaises(ValueError):
                    self.adapter.translate(self.source, config, self.task_id, lambda _: None)
                self.assertFalse(hasattr(self, "child"))

    def test_config_never_falls_back_or_uses_plugin_credentials(self):
        config = Config(
            {
                "engine": "wenyi",
                "service": "openai",
                "llm_api": {"apiKey": "must-not-forward", "model": "another-model"},
            }
        )
        self.assertEqual(config.engine, "wenyi")
        self.assertEqual(config.service, "deepseek")
        self.assertEqual(config.llm_api, {"model": "deepseek-flash"})
        with self.assertRaisesRegex(ValueError, "engine"):
            Config({"engine": "unknown"})
        self.assertEqual(Config({"engine": "pdf2zh"}).service, "bing")
        self.assertEqual(Config({"engine": "pdf2zh_next"}).service, "siliconflowfree")

    def test_progress_rejects_another_invocation(self):
        path = self.root / "progress.json"
        path.write_text(json.dumps({"protocol_version": 1, "run_id": "another"}))
        with self.assertRaisesRegex(ValueError, "invocation"):
            self.adapter._progress(path, "previous", lambda _: None)

    def test_flask_async_protocol_returns_downloadable_mono_attachment(self):
        with (
            patch.object(server, "root_path", str(self.root)),
            patch.object(server, "output_folder", str(self.root / "published")),
        ):
            translator = server.PDFTranslator(SimpleNamespace(enable_venv=False))
        translator.wenyi = self.adapter
        client = translator.app.test_client()
        response = client.post(
            "/translate",
            json={
                "engine": "wenyi",
                "asyncJob": True,
                "wenyi": {
                    "pipeline": {
                        "translation_mode": "best_of_three",
                        "polish": True,
                        "review": False,
                    },
                    "model": {"thinking": False},
                },
                "fileName": self.source.name,
                "fileContent": base64.b64encode(self.source.read_bytes()).decode(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "accepted")
        task_id = response.json["taskId"]
        deadline = time.monotonic() + 5
        task = None
        while time.monotonic() < deadline:
            tasks = client.get("/api/tasks").json["tasks"]
            task = next((item for item in tasks if item["taskId"] == task_id), None)
            if task and task.get("finished"):
                break
            time.sleep(0.02)
        self.assertIsNotNone(task)
        self.assertEqual(task["result"]["status"], "success", task)
        settings = json.loads((self.adapter.workspace(task_id) / "config.yaml").read_text())
        self.assertEqual(settings["pipeline"]["translation_mode"], "best_of_three")
        self.assertIs(settings["pipeline"]["polish"], True)
        self.assertIs(settings["pipeline"]["review"], False)
        self.assertIs(settings["llm"]["models"]["default_strong"]["options"]["thinking"], False)
        name = task["result"]["fileList"][0]
        with patch.object(server, "output_folder", str(self.root / "published")):
            download = client.get("/translatedFile/" + name)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, self.source.read_bytes())
        download.close()


if __name__ == "__main__":
    unittest.main()
