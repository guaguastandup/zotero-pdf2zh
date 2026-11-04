"""Narrow font-subsetting retry policy for the legacy pdf2zh 1.x engine.

Do not rerun a paid model translation for unrelated failures (API errors,
configuration, networking, missing dependencies, etc.). The original Server
retried EVERY nonzero exit and could duplicate --skip-subset-fonts.
"""

from __future__ import annotations

import re
import subprocess


_FONT_SUBSET_ERROR = re.compile(
    r"(?i)(?:"
    r"(?:error|failed|failure|cannot|can't|unable|exception|unsupported|fzerror)"
    r".{0,140}(?:subset[_ -]?fonts?|fonts?[_ -]?subset)"
    r"|(?:subset[_ -]?fonts?|fonts?[_ -]?subset)"
    r".{0,140}(?:error|failed|failure|cannot|can't|unable|exception|unsupported|fzerror)"
    r")"
)
_SUBSET_FRAME = re.compile(r"(?i)\.subset_fonts\s*\(|subset_fonts\s*\(")
_EXCEPTION_LINE = re.compile(
    r"(?im)^\s*(?:[\w.]*Error|[\w.]*Exception|RuntimeError|ValueError)\s*:"
)
_PAID_REQUEST_FAILURE = re.compile(
    r"(?i)\b(?:401|403|429)\b|invalid_api_key|rate_limit|"
    r"authenticationerror|connectionerror|timeout|readtimedout"
)


def is_font_subsetting_failure(stderr: object) -> bool:
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    blob = str(stderr or "")[-12000:]
    if not blob or _PAID_REQUEST_FAILURE.search(blob):
        return False
    if _FONT_SUBSET_ERROR.search(blob):
        return True
    # PyMuPDF may give a generic FzError after a subset_fonts() stack frame.
    return bool(
        _SUBSET_FRAME.search(blob)
        and _EXCEPTION_LINE.search(blob)
        and re.search(r"(?i)\b(?:fzerror|font|subset)\b", blob)
    )


def execute_legacy_pdf_with_font_fallback(
    command: list[str], runner, *args
) -> bool:
    """Run once, and retry exactly once only for a proven subset error.

    Returns whether a retry was performed. The retry is not silent: a failure
    after the translation stage can repeat paid API calls unless cached.
    """
    try:
        runner(command, *args)
        return False
    except subprocess.CalledProcessError as exc:
        if "--skip-subset-fonts" in command:
            print("⚠️ 已开启跳过字体子集化；翻译仍失败，不再重复尝试。")
            raise
        if not is_font_subsetting_failure(getattr(exc, "stderr", "")):
            print(
                "⚠️ pdf2zh 1.x 翻译失败，但日志没有明确指向字体子集化；"
                "为避免重复 API 调用，不会自动重新翻译。"
            )
            raise

        print(
            "⚠️ 检测到明确的字体子集化失败，尝试跳过字体子集化重跑一次。"
            "注意：这可能再次产生模型 API 费用，请检查缓存和账单。"
        )
        retry_command = [*command, "--skip-subset-fonts"]
        runner(retry_command, *args)
        return True
