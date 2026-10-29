"""Opt-in /translate -> CLI -> native translation subprocess -> PDF test.

Requires a full pdf2zh-next 2.9.0 / BabelDOC 0.6.2 environment and cached assets.
Set ZOTERO_PDF2ZH_ENGINE_PYTHON and ZOTERO_PDF2ZH_TABLE_FIXTURE (a PDF containing
detectable tables). No API credentials or external translation service are used.
"""

import base64
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ENGINE = os.environ.get("ZOTERO_PDF2ZH_ENGINE_PYTHON")
FIXTURE = os.environ.get("ZOTERO_PDF2ZH_TABLE_FIXTURE")


@unittest.skipUnless(
    ENGINE and FIXTURE, "Set engine Python and table PDF for CLI integration"
)
class TableCLIIntegrationTests(unittest.TestCase):
    def test_translate_route_uses_spawned_policy_and_writes_valid_pdf(self):
        import pymupdf
        import toml

        import server

        requests = []
        scalar_requests = []
        grouping_requests = []

        class Model(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                prompt = body["messages"][-1]["content"]
                if "## Table grouping input:\n" in prompt:
                    payload = json.loads(prompt.split("## Table grouping input:\n")[1])
                    grouping_requests.append(payload)
                    # This HTTP double confirms fixture candidates explicitly;
                    # production never treats their presence as confirmation.
                    groups = list(payload.get("merge_candidates", []))
                    fragments = payload["fragments"]
                    for first in fragments:
                        if first["text"] != "Task-level":
                            continue
                        for second in fragments:
                            if second["text"] == "SR (%)":
                                groups.append([first["id"], second["id"]])
                    policies = []
                    from utils.table_structure import join_wrapped_text

                    covered = {i for group in groups for i in group}
                    final_groups = groups + [
                        [f["id"]] for f in fragments if f["id"] not in covered
                    ]
                    by_id = {f["id"]: f for f in fragments}
                    for ids in final_groups:
                        source = join_wrapped_text([by_id[i]["text"] for i in ids])
                        if "EPIC" in source and source.endswith(("(Seen)", "(Unseen)")):
                            start = source.rfind("(")
                            policies.append(
                                {
                                    "ids": ids,
                                    "kind": "label",
                                    "parts": [
                                        {"text": source[:start], "translate": False},
                                        {"text": source[start:], "translate": True},
                                    ],
                                }
                            )
                        else:
                            # Eligibility is explicit even for ordinary cells;
                            # omitted IDs now intentionally retain source text.
                            policies.append({"ids": ids, "kind": "sentence"})
                    answer = json.dumps(
                        {
                            "is_code": False,
                            "merge_groups": groups,
                            "units": policies,
                        }
                    )
                elif "## Here is the input:" in prompt:
                    items = json.loads(prompt.rsplit("## Here is the input:", 1)[1])
                    labels = {i.get("layout_label") for i in items}
                    if "table_text" in labels:
                        assert labels == {"table_text"}, items
                    replacements = {
                        "Dataset": "数据集",
                        "Method": "方法",
                        "Meth./Set.": "方法/设置",
                        "(Seen)": "（已见）",
                        "(Unseen)": "（未见）",
                    }
                    answer = json.dumps(
                        [
                            {
                                "id": i["id"],
                                "output": replacements.get(i["input"], i["input"]),
                            }
                            for i in items
                        ],
                        ensure_ascii=False,
                    )
                    requests.append(items)
                else:
                    scalar_requests.append(prompt)
                    if "Now translate the following text:" in prompt:
                        answer = prompt.rsplit("Now translate the following text:", 1)[
                            1
                        ].strip()
                    elif "Input:\n\n" in prompt:
                        answer = prompt.rsplit("Input:\n\n", 1)[1].strip()
                    else:
                        answer = prompt
                    if answer == "Hello":
                        answer = "你好"
                response = json.dumps(
                    {
                        "id": "local-integration",
                        "object": "chat.completion",
                        "created": 0,
                        "model": "local-integration",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": answer},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 1,
                            "total_tokens": 2,
                        },
                    },
                    ensure_ascii=False,
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        model = ThreadingHTTPServer(("127.0.0.1", 0), Model)
        thread = threading.Thread(target=model.serve_forever, daemon=True)
        thread.start()
        temporary = tempfile.TemporaryDirectory()
        root = Path(
            os.environ.get("ZOTERO_PDF2ZH_TEST_ARTIFACTS", temporary.name)
        ).resolve()
        root.mkdir(parents=True, exist_ok=True)
        bootstrap = root / "bootstrap"
        bootstrap.mkdir(exist_ok=True)
        shutil.copyfile(
            Path(__file__).parent / "fixtures" / "table_cli_bootstrap.py",
            bootstrap / "sitecustomize.py",
        )
        server_dir = Path(__file__).resolve().parents[1]
        engine = Path(ENGINE).resolve()
        results = []
        try:
            for mode in ("fixed", "preserve", None):
                with self.subTest(mode=mode):
                    grouping_start = len(grouping_requests)
                    # Never accept stale PDFs or policy records from a prior
                    # invocation when artifacts are kept for inspection.
                    folder = Path(
                        tempfile.mkdtemp(prefix=f"{mode or 'legacy'}-", dir=root)
                    )
                    settings = toml.load(server_dir / "config" / "config.toml.example")
                    settings["basic"]["debug"] = False
                    settings["translation"].update(
                        min_text_length=1,
                        ignore_cache=True,
                        no_auto_extract_glossary=True,
                    )
                    settings["pdf"].update(
                        skip_scanned_detection=True,
                        disable_same_text_fallback=True,
                        translate_table_text=False,
                    )
                    config = folder / "config.toml"
                    config.write_text(toml.dumps(settings), encoding="utf-8")
                    arguments = SimpleNamespace(
                        enable_venv=False, enable_winexe=False, winexe_path=""
                    )
                    environment = {
                        "PATH": str(engine.parent)
                        + os.pathsep
                        + os.environ.get("PATH", ""),
                        "PYTHONPATH": os.pathsep.join(
                            (str(bootstrap), str(server_dir))
                        ),
                        "PYTHONIOENCODING": "utf-8",
                        "LOKY_MAX_CPU_COUNT": "4",
                        "ZOTERO_TABLE_TEST_ROOT": str(folder),
                        "NO_PROXY": "127.0.0.1,localhost",
                    }
                    payload = {
                        "engine": "pdf2zh_next",
                        "next_service": "openai",
                        "sourceLang": "en",
                        "targetLang": "zh-CN",
                        "noDual": True,
                        "noMono": False,
                        "noWatermark": True,
                        "disableGlossary": True,
                        "disableRichTextTranslate": True,
                        "qps": 10,
                        "poolSize": 1,
                        "asyncJob": True,
                        "fileName": "input.pdf",
                        "fileContent": base64.b64encode(
                            Path(FIXTURE).read_bytes()
                        ).decode(),
                        "llm_api": {
                            "service": "openai",
                            "apiKey": "local-test-only",
                            "model": "local-integration",
                            "apiUrl": f"http://127.0.0.1:{model.server_port}/v1",
                        },
                    }
                    if mode:
                        payload["tableMode"] = mode
                    start = len(requests)
                    scalar_start = len(scalar_requests)
                    with (
                        patch.dict(os.environ, environment),
                        patch.object(server, "args", arguments, create=True),
                        patch.object(server, "output_folder", str(folder)),
                        patch.dict(server.config_path, {"pdf2zh_next": str(config)}),
                    ):
                        translator = server.PDFTranslator(arguments)
                        client = translator.app.test_client()
                        accepted = client.post("/translate", json=payload)
                        self.assertEqual(accepted.status_code, 200, accepted.get_json())
                        task_id = accepted.get_json()["taskId"]
                        deadline = time.monotonic() + 180
                        result = None
                        while time.monotonic() < deadline:
                            history = client.get("/api/history").get_json()["history"]
                            result = next(
                                (h for h in history if h["taskId"] == task_id), None
                            )
                            if result is not None:
                                break
                            time.sleep(0.1)
                        self.assertIsNotNone(result, "Translation job timed out")
                        self.assertEqual(result["status"], "success", result)
                        self.assertTrue(result["filePaths"])
                        output = Path(result["filePaths"][0])
                        pdf = pymupdf.open(output)
                        self.assertGreater(len(pdf), 0)
                        text = "".join(p.get_text() for p in pdf)
                        pdf.close()
                        policies = [
                            json.loads(line)
                            for p in folder.glob("policy-*.jsonl")
                            for line in p.read_text(encoding="utf-8").splitlines()
                        ]
                        batches = [
                            json.loads(line)
                            for p in folder.glob("batches-*.jsonl")
                            for line in p.read_text(encoding="utf-8").splitlines()
                        ]
                        table_requests = [
                            items
                            for items in requests[start:]
                            if any(i.get("layout_label") == "table_text" for i in items)
                        ]
                        if mode:
                            installs = [
                                p for p in policies if p["event"] == "installed"
                            ]
                            pids = {p["pid"] for p in installs}
                            self.assertEqual(len(pids), 2, policies)
                            self.assertEqual(len(installs), 2, policies)
                            self.assertTrue(
                                all(
                                    p["hook_module"] == "utils.table_runtime"
                                    for p in installs
                                )
                            )
                            self.assertTrue(all(len(b["groups"]) == 1 for b in batches))
                            self.assertTrue(
                                all(
                                    any(
                                        p["event"] == "restored" and p["pid"] == pid
                                        for p in policies
                                    )
                                    for pid in pids
                                )
                            )
                        else:
                            self.assertEqual(policies, [])
                        if mode == "fixed":
                            self.assertTrue(table_requests)
                            self.assertIn("数据集", text)
                            self.assertTrue(grouping_requests[grouping_start:])
                            self.assertIn("已见", text)
                            original_pdf = pymupdf.open(FIXTURE)
                            output_pdf = pymupdf.open(output)

                            def spans(page):
                                return [
                                    s
                                    for b in page.get_text("dict")["blocks"]
                                    for line in b.get("lines", [])
                                    for s in line["spans"]
                                ]

                            source_names = [
                                s
                                for s in spans(original_pdf[0])
                                if s["text"] in {"EPIC", "EPIC-", "Kitchens"}
                            ]
                            self.assertTrue(source_names)
                            rendered = spans(output_pdf[0])
                            for source in source_names:
                                matches = [
                                    s
                                    for s in rendered
                                    if s["text"] == source["text"]
                                    and max(
                                        abs(a - b)
                                        for a, b in zip(s["bbox"], source["bbox"])
                                    )
                                    < 0.01
                                ]
                                self.assertTrue(matches, source)
                                self.assertEqual(matches[0]["font"], source["font"])
                                self.assertAlmostEqual(
                                    matches[0]["size"], source["size"], places=3
                                )
                            original_pdf.close()
                            output_pdf.close()
                            self.assertTrue(
                                all(
                                    "lines" in p
                                    for p in grouping_requests[grouping_start:]
                                )
                            )
                            # The real fixture has this wrapped header. Verify
                            # the grouping decision reaches native translation.
                            if any(
                                f["text"] == "Task-level"
                                for p in grouping_requests[grouping_start:]
                                for f in p["fragments"]
                            ):
                                self.assertTrue(
                                    any(
                                        i["input"] == "Task-level SR (%)"
                                        for batch in table_requests
                                        for i in batch
                                    )
                                )
                        else:
                            self.assertEqual(len(grouping_requests), grouping_start)
                        if mode == "preserve":
                            self.assertFalse(table_requests)
                            self.assertIn("Dataset", text)
                        summary = {
                            "mode": mode,
                            "output": str(output),
                            "policies": policies,
                            "batches": batches,
                            "table_requests": len(table_requests),
                            "batch_requests": len(requests) - start,
                            "scalar_requests": len(scalar_requests) - scalar_start,
                            "grouping_requests": grouping_requests[grouping_start:],
                        }
                        results.append(summary)
                        (folder / "result.json").write_text(
                            json.dumps(summary, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
            (root / "report.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        finally:
            model.shutdown()
            model.server_close()
            thread.join(timeout=5)
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
