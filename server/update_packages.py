#!/usr/bin/env python3
"""Safely update Zotero PDF2zh translation environments.

Normal users should run only:

    python update_packages.py

The update is transactional: packages are installed and validated in a staging
environment first. The currently working environment is never edited in place.
The normal-user path auto-detects an existing uv/conda environment.
For a fresh install uv is preferred; manager failures never trigger a silent switch.
"""

from __future__ import annotations

import argparse

from utils.environment_lifecycle import transactional_install_or_update


def main() -> int:
    parser = argparse.ArgumentParser(
        description="在独立 staging 环境中安全更新 Zotero PDF2zh 翻译依赖。"
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
            "默认使用 uv，与 Server 默认行为一致；只有显式传入 conda 或 auto "
            "时才会使用 conda / 跨工具探测。"
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
        print(f"🔄 安全更新翻译环境: {engine}")
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
        print("\n✅ 所请求的翻译环境均已安全更新。")
        return 0

    print(
        "\n⚠️ 至少一个环境没有完成更新。"
        "已有正式环境未被原地修改；如果此前可以使用，可以继续使用旧环境。"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
