#!/usr/bin/env python3
"""Build server.zip from git-tracked sources only.

Why a whitelist: the old `zip -r server server -x ...` approach excludes
runtime junk by pattern, so every exclusion miss ships to users and local
packing requires deleting venvs/translated/config instances first. This
script packs exactly what git tracks, so the working tree can stay dirty.

Usage:
    python3 pack_server.py [--output server.zip] [--include-tests]

Checks performed:
- plugin/package.json and server/server.py versions must match
- uncommitted changes in server/ are reported (zip uses the tracked tree)
- README stale-version labels are reported
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
SERVER_DIR = REPO / "server"

# Never ship to end users even if tracked.
DEFAULT_EXCLUDES = ("server/tests",)


def git_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "server"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def read_version(source: str) -> str | None:
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE
    )
    return match.group(1) if match else None


def check_versions() -> str | None:
    plugin = json.loads((REPO / "plugin" / "package.json").read_text("utf-8"))
    plugin_version = str(plugin.get("version", ""))
    server_version = read_version(
        (SERVER_DIR / "server.py").read_text("utf-8")
    )
    if plugin_version and server_version and plugin_version != server_version:
        return (
            f"版本不一致: plugin={plugin_version} server={server_version}。"
            "发版前请先统一版本号。"
        )
    return None


def report_dirty_files() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "server"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        line[3:].strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def report_stale_readme_versions() -> list[str]:
    """README 里硬编码的 vX.Y.Z 链接文字, 发版后容易忘记更新。"""
    text = (REPO / "README.md").read_text("utf-8")
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in re.finditer(
            r"\[(v\d+\.\d+\.\d+)\]\(([^)]*releases/latest[^)]*)\)", line
        ):
            hits.append(
                f"  README.md:{number} 链接文字仍是 {match.group(1)} "
                "（链接本身是 latest，改文字即可）"
            )
        if re.search(r"最新版本\s*v\d+\.\d+", line):
            hits.append(
                f"  README.md:{number} '最新版本' 后面跟着具体版本号, "
                "发版后容易过时"
            )
        if "raw/v" in line and "/server.zip" in line:
            hits.append(f"  README.md:{number} Gitee 备用链接指向固定版本 tag")
    return hits


def build(output: Path, include_tests: bool) -> int:
    excludes = () if include_tests else DEFAULT_EXCLUDES
    files = [
        f
        for f in git_tracked_files()
        if not any(f == ex or f.startswith(ex + "/") for ex in excludes)
    ]
    if not files:
        print("❌ git 索引里没有 server/ 文件（不在 git 仓库里？）")
        return 1

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(REPO / rel, rel)

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"✅ {output.name} 打包完成: {len(files)} 个文件, {size_mb:.2f} MB")
    for required in (
        "server/server.py",
        "server/requirements.txt",
        "server/update_packages.py",
        "server/config/venv.json.example",
    ):
        if required not in files:
            print(f"❌ 缺少关键文件: {required}")
            return 1
    print("✅ 关键文件齐全 (server.py / requirements / update_packages / example)")
    if not include_tests:
        print("ℹ️ server/tests 已排除 (--include-tests 可包含)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="server.zip", help="输出路径")
    parser.add_argument(
        "--include-tests", action="store_true", help="把 server/tests 打进包"
    )
    args = parser.parse_args()

    problem = check_versions()
    if problem:
        print(f"⚠️ {problem}")

    dirty = report_dirty_files()
    if dirty:
        print(f"⚠️ server/ 有 {len(dirty)} 个未提交变更（zip 只含 git 跟踪内容）:")
        for item in dirty[:5]:
            print(f"    {item}")
        if len(dirty) > 5:
            print(f"    ... 共 {len(dirty)} 项")

    stale = report_stale_readme_versions()
    if stale:
        print("⚠️ README 版本残留检查:")
        print("\n".join(stale))

    return build(REPO / args.output, args.include_tests)


if __name__ == "__main__":
    sys.exit(main())
