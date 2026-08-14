#!/usr/bin/env python3
"""Inspect or explicitly update Zotero PDF2zh translation environments.

Normal server startup never calls this script. Package updates are therefore an
explicit maintenance action instead of a side effect of starting server.py.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_CONFIG = ROOT / "config" / "venv.json.example"

ENGINE_ENV_NAMES = {
    "pdf2zh": "zotero-pdf2zh-venv",
    "pdf2zh_next": "zotero-pdf2zh-next-venv",
}

VERSION_PACKAGES = {
    "pdf2zh": ["pdf2zh", "BabelDOC", "PyMuPDF", "pypdf"],
    "pdf2zh_next": ["pdf2zh-next", "BabelDOC", "PyMuPDF", "pypdf"],
}


def _version_tuple(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    return tuple(int(x) for x in re.findall(r"\d+", value)[:4])


def _python_in_env(env_path: Path) -> Path:
    if platform.system() == "Windows":
        return env_path / "Scripts" / "python.exe"
    return env_path / "bin" / "python"


def _find_uv_env(engine: str) -> tuple[str, Path] | None:
    env_path = ROOT / ENGINE_ENV_NAMES[engine]
    python_path = _python_in_env(env_path)
    if python_path.exists():
        return "uv", python_path
    return None


def _find_conda_env(engine: str) -> tuple[str, Path] | None:
    if not shutil.which("conda"):
        return None
    try:
        result = subprocess.run(
            ["conda", "info", "--json"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        info = json.loads(result.stdout)
    except Exception:
        return None

    wanted = ENGINE_ENV_NAMES[engine]
    for raw_path in info.get("envs", []):
        env_path = Path(raw_path)
        if env_path.name == wanted:
            python_path = _python_in_env(env_path)
            if python_path.exists():
                return "conda", python_path
    return None


def find_environment(engine: str, env_tool: str) -> tuple[str, Path] | None:
    if env_tool == "uv":
        return _find_uv_env(engine)
    if env_tool == "conda":
        return _find_conda_env(engine)
    return _find_uv_env(engine) or _find_conda_env(engine)


def read_versions(python_path: Path, engine: str) -> dict[str, str | None]:
    package_names = VERSION_PACKAGES[engine]
    code = (
        "import json; "
        "from importlib.metadata import version, PackageNotFoundError; "
        f"names={package_names!r}; "
        "out={}; "
        "\nfor name in names:\n"
        "    try: out[name]=version(name)\n"
        "    except PackageNotFoundError: out[name]=None\n"
        "print(json.dumps(out))"
    )
    result = subprocess.run(
        [str(python_path), "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "无法读取环境版本")
    return json.loads(result.stdout)


def print_versions(engine: str, env_tool: str, python_path: Path) -> dict[str, str | None]:
    versions = read_versions(python_path, engine)
    print(f"\n[{engine}] env_tool={env_tool}")
    print(f"Python: {python_path}")
    for name in VERSION_PACKAGES[engine]:
        print(f"  {name:14s} {versions.get(name) or 'NOT INSTALLED'}")
    print_compatibility_notes(engine, versions)
    return versions


def print_compatibility_notes(engine: str, versions: dict[str, str | None]) -> None:
    if engine != "pdf2zh_next":
        return

    pdf2zh_version = versions.get("pdf2zh-next")
    babeldoc_version = versions.get("BabelDOC")

    if _version_tuple(pdf2zh_version) >= (2, 9, 0) and _version_tuple(babeldoc_version) <= (0, 6, 2):
        print(
            "  ⚠️  检测到 pdf2zh-next >= 2.9.0 + BabelDOC <= 0.6.2。\n"
            "      该组合使用 BabelDOC 0.6 系列的新 PDF parser；部分结构不规范的 PDF\n"
            "      可能出现 object/xref 解析失败。BabelDOC 0.6.3+ 还包含后续安全修复。\n"
            "      但 pdf2zh-next 2.9.0 的 Python 依赖约束可能阻止 pip/uv 自动升级到\n"
            "      新 BabelDOC。不要使用 --no-deps 强行覆盖；请优先等待/采用上游兼容发布。"
        )


def load_requirements(engine: str, env_tool: str) -> list[str]:
    with VENV_CONFIG.open("r", encoding="utf-8") as f:
        config = json.load(f)
    return list(config[engine][env_tool].get("packages", []))


def update_environment(
    engine: str,
    env_tool: str,
    python_path: Path,
    index_url: str | None,
    assume_yes: bool,
) -> bool:
    requirements = load_requirements(engine, env_tool)
    if not requirements:
        print(f"[{engine}] 没有声明需要维护的包。")
        return True

    print_versions(engine, env_tool, python_path)
    print("\n将更新到当前依赖约束允许的最新兼容版本：")
    for requirement in requirements:
        print(f"  - {requirement}")
    print("不会使用 --no-deps，也不会绕过上游依赖约束。")

    if not assume_yes:
        try:
            answer = input("确认更新这个环境？(y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in {"y", "yes"}:
            print("已取消更新。")
            return True

    if env_tool == "uv":
        uv_path = shutil.which("uv")
        if not uv_path:
            print("❌ 找不到 uv，无法更新 uv 环境。")
            return False
        cmd = [uv_path, "pip", "install", "--upgrade"]
        if index_url:
            cmd.extend(["--index-url", index_url])
        cmd.extend(requirements)
        cmd.extend(["--python", str(python_path)])
    else:
        cmd = [str(python_path), "-m", "pip", "install", "--upgrade"]
        if index_url:
            cmd.extend(["--index-url", index_url])
        cmd.extend(requirements)

    print("\n执行：", " ".join(cmd))
    env = os.environ.copy()
    env.setdefault("UV_HTTP_TIMEOUT", "1200")
    try:
        subprocess.run(cmd, cwd=ROOT, check=True, env=env, timeout=1200)
    except subprocess.CalledProcessError as exc:
        print(f"❌ 更新失败，包管理器退出码: {exc.returncode}")
        print("环境不会由本脚本使用 --no-deps 强制改成不兼容组合。")
        return False
    except subprocess.TimeoutExpired:
        print("❌ 更新超时。")
        return False

    print("\n✅ 包管理器执行完成。更新后的版本：")
    print_versions(engine, env_tool, python_path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查或显式更新 Zotero PDF2zh 的 Python 翻译环境。"
    )
    parser.add_argument(
        "action",
        choices=["status", "update"],
        help="status 仅查看版本；update 显式更新到最新兼容版本",
    )
    parser.add_argument(
        "--engine",
        choices=["pdf2zh_next", "pdf2zh", "all"],
        default="pdf2zh_next",
        help="默认只管理 pdf2zh_next；可指定 pdf2zh 或 all",
    )
    parser.add_argument(
        "--env-tool",
        choices=["auto", "uv", "conda"],
        default="auto",
        help="默认自动查找现有环境，优先 uv",
    )
    parser.add_argument(
        "--index-url",
        default=None,
        help="可选 PyPI 镜像地址；不填写时使用包管理器默认源",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="更新时跳过确认提示，适合脚本化使用",
    )
    args = parser.parse_args()

    engines = ["pdf2zh", "pdf2zh_next"] if args.engine == "all" else [args.engine]
    ok = True

    for engine in engines:
        found = find_environment(engine, args.env_tool)
        if not found:
            print(
                f"\n[{engine}] 未找到现有虚拟环境。"
                "请先正常运行 server.py，让 Server 在首次使用该引擎时创建环境。"
            )
            ok = False
            continue

        env_tool, python_path = found
        try:
            if args.action == "status":
                print_versions(engine, env_tool, python_path)
            else:
                ok = update_environment(
                    engine,
                    env_tool,
                    python_path,
                    args.index_url,
                    args.yes,
                ) and ok
        except Exception as exc:
            print(f"❌ [{engine}] 操作失败: {exc}")
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
