"""Offline child-process fixture. It copies a synthetic PDF; it does not translate."""

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def argument(name):
    return Path(sys.argv[sys.argv.index(name) + 1])


mode = os.environ.get("WENYI_TEST_MODE", "")
if mode == "exit":
    raise SystemExit(2)
if mode == "stall":
    time.sleep(10)
source = Path(sys.argv[sys.argv.index("translate") + 1])
output = argument("--out")
progress = argument("--progress-json")
result = argument("--result-json")
if mode == "no-result":
    raise SystemExit(0)
outputs = []
if "--mono" in sys.argv:
    shutil.copyfile(source, output)
    outputs.append(output)
if "--bilingual" in sys.argv:
    bilingual = output.with_name(f"{output.stem}-bi{output.suffix}")
    pdf = PdfWriter()
    for page in PdfReader(source).pages:
        pdf.add_blank_page(width=float(page.mediabox.width) * 2, height=page.mediabox.height)
    pdf.write(bilingual)
    outputs.append(bilingual)
if mode == "invalid-pdf":
    outputs[0].write_text("<html>not a PDF</html>")
artifacts = [
    {
        "path": str(source if mode == "wrong-path" else path),
        "size": path.stat().st_size,
        "sha256": (
            "wrong"
            if mode == "bad-hash" or (mode == "bad-dual-hash" and path == outputs[-1])
            else hashlib.sha256(path.read_bytes()).hexdigest()
        ),
    }
    for path in outputs
]
if mode == "missing-dual":
    artifacts.pop()
if mode == "duplicate-output":
    artifacts[-1] = artifacts[0]
if mode == "unexpected-output":
    artifacts[-1] = {**artifacts[-1], "path": str(source)}
run_id = "fixture-invocation"
progress.write_text(
    json.dumps(
        {
            "protocol_version": 1,
            "run_id": run_id,
            "status": "success",
            "done": 1,
            "total": 1,
            "label": "Completed",
        }
    )
)
result.write_text(
    json.dumps(
        {
            "protocol_version": 1,
            "run_id": "another-run" if mode == "wrong-run" else run_id,
            "status": "failed" if mode == "failed-receipt" else "success",
            "source_sha256": (
                "wrong"
                if mode == "wrong-source"
                else hashlib.sha256(source.read_bytes()).hexdigest()
            ),
            "outputs": artifacts,
        }
    )
)
