"""Test-only cache isolation and observation for a real installed engine CLI.

Copied to an isolated directory as sitecustomize.py by the opt-in integration
test. Does not install a table policy: only records installations performed by
the real runner/worker. The native layout, translation and PDF pipeline runs.
"""

# This bootstrap must isolate caches before importing the translation modules.
# ruff: noqa: E402

import json
import os
from pathlib import Path
from unittest.mock import patch

root = Path(os.environ["ZOTERO_TABLE_TEST_ROOT"])
root.mkdir(parents=True, exist_ok=True)

import babeldoc.const as constants

assets_cache = constants.CACHE_FOLDER
constants.CACHE_FOLDER = root / "babeldoc-cache"
constants.CACHE_FOLDER.mkdir(exist_ok=True)
from babeldoc.translator import cache  # noqa: F401

constants.CACHE_FOLDER = assets_cache
native_expanduser = Path.expanduser


def expanduser(path):
    if str(path).replace("\\", "/") == "~/.config/pdf2zh":
        return root / "config"
    return native_expanduser(path)


with (
    patch.object(Path, "expanduser", expanduser),
    patch.object(Path, "home", return_value=root),
):
    import pdf2zh_next  # noqa: F401

import babeldoc.assets.assets

# Avoid pre-downloading unrelated OCR assets. The real layout model and fonts
# used by this PDF are still loaded from the installed engine's existing cache.
babeldoc.assets.assets.warmup = lambda: None

from utils import table_process
from utils.table_batching import paragraph_group

native_install = table_process.install_table_policy


def record(name, data):
    with (root / f"{name}-{os.getpid()}.jsonl").open("a", encoding="utf-8") as output:
        output.write(json.dumps(data, ensure_ascii=False) + "\n")


def observed_install(mode):
    restore = native_install(mode)
    from babeldoc.format.pdf.document_il.midend.il_translator_llm_only import (
        ILTranslatorLLMOnly,
    )
    from babeldoc.format.pdf.document_il.midend.paragraph_finder import ParagraphFinder

    native_batch = ILTranslatorLLMOnly.translate_paragraph
    record(
        "policy",
        {
            "event": "installed",
            "mode": mode,
            "pid": os.getpid(),
            "parent_pid": os.getppid(),
            "hook_module": ParagraphFinder.process_page.__module__,
        },
    )

    def batch(translator, paragraphs, *args, **kwargs):
        groups = sorted(
            {
                (page.page_number, *paragraph_group(para))
                for page, para in zip(paragraphs.pages, paragraphs.paragraphs)
            },
            key=str,
        )
        record(
            "batches",
            {
                "groups": groups,
                "pid": os.getpid(),
                "text": [p.unicode for p in paragraphs.paragraphs],
            },
        )
        return native_batch(translator, paragraphs, *args, **kwargs)

    ILTranslatorLLMOnly.translate_paragraph = batch

    def observed_restore():
        ILTranslatorLLMOnly.translate_paragraph = native_batch
        restore()
        record("policy", {"event": "restored", "pid": os.getpid()})

    return observed_restore


table_process.install_table_policy = observed_install
