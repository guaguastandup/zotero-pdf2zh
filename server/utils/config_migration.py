from __future__ import annotations

import copy
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import toml


def _package_name(requirement: str) -> str:
    raw = str(requirement).strip()
    name = re.split(r"[<>=!~\[\s@]", raw, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def _merge_managed_requirements(default_items: list, current_items: list) -> list:
    """Use release constraints for managed packages and preserve user extras."""
    defaults = [str(item) for item in default_items]
    current = [str(item) for item in current_items]
    managed_names = {_package_name(item) for item in defaults}
    extras = [item for item in current if _package_name(item) not in managed_names]
    return defaults + extras


def _merge_defaults(default: Any, current: Any) -> Any:
    """Fill missing defaults while preserving user/application state."""
    if isinstance(default, dict) and isinstance(current, dict):
        merged = copy.deepcopy(current)
        for key, default_value in default.items():
            if key not in merged:
                merged[key] = copy.deepcopy(default_value)
                continue
            current_value = merged[key]
            if (
                key == "translators"
                and isinstance(default_value, list)
                and isinstance(current_value, list)
            ):
                merged[key] = _merge_translators(default_value, current_value)
            elif (
                key == "packages"
                and isinstance(default_value, list)
                and isinstance(current_value, list)
            ):
                merged[key] = _merge_managed_requirements(
                    default_value, current_value
                )
            else:
                merged[key] = _merge_defaults(default_value, current_value)
        return merged
    return copy.deepcopy(current)


def _merge_translators(default_items: list, current_items: list) -> list:
    merged = copy.deepcopy(current_items)
    positions: dict[str, int] = {}
    for index, item in enumerate(merged):
        if isinstance(item, dict) and item.get("name"):
            positions[str(item["name"])] = index

    for default_item in default_items:
        if not isinstance(default_item, dict) or not default_item.get("name"):
            if default_item not in merged:
                merged.append(copy.deepcopy(default_item))
            continue
        name = str(default_item["name"])
        if name not in positions:
            positions[name] = len(merged)
            merged.append(copy.deepcopy(default_item))
            continue
        index = positions[name]
        if isinstance(merged[index], dict):
            merged[index] = _merge_defaults(default_item, merged[index])
    return merged


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def _backup_invalid(path: Path) -> Path:
    candidate = path.with_name(path.name + ".invalid.bak")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(path.name + f".invalid.{counter}.bak")
        counter += 1
    shutil.copy2(path, candidate)
    return candidate


def _migrate_json(active: Path, example: Path) -> None:
    with example.open("r", encoding="utf-8") as handle:
        defaults = json.load(handle)

    if not active.exists():
        _atomic_write_text(
            active,
            json.dumps(defaults, ensure_ascii=False, indent=4) + "\n",
        )
        print(f"🔍 [配置文件] 创建 {active.name}")
        return

    try:
        with active.open("r", encoding="utf-8") as handle:
            current = json.load(handle)
    except Exception as exc:
        backup = _backup_invalid(active)
        _atomic_write_text(
            active,
            json.dumps(defaults, ensure_ascii=False, indent=4) + "\n",
        )
        print(
            f"⚠️ [配置文件] {active.name} 无法解析 ({exc})；"
            f"已备份到 {backup.name} 并恢复默认配置。"
        )
        return

    merged = _merge_defaults(defaults, current)
    if merged != current:
        _atomic_write_text(
            active,
            json.dumps(merged, ensure_ascii=False, indent=4) + "\n",
        )
        print(f"✅ [配置迁移] {active.name}: 已迁移托管默认并保留用户配置。")
    else:
        print(f"✅ [配置迁移] {active.name}: 无需修改。")


def _migrate_toml(active: Path, example: Path) -> None:
    defaults = toml.load(example)

    if not active.exists():
        _atomic_write_text(active, toml.dumps(defaults))
        print(f"🔍 [配置文件] 创建 {active.name}")
        return

    try:
        current = toml.load(active)
    except Exception as exc:
        backup = _backup_invalid(active)
        _atomic_write_text(active, toml.dumps(defaults))
        print(
            f"⚠️ [配置文件] {active.name} 无法解析 ({exc})；"
            f"已备份到 {backup.name} 并恢复默认配置。"
        )
        return

    merged = _merge_defaults(defaults, current)
    if merged != current:
        _atomic_write_text(active, toml.dumps(merged))
        print(f"✅ [配置迁移] {active.name}: 已补充新默认字段，保留现有用户值。")
    else:
        print(f"✅ [配置迁移] {active.name}: 无需修改。")


def migrate_config_file(active_path: str | os.PathLike[str]) -> None:
    active = Path(active_path)
    example = active.with_name(active.name + ".example")
    if not example.exists():
        if not active.exists():
            raise FileNotFoundError(f"缺少配置文件及模板: {active}")
        return

    if active.suffix.lower() == ".toml":
        _migrate_toml(active, example)
    elif active.suffix.lower() == ".json":
        _migrate_json(active, example)
    elif not active.exists():
        shutil.copy2(example, active)


def prepare_config_files(config_paths: dict[str, str]) -> None:
    print("🔍 [配置文件] 检查并迁移配置...")
    for path in config_paths.values():
        migrate_config_file(path)
    print("✅ [配置文件] 配置检查完成\n")
