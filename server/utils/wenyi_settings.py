"""Validate native Wenyi options and the plugin's DeepSeek credential."""

from typing import Any

WENYI_MODEL = "deepseek-flash"

_FIELDS = {
    "pipeline": {"book_understanding", "translation_mode", "polish", "review"},
    "model": {"thinking", "reasoning_effort"},
}


def wenyi_api_key(value: Any) -> str:
    """Accept only a DeepSeek key; never inherit the Server's credentials."""
    if not isinstance(value, dict) or value.get("service") != "deepseek":
        raise ValueError("Configure and activate a DeepSeek API key in the plugin")
    key = value.get("apiKey")
    if (
        not isinstance(key, str)
        or not key.strip()
        or len(key) > 4096
        or any(character in key for character in ("\x00", "\r", "\n"))
    ):
        raise ValueError("Configure and activate a valid DeepSeek API key in the plugin")
    return key.strip()


def normalize_wenyi_options(value: Any) -> dict[str, dict[str, Any]]:
    """Reject unknown keys instead of silently accepting PDF2zh options or credentials."""
    if not isinstance(value, dict) or value.keys() - _FIELDS.keys():
        raise ValueError("Unsupported Wenyi settings; expected pipeline or model")
    result = {}
    for section, allowed in _FIELDS.items():
        fields = value.get(section, {})
        if not isinstance(fields, dict) or fields.keys() - allowed:
            raise ValueError(f"Unsupported Wenyi {section} settings")
        for key, item in fields.items():
            if key == "reasoning_effort":
                if not isinstance(item, str) or item not in {"high", "max"}:
                    raise ValueError("Wenyi reasoning_effort must be high or max")
            elif key == "translation_mode":
                if not isinstance(item, str) or item not in {"standard", "best_of_three"}:
                    raise ValueError("Wenyi translation_mode must be standard or best_of_three")
            elif not isinstance(item, bool):
                raise ValueError(f"Wenyi {key} must be a boolean")
        if fields:
            result[section] = dict(fields)
    pipeline = result.get("pipeline", {})
    if pipeline.get("translation_mode") == "best_of_three" and pipeline.get("polish") is False:
        raise ValueError("Wenyi best_of_three requires polish to be enabled")
    return result


def llm_config(options: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Override only the fixed DeepSeek preset; never accept client connection details."""
    result: dict[str, Any] = {"preset": "deepseek"}
    if options.get("model"):
        result["models"] = {
            f"default_{tier}": {
                "provider": "default",
                "model": WENYI_MODEL,
                "options": dict(options["model"]),
            }
            for tier in ("strong", "cheap", "fast")
        }
    return result
