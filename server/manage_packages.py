#!/usr/bin/env python3
"""Inspect and maintain Zotero PDF2zh translation environments.

`status` and `network` are read-only. `update` installs packages in the current
uv/conda environment, same as update_packages.py.

The normal/default mode is auto: keep an existing uv/conda environment;
for a fresh install prefer uv. A failed install never silently switches managers.
"""

from __future__ import annotations

import argparse

from utils.environment_lifecycle import find_existing_environment
from utils.environment_lifecycle import format_versions
from utils.environment_lifecycle import read_versions
from utils.environment_lifecycle import transactional_install_or_update
from utils.package_network import print_probe_report
from utils.package_network import probe_indexes
from utils.package_network import usable_indexes

PRIMARY_PACKAGES = {
    "pdf2zh": "pdf2zh",
    "pdf2zh_next": "pdf2zh-next",
}


def _engines(value: str) -> list[str]:
    return ["pdf2zh_next", "pdf2zh"] if value == "all" else [value]


def status(engine: str, env_tool: str) -> bool:
    existing = find_existing_environment(engine, env_tool)
    if not existing:
        print(f"\n[{engine}] 未找到现有翻译环境 (env_tool={env_tool})。")
        return False
    tool, env_dir, python_path = existing
    try:
        versions = read_versions(python_path, engine)
    except Exception as exc:
        print(f"\n[{engine}] 无法读取版本: {exc}")
        return False
    print(f"\n[{engine}] env_tool={tool}")
    print(f"环境: {env_dir}")
    print(f"Python: {python_path}")
    for name, version in versions.items():
        print(f"  {name:14s} {version or 'NOT INSTALLED'}")
    return True


def network(engine: str, index_url: str | None, timeout: float) -> bool:
    results = probe_indexes(
        PRIMARY_PACKAGES[engine],
        preferred_index=index_url,
        timeout=timeout,
    )
    print(f"\n[{engine}] target={PRIMARY_PACKAGES[engine]}")
    print_probe_report(results)
    return bool(usable_indexes(results))


def update(
    engine: str,
    env_tool: str,
    index_url: str | None,
    timeout: float,
    assume_yes: bool,
) -> bool:
    existing = find_existing_environment(engine, env_tool)
    if existing:
        try:
            before = read_versions(existing[2], engine)
            print(f"\n[{engine}] 当前: {format_versions(before)}")
        except Exception:
            pass
    else:
        print(
            f"\n[{engine}] 未找到 {env_tool} 环境，将按首次安装流程创建。"
        )

    if not assume_yes:
        print(
            "更新会在当前翻译环境中直接安装依赖，不再创建 staging 或 backup 环境。\n"
        )
        try:
            answer = input("确认开始安全更新？(y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in {"y", "yes"}:
            print("已取消更新。")
            return True

    success, _, _ = transactional_install_or_update(
        engine,
        env_tool=env_tool,
        preferred_index=index_url,
        network_timeout=timeout,
        require_deepseek_thinking=(engine == "pdf2zh_next"),
    )
    return success


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查网络、查看版本或安全更新 Zotero PDF2zh 翻译环境。"
    )
    parser.add_argument("action", choices=["network", "status", "update"])
    parser.add_argument(
        "--engine",
        choices=["pdf2zh_next", "pdf2zh", "all"],
        default="pdf2zh_next",
    )
    parser.add_argument(
        "--env-tool",
        choices=["auto", "uv", "conda"],
        default="auto",
        help=(
            "默认 auto：沿用已有 uv/conda 环境；没有已有环境时优先 uv。"
            "显式指定 uv 或 conda 时严格使用所选工具，安装失败不会静默切换。"
        ),
    )
    parser.add_argument("--index-url", default=None)
    parser.add_argument("--network-timeout", type=float, default=4.0)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="跳过 manage_packages.py 自己的确认。",
    )
    args = parser.parse_args()

    ok = True
    for engine in _engines(args.engine):
        if args.action == "status":
            result = status(engine, args.env_tool)
        elif args.action == "network":
            result = network(engine, args.index_url, args.network_timeout)
        else:
            result = update(
                engine,
                args.env_tool,
                args.index_url,
                args.network_timeout,
                args.yes,
            )
        ok = ok and result

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
