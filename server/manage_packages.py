#!/usr/bin/env python3
"""Inspect or explicitly update Zotero PDF2zh translation environments.

Normal server startup never calls the update action. Package updates are an
explicit maintenance action instead of a side effect of starting server.py.
Before an update, the script checks real package metadata + distribution download
reachability and asks the package manager to resolve the change without writing
anything to the environment.
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

from utils.package_network import print_probe_report
from utils.package_network import probe_indexes
from utils.package_network import usable_indexes

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

PRIMARY_PACKAGES = {
    "pdf2zh": "pdf2zh",
    "pdf2zh_next": "pdf2zh-next",
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


def print_versions(
    engine: str,
    env_tool: str,
    python_path: Path,
) -> dict[str, str | None]:
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

    if (
        _version_tuple(pdf2zh_version) >= (2, 9, 0)
        and _version_tuple(babeldoc_version) <= (0, 6, 2)
    ):
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


def _package_manager_env() -> dict[str, str]:
    env = os.environ.copy()
    # Bad links should retry, but an unreachable source should not hang forever.
    env.setdefault("UV_HTTP_CONNECT_TIMEOUT", "10")
    env.setdefault("UV_HTTP_TIMEOUT", "120")
    env.setdefault("UV_HTTP_RETRIES", "5")
    return env


def _pip_supports_dry_run(python_path: Path) -> bool:
    try:
        result = subprocess.run(
            [str(python_path), "-m", "pip", "install", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0 and "--dry-run" in result.stdout
    except Exception:
        return False


def build_install_command(
    env_tool: str,
    python_path: Path,
    requirements: list[str],
    index_url: str,
    *,
    dry_run: bool,
) -> list[str] | None:
    if env_tool == "uv":
        uv_path = shutil.which("uv")
        if not uv_path:
            return None
        cmd = [uv_path, "pip", "install", "--upgrade"]
        if dry_run:
            cmd.append("--dry-run")
        cmd.extend(["--index-url", index_url])
        cmd.extend(requirements)
        cmd.extend(["--python", str(python_path)])
        return cmd

    if dry_run and not _pip_supports_dry_run(python_path):
        return None
    cmd = [str(python_path), "-m", "pip", "install", "--upgrade"]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend(["--index-url", index_url])
    cmd.extend(requirements)
    return cmd


def resolver_preflight(
    engine: str,
    env_tool: str,
    python_path: Path,
    requirements: list[str],
    index_url: str,
) -> bool:
    cmd = build_install_command(
        env_tool,
        python_path,
        requirements,
        index_url,
        dry_run=True,
    )
    if cmd is None:
        if env_tool == "uv":
            print("  ❌ 找不到 uv，无法执行依赖解析预检。")
            return False
        print("  ⚠️ 当前 pip 不支持 --dry-run，仅使用网络预检结果。")
        return True

    print(f"\n🧪 依赖解析预检: {index_url}")
    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=_package_manager_env(),
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        print("  ❌ 依赖解析超时，尝试其他下载源。")
        return False
    except Exception as exc:
        print(f"  ❌ 无法执行依赖解析: {exc}")
        return False

    if result.returncode == 0:
        print("  ✅ 包管理器能够从该源解析完整依赖；未修改现有环境。")
        return True

    detail = (result.stderr or result.stdout or "").strip().splitlines()
    tail = " | ".join(detail[-3:]) if detail else f"exit={result.returncode}"
    print(f"  ❌ 该源无法完成依赖解析: {tail}")
    return False


def choose_update_sources(
    engine: str,
    env_tool: str,
    python_path: Path,
    requirements: list[str],
    preferred_index: str | None,
    network_timeout: float,
) -> list[str]:
    results = probe_indexes(
        PRIMARY_PACKAGES[engine],
        preferred_index=preferred_index,
        timeout=network_timeout,
    )
    print_probe_report(results)
    ranked = usable_indexes(results)
    if not ranked:
        return []

    resolved: list[str] = []
    for result in ranked:
        if resolver_preflight(
            engine,
            env_tool,
            python_path,
            requirements,
            result.url,
        ):
            resolved.append(result.url)

    if resolved:
        print(f"\n✅ 首选更新源: {resolved[0]}")
        if len(resolved) > 1:
            print("   备用源: " + ", ".join(resolved[1:]))
    else:
        print("\n❌ 网络看起来可达，但没有任何源能解析完整依赖；不会开始更新。")
    return resolved


def run_install(
    env_tool: str,
    python_path: Path,
    requirements: list[str],
    index_url: str,
) -> bool:
    cmd = build_install_command(
        env_tool,
        python_path,
        requirements,
        index_url,
        dry_run=False,
    )
    if cmd is None:
        print("❌ 找不到对应包管理器。")
        return False

    print(f"\n📦 使用下载源: {index_url}")
    print("执行：", " ".join(cmd))
    try:
        subprocess.run(
            cmd,
            cwd=ROOT,
            check=True,
            env=_package_manager_env(),
            timeout=1200,
        )
        return True
    except subprocess.CalledProcessError as exc:
        print(f"❌ 下载/安装失败，退出码: {exc.returncode}")
        return False
    except subprocess.TimeoutExpired:
        print("❌ 下载/安装超时。")
        return False


def update_environment(
    engine: str,
    env_tool: str,
    python_path: Path,
    preferred_index: str | None,
    network_timeout: float,
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

    sources = choose_update_sources(
        engine,
        env_tool,
        python_path,
        requirements,
        preferred_index,
        network_timeout,
    )
    if not sources:
        print(
            "\n🛡️ 更新已安全停止：当前没有可验证的包下载路径。"
            "现有虚拟环境保持原样。可以稍后重试，或使用 --index-url 指定可访问镜像。"
        )
        return False

    if not assume_yes:
        try:
            answer = input("\n网络和依赖检查通过。确认更新这个环境？(y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in {"y", "yes"}:
            print("已取消更新，现有环境未修改。")
            return True

    # If a download fails after the dry-run, automatically retry other sources
    # that passed both the artifact probe and dependency resolution.
    for position, index_url in enumerate(sources, start=1):
        if run_install(env_tool, python_path, requirements, index_url):
            print("\n✅ 包管理器执行完成。更新后的版本：")
            print_versions(engine, env_tool, python_path)
            return True
        if position < len(sources):
            print("↪ 当前源失败，自动切换到下一已验证备用源。")

    print(
        "\n❌ 所有已验证下载源都在实际安装阶段失败。"
        "请再次运行 status 检查当前版本；不要使用 --no-deps 强行覆盖依赖。"
    )
    try:
        print_versions(engine, env_tool, python_path)
    except Exception:
        pass
    return False


def run_network_check(
    engine: str,
    preferred_index: str | None,
    network_timeout: float,
) -> bool:
    results = probe_indexes(
        PRIMARY_PACKAGES[engine],
        preferred_index=preferred_index,
        timeout=network_timeout,
    )
    print(f"\n[{engine}] target={PRIMARY_PACKAGES[engine]}")
    print_probe_report(results)
    return bool(usable_indexes(results))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查网络、查看版本或显式更新 Zotero PDF2zh 的 Python 翻译环境。"
    )
    parser.add_argument(
        "action",
        choices=["network", "status", "update"],
        help="network 检查包下载网络；status 仅查看版本；update 显式更新",
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
        help="优先测试/使用的自定义 PyPI 镜像；失败时仍会尝试内置备用源",
    )
    parser.add_argument(
        "--network-timeout",
        type=float,
        default=4.0,
        help="每个网络探测请求的超时秒数，默认 4 秒",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="更新时跳过最终确认，适合脚本化使用",
    )
    args = parser.parse_args()

    engines = ["pdf2zh", "pdf2zh_next"] if args.engine == "all" else [args.engine]
    ok = True

    for engine in engines:
        if args.action == "network":
            ok = run_network_check(
                engine,
                args.index_url,
                args.network_timeout,
            ) and ok
            continue

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
                    max(1.0, args.network_timeout),
                    args.yes,
                ) and ok
        except Exception as exc:
            print(f"❌ [{engine}] 操作失败: {exc}")
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
