"""Offline child-process fixture. It copies a synthetic PDF; it does not translate."""

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path


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
shutil.copyfile(source, output)
if mode == "invalid-pdf":
    output.write_text("<html>not a PDF</html>")
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
            "outputs": [
                {
                    "path": str(source if mode == "wrong-path" else output),
                    "size": output.stat().st_size,
                    "sha256": (
                        "wrong"
                        if mode == "bad-hash"
                        else hashlib.sha256(output.read_bytes()).hexdigest()
                    ),
                }
            ],
        }
    )
)
