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


# 顺序：更具体的规则靠前。
ERROR_RULES: list[dict] = [
    _rule(
        "PDF_PASSWORD_REQUIRED",
        "这份 PDF 有密码保护，暂时无法翻译。",
        "请先用 PDF 阅读器解锁并另存副本，再对副本翻译。",
        lambda t, l: _any(
            l,
            "file has not been decrypted",
            "password required",
            "document is encrypted",
            "incorrect password",
        ),
    ),
    _rule(
        "SCANNED_PDF_DETECTED",
        "检测到扫描版 PDF：页面是图片，没有可提取的文字层，无法翻译。",
        "请换一份带文字层的 PDF（出版社原版通常可以），"
        "或先用 OCR 工具把扫描件转成文字版再翻译。",
        lambda t, l: _any(
            l,
            "contains no graphs",
            "no extractable text",
            "scanned pdf",
            "no text layer",
            "without text layer",
            "没有可提取的文本",
        ),
    ),
    _rule(
        "PDF_CID_CHARS_TOO_MANY",
        "这份 PDF 的内嵌字体异常（CID 字符过多），解析失败。",
        "常见于老旧或扫描转换的 PDF。请换一份该文献的其他 PDF 版本；"
        "或先用 OCR 工具转成文字版再翻译。",
        lambda t, l: _any(l, "too many cid chars", "cid chars"),
    ),
    _rule(
        "DISK_SPACE_INSUFFICIENT",
        "磁盘空间不足，无法保存翻译文件。",
        "请释放一些磁盘空间后重试。",
        lambda t, l: _any(
            l, "no space left on device", "disk full", "winerror 112", "errno 28"
        ),
    ),
    _rule(
        "FILE_PERMISSION_DENIED",
        "无法读取文件或写入输出目录。",
        "请确认 PDF 可以打开，且 server 目录有写入权限（Windows 可尝试管理员运行）。",
        lambda t, l: _any(
            l, "permission denied", "access is denied", "winerror 5", "errno 13"
        )
        and not _any(l, "site-packages", "pip", "install"),
    ),
    _rule(
        "ENV_RUST_BUILD_REQUIRED",
        "安装 pdf2zh_next 依赖时需要 Rust 编译器。",
        "请安装 rustup 后重试，或改用 uv 管理环境。",
        lambda t, l: _any(l, "rust compiler")
        or ("tiktoken" in l and "rust" in l),
    ),
    _rule(
        "MSVC_REDIST_REQUIRED",
        "缺少 Microsoft Visual C++ 运行库。",
        "请安装 VC++ 运行库后重启: https://aka.ms/vs/17/release/vc_redist.x64.exe",
        lambda t, l: _any(
            l, "visual c++ redistributable", "dll 初始化", "dll load failed"
        ),
    ),
    _rule(
        "VENV_PATH_INVALID",
        "翻译虚拟环境路径失效（常见于移动 server 文件夹之后）。",
        "uv 用户请勿移动 server 文件夹；或删除 server 下的 *-venv 文件夹后重跑 update_packages.py 重建。",
        lambda t, l: _any(l, "failed to canonicalize script path"),
    ),
    _rule(
        "CONDA_ENV_NOT_FOUND",
        "无法定位 Conda 虚拟环境，翻译引擎未能启动。",
        "请运行 conda env list 检查，或重跑 python update_packages.py 重建环境。",
        lambda t, l: "conda" in l
        and _any(l, "无法自动定位", "环境的可执行文件未找到", "extra data: line"),
    ),
    _rule(
        "LLM_API_KEY_INVALID",
        "当前 API Key 无效或未通过服务商校验。",
        "请在插件「LLM API 配置管理」中核对 Key。",
        lambda t, l: _any(l, "api key not valid", "api_key_invalid", "incorrect api key")
        or ("api key" in l and "invalid" in l),
    ),
    _rule(
        "UPSTREAM_BALANCE_INSUFFICIENT",
        "翻译服务账户余额不足或额度已用完。",
        "请在服务商控制台充值，或更换可用的 API Key。",
        lambda t, l: _any(l, "balance is insufficient", "余额不足", "account balance"),
    ),
    _rule(
        "UPSTREAM_RATE_LIMIT",
        "上游翻译服务限流或配额用尽。",
        "请降低 QPS/并发（bing/google 建议 ≤2），稍后再试。",
        lambda t, l: _any(
            l, "rate limit", "resource_exhausted", "error 429", "status 429", "code 429"
        ),
    ),
    _rule(
        "UPSTREAM_SSL_TIMEOUT",
        "连接翻译 API 时 SSL 握手超时。",
        "请检查网络或代理设置。",
        lambda t, l: "handshake" in l and "timed out" in l,
    ),
    _rule(
        "UPSTREAM_SSL_ERROR",
        "与翻译 API 的 HTTPS 连接异常中断。",
        "请检查代理/防火墙，或更换网络环境。",
        lambda t, l: _any(l, "unexpected_eof_while_reading", "ssl error"),
    ),
    _rule(
        "UPSTREAM_CONNECTION_REFUSED",
        "无法连接翻译 API（连接被拒绝）。",
        "请核对 API 地址、代理与防火墙设置。",
        lambda t, l: _any(l, "connection refused", "积极拒绝", "10061"),
    ),
    _rule(
        "UPSTREAM_NETWORK_ERROR",
        "无法连接上游翻译服务（网络或 DNS 问题）。",
        "请检查网络、代理与 API 地址。",
        lambda t, l: _any(
            l, "apiconnectionerror", "connection error", "connecterror", "name resolution"
        ),
    ),
    _rule(
        "UPSTREAM_HTML_RESPONSE",
        "翻译 API 返回了 HTML 页面而不是 JSON。",
        "通常是 API 地址写错或被网关拦截，请核对地址与 Key。",
        lambda t, l: "</html>" in l and "translation" in l,
    ),
    _rule(
        "TRANSLATION_CANCELLED",
        "翻译进程被取消或超时终止。",
        "请缩小翻译页码范围、降低并发后重试。",
        lambda t, l: _any(
            l, "translation cancelled", "translation canceled", "did not finish in time"
        ),
    ),
    _rule(
        "ENGINE_STDIO_BROKEN",
        "翻译引擎子进程过早退出，或日志管道断开，翻译未完成。",
        "请查看终端日志：若前面有 API/模型/PDF 报错先修正；"
        "若只有 Broken pipe，重启 server 并降低并发重试。",
        lambda t, l: _any(
            l, "brokenpipeerror", "broken pipe", "errno 32"
        ),
    ),
    _rule(
        "BABELDOC_INTERNAL_ERROR",
        "BabelDOC 处理 PDF 时发生内部错误。",
        "可尝试换引擎（pdf2zh ↔ pdf2zh_next）、降低并发，或换其他 PDF。",
        lambda t, l: _any(
            l, "cannot unpack non-iterable nonetype", "babeldoc translation error"
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
