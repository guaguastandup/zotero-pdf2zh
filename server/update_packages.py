#!/usr/bin/env python3
"""Update Zotero PDF2zh translation environments.

Normal users should run only:

    python update_packages.py

Packages are installed in the current uv/conda environment. The command
auto-detects an existing manager; for a fresh install uv is preferred.
A failed install never silently switches managers.
"""

from __future__ import annotations

import argparse

from utils.environment_lifecycle import transactional_install_or_update


def main() -> int:
    parser = argparse.ArgumentParser(
        description="在当前翻译环境中直接更新 Zotero PDF2zh 依赖。"
    )
    parser.add_argument(
        "--engine",
        choices=["pdf2zh_next", "pdf2zh", "all"],
        default="pdf2zh_next",
        help="默认更新 pdf2zh_next；高级用户也可指定 pdf2zh 或 all。",
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
    parser.add_argument(
        "--index-url",
        default=None,
        help="优先测试的自定义 PyPI 镜像；失败时仍会尝试内置备用源。",
    )
    parser.add_argument(
        "--network-timeout",
        type=float,
        default=4.0,
        help="单个下载源预检超时秒数，默认 4。",
    )
    args = parser.parse_args()

    engines = ["pdf2zh_next", "pdf2zh"] if args.engine == "all" else [args.engine]
    all_ok = True
    for engine in engines:
        print("\n" + "=" * 68)
        print(f"🔄 更新翻译环境: {engine}")
        print(f"🔧 环境管理工具: {args.env_tool}")
        success, _, _ = transactional_install_or_update(
            engine,
            env_tool=args.env_tool,
            preferred_index=args.index_url,
            network_timeout=args.network_timeout,
            require_deepseek_thinking=(engine == "pdf2zh_next"),
        )
        all_ok = all_ok and success

    if all_ok:
        print("\n✅ 所请求的翻译环境均已更新。")
        return 0

    print("\n⚠️ 至少一个环境没有完成更新。可稍后重新运行本命令重试。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
