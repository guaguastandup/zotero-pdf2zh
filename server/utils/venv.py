from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import traceback
from collections import defaultdict
from pathlib import Path

from utils.environment_lifecycle import ENGINE_ENV_NAMES
from utils.environment_lifecycle import find_conda_env_path
from utils.environment_lifecycle import find_existing_environment
from utils.environment_lifecycle import load_requirements
from utils.environment_lifecycle import maybe_prompt_existing_user_update
from utils.environment_lifecycle import transactional_install_or_update

DEFAULT_MIRROR_SOURCE = "https://mirrors.ustc.edu.cn/pypi/simple"
PYPI_SOURCE = "https://pypi.org/simple"


def normalize_pkg_name(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-").split("=")[0]


def check_packages_python_snippet(requirements_list):
    """Compatibility helper kept for older callers."""
    from packaging import requirements

    result = {"satisfied": [], "missing": []}
    for package_requirement in requirements_list:
        try:
            req_obj = requirements.Requirement(package_requirement)
            installed_version = importlib.metadata.version(req_obj.name)
            if not req_obj.specifier or req_obj.specifier.contains(installed_version):
                result["satisfied"].append(package_requirement)
            else:
                result["missing"].append(package_requirement)
        except Exception:
            result["missing"].append(package_requirement)
    print(json.dumps(result))


class VirtualEnvManager:
    """Resolve and maintain pdf2zh environments without in-place upgrades.

    Existing environments are judged by runtime health, not by whether they
    already satisfy the newest release target. This distinction is important:
    an existing pdf2zh_next 2.8.x environment can keep serving old capabilities
    after the user declines the v4.1.0 environment update, while new installs
    and explicit updates target the release-managed >=2.9.0,<3.0.0 range.

    Environment-manager selection is also strict: ``uv`` means uv only and
    ``conda`` means conda only. ``auto`` only discovers an existing manager; for a fresh install it picks
    one manager (uv preferred) and never falls through after failure. The Server
    default is auto so historical conda users are retained transparently.
    """

    def __init__(
        self,
        config_path,
        env_name,
        default_env_tool,
        enable_mirror=True,
        skip_install=False,
        mirror_source=None,
    ):
        self.is_windows = platform.system() == "Windows"
        self.config_path = config_path
        self.env_name = env_name or ENGINE_ENV_NAMES.copy()
        normalized_tool = str(default_env_tool or "uv").strip().lower()
        if normalized_tool not in {"uv", "conda", "auto"}:
            print(f"⚠️ 未知 env_tool={default_env_tool!r}，回退到默认 uv。")
            normalized_tool = "uv"
        self.default_env_tool = normalized_tool
        self.enable_mirror = enable_mirror
        self.skip_install = skip_install
        self.mirror_source = mirror_source

        self.curr_envtool = None
        self.curr_envname = None
        self.curr_env_path = None
        self.conda_env_path = defaultdict(lambda: None)
        self.ensured_env = defaultdict(lambda: None)

        # Respect the user's selected manager when checking the existing env.
        # Only explicit `auto` may discover either uv or conda.
        if not self.skip_install:
            try:
                maybe_prompt_existing_user_update(
                    env_tool=self.default_env_tool,
                    config_path=self.config_path,
                    preferred_index=self._preferred_index(),
                )
            except Exception as exc:
                print(f"⚠️ 翻译环境更新提示检查失败，将继续启动 Server: {exc}")

    def _preferred_tools(self) -> list[str]:
        if self.default_env_tool == "conda":
            return ["conda"]
        if self.default_env_tool == "auto":
            # Keep uv first because it is the project default, but auto is an
            # explicit opt-in to cross-tool discovery/fallback.
            return ["uv", "conda"]
        return ["uv"]

    def _install_tools(self) -> list[str]:
        """Choose exactly one manager for a fresh/repair install.

        ``auto`` is discovery, not fallback: retain an existing uv/conda env;
        when no managed env exists, prefer uv if available, otherwise conda.
        Once installation starts with a manager, failure never switches to the
        other manager implicitly.
        """
        if self.default_env_tool == "uv":
            return ["uv"]
        if self.default_env_tool == "conda":
            return ["conda"]
        if shutil.which("uv"):
            return ["uv"]
        if shutil.which("conda"):
            return ["conda"]
        return ["uv"]

    def _preferred_index(self) -> str | None:
        """Return only an explicit preference; default mode auto-ranks sources."""
        if not self.enable_mirror:
            return PYPI_SOURCE
        normalized = str(self.mirror_source or "").rstrip("/")
        if normalized and normalized != DEFAULT_MIRROR_SOURCE.rstrip("/"):
            return normalized
        # The historical default was USTC. In v4.1.0 that default means
        # "auto-select a working fast source" rather than force USTC forever.
        return None

    def _remember_environment(self, engine: str, env_tool: str, env_dir: Path) -> None:
        env_name = self.env_name.get(engine, ENGINE_ENV_NAMES[engine])
        self.curr_envtool = env_tool
        self.curr_envname = env_name
        self.curr_env_path = str(env_dir)
        self.ensured_env[engine] = (env_tool, env_name, str(env_dir))
        if env_tool == "conda":
            self.conda_env_path[env_name] = str(env_dir)

    def _existing(self, engine: str, env_tool: str):
        expected = self.env_name.get(engine, ENGINE_ENV_NAMES[engine])
        if expected != ENGINE_ENV_NAMES[engine]:
            if env_tool == "uv":
                env_dir = Path(__file__).resolve().parent.parent / expected
                python_path = env_dir / (
                    "Scripts/python.exe" if self.is_windows else "bin/python"
                )
                if python_path.exists():
                    return env_tool, env_dir, python_path
            elif env_tool == "conda":
                env_dir = find_conda_env_path(expected)
                if env_dir:
                    python_path = env_dir / (
                        "Scripts/python.exe" if self.is_windows else "bin/python"
                    )
                    if python_path.exists():
                        return env_tool, env_dir, python_path
            return None
        return find_existing_environment(engine, env_tool)

    def _requirements_ok(self, engine: str, env_tool: str, python_path: Path) -> bool:
        """Check whether an existing environment is usable without upgrading it.

        Version specifiers in venv.json describe the target for a fresh install
        or an explicit update. They are intentionally *not* enforced here, so a
        user who declined an optional environment update can keep the older
        working runtime. Missing managed packages or a broken pdf2zh_next CLI
        still cause a transactional repair attempt.
        """
        try:
            _, required_packages = load_requirements(engine, env_tool, self.config_path)
            if required_packages:
                code = (
                    "from packaging.requirements import Requirement; "
                    "from importlib.metadata import version; "
                    f"reqs={required_packages!r}; "
                    "\nfor raw in reqs:\n"
                    "    req=Requirement(raw)\n"
                    "    version(req.name)\n"
                )
                result = subprocess.run(
                    [str(python_path), "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                if result.returncode != 0:
                    print(
                        f"⚠️ {engine} 环境缺少项目需要的包: "
                        + (result.stderr or result.stdout or "unknown error").strip()
                    )
                    return False

            # Package presence is sufficient for an existing environment health
            # check.  Never launch ``pdf2zh_next --help`` here: pdf2zh_next 2.9
            # imports BabelDOC/high-level modules before CLI parsing, so --help is
            # a heavyweight operation and can exceed a minute on otherwise
            # healthy machines.  Capability checks are handled statically by
            # environment_lifecycle.runtime_supports_deepseek_thinking().
            return True
        except Exception as exc:
            print(f"⚠️ 检查 {engine} 环境健康状态失败: {exc}")
            return False

    def check_envtool(self, envtool):
        executable = shutil.which(envtool)
        if not executable:
            print(f"❌ {envtool} 未安装或不在 PATH 中")
            return False
        try:
            result = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                version = (result.stdout or result.stderr).strip()
                print(f"✅ {envtool} 可用: {version}")
                return True
        except Exception as exc:
            print(f"❌ 检查 {envtool} 失败: {exc}")
        return False

    def check_env(self, engine, envtool):
        return self._existing(engine, envtool) is not None

    def check_packages(self, engine, envtool, envname=None):
        existing = self._existing(engine, envtool)
        if not existing:
            return False
        return self._requirements_ok(engine, envtool, existing[2])

    def install_packages(self, engine, envtool, envname=None):
        if self.skip_install:
            print(f"⚠️ skip_install=True，不修改 {engine} 环境")
            return self.check_env(engine, envtool)
        success, selected_tool, final_dir = transactional_install_or_update(
            engine,
            env_tool=envtool,
            config_path=self.config_path,
            preferred_index=self._preferred_index(),
            require_deepseek_thinking=(engine == "pdf2zh_next"),
        )
        if success and selected_tool and final_dir:
            self._remember_environment(engine, selected_tool, final_dir)
        return success

    def create_env(self, engine, envtool):
        return self.install_packages(engine, envtool)

    def ensure_env(self, engine):
        cached = self.ensured_env.get(engine)
        if cached:
            tool, _, cached_path = cached
            existing = self._existing(engine, tool)
            if existing and str(existing[1]) == cached_path:
                self.curr_envtool = tool
                self.curr_envname = self.env_name.get(engine, ENGINE_ENV_NAMES[engine])
                self.curr_env_path = cached_path
                return True
            self.ensured_env[engine] = None

        # Prefer an already usable environment even when it is older than the
        # current update target. In explicit uv/conda mode, only that selected
        # manager is considered. This honors both the user's manager choice and
        # an explicit "N" response to the optional update prompt.
        for envtool in self._preferred_tools():
            existing = self._existing(engine, envtool)
            if not existing:
                continue
            if self.skip_install or self._requirements_ok(engine, envtool, existing[2]):
                self._remember_environment(engine, envtool, existing[1])
                print(f"✅ 使用 {envtool} 环境: {existing[1]}")
                return True

            print(f"🔧 检测到 {envtool} 环境确实不完整，将通过 staging 安全修复。")
            if self.install_packages(engine, envtool):
                return True
            print("⚠️ 安全修复失败，不会把不完整环境缓存为可用环境。")

        if self.skip_install:
            print(f"❌ 未找到可用的 {engine} 环境，且 skip_install=True")
            return False

        # New user / no usable env. Auto chooses one manager once (uv
        # preferred) and never switches managers because an installation failed.
        tools = self._install_tools()
        for envtool in tools:
            if not self.check_envtool(envtool):
                continue
            print(f"🔧 首次创建 {engine} 环境，将使用 {envtool} staging 安装。")
            if self.install_packages(engine, envtool):
                return True
            print(f"⚠️ {envtool} 首次安装失败；不会自动切换到其他环境工具。")

        print("\n" + "=" * 70)
        print(f"❌ 无法创建可验证的 {engine} 翻译环境")
        print(f"当前环境管理模式: {self.default_env_tool}")
        print("Server 仍可启动，但该翻译引擎暂时不可用。")
        print("安装失败不会留下新的半安装正式环境。")
        print("可稍后重新启动 Server，或执行: python update_packages.py")
        print("如需改用另一环境工具，请显式传入 --env_tool=conda 或 --env_tool=auto。")
        print("=" * 70 + "\n")
        return False

    def _get_conda_env_path(self, env_name):
        cached = self.conda_env_path.get(env_name)
        if cached and os.path.exists(cached):
            return cached
        path = find_conda_env_path(env_name)
        if path:
            self.conda_env_path[env_name] = str(path)
            return str(path)
        return None

    def get_conda_bin_dir(self):
        if self.curr_envtool != "conda" or not self.curr_envname:
            return False
        env_path = self._get_conda_env_path(self.curr_envname)
        if not env_path:
            return False
        bin_dir = os.path.join(env_path, "Scripts" if self.is_windows else "bin")
        return bin_dir if os.path.exists(bin_dir) else False

    def _resolved_command(self, command):
        engine = "pdf2zh_next" if "pdf2zh_next" in " ".join(command).lower() else "pdf2zh"
        if not self.ensure_env(engine):
            raise RuntimeError(
                f"无法准备可用的 {engine} 托管翻译环境。Server 本身仍可运行，"
                "但本次翻译无法执行。请稍后重试，或在 server 目录运行 "
                "`python update_packages.py`。如需明确使用系统环境，请使用 "
                "`--enable_venv=False` 启动 Server。"
            )

        existing = self._existing(engine, self.curr_envtool)
        if not existing:
            raise RuntimeError(f"已选择的 {engine} 翻译环境在执行前不可用。")
        _, env_dir, python_path = existing
        bin_dir = env_dir / ("Scripts" if self.is_windows else "bin")

        if command[0].lower() in {"pdf2zh", "pdf2zh_next"}:
            executable = bin_dir / (command[0] + (".exe" if self.is_windows else ""))
            if executable.exists():
                final_cmd = [str(executable), *command[1:]]
            else:
                final_cmd = [str(python_path), "-u", "-m", command[0], *command[1:]]
        else:
            final_cmd = [str(python_path), "-u", *command]

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
        return final_cmd, env

    def get_command_and_env(self, command):
        try:
            return self._resolved_command(command)
        except Exception as exc:
            print(f"⚠️ 获取虚拟环境命令失败: {exc}")
            traceback.print_exc()
            raise

    def execute_in_env(self, command):
        final_cmd, env = self.get_command_and_env(command)
        print(f"🚀 执行命令: {' '.join(str(value) for value in final_cmd)}")
        process = subprocess.Popen(
            final_cmd,
            stdout=None,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        stderr_lines = []
        if process.stderr:
            for line in process.stderr:
                stderr_lines.append(line)
                sys.stderr.write(line)
                sys.stderr.flush()
            process.stderr.close()
        return_code = process.wait()
        stderr_text = "".join(stderr_lines)
        if return_code != 0:
            raise subprocess.CalledProcessError(
                returncode=return_code,
                cmd=final_cmd,
                output=None,
                stderr=stderr_text,
            )
        return stderr_text
