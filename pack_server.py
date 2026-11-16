#!/usr/bin/env python3
"""Build server.zip from git-tracked sources only.

Why a whitelist: the old `zip -r server server -x ...` approach excludes
runtime junk by pattern, so every exclusion miss ships to users and local
packing requires deleting venvs/translated/config instances first. This
script packs exactly what git tracks, so the working tree can stay dirty.

Usage:
    python3 pack_server.py [--output server.zip] [--include-tests] [--strict]

Checks performed:
- plugin/package.json and server/server.py versions must match (--strict makes a mismatch fatal)
- tracked-but-missing files are reported with a fix hint instead of a raw traceback
- tracked build artifacts (versioned README pdf, zip, xpi...) are flagged
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

# 应走 Release 资产的构建产物; 打进 server.zip 只会白白增大用户下载体积。
# README PDF 不在此列: 作者决定说明书 PDF 随包发布(发版时 git add 对应版本)。
ARTIFACT_NAME_RE = re.compile(r"\.(zip|xpi|dmg|exe)$", re.IGNORECASE)

# 打包后单独提示的大文件阈值 (500 KB)
LARGE_FILE_BYTES = 500 * 1024


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


def report_untracked_server_files() -> list[str]:
    """server/ 下未跟踪的新文件: 白名单打包会静默忽略它们。

    典型事故: 发版时把新 README PDF 放进 server/ 却没 git add,
    打出的 zip 里没有它, 且没有任何提示。
    """
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "server"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


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

    # git 索引里有、工作区却没有的文件: 直接 zf.write 会抛裸
    # FileNotFoundError。提前拦下并给出人话修复建议。
    missing = [f for f in files if not (REPO / f).is_file()]
    if missing:
        print(f"❌ {len(missing)} 个文件在 git 索引里但工作区不存在, 无法打包:")
        for item in missing[:10]:
            print(f"    {item}")
        print("    恢复文件: git checkout -- <路径>")
        print("    确认删除: git rm <路径> 后提交")
        return 1

    artifacts = [f for f in files if ARTIFACT_NAME_RE.search(Path(f).name)]
    if artifacts:
        print("⚠️ 以下构建产物会被打进包(建议 git rm, 走 Release 资产):")
        for item in artifacts:
            print(f"    {item}")

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(REPO / rel, rel)

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"✅ {output.name} 打包完成: {len(files)} 个文件, {size_mb:.2f} MB")

    large = sorted(
        (f for f in files if (REPO / f).stat().st_size > LARGE_FILE_BYTES),
        key=lambda f: (REPO / f).stat().st_size,
        reverse=True,
    )
    if large:
        print(f"ℹ️ 包内 >500KB 的文件:")
        for item in large:
            print(
                f"    {(REPO / item).stat().st_size / 1024 / 1024:5.2f} MB  {item}"
            )

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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="版本不一致时直接失败(CI/发版用); 默认仅警告",
    )
    args = parser.parse_args()

    problem = check_versions()
    if problem:
        if args.strict:
            print(f"❌ {problem} (--strict)")
            return 1
        print(f"⚠️ {problem}")

    dirty = report_dirty_files()
    if dirty:
        print(f"⚠️ server/ 有 {len(dirty)} 个未提交变更（zip 只含 git 跟踪内容）:")
        for item in dirty[:5]:
            print(f"    {item}")
        if len(dirty) > 5:
            print(f"    ... 共 {len(dirty)} 项")

    untracked = report_untracked_server_files()
    if untracked:
        print("⚠️ server/ 有未跟踪的新文件(白名单打包【不会】包含它们):")
        for item in untracked:
            print(f"    {item}")
        print("    想随包发布请先 git add; 不随包请移走, 避免误会")

    stale = report_stale_readme_versions()
    if stale:
        print("⚠️ README 版本残留检查:")
        print("\n".join(stale))

    return build(REPO / args.output, args.include_tests)


if __name__ == "__main__":
    sys.exit(main())
