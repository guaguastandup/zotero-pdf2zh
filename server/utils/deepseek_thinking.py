from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import toml

THINKING_MODE_FIELD = "deepseek_thinking_mode"
REASONING_EFFORT_FIELD = "deepseek_reasoning_effort"
THINKING_MODE_FLAG = "--deepseek-thinking-mode"
REASONING_EFFORT_FLAG = "--deepseek-reasoning-effort"

_RUNTIME_CAPABILITY_CACHE: dict[tuple[str, ...], bool] = {}


def is_deepseek_v4_model(model: Any) -> bool:
    return str(model or "").strip().startswith("deepseek-v4-")


def normalize_deepseek_extra_data(llm_api: dict, old_config: dict) -> str:
    """Normalize request-scoped DeepSeek controls and return the effective model.

    The plugin uses extraData as its generic transport. For V4 we always make
    thinking explicit so an older saved configuration cannot accidentally fall
    back to the provider's thinking default. For non-V4 models the V4-only
    fields are removed before writing the pdf2zh_next configuration.
    """
    extra_data = llm_api.get("extraData")
    if not isinstance(extra_data, dict):
        extra_data = {}
    else:
        extra_data = dict(extra_data)

    configured_model = (
        old_config.get("deepseek_detail", {}).get("deepseek_model", "")
        if isinstance(old_config.get("deepseek_detail", {}), dict)
        else ""
    )
    effective_model = str(llm_api.get("model") or configured_model or "").strip()

    if not is_deepseek_v4_model(effective_model):
        extra_data.pop(THINKING_MODE_FIELD, None)
        extra_data.pop(REASONING_EFFORT_FIELD, None)
        llm_api["extraData"] = extra_data
        return effective_model

    mode = str(extra_data.get(THINKING_MODE_FIELD) or "disabled").strip().lower()
    if mode not in {"enabled", "disabled"}:
        raise ValueError("DeepSeek V4 思考模式只能是 enabled 或 disabled。")
    extra_data[THINKING_MODE_FIELD] = mode

    if mode == "enabled":
        effort = str(extra_data.get(REASONING_EFFORT_FIELD) or "high").strip().lower()
        if effort not in {"high", "max"}:
            raise ValueError("DeepSeek V4 reasoning effort 只能是 high 或 max。")
        extra_data[REASONING_EFFORT_FIELD] = effort
    else:
        extra_data.pop(REASONING_EFFORT_FIELD, None)

    llm_api["extraData"] = extra_data
    return effective_model


def remove_stale_thinking_fields(translator: dict, effective_model: str) -> None:
    if is_deepseek_v4_model(effective_model):
        return
    translator.pop(THINKING_MODE_FIELD, None)
    translator.pop(REASONING_EFFORT_FIELD, None)


def strip_thinking_fields_from_config(config_path: str) -> None:
    """Best-effort rollback for runtimes that do not understand V4 fields."""
    try:
        config_data = toml.load(config_path)
        detail = config_data.get("deepseek_detail")
        if not isinstance(detail, dict):
            return
        changed = False
        for key in (THINKING_MODE_FIELD, REASONING_EFFORT_FIELD):
            if key in detail:
                detail.pop(key, None)
                changed = True
        if changed:
            with open(config_path, "w", encoding="utf-8") as handle:
                toml.dump(config_data, handle)
            print(
                "🧹 [DeepSeek V4] 当前运行时不支持思考控制；"
                "已从 config.toml 移除仅新版本支持的字段。"
            )
    except Exception as exc:
        print(f"⚠️ [DeepSeek V4] 清理不兼容配置字段失败: {exc}")


def _option_value(cmd: list[str], flag: str) -> str | None:
    for index, value in enumerate(cmd):
        if value == flag and index + 1 < len(cmd):
            return str(cmd[index + 1])
        prefix = flag + "="
        if value.startswith(prefix):
            return value[len(prefix):]
    return None


def _remove_option(cmd: list[str], flag: str) -> list[str]:
    result: list[str] = []
    index = 0
    prefix = flag + "="
    while index < len(cmd):
        value = cmd[index]
        if value == flag:
            index += 2 if index + 1 < len(cmd) else 1
            continue
        if value.startswith(prefix):
            index += 1
            continue
        result.append(value)
        index += 1
    return result


def _invocation_prefix(final_cmd: list[str]) -> list[str]:
    """Return the exact executable prefix used for this pdf2zh_next process."""
    for index, value in enumerate(final_cmd):
        if value == "-m" and index + 1 < len(final_cmd) and final_cmd[index + 1] == "pdf2zh_next":
            return final_cmd[: index + 2]
    return final_cmd[:1]


