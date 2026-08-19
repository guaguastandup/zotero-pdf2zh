from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from utils.package_network import print_probe_report
from utils.package_network import probe_indexes
from utils.package_network import usable_indexes

SERVER_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VENV_CONFIG = SERVER_ROOT / "config" / "venv.json.example"

ENGINE_ENV_NAMES = {
    "pdf2zh": "zotero-pdf2zh-venv",
    "pdf2zh_next": "zotero-pdf2zh-next-venv",
}
PRIMARY_PACKAGES = {
    "pdf2zh": "pdf2zh",
    "pdf2zh_next": "pdf2zh-next",
}
VERSION_PACKAGES = {
    "pdf2zh": ["pdf2zh", "BabelDOC", "PyMuPDF", "pypdf"],
    "pdf2zh_next": ["pdf2zh-next", "BabelDOC", "PyMuPDF", "pypdf"],
}
THINKING_FLAGS = (
    "--deepseek-thinking-mode",
    "--deepseek-reasoning-effort",
)


def environment_python_candidates(env_dir: Path) -> tuple[Path, ...]:
    """Return supported Python locations for a managed environment.

    On Windows, uv/venv puts Python in ``Scripts\\python.exe`` while Conda
    puts it at the environment root as ``<env>\\python.exe``.  The v4.1.0
    lifecycle originally assumed the uv layout for both managers, which made a
    healthy Windows Conda environment look broken immediately after creation.
    """
    env_dir = Path(env_dir)
    if platform.system() == "Windows":
        return (env_dir / "python.exe", env_dir / "Scripts" / "python.exe")
    return (env_dir / "bin" / "python",)


def resolve_environment_python(env_dir: Path) -> Path:
    candidates = environment_python_candidates(env_dir)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    # Callers still verify existence.  This fallback only gives diagnostics a
    # manager-appropriate expected path when environment creation is incomplete.
    env_dir = Path(env_dir)
    if platform.system() == "Windows" and (env_dir / "conda-meta").exists():
        return env_dir / "python.exe"
    return candidates[-1]


def resolve_environment_root(python_path: Path) -> Path:
    """Recover an environment root from either uv/venv or Conda Python."""
    python_path = Path(python_path)
    parent = python_path.parent
    if platform.system() == "Windows":
        return parent.parent if parent.name.lower() == "scripts" else parent
    return parent.parent if parent.name == "bin" else parent


def environment_path_entries(env_dir: Path, env_tool: str) -> list[Path]:
    """Return PATH entries needed to execute tools from a managed environment."""
    env_dir = Path(env_dir)
    if platform.system() != "Windows":
        candidates = [env_dir / "bin"]
    elif env_tool == "conda":
        # Important parts of a normal ``conda activate`` PATH on Windows.
        candidates = [
            env_dir,
            env_dir / "Library" / "mingw-w64" / "bin",
            env_dir / "Library" / "usr" / "bin",
            env_dir / "Library" / "bin",
            env_dir / "Scripts",
            env_dir / "bin",
        ]
    else:
        candidates = [env_dir / "Scripts"]

    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(str(candidate)))
        if candidate.exists() and key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _python_in_env_dir(env_dir: Path) -> Path:
    # Compatibility alias for the lifecycle internals.
    return resolve_environment_python(env_dir)


def _bin_dir(env_dir: Path) -> Path:
    return env_dir / ("Scripts" if platform.system() == "Windows" else "bin")


