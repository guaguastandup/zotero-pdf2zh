"""用户可见错误分类：把引擎/上游的技术报错翻译成用户能看懂的提示。

规则移植自 zotero-omni-translate 的 error_catalog，并针对本项目的
BabelDOC / pdf2zh_next 报错补充规则（如扫描件、CID 字符）。
原始错误始终保留在日志与 message 字段中，这里只做附加解读。
"""

from __future__ import annotations

import re
from typing import Callable, Optional

MatchFn = Callable[[str, str], bool]


def _any(lower: str, *parts: str) -> bool:
    return any(part in lower for part in parts)


def _rule(code: str, user: str, hint: str, match: MatchFn) -> dict:
    return {"code": code, "user": user, "hint": hint, "match": match}


# 起步原则: 只收录经用户真实报错验证过的案例, 宁缺勿滥——
# 错误的解读比没有解读更糟。新规则需先拿到真实错误文本再添加。
ERROR_RULES: list[dict] = [
    _rule(
        "PDF_UNREADABLE_TEXT",
        "这份 PDF 读不出可翻译的文字（扫描件没有文字层，或内嵌字体编码异常）。",
        "请换一份带文字层的 PDF（出版社原版通常可以），"
        "或先用 OCR 工具转成文字版再翻译。",
        lambda t, l: _any(
            l,
            "too many cid chars",
            "contains no graphs",
            "no extractable text",
            "scanned pdf",
            "no text layer",
            "without text layer",
            "没有可提取的文本",
        ),
    ),
]


def classify_error_message(message: Optional[str]) -> dict:
    text = str(message or "").strip()
    lower = text.lower()
    info = {
        "errorCode": "UNKNOWN_ERROR",
        "userMessage": "",
        "hint": "",
    }
    if not text:
        return info
    for rule in ERROR_RULES:
        try:
            matched = rule["match"](text, lower)
        except Exception:
            matched = False
        if matched:
            info["errorCode"] = rule["code"]
            info["userMessage"] = rule["user"]
            info["hint"] = rule["hint"]
            return info
    return info


def classify_error_blob(blob: Optional[str]) -> dict:
    """从多行引擎日志中提取最相关的一条用户提示。

    优先对含错误关键词的行逐行匹配，再退回对整段文本匹配。
    """
    if not blob:
        return classify_error_message(None)
    interesting = []
    for raw in str(blob).splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("File ", "Traceback", "return ", "raise ")):
            continue
        if "site-packages" in line and ".py" in line:
            continue
        interesting.append(line)
    # 真正的报错通常在日志末尾，从最后一行往前匹配。
    for line in reversed(interesting):
        lowered = line.lower()
        for rule in ERROR_RULES:
            try:
                matched = rule["match"](line, lowered)
            except Exception:
                matched = False
            if matched:
                return {
                    "errorCode": rule["code"],
                    "userMessage": rule["user"],
                    "hint": rule["hint"],
                }
    # 兜底：整段拼接再匹配一次（覆盖跨行错误文本）。
    return classify_error_message(" | ".join(interesting[-30:]))
