"""Safe temporary compatibility hook for pdf2zh-next 2.9.0 DeepSeek Flash.

The upstream DeepSeekSettings.transform() only applies thinking controls to
deepseek-v4-* models. The official deepseek-flash alias uses the same API and
defaults to thinking enabled, so silently dropping the field can be costly.

Patch only the narrow transform boundary; never modify installed package files
or HTTP clients. Unknown engine versions fail closed.
"""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version

from utils.deepseek_thinking import DEEPSEEK_EFFORT_VALUES
from utils.deepseek_thinking import resolved_thinking_mode

logger = logging.getLogger(__name__)
SUPPORTED_PDF2ZH_NEXT = "2.9.0"


def install_deepseek_flash_patch():
    try:
        installed = version("pdf2zh-next")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "找不到 pdf2zh-next Python 环境，无法为 deepseek-flash 安全设置思考模式；"
            "翻译已在 API 调用前停止。"
        ) from exc
    if installed != SUPPORTED_PDF2ZH_NEXT:
        raise RuntimeError(
            f"deepseek-flash 思考控制补丁尚未验证 pdf2zh-next {installed}，"
            f"目前仅验证 {SUPPORTED_PDF2ZH_NEXT}；翻译已在 API 调用前停止。"
        )

    from pdf2zh_next.config.translate_engine_model import DeepSeekSettings

    original = DeepSeekSettings.transform
    if getattr(original, "_zotero_flash_patch", False):
        raise RuntimeError("deepseek-flash 补丁重复安装，已停止以避免参数错误。")

    def patched_transform(self):
        settings = original(self)
        if self.deepseek_model != "deepseek-flash":
            return settings

        mode = resolved_thinking_mode(self.deepseek_thinking_mode)
        body = getattr(settings, "_openai_extra_body", None)
        if body is not None and not isinstance(body, dict):
            raise RuntimeError("DeepSeek 内部参数格式已改变，拒绝发送未经验证的请求。")
        settings._openai_extra_body = {**(body or {}), "thinking": {"type": mode}}
        if mode == "enabled":
            effort = str(self.deepseek_reasoning_effort or "high").strip().lower()
            if effort not in DEEPSEEK_EFFORT_VALUES:
                raise ValueError(
                    "DeepSeek 思考强度仅支持: " + "/".join(DEEPSEEK_EFFORT_VALUES) + "。"
                )
            settings.openai_reasoning_effort = effort
            settings.openai_send_reasoning_effort = True
        else:
            settings.openai_send_reasoning_effort = False
        if settings.openai_model != "deepseek-flash":
            raise RuntimeError("DeepSeek 模型名意外变化，拒绝发送请求。")
        return settings

    patched_transform._zotero_flash_patch = True
    DeepSeekSettings.transform = patched_transform

    def restore():
        DeepSeekSettings.transform = original

    try:
        # Check real Pydantic fields in this interpreter with no API requests.
        for mode in ("disabled", "enabled"):
            candidate = DeepSeekSettings(
                deepseek_model="deepseek-flash",
                deepseek_api_key="test-no-network",
                deepseek_thinking_mode=mode,
                deepseek_reasoning_effort="high" if mode == "enabled" else None,
            )
            result = candidate.transform()
            if result._openai_extra_body != {"thinking": {"type": mode}}:
                raise RuntimeError("DeepSeek thinking extra_body 预检未通过。")
            if mode == "enabled" and not result.openai_send_reasoning_effort:
                raise RuntimeError("DeepSeek reasoning_effort 预检未通过。")
    except Exception:
        restore()
        raise

    logger.info("DeepSeek flash compatibility enabled (pdf2zh-next 2.9.0)")
    return restore
