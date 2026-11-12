"""Isolated protocol and Flask tests using synthetic PDFs and an offline fake CLI."""

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pypdf import PdfReader, PdfWriter
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
        self.credentials = {"service": "deepseek", "apiKey": "fake-plugin-credential"}
        self.config = self.make_config(sourceLang="en", targetLang="zh-CN")
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"DEEPSEEK_API_KEY": "must-not-use-server-key"}).start()
        # Keep pypdf's lazy tool discovery on the real standard-library module.
        cli_shutil = patch("utils.wenyi.shutil", wraps=shutil).start()
        cli_shutil.which.return_value = sys.executable
        original_popen = subprocess.Popen

        def child(command, **kwargs):
            self.command = command
            self.child_environment = kwargs["env"]
            self.child = original_popen(
                [sys.executable, str(Path(__file__).with_name("fake_wenyi.py")), *command[1:]],
                **kwargs,
            )
            return self.child

        patch("utils.wenyi.subprocess.Popen", side_effect=child).start()

    def make_config(self, **fields):
        return Config({"engine": "wenyi", "llm_api": self.credentials, **fields})

    def translate(self):
        self.frames = []
        return self.adapter.translate(self.source, self.config, self.task_id, self.frames.append)

    def test_cli_lookup_mock_does_not_change_standard_library_lookup(self):
        self.assertIsNone(shutil.which(str(self.root / "missing-tool")))

    def test_real_child_receipt_and_atomic_publication(self):
        files = self.translate()
        self.assertEqual(len(files), 1)
        self.assertTrue(Path(files[0]).name.endswith(".zh.mono.pdf"))
        self.assertEqual(Path(files[0]).read_bytes(), self.source.read_bytes())
        self.assertTrue(self.frames)
        self.assertLess(self.frames[-1]["progress"], 100)
        self.assertEqual(self.child_environment["DEEPSEEK_API_KEY"], self.credentials["apiKey"])
        self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "must-not-use-server-key")
        self.assertNotIn(self.credentials["apiKey"], repr(self.command))
        settings = json.loads((self.source.parent / "config.yaml").read_text())
        self.assertEqual(settings["llm"], {"preset": "deepseek"})
        self.assertEqual(settings["pipeline"]["pdf_backend"], "babeldoc")
        self.assertIs(settings["pipeline"]["annotation_alignment"], False)
        self.assertEqual(
            settings["output"],
            {"mono": True, "bilingual": False, "bilingual_order": "target_first"},
        )
        self.assertEqual(settings["language"]["target"], "zh")
        genre_index = self.command.index("--prompt-genre")
        self.assertEqual(self.command[genre_index + 1], "academic")
        self.assertLess(genre_index, self.command.index("translate"))
        self.assertNotIn("prompt_genre", json.dumps(settings))
        for path in self.source.parent.rglob("*"):
            if path.is_file():
                self.assertNotIn(self.credentials["apiKey"].encode(), path.read_bytes(), str(path))
        self.assertEqual(list(self.adapter.output_root.glob(".wenyi-*")), [])

    def test_editions_alignment_and_order_reach_cli_and_publish_matching_attachments(self):
        for mono, bilingual in ((True, False), (False, True), (True, True)):
            for order in ("target_first", "source_first"):
                with self.subTest(mono=mono, bilingual=bilingual, order=order):
                    task_id = str(uuid4())
                    source = self.adapter.workspace(task_id) / "paper.pdf"
                    source.write_bytes(self.source.read_bytes())
                    config = self.make_config(
                        mono=mono,
                        dual=bilingual,
                        noMono=not mono,
                        noDual=not bilingual,
                        wenyi={
                            "pipeline": {"annotation_alignment": bilingual},
                            "output": {"bilingual_order": order},
                        },
                    )
                    files = self.adapter.translate(source, config, task_id, lambda _: None)
                    expected = (["mono"] if mono else []) + (["dual"] if bilingual else [])
                    self.assertEqual([Path(path).stem.split(".")[-1] for path in files], expected)
                    settings = json.loads((source.parent / "config.yaml").read_text())
                    self.assertEqual(
                        settings["output"],
                        {"mono": mono, "bilingual": bilingual, "bilingual_order": order},
                    )
                    self.assertIs(settings["pipeline"]["annotation_alignment"], bilingual)
                    self.assertIn("--mono" if mono else "--no-mono", self.command)
                    self.assertIn("--bilingual" if bilingual else "--no-bilingual", self.command)
                    for path, edition in zip(files, expected):
                        pages = PdfReader(path).pages
                        self.assertEqual(len(pages), 1)
                        self.assertEqual(
                            float(pages[0].mediabox.width), 600 if edition == "dual" else 300
                        )

    def test_invalid_bilingual_receipts_publish_neither_edition(self):
        for mode in ("missing-dual", "duplicate-output", "unexpected-output", "bad-dual-hash"):
            with self.subTest(mode=mode), patch.dict(os.environ, {"WENYI_TEST_MODE": mode}):
                task_id = str(uuid4())
                source = self.adapter.workspace(task_id) / "paper.pdf"
                source.write_bytes(self.source.read_bytes())
                config = self.make_config(mono=True, dual=True)
                with self.assertRaises(ValueError):
                    self.adapter.translate(source, config, task_id, lambda _: None)
                self.assertFalse(self.adapter.output_root.exists())

    def test_native_options_reach_all_model_tiers_and_pipeline(self):
        self.config = self.make_config(
            wenyi={
                "pipeline": {
                    "book_understanding": False,
                    "translation_mode": "standard",
                    "polish": False,
                    "review": False,
                },
                "model": {"thinking": False, "reasoning_effort": "max"},
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

    def test_managed_runtime_supplies_command_environment_and_bridge_url(self):
        self.adapter.runtime = Mock()
        environment = dict(os.environ, WENYI_MANAGED_TEST="yes")
        self.adapter.runtime.prepare.return_value = (
            [sys.executable],
            environment,
            "http://127.0.0.1:49152",
        )
        with patch("utils.wenyi.shutil.which") as ambient:
            self.translate()
        ambient.assert_not_called()
        self.adapter.runtime.prepare.assert_called_once_with()
        self.assertEqual(self.child_environment["DEEPSEEK_API_KEY"], self.credentials["apiKey"])
        self.assertEqual(environment["DEEPSEEK_API_KEY"], "must-not-use-server-key")
        settings = json.loads((self.source.parent / "config.yaml").read_text())
        self.assertEqual(settings["pipeline"]["babeldoc_bridge_url"], "http://127.0.0.1:49152")

    def test_managed_install_failure_never_uses_an_ambient_cli(self):
        self.adapter.runtime = Mock()
        self.adapter.runtime.prepare.side_effect = RuntimeError("Managed install failed")
        with patch("utils.wenyi.shutil.which") as ambient:
            with self.assertRaisesRegex(RuntimeError, "Managed install failed"):
                self.translate()
        ambient.assert_not_called()
        self.assertFalse(hasattr(self, "child"))
        self.assertFalse((self.source.parent / "config.yaml").exists())

    def test_invalid_wenyi_options_fail_before_starting_process(self):
        for options in (
            None,
            [],
            {"apiKey": "must-not-forward"},
            {"prompt_genre": "neutral"},
            {"prompt_genre": "Academic"},
            {"prompt_genre": "../academic"},
            {"prompt_genre": ""},
            {"prompt_genre": None},
            {"prompt_genre": True},
            {"prompt_genre": []},
            {"model": {"deepseek_thinking_mode": "enabled"}},
            {"model": {"thinking": "false"}},
            {"model": {"reasoning_effort": "ultra"}},
            {"model": {"extra_body": {"anything": True}}},
            {"pipeline": {"polish": "false"}},
            {"pipeline": {"annotation_alignment": "false"}},
            {"pipeline": {"translation_mode": True}},
            {"pipeline": {"translation_mode": "best_of_five"}},
            {"pipeline": {"translation_mode": "best_of_three", "polish": False}},
            {"pipeline": {"pdf_backend": "mineru"}},
            {"pipeline": {"prompt_genre": "literary"}},
            {"output": {"bilingual_order": "top"}},
            {"output": {"bilingual_order": True}},
            {"output": {"bilingual_order": []}},
            {"output": {"bilingual": True}},
            {"output": None},
            {"provider": {"base_url": "http://untrusted.invalid"}},
            {"provider": {"max_concurrency": 6}},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.make_config(wenyi=options)
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
        for credentials in (
            None,
            {},
            {"service": "openai", "apiKey": "wrong-provider-key"},
            {"service": "deepseek"},
            {"service": "deepseek", "apiKey": "  "},
            {"service": "deepseek", "apiKey": 123},
            {"service": "deepseek", "apiKey": "invalid\nkey"},
            {"service": "deepseek", "apiKey": "invalid\x00key"},
            {"service": "deepseek", "apiKey": "x" * 4097},
        ):
            with self.subTest(credentials=credentials):
                with self.assertRaisesRegex(ValueError, "DeepSeek API key in the plugin"):
                    self.make_config(llm_api=credentials)
        self.assertFalse(hasattr(self, "child"))

    def test_request_keys_do_not_leak_between_cli_environments(self):
        self.translate()
        first_environment = self.child_environment
        task_id = str(uuid4())
        source = self.adapter.workspace(task_id) / "another.pdf"
        source.write_bytes(self.source.read_bytes())
        config = self.make_config(llm_api={"service": "deepseek", "apiKey": "second-plugin-key"})
        self.adapter.translate(source, config, task_id, lambda _: None)
        self.assertEqual(first_environment["DEEPSEEK_API_KEY"], self.credentials["apiKey"])
        self.assertEqual(self.child_environment["DEEPSEEK_API_KEY"], "second-plugin-key")
        self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "must-not-use-server-key")

    def test_unsupported_options_and_languages_fail_before_starting_process(self):
        for changes in (
            {"mono": False},
            {"no_mono": True},
            {"no_mono": True, "dual": True, "no_dual": True},
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
                config = self.make_config()
                config.sourceLang = "en"
                for key, value in changes.items():
                    setattr(config, key, value)
                with self.assertRaises(ValueError):
                    self.adapter.translate(self.source, config, self.task_id, lambda _: None)
                self.assertFalse(hasattr(self, "child"))

    def test_config_uses_only_plugin_deepseek_key_and_keeps_fixed_model(self):
        logs = io.StringIO()
        with redirect_stdout(logs):
            config = self.make_config(
                service="openai",
                llm_api={
                    **self.credentials,
                    "model": "another-model",
                    "apiUrl": "http://untrusted.invalid",
                    "extraData": {"api_key": "must-not-forward"},
                },
            )
        self.assertEqual(config.engine, "wenyi")
        self.assertEqual(config.service, "deepseek")
        self.assertEqual(
            config.llm_api, {"model": "deepseek-flash", "apiKey": self.credentials["apiKey"]}
        )
        with patch("utils.config.os.path.exists") as saved_config_exists:
            self.assertIsNone(config.detect_saved_credential_reuse(self.root / "config.toml"))
        saved_config_exists.assert_not_called()
        self.assertEqual(config.warnings, [])
        self.assertNotIn(self.credentials["apiKey"], logs.getvalue())
        with self.assertRaisesRegex(ValueError, "engine"):
            Config({"engine": "unknown"})
        self.assertEqual(Config({"engine": "pdf2zh"}).service, "bing")
        self.assertEqual(Config({"engine": "pdf2zh_next"}).service, "siliconflowfree")

    def test_progress_rejects_another_invocation(self):
        path = self.root / "progress.json"
        path.write_text(json.dumps({"protocol_version": 1, "run_id": "another"}))
        with self.assertRaisesRegex(ValueError, "invocation"):
            self.adapter._progress(path, "previous", lambda _: None)

    def test_flask_async_protocol_returns_downloadable_mono_and_dual_attachments(self):
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
                "mono": True,
                "dual": True,
                "llm_api": self.credentials,
                "wenyi": {
                    "prompt_genre": "literary",
                    "pipeline": {
                        "translation_mode": "best_of_three",
                        "polish": True,
                        "review": False,
                        "annotation_alignment": True,
                    },
                    "output": {"bilingual_order": "source_first"},
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
        self.assertNotIn(self.credentials["apiKey"], json.dumps(tasks))
        for path in self.root.rglob("*.json"):
            self.assertNotIn(self.credentials["apiKey"], path.read_text(), str(path))
        settings = json.loads((self.adapter.workspace(task_id) / "config.yaml").read_text())
        self.assertEqual(settings["pipeline"]["translation_mode"], "best_of_three")
        self.assertIs(settings["pipeline"]["polish"], True)
        self.assertIs(settings["pipeline"]["review"], False)
        self.assertIs(settings["pipeline"]["annotation_alignment"], True)
        self.assertEqual(
            settings["output"],
            {"mono": True, "bilingual": True, "bilingual_order": "source_first"},
        )
        self.assertIs(settings["llm"]["models"]["default_strong"]["options"]["thinking"], False)
        genre_index = self.command.index("--prompt-genre")
        self.assertEqual(self.command[genre_index + 1], "literary")
        self.assertLess(genre_index, self.command.index("translate"))
        self.assertNotIn("prompt_genre", json.dumps(settings))
        files = task["result"]["fileList"]
        self.assertEqual(len(files), 2)
        for name, edition in zip(files, ("mono", "dual")):
            self.assertTrue(name.endswith(f".{edition}.pdf"))
            with patch.object(server, "output_folder", str(self.root / "published")):
                download = client.get("/translatedFile/" + name)
            self.assertEqual(download.status_code, 200)
            if edition == "mono":
                self.assertEqual(download.data, self.source.read_bytes())
            else:
                self.assertEqual(
                    float(PdfReader(io.BytesIO(download.data)).pages[0].mediabox.width), 600
                )
            download.close()


if __name__ == "__main__":
    unittest.main()
