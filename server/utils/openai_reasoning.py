"""Validate model-dependent OpenAI reasoning_effort='none' safely.

pdf2zh-next 2.9.0 already forwards openai_reasoning_effort through Chat
Completions when openai_send_reasoning_effort is true. No hook is needed.
Reject unverified official OpenAI models before sending the HTTP request.
"""

from __future__ import annotations

import re

# Explicit documented model families. Do not infer support for future models.
_NONE_FAMILIES = {
    "gpt-5.1", "gpt-5.2", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano",
    "gpt-5.5", "gpt-5.6", "gpt-5.6-sol", "gpt-5.6-terra",
    "gpt-5.6-luna", "gpt-6-sol", "gpt-6-luna", "gpt-6.1-terra",
}
_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def supports_none(model: object) -> bool:
    name = str(model or "").strip().lower()
    return _SNAPSHOT.sub("", name) in _NONE_FAMILIES


def _true(value: object) -> bool:
    return value is True or str(value or "").strip().lower() in {
        "true", "yes", "1", "on",
    }


def validate_openai_none(llm_api: dict, old_config: dict) -> None:
    """Only validate explicitly sent none on official OpenAI service."""
    extra = llm_api.get("extraData")
    if not isinstance(extra, dict):
        return
    effort = str(extra.get("openai_reasoning_effort") or "").strip().lower()
    if effort != "none" or not _true(extra.get("openai_send_reasoning_effort")):
        return
    detail = old_config.get("openai_detail")
    configured = detail.get("openai_model", "") if isinstance(detail, dict) else ""
    model = str(llm_api.get("model") or configured or "").strip()
    if not supports_none(model):
        raise ValueError(
            f"OpenAI 模型 {model or '(未填写)'} 未经验证支持 reasoning_effort=none。"
            "为避免 API HTTP 400，本次请求已在发送前停止。"
            "建议改用模型支持的 low/medium，或选择已验证支持 none 的模型。"
        )
