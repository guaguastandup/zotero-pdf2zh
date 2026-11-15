"""Run the real plugin launcher/CLI, replacing only paid model requests."""

import json
import os
import re
import runpy
import signal
import sys
import time
from pathlib import Path
from unittest.mock import patch

import tiktoken
from wenyi_core.llm.providers.fake import FakeClient


def respond(messages, _tier, _json_mode):
    count = len(re.findall(r"^\[\d+\]", messages[-1]["content"], re.MULTILINE))
    return json.dumps(
        {
            "translations": [f"Offline translation {index}" for index in range(count)],
            "titles": [f"Offline title {index}" for index in range(count)],
            "polished": [f"Offline polish {index}" for index in range(count)],
            "terms": [],
        }
    )


class OfflineClient(FakeClient):
    def complete(self, messages, *, operation, **kwargs):
        with Path("model-calls.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"operation": operation}) + "\n")
        if operation == "translation.body":
            count = sum(call["operation"] == operation for call in self.calls) + 1
            if str(count) == os.environ.get("ZOTERO_TEST_INTERRUPT_BODY_AT"):
                signal.raise_signal(signal.SIGINT)
            time.sleep(float(os.environ.get("ZOTERO_TEST_BODY_DELAY", "0")))
        return super().complete(messages, operation=operation, **kwargs)


runner = sys.argv.pop(1)
sys.argv[0] = runner
# Use a tiny deterministic tokenizer too: the first real vocabulary download is
# unrelated to bridge routing and would make these regressions depend on network.
encoding = tiktoken.Encoding(
    name="offline-test",
    pat_str=r"(?s).",
    mergeable_ranks={bytes([index]): index for index in range(256)},
    special_tokens={},
)
with (
    patch(
        "wenyi_core.pipeline.run.runtime.build_client",
        lambda config: OfflineClient(handler=respond, config=config.llm),
    ),
    patch("wenyi_core.ingest.tokens._encoding", return_value=encoding),
):
    runpy.run_path(runner, run_name="__main__")