def load_environment_config(config_path: str | os.PathLike[str] | None = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_VENV_CONFIG
    if not path.exists():
        path = DEFAULT_VENV_CONFIG
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_requirements(
    engine: str,
    env_tool: str,
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[str, list[str]]:
    config = load_environment_config(config_path)
    engine_config = config.get(engine, {}).get(env_tool, {})
    return (
        str(engine_config.get("python_version", "3.12")),
        list(engine_config.get("packages", [])),
    )


def _conda_info() -> dict | None:
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
        return json.loads(result.stdout)
    except Exception:
        return None


def find_conda_env_path(name: str) -> Path | None:
    info = _conda_info()
    if not info:
        return None
    for raw_path in info.get("envs", []):
        path = Path(raw_path)
        if path.name == name:
            return path
    for raw_dir in info.get("envs_dirs", []):
        path = Path(raw_dir) / name
        if path.exists():
            return path
    return None


def find_existing_environment(
    engine: str,
    env_tool: str = "auto",
) -> tuple[str, Path, Path] | None:
    env_name = ENGINE_ENV_NAMES[engine]
    if env_tool in {"auto", "uv"}:
        env_dir = SERVER_ROOT / env_name
        python_path = _python_in_env_dir(env_dir)
        if python_path.exists():
            return "uv", env_dir, python_path
    if env_tool in {"auto", "conda"}:
        env_dir = find_conda_env_path(env_name)
        if env_dir:
            python_path = _python_in_env_dir(env_dir)
            if python_path.exists():
                return "conda", env_dir, python_path
    return None


def read_versions(python_path: Path, engine: str) -> dict[str, str | None]:
    names = VERSION_PACKAGES[engine]
    code = (
        "import json; "
        "from importlib.metadata import version, PackageNotFoundError; "
        f"names={names!r}; out={{}}; "
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
        raise RuntimeError(result.stderr.strip() or "无法读取翻译环境版本")
    return json.loads(result.stdout)


def format_versions(versions: dict[str, str | None]) -> str:
    return ", ".join(
        f"{name}={value}" for name, value in versions.items() if value is not None
    )


def _runtime_command(python_path: Path, module: str) -> list[str]:
    env_dir = resolve_environment_root(python_path)
    executable = _bin_dir(env_dir) / (
        module + (".exe" if platform.system() == "Windows" else "")
    )
    if executable.exists():
        return [str(executable)]
    return [str(python_path), "-m", module]


def runtime_supports_deepseek_thinking(python_path: Path) -> bool:
    """Check DeepSeek V4 capability without importing or starting pdf2zh_next.

    pdf2zh_next 2.9.0 imports BabelDOC/high-level modules before its CLI parser
    runs, so ``pdf2zh_next --help`` is not a safe health probe: on some Macs it
    can spend more than a minute in import/asset initialization.  We instead
    inspect the installed distribution files using importlib.metadata from the
    target interpreter.  This verifies both DeepSeek setting fields and the
    generic underscore-to-hyphen CLI argument generation used upstream.
    """
    code = (
        "import json; "
        "from importlib.metadata import distribution; "
        "from pathlib import Path; "
        "out={'supported': False, 'reason': ''}; "
        "\ntry:\n"
        "    dist=distribution('pdf2zh-next')\n"
        "    settings=Path(dist.locate_file('pdf2zh_next/config/translate_engine_model.py'))\n"
        "    cli=Path(dist.locate_file('pdf2zh_next/config/main.py'))\n"
        "    settings_text=settings.read_text(encoding='utf-8')\n"
        "    cli_text=cli.read_text(encoding='utf-8')\n"
        "    fields=('deepseek_thinking_mode','deepseek_reasoning_effort')\n"
        "    field_ok=all(field in settings_text for field in fields)\n"
        "    cli_ok='field_name.replace(\"_\", \"-\").lower()' in cli_text\n"
        "    out={'supported': bool(field_ok and cli_ok), 'reason': 'ok' if field_ok and cli_ok else 'missing-fields-or-cli-mapping'}\n"
        "except Exception as exc:\n"
        "    out={'supported': False, 'reason': type(exc).__name__ + ': ' + str(exc)}\n"
        "print(json.dumps(out))"
    )
    try:
        result = subprocess.run(
            [str(python_path), "-c", code],
            cwd=SERVER_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return False
        payload = json.loads(result.stdout.strip() or "{}")
        return bool(payload.get("supported"))
    except Exception:
        return False


def _package_manager_env() -> dict[str, str]:
    env = os.environ.copy()
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
        return result.returncode == 0 and "--dry-run" in (result.stdout or "")
    except Exception:
        return False


def _build_install_command(
    env_tool: str,
    python_path: Path,
    requirements: Iterable[str],
    index_url: str,
    *,
    dry_run: bool,
) -> list[str] | None:
    requirements = list(requirements)
    if env_tool == "uv":
        uv_path = shutil.which("uv")
        if not uv_path:
            return None
        command = [uv_path, "pip", "install"]
        if dry_run:
            command.append("--dry-run")
        command.extend(
            ["--index-url", index_url, *requirements, "--python", str(python_path)]
        )
        return command
    if dry_run and not _pip_supports_dry_run(python_path):
        return None
    command = [str(python_path), "-m", "pip", "install"]
    if dry_run:
        command.append("--dry-run")
    command.extend(["--index-url", index_url, *requirements])
    return command


def _resolver_preflight(
    env_tool: str,
    python_path: Path,
    requirements: list[str],
    index_url: str,
) -> bool:
    command = _build_install_command(
        env_tool, python_path, requirements, index_url, dry_run=True
    )
    if command is None:
        return env_tool == "conda"
    try:
        result = subprocess.run(
            command,
            cwd=SERVER_ROOT,
            capture_output=True,
            text=True,
            env=_package_manager_env(),
            timeout=180,
        )
        return result.returncode == 0
    except Exception:
        return False


def choose_install_sources(
    engine: str,
    env_tool: str,
    python_path: Path,
    requirements: list[str],
    preferred_index: str | None = None,
    network_timeout: float = 4.0,
) -> list[str]:
    results = probe_indexes(
        PRIMARY_PACKAGES[engine],
        preferred_index=preferred_index,
        timeout=network_timeout,
    )
    print_probe_report(results)
    sources: list[str] = []
    for result in usable_indexes(results):
        if _resolver_preflight(env_tool, python_path, requirements, result.url):
            sources.append(result.url)
    return sources


def _remove_conda_env(name: str) -> None:
    if not shutil.which("conda") or not find_conda_env_path(name):
        return
    try:
        subprocess.run(
            ["conda", "env", "remove", "-n", name, "-y"],
            cwd=SERVER_ROOT,
            check=False,
            timeout=1200,
        )
    except Exception:
        pass


def _create_uv_environment(path: Path, python_version: str) -> Path:
    uv_path = shutil.which("uv")
    if not uv_path:
        raise RuntimeError("未找到 uv")
    shutil.rmtree(path, ignore_errors=True)
    subprocess.run(
        [uv_path, "venv", str(path), "--python", python_version],
        cwd=SERVER_ROOT,
        check=True,
        env=_package_manager_env(),
        timeout=1200,
    )
    python_path = _python_in_env_dir(path)
    if not python_path.exists():
        raise RuntimeError(f"uv 环境没有生成 Python 可执行文件: {path}")
    return python_path


def _create_staging_environment(
    engine: str,
    env_tool: str,
    python_version: str,
) -> tuple[str, Path, Path]:
    env_name = ENGINE_ENV_NAMES[engine]
    if env_tool == "uv":
        staging_dir = SERVER_ROOT / f"{env_name}.staging"
        python_path = _create_uv_environment(staging_dir, python_version)
        return f"{env_name}.staging", staging_dir, python_path
    conda_path = shutil.which("conda")
    if not conda_path:
        raise RuntimeError("未找到 conda")
    staging_name = f"{env_name}-staging"
    _remove_conda_env(staging_name)
    subprocess.run(
        [
            conda_path,
            "create",
            "-n",
            staging_name,
            f"python={python_version}",
            "pip",
            "-y",
        ],
        cwd=SERVER_ROOT,
        check=True,
        timeout=1200,
    )
    staging_dir = find_conda_env_path(staging_name)
    if not staging_dir:
        raise RuntimeError("创建 staging conda 环境后无法定位其路径")
    python_path = _python_in_env_dir(staging_dir)
    if not python_path.exists():
        raise RuntimeError(f"staging conda 环境没有 Python 可执行文件: {python_path}")
    return staging_name, staging_dir, python_path


def _cleanup_staging(env_tool: str, staging_name: str, staging_dir: Path | None) -> None:
    if env_tool == "uv":
        if staging_dir is not None:
            shutil.rmtree(staging_dir, ignore_errors=True)
    elif staging_name:
        _remove_conda_env(staging_name)


def _run_install(
    env_tool: str,
    python_path: Path,
    requirements: list[str],
    sources: list[str],
) -> bool:
    for position, index_url in enumerate(sources, start=1):
        command = _build_install_command(
            env_tool, python_path, requirements, index_url, dry_run=False
        )
        if command is None:
            return False
        print(f"\n📦 使用下载源: {index_url}")
        try:
            subprocess.run(
                command,
                cwd=SERVER_ROOT,
                check=True,
                env=_package_manager_env(),
                timeout=1200,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            print(f"❌ 安装失败: {exc}")
            if position < len(sources):
                print("↪ 自动切换到下一已验证下载源。")
    return False


def validate_environment(
    engine: str,
    python_path: Path,
    requirements: list[str],
    *,
    require_deepseek_thinking: bool = False,
) -> bool:
    try:
        code = (
            "from packaging.requirements import Requirement; "
            "from importlib.metadata import version; "
            f"reqs={requirements!r}; "
            "\nfor raw in reqs:\n"
            "    req=Requirement(raw)\n"
            "    installed=version(req.name)\n"
            "    assert not req.specifier or req.specifier.contains(installed), (raw, installed)\n"
        )
        result = subprocess.run(
            [str(python_path), "-c", code],
            cwd=SERVER_ROOT,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            print("❌ 环境依赖完整性检查失败:", (result.stderr or result.stdout).strip())
            return False
        module = "pdf2zh_next" if engine == "pdf2zh_next" else "pdf2zh"
        env_dir = resolve_environment_root(python_path)
        executable = _bin_dir(env_dir) / (
            module + (".exe" if platform.system() == "Windows" else "")
        )
        if not executable.exists():
            print(f"❌ {module} CLI 入口不存在: {executable}")
            return False

        # Do not launch the heavyweight pdf2zh_next CLI help path here. Upstream imports
        # BabelDOC/high-level modules before CLI parsing, so --help can be a
        # heavyweight operation and is not a reliable installation probe.
        if require_deepseek_thinking and engine == "pdf2zh_next":
            if not runtime_supports_deepseek_thinking(python_path):
                print("❌ pdf2zh_next 缺少 DeepSeek V4 thinking capability")
                return False
        return True
    except Exception as exc:
        print(f"❌ 环境验证失败: {exc}")
        return False


def _freeze_exact_requirements(python_path: Path) -> list[str]:
    code = (
        "from importlib.metadata import distributions; items=[]; "
        "\nfor d in distributions():\n"
        "    name=d.metadata.get('Name')\n"
        "    version=d.version\n"
        "    if name and version: items.append(f'{name}=={version}')\n"
        "\nfor item in sorted(set(items), key=str.lower): print(item)\n"
    )
    result = subprocess.run(
        [str(python_path), "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "无法冻结 staging 包版本")
    specs = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not specs:
        raise RuntimeError("staging 环境没有可冻结的包版本")
    return specs


def _activate_uv_candidate(
    engine: str,
    staging_python: Path,
    python_version: str,
    declared_requirements: list[str],
    sources: list[str],
    require_deepseek_thinking: bool,
) -> tuple[Path, Path]:
    final_dir = SERVER_ROOT / ENGINE_ENV_NAMES[engine]
    backup_dir = SERVER_ROOT / f"{ENGINE_ENV_NAMES[engine]}.backup"
    exact_requirements = _freeze_exact_requirements(staging_python)
    shutil.rmtree(backup_dir, ignore_errors=True)
    had_old = final_dir.exists()
    if had_old:
        final_dir.rename(backup_dir)
    try:
        final_python = _create_uv_environment(final_dir, python_version)
        if not _run_install("uv", final_python, exact_requirements, sources):
            raise RuntimeError("正式路径环境安装失败")
        if not validate_environment(
            engine,
            final_python,
            declared_requirements,
            require_deepseek_thinking=require_deepseek_thinking,
        ):
            raise RuntimeError("正式路径环境验证失败")
        return final_dir, final_python
    except Exception:
        shutil.rmtree(final_dir, ignore_errors=True)
        if had_old and backup_dir.exists():
            backup_dir.rename(final_dir)
        raise


def _clone_conda_env(source: str, target: str) -> bool:
    _remove_conda_env(target)
    try:
        subprocess.run(
            ["conda", "create", "-n", target, "--clone", source, "-y"],
            cwd=SERVER_ROOT,
            check=True,
            timeout=1800,
        )
        return True
    except Exception:
        return False


def _activate_conda_candidate(
    engine: str,
    staging_name: str,
    declared_requirements: list[str],
    require_deepseek_thinking: bool,
) -> tuple[Path, Path]:
    final_name = ENGINE_ENV_NAMES[engine]
    backup_name = f"{final_name}-backup"
    had_old = find_conda_env_path(final_name) is not None
    if had_old:
        if not _clone_conda_env(final_name, backup_name):
            raise RuntimeError("无法创建旧 conda 环境备份")
        _remove_conda_env(final_name)
    try:
        if not _clone_conda_env(staging_name, final_name):
            raise RuntimeError("无法将 staging conda 环境克隆为正式环境")
        final_dir = find_conda_env_path(final_name)
        if not final_dir:
            raise RuntimeError("切换后无法定位正式 conda 环境")
        final_python = _python_in_env_dir(final_dir)
        if not final_python.exists():
            raise RuntimeError(f"正式 conda 环境没有 Python 可执行文件: {final_python}")
        if not validate_environment(
            engine,
            final_python,
            declared_requirements,
            require_deepseek_thinking=require_deepseek_thinking,
        ):
            raise RuntimeError("正式 conda 环境验证失败")
        return final_dir, final_python
    except Exception:
        _remove_conda_env(final_name)
        if had_old and find_conda_env_path(backup_name):
            _clone_conda_env(backup_name, final_name)
        raise


def transactional_install_or_update(
    engine: str = "pdf2zh_next",
    *,
    env_tool: str = "auto",
    config_path: str | os.PathLike[str] | None = None,
    preferred_index: str | None = None,
    network_timeout: float = 4.0,
    require_deepseek_thinking: bool = False,
) -> tuple[bool, str | None, Path | None]:
    if engine not in ENGINE_ENV_NAMES:
        raise ValueError(f"Unknown engine: {engine}")
    existing = find_existing_environment(engine, env_tool)
    selected_tool = existing[0] if existing else None
    if selected_tool is None:
        candidates = [env_tool] if env_tool in {"uv", "conda"} else ["uv", "conda"]
        selected_tool = next((tool for tool in candidates if shutil.which(tool)), None)
    if selected_tool is None:
        print("❌ 未找到可用的 uv 或 conda，无法创建翻译环境。")
        return False, None, None
    python_version, requirements = load_requirements(engine, selected_tool, config_path)
    if not requirements:
        print(f"❌ {engine} 没有声明安装依赖。")
        return False, selected_tool, existing[1] if existing else None
    staging_name = ""
    staging_dir: Path | None = None
    try:
        print("\n🛡️ 将在独立 staging 环境完成试装和验证；失败不会修改当前可用环境。")
        staging_name, staging_dir, staging_python = _create_staging_environment(
            engine, selected_tool, python_version
        )
        sources = choose_install_sources(
            engine,
            selected_tool,
            staging_python,
            requirements,
            preferred_index=preferred_index,
            network_timeout=network_timeout,
        )
        if not sources:
            print("❌ 没有可验证且能解析完整依赖的下载源。")
            return False, selected_tool, existing[1] if existing else None
        if not _run_install(selected_tool, staging_python, requirements, sources):
            return False, selected_tool, existing[1] if existing else None
        if not validate_environment(
            engine,
            staging_python,
            requirements,
            require_deepseek_thinking=require_deepseek_thinking,
        ):
            return False, selected_tool, existing[1] if existing else None
        before_versions = None
        if existing:
            try:
                before_versions = read_versions(existing[2], engine)
            except Exception:
                pass
        if selected_tool == "uv":
            final_dir, final_python = _activate_uv_candidate(
                engine,
                staging_python,
                python_version,
                requirements,
                sources,
                require_deepseek_thinking,
            )
        else:
            final_dir, final_python = _activate_conda_candidate(
                engine,
                staging_name,
                requirements,
                require_deepseek_thinking,
            )
        after_versions = read_versions(final_python, engine)
        print("\n✅ 翻译环境已通过 staging 和正式路径双重验证并安全切换。")
        if before_versions:
            print("   更新前:", format_versions(before_versions))
        print("   当前:", format_versions(after_versions))
        return True, selected_tool, final_dir
    except Exception as exc:
        print(f"\n⚠️ 翻译环境安装/更新失败: {exc}")
        restored = find_existing_environment(engine, selected_tool)
        if existing and restored:
            print("   原有翻译环境已保留/恢复，将继续使用原环境。")
        elif existing:
            print("   ⚠️ 原环境自动恢复未能被确认，请保留 .backup 环境并查看日志。")
        else:
            print("   未留下半安装的正式环境；可以稍后重新尝试。")
        return False, selected_tool, restored[1] if restored else None
    finally:
        _cleanup_staging(selected_tool, staging_name, staging_dir)


def server_version_from_source() -> str:
    try:
        text = (SERVER_ROOT / "server.py").read_text(encoding="utf-8")
        match = re.search(
            r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE
        )
        return match.group(1) if match else "unknown"
    except Exception:
        return "unknown"


def package_update_state_path() -> Path:
    return SERVER_ROOT / "config" / "package_update_state.json"


def read_package_update_state() -> dict:
    try:
        with package_update_state_path().open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write_package_update_state(server_version: str, status: str) -> None:
    path = package_update_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(
            {"server_version": server_version, "status": status},
            handle,
            ensure_ascii=False,
            indent=2,
        )
    os.replace(temp, path)


def _server_cli_bool(name: str, default: bool = False) -> bool:
    flag = "--" + name
    args = sys.argv[1:]
    for index, value in enumerate(args):
        if value == flag and index + 1 < len(args):
            return str(args[index + 1]).strip().lower() in {"1", "true", "yes", "y"}
        prefix = flag + "="
        if value.startswith(prefix):
            return value[len(prefix):].strip().lower() in {"1", "true", "yes", "y"}
    return default


def maybe_prompt_existing_user_update(
    *,
    env_tool: str = "auto",
    config_path: str | os.PathLike[str] | None = None,
    preferred_index: str | None = None,
) -> None:
    if not sys.stdin or not sys.stdin.isatty() or _server_cli_bool("enable_winexe"):
        return
    existing = find_existing_environment("pdf2zh_next", env_tool)
    if not existing:
        return
    server_version = server_version_from_source()
    state = read_package_update_state()
    if state.get("server_version") == server_version and state.get("status") in {
        "success",
        "declined",
        "failed",
    }:
        return
    try:
        versions = read_versions(existing[2], "pdf2zh_next")
        current = versions.get("pdf2zh-next") or "unknown"
    except Exception:
        current = "unknown"
    has_thinking = runtime_supports_deepseek_thinking(existing[2])
    print("\n" + "─" * 60)
    print("🔄 检测到已有 Python 翻译环境")
    print(f"当前 pdf2zh_next: {current}")
    if has_thinking:
        print("当前环境已支持 DeepSeek V4 思考控制；仍可检查其他兼容依赖更新。")
    else:
        print(f"Zotero PDF2zh v{server_version} 的 DeepSeek V4 思考控制需要新版运行时。")
    print("更新会先在独立临时环境完成；失败不会原地修改您当前可用的环境。")
    print("\n[Y] 安全检查并更新（推荐）")
    print("[N] 暂不更新")
    try:
        answer = input("\n选择 [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"
    if answer in {"", "y", "yes"}:
        success, _, _ = transactional_install_or_update(
            "pdf2zh_next",
            env_tool=existing[0],
            config_path=config_path,
            preferred_index=preferred_index,
            require_deepseek_thinking=True,
        )
        write_package_update_state(server_version, "success" if success else "failed")
        if not success:
            print(
                "⚠️ 本次更新未完成。Server 将继续使用原有环境；"
                "本版本不会再次自动询问，可稍后运行 python update_packages.py 重试。"
            )
    else:
        write_package_update_state(server_version, "declined")
        print("👌 已保留当前翻译环境；本 Server 版本不会再次询问。")
