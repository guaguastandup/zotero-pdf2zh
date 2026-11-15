"""Real CLI, Core locks and HTTP, with synthetic PDFs and offline model responses.

Requires wenyi-cli/core in this test Python. No bridge/BabelDOC install is needed.
"""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from copy import copy
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from pypdf import PdfWriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.config import Config
from utils.environment_lifecycle import managed_python_env
from utils.wenyi import WenyiAdapter
from utils.wenyi_runner import LOGICAL_BRIDGE_URL


class SyntheticBridge:
    """Restore a tiny frozen fixture from disk; never invent a missing session."""

    def __init__(self, sessions):
        self.sessions = sessions
        self.requests = []

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def reply(self, status, data, content_type="application/json"):
                payload = json.dumps(data).encode() if isinstance(data, dict) else data
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                owner.requests.append(("health", None))
                self.reply(200, {"ok": True, "capabilities": []})

            def do_POST(self):
                data = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path == "/extract":
                    message = BytesParser(policy=policy.default).parsebytes(
                        f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode() + data
                    )
                    fields = {
                        part.get_param("name", header="content-disposition"): part.get_payload(
                            decode=True
                        )
                        for part in message.iter_parts()
                    }
                    owner.requests.append(("extract", fields.get("pages")))
                    session_id = uuid4().hex
                    folder = owner.sessions / session_id
                    folder.mkdir(parents=True)
                    (folder / "source.pdf").write_bytes(fields["file"])
                    snapshot = {
                        "source_sha256": hashlib.sha256(fields["file"]).hexdigest(),
                        "session_id": session_id,
                        "pages": fields.get("pages"),
                        "frozen_il": "synthetic immutable fixture",
                        "paragraphs": {
                            "paragraphs": [
                                {
                                    "id": f"{page}:0",
                                    "page": page,
                                    "index": 0,
                                    "source": f"Offline source paragraph {page}.",
                                    "layout_label": "plain text",
                                }
                                for page in (0, 1)
                            ]
                        },
                    }
                    (folder / "session.json").write_text(json.dumps(snapshot))
                    self.reply(200, snapshot)
                elif self.path == "/fillback":
                    request = json.loads(data)
                    owner.requests.append(("fillback", request))
                    folder = owner.sessions / request["session_id"]
                    if not (folder / "session.json").is_file():
                        self.reply(404, {"detail": "session not found"})
                        return
                    snapshot = json.loads((folder / "session.json").read_text())
                    expected = {item["id"] for item in snapshot["paragraphs"]["paragraphs"]}
                    if set(request["translations"]) != expected:
                        self.reply(400, {"detail": "paragraph identity changed"})
                        return
                    self.reply(200, (folder / "source.pdf").read_bytes(), "application/pdf")
                else:
                    self.reply(404, {"detail": "unexpected endpoint"})

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@unittest.skipUnless(
    importlib.util.find_spec("wenyi_cli"), "Install wenyi-cli/core for CLI contracts"
)
class WenyiCoreContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bridge = SyntheticBridge(self.root / "sessions").start()
        self.addCleanup(self.bridge.close)
        self.environment = managed_python_env()
        self.environment["WENYI_LOCKS_BACKEND"] = "python"
        self.environment["HTTP_PROXY"] = "http://127.0.0.1:1"
        self.environment["HTTPS_PROXY"] = "http://127.0.0.1:1"
        self.environment["ALL_PROXY"] = "http://127.0.0.1:1"
        self.environment["NO_PROXY"] = ""
        self.adapter = WenyiAdapter(
            self.root / "tasks",
            self.root / "exports",
            state_root=self.root / "translations",
            cache_root=self.root / "cache",
            runtime=SimpleNamespace(prepare=self.prepare),
            timeout=30,
        )
        with redirect_stdout(io.StringIO()):
            self.config = Config(
                {
                    "engine": "wenyi",
                    "sourceLang": "en",
                    "targetLang": "zh",
                    "llm_api": {"service": "deepseek", "apiKey": "offline-placeholder"},
                    "wenyi": {
                        "pipeline": {
                            "book_understanding": False,
                            "polish": False,
                            "review": False,
                        }
                    },
                }
            )
        pdf = PdfWriter()
        for page in (0, 1):
            pdf.add_blank_page(width=300, height=400)
            pdf.add_outline_item(title=f"Chapter {page}", page_number=page)
        buffer = io.BytesIO()
        pdf.write(buffer)
        self.source_bytes = buffer.getvalue()

    def prepare(self):
        runner = Path(__file__).parents[1] / "utils" / "wenyi_runner.py"
        fixture = Path(__file__).with_name("offline_wenyi_cli.py")
        return [sys.executable, "-I", str(fixture), str(runner)], self.environment, self.bridge.url

    def submit(self, name="paper.pdf", config=None):
        task_id = str(uuid4())
        source = self.adapter.workspace(task_id) / name
        source.write_bytes(self.source_bytes)
        try:
            outputs = self.adapter.translate(source, config or self.config, task_id, lambda _: None)
        except RuntimeError as error:
            raise RuntimeError(f"{error}\n{(source.parent / 'wenyi.log').read_text()}") from error
        return source.parent, outputs

    def test_interrupted_translation_resumes_across_port_change_without_reextracting(self):
        self.environment["ZOTERO_TEST_INTERRUPT_BODY_AT"] = "2"
        with self.assertRaisesRegex(RuntimeError, "exited"):
            self.submit()
        manifests = list(self.adapter.state_root.rglob("manifest.json"))
        self.assertEqual(len(manifests), 1)
        manifest_path = manifests[0]
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(
            [chapter["status"] for chapter in manifest["chapters"]],
            ["done", "pending"],
            "\n".join(path.read_text() for path in self.adapter.task_root.glob("*/wenyi.log")),
        )
        self.assertEqual(manifest["meta"]["babeldoc_bridge_url"], LOGICAL_BRIDGE_URL)
        session = manifest["meta"]["babeldoc_session_id"]
        snapshot = self.bridge.sessions / session / "session.json"
        frozen = snapshot.read_bytes()
        chapter = manifest_path.parent / "chapters" / "ch0.json"
        retained = chapter.read_bytes()
        self.bridge.close()
        previous_port = self.bridge.server.server_port
        # Keep the old port reserved so this test proves rebinding, not lucky reuse.
        with ThreadingHTTPServer(("127.0.0.1", previous_port), BaseHTTPRequestHandler):
            self.bridge.start()
            self.assertNotEqual(self.bridge.server.server_port, previous_port)
            del self.environment["ZOTERO_TEST_INTERRUPT_BODY_AT"]
            attempt, outputs = self.submit("paper.pdf")
        self.assertEqual(snapshot.read_bytes(), frozen)
        self.assertEqual(chapter.read_bytes(), retained)
        self.assertEqual(len(outputs), 1)
        calls = [
            json.loads(line) for line in (attempt / "model-calls.jsonl").read_text().splitlines()
        ]
        self.assertEqual(sum(call["operation"] == "translation.body" for call in calls), 1)
        self.assertEqual(sum(kind == "extract" for kind, _ in self.bridge.requests), 1)
        request = [data for kind, data in self.bridge.requests if kind == "fillback"][-1]
        self.assertEqual(request["session_id"], session)
        self.assertEqual(set(request["translations"]), {"0:0", "1:0"})
        self.assertIsNone(json.loads(frozen)["pages"])
        self.assertEqual(
            json.loads(frozen)["source_sha256"], hashlib.sha256(self.source_bytes).hexdigest()
        )
        self.assertEqual(
            json.loads(manifest_path.read_text())["meta"]["babeldoc_session_id"], session
        )
        self.assertEqual(
            [chapter["status"] for chapter in json.loads(manifest_path.read_text())["chapters"]],
            ["done", "done"],
        )
        self.assertEqual(json.loads((attempt / "result.json").read_text())["status"], "success")

    def test_missing_session_fails_without_reextracting_or_success_receipt(self):
        self.submit()
        snapshot = next(self.bridge.sessions.glob("*/session.json"))
        snapshot.unlink()
        with self.assertRaisesRegex(RuntimeError, "exited"):
            self.submit()
        self.assertEqual(sum(kind == "extract" for kind, _ in self.bridge.requests), 1)
        logs = [path.read_text() for path in self.adapter.task_root.glob("*/wenyi.log")]
        self.assertTrue(any("session not found" in log and "404" in log for log in logs))
        statuses = [
            json.loads(path.read_text())["status"]
            for path in self.adapter.task_root.glob("*/result.json")
        ]
        self.assertCountEqual(statuses, ["success", "failed"])
        self.assertEqual(len(list(self.adapter.output_root.iterdir())), 1)

    def test_saved_physical_address_is_resolved_without_metadata_rewrite(self):
        self.submit()
        manifest_path = next(self.adapter.state_root.rglob("manifest.json"))
        manifest = json.loads(manifest_path.read_text())
        session = manifest["meta"]["babeldoc_session_id"]
        # Model an old saved port with a socket owned only by this test. It is
        # deliberately not listening: no request may fall back to this address.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as previous:
            previous.bind(("127.0.0.1", 0))
            stale_url = f"http://127.0.0.1:{previous.getsockname()[1]}"
            manifest["meta"]["babeldoc_bridge_url"] = stale_url
            manifest_path.write_text(json.dumps(manifest))
            self.submit("renamed.pdf")
        self.assertEqual(json.loads(manifest_path.read_text())["meta"], manifest["meta"])
        self.assertEqual(sum(kind == "extract" for kind, _ in self.bridge.requests), 1)
        fills = [data for kind, data in self.bridge.requests if kind == "fillback"]
        self.assertEqual(len(fills), 2)
        self.assertTrue(all(data["session_id"] == session for data in fills))

    def test_attempt_cleanup_keeps_checkpoints_and_target_languages_are_isolated(self):
        first, _ = self.submit()
        old_run_id = json.loads((first / "result.json").read_text())["run_id"]
        shutil.rmtree(first)
        second, _ = self.submit("new-name.pdf")
        self.assertFalse((second / "model-calls.jsonl").exists())
        self.assertNotEqual(json.loads((second / "result.json").read_text())["run_id"], old_run_id)
        target = copy(self.config)
        target.targetLang = "ja"
        self.submit(config=target)
        manifests = list(self.adapter.state_root.rglob("manifest.json"))
        self.assertEqual({path.parent.name for path in manifests}, {"zh", "ja"})
        sessions = {
            json.loads(path.read_text())["meta"]["babeldoc_session_id"] for path in manifests
        }
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sum(kind == "extract" for kind, _ in self.bridge.requests), 2)

    def test_concurrent_submissions_share_core_locks_not_model_calls(self):
        self.environment["ZOTERO_TEST_BODY_DELAY"] = "0.4"
        with ThreadPoolExecutor(max_workers=2) as pool:
            submissions = list(pool.map(lambda index: self.submit(f"name-{index}.pdf"), range(2)))
        self.assertEqual(sum(kind == "extract" for kind, _ in self.bridge.requests), 1)
        calls = [
            json.loads(line)
            for attempt, _ in submissions
            if (attempt / "model-calls.jsonl").exists()
            for line in (attempt / "model-calls.jsonl").read_text().splitlines()
        ]
        self.assertEqual(sum(call["operation"] == "translation.body" for call in calls), 2)
        self.assertEqual(len(list(self.adapter.state_root.rglob(".run.lock"))), 1)
        self.assertNotEqual(submissions[0][1], submissions[1][1])

    def test_logical_url_without_resolver_cannot_use_dns_or_proxy(self):
        from wenyi_core.pdf_bridge.client import BabeldocBridgeClient, BabeldocBridgeError

        with (
            patch.dict(os.environ, {"ALL_PROXY": self.bridge.url, "NO_PROXY": ""}),
            patch("socket.getaddrinfo", side_effect=AssertionError("Unexpected DNS")) as dns,
        ):
            with self.assertRaises(BabeldocBridgeError):
                BabeldocBridgeClient(LOGICAL_BRIDGE_URL).health()
        dns.assert_not_called()
        self.assertEqual(self.bridge.requests, [])


if __name__ == "__main__":
    unittest.main()