def _runtime_supports_thinking(
    invocation_prefix: list[str],
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> bool:
    cache_key = tuple(invocation_prefix + ([f"cwd={cwd}"] if cwd else []))
    if cache_key in _RUNTIME_CAPABILITY_CACHE:
        return _RUNTIME_CAPABILITY_CACHE[cache_key]

    try:
        result = subprocess.run(
            [*invocation_prefix, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            cwd=cwd,
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        supported = (
            result.returncode == 0
            and THINKING_MODE_FLAG in output
            and REASONING_EFFORT_FLAG in output
        )
    except Exception:
        supported = False

    _RUNTIME_CAPABILITY_CACHE[cache_key] = supported
    return supported


def _unsupported_runtime_message(*, winexe: bool = False) -> str:
    if winexe:
        return (
            "当前实际使用的 Windows pdf2zh_next.exe 不支持 DeepSeek V4 思考控制。"
            "为避免 thinking 设置被忽略并产生额外费用，本次翻译已在 API 调用前停止。"
            "请更新到支持 --deepseek-thinking-mode 的新版 exe，或关闭 --enable_winexe "
            "后在 server 目录运行 `python update_packages.py`。"
        )
    return (
        "当前实际使用的 pdf2zh_next 不支持 DeepSeek V4 思考控制。"
        "为避免 thinking 设置被忽略并产生额外费用，本次翻译已在 API 调用前停止。"
        "请在 server 目录运行 `python update_packages.py`，完成后重启 Server。"
    )


def prepare_deepseek_runtime_command(
    final_cmd: list[str],
    final_env: dict[str, str] | None = None,
) -> list[str]:
    """Validate the actual runtime and map config fields to upstream CLI flags.

    pdf2zh_next generates --deepseek-thinking-mode and
    --deepseek-reasoning-effort from the same DeepSeekSettings fields that are
    accepted in config.toml. Passing them explicitly on the CLI makes the
    runtime behavior match the upstream developer-provided command examples and
    prevents an older runtime from silently ignoring config-only fields.
    """
    if "--deepseek" not in final_cmd:
        return final_cmd

    config_path = _option_value(final_cmd, "--config-file")
    if not config_path:
        return final_cmd

    try:
        config_data = toml.load(config_path)
    except Exception as exc:
        raise ValueError(f"无法读取 pdf2zh_next 配置文件: {exc}") from exc

    detail = config_data.get("deepseek_detail", {})
    if not isinstance(detail, dict):
        detail = {}

    model = _option_value(final_cmd, "--deepseek-model") or detail.get("deepseek_model", "")
    if not is_deepseek_v4_model(model):
        return final_cmd

    mode = _option_value(final_cmd, THINKING_MODE_FLAG) or detail.get(THINKING_MODE_FIELD) or "disabled"
    mode = str(mode).strip().lower()
    if mode not in {"enabled", "disabled"}:
        raise ValueError("DeepSeek V4 思考模式只能是 enabled 或 disabled。")

    effort = _option_value(final_cmd, REASONING_EFFORT_FLAG) or detail.get(REASONING_EFFORT_FIELD)
    if mode == "enabled":
        effort = str(effort or "high").strip().lower()
        if effort not in {"high", "max"}:
            raise ValueError("DeepSeek V4 reasoning effort 只能是 high 或 max。")

    invocation_prefix = _invocation_prefix(final_cmd)
    if not _runtime_supports_thinking(invocation_prefix, env=final_env):
        strip_thinking_fields_from_config(config_path)
        raise ValueError(_unsupported_runtime_message())

    updated = _remove_option(list(final_cmd), THINKING_MODE_FLAG)
    updated = _remove_option(updated, REASONING_EFFORT_FLAG)
    updated.extend([THINKING_MODE_FLAG, mode])
    if mode == "enabled":
        updated.extend([REASONING_EFFORT_FLAG, str(effort)])

    print(
        "🧠 [DeepSeek V4] 已验证当前 pdf2zh_next 支持思考控制；"
        f"thinking={mode}"
        + (f", reasoning_effort={effort}" if mode == "enabled" else "")
    )
    return updated


def _server_cli_option(name: str, default: str | None = None) -> str | None:
    flag = "--" + name
    for index, value in enumerate(sys.argv[1:], start=1):
        if value == flag and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
        prefix = flag + "="
        if value.startswith(prefix):
            return value[len(prefix):]
    return default


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def validate_winexe_runtime_if_selected(config_file: str, effective_model: str) -> None:
    """Protect the winexe path, which bypasses execute_with_progress()."""
    if not is_deepseek_v4_model(effective_model):
        return
    if not _as_bool(_server_cli_option("enable_winexe", "false")):
        return

    configured_path = _server_cli_option(
        "winexe_path",
        "./pdf2zh-v2.6.3-BabelDOC-v0.5.7-win64/pdf2zh/pdf2zh.exe",
    )
    exe_path = Path(str(configured_path))
    # Match server.py exactly: os.path.exists(args.winexe_path) is evaluated
    # relative to the Server process working directory. If it is absent,
    # server.py falls back to the normal venv/system execution path.
    actual_path = exe_path if exe_path.is_absolute() else Path.cwd() / exe_path
    if not actual_path.exists():
        return
    actual_path = actual_path.resolve()

    if not _runtime_supports_thinking(
        [str(actual_path)],
        env=os.environ.copy(),
        cwd=str(actual_path.parent),
    ):
        raise ValueError(_unsupported_runtime_message(winexe=True))
