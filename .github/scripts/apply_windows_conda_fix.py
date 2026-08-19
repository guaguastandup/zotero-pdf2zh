from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_environment_lifecycle() -> None:
    path = ROOT / "server" / "utils" / "environment_lifecycle.py"
    text = path.read_text(encoding="utf-8")

    old = '''def _python_in_env_dir(env_dir: Path) -> Path:\n    if platform.system() == "Windows":\n        return env_dir / "Scripts" / "python.exe"\n    return env_dir / "bin" / "python"\n\n\ndef _bin_dir(env_dir: Path) -> Path:\n    return env_dir / ("Scripts" if platform.system() == "Windows" else "bin")\n'''
    new = '''def environment_python_candidates(env_dir: Path) -> tuple[Path, ...]:\n    """Return supported Python locations for a managed environment.\n\n    Windows virtualenv/uv puts Python in ``Scripts\\python.exe`` while Conda\n    puts it at the environment root (``<env>\\python.exe``).  Keeping both\n    layouts explicit prevents a healthy Conda environment from being mistaken\n    for a broken virtualenv.\n    """\n    env_dir = Path(env_dir)\n    if platform.system() == "Windows":\n        return (env_dir / "python.exe", env_dir / "Scripts" / "python.exe")\n    return (env_dir / "bin" / "python",)\n\n\ndef resolve_environment_python(env_dir: Path) -> Path:\n    candidates = environment_python_candidates(env_dir)\n    for candidate in candidates:\n        if candidate.exists():\n            return candidate\n    # For error reporting before creation has finished, prefer the layout that\n    # matches the environment marker.  Existing callers still verify exists().\n    env_dir = Path(env_dir)\n    if platform.system() == "Windows" and (env_dir / "conda-meta").exists():\n        return env_dir / "python.exe"\n    return candidates[-1]\n\n\ndef resolve_environment_root(python_path: Path) -> Path:\n    """Recover the environment root from either uv/venv or Conda Python."""\n    python_path = Path(python_path)\n    parent = python_path.parent\n    if platform.system() == "Windows":\n        return parent.parent if parent.name.lower() == "scripts" else parent\n    return parent.parent if parent.name == "bin" else parent\n\n\ndef environment_path_entries(env_dir: Path, env_tool: str) -> list[Path]:\n    """Return PATH entries needed to execute tools from a managed env."""\n    env_dir = Path(env_dir)\n    if platform.system() != "Windows":\n        candidates = [env_dir / "bin"]\n    elif env_tool == "conda":\n        # Mirrors the important parts of ``conda activate`` on Windows.\n        candidates = [\n            env_dir,\n            env_dir / "Library" / "mingw-w64" / "bin",\n            env_dir / "Library" / "usr" / "bin",\n            env_dir / "Library" / "bin",\n            env_dir / "Scripts",\n            env_dir / "bin",\n        ]\n    else:\n        candidates = [env_dir / "Scripts"]\n\n    result: list[Path] = []\n    seen: set[str] = set()\n    for candidate in candidates:\n        key = os.path.normcase(os.path.abspath(str(candidate)))\n        if candidate.exists() and key not in seen:\n            seen.add(key)\n            result.append(candidate)\n    return result\n\n\ndef _python_in_env_dir(env_dir: Path) -> Path:\n    # Backward-compatible private alias used by the lifecycle implementation.\n    return resolve_environment_python(env_dir)\n\n\ndef _bin_dir(env_dir: Path) -> Path:\n    return env_dir / ("Scripts" if platform.system() == "Windows" else "bin")\n'''
    text = replace_once(text, old, new, "environment helpers")

    old = '''def _runtime_command(python_path: Path, module: str) -> list[str]:\n    env_dir = python_path.parent.parent\n'''
    new = '''def _runtime_command(python_path: Path, module: str) -> list[str]:\n    env_dir = resolve_environment_root(python_path)\n'''
    text = replace_once(text, old, new, "runtime env root")

    old = '''        module = "pdf2zh_next" if engine == "pdf2zh_next" else "pdf2zh"\n        env_dir = python_path.parent.parent\n        executable = _bin_dir(env_dir) / (\n'''
    new = '''        module = "pdf2zh_next" if engine == "pdf2zh_next" else "pdf2zh"\n        env_dir = resolve_environment_root(python_path)\n        executable = _bin_dir(env_dir) / (\n'''
    text = replace_once(text, old, new, "validation env root")

    path.write_text(text, encoding="utf-8")


def patch_venv() -> None:
    path = ROOT / "server" / "utils" / "venv.py"
    text = path.read_text(encoding="utf-8")

    old = '''from utils.environment_lifecycle import ENGINE_ENV_NAMES\nfrom utils.environment_lifecycle import find_conda_env_path\nfrom utils.environment_lifecycle import find_existing_environment\nfrom utils.environment_lifecycle import load_requirements\n'''
    new = '''from utils.environment_lifecycle import ENGINE_ENV_NAMES\nfrom utils.environment_lifecycle import environment_path_entries\nfrom utils.environment_lifecycle import find_conda_env_path\nfrom utils.environment_lifecycle import find_existing_environment\nfrom utils.environment_lifecycle import load_requirements\nfrom utils.environment_lifecycle import resolve_environment_python\n'''
    text = replace_once(text, old, new, "venv imports")

    old = '''            if env_tool == "uv":\n                env_dir = Path(__file__).resolve().parent.parent / expected\n                python_path = env_dir / (\n                    "Scripts/python.exe" if self.is_windows else "bin/python"\n                )\n                if python_path.exists():\n                    return env_tool, env_dir, python_path\n            elif env_tool == "conda":\n                env_dir = find_conda_env_path(expected)\n                if env_dir:\n                    python_path = env_dir / (\n                        "Scripts/python.exe" if self.is_windows else "bin/python"\n                    )\n                    if python_path.exists():\n                        return env_tool, env_dir, python_path\n'''
    new = '''            if env_tool == "uv":\n                env_dir = Path(__file__).resolve().parent.parent / expected\n                python_path = resolve_environment_python(env_dir)\n                if python_path.exists():\n                    return env_tool, env_dir, python_path\n            elif env_tool == "conda":\n                env_dir = find_conda_env_path(expected)\n                if env_dir:\n                    python_path = resolve_environment_python(env_dir)\n                    if python_path.exists():\n                        return env_tool, env_dir, python_path\n'''
    text = replace_once(text, old, new, "custom environment discovery")

    old = '''        _, env_dir, python_path = existing\n        bin_dir = env_dir / ("Scripts" if self.is_windows else "bin")\n\n        if command[0].lower() in {"pdf2zh", "pdf2zh_next"}:\n            executable = bin_dir / (command[0] + (".exe" if self.is_windows else ""))\n'''
    new = '''        _, env_dir, python_path = existing\n        bin_dir = env_dir / ("Scripts" if self.is_windows else "bin")\n\n        if command[0].lower() in {"pdf2zh", "pdf2zh_next"}:\n            executable = bin_dir / (command[0] + (".exe" if self.is_windows else ""))\n'''
    # This block stays textually the same; keep it as an anchor for the PATH patch below.
    if text.count(old) != 1:
        raise RuntimeError("resolved command anchor not found")

    old = '''        env = os.environ.copy()\n        env["PYTHONUNBUFFERED"] = "1"\n        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")\n        return final_cmd, env\n'''
    new = '''        env = os.environ.copy()\n        env["PYTHONUNBUFFERED"] = "1"\n        path_entries = environment_path_entries(env_dir, self.curr_envtool)\n        if not path_entries:\n            path_entries = [bin_dir]\n        env["PATH"] = os.pathsep.join(\n            [str(value) for value in path_entries] + [env.get("PATH", "")]\n        ).rstrip(os.pathsep)\n        return final_cmd, env\n'''
    text = replace_once(text, old, new, "managed PATH")

    path.write_text(text, encoding="utf-8")


def patch_ci() -> None:
    path = ROOT / ".github" / "workflows" / "ci.yml"
    text = path.read_text(encoding="utf-8")
    marker = "    lint:\n"
    if "windows-conda-paths:" in text:
        return
    block = '''    windows-conda-paths:\n        runs-on: windows-latest\n        steps:\n            - name: Checkout\n              uses: actions/checkout@v4\n\n            - name: Setup Python\n              uses: actions/setup-python@v5\n              with:\n                  python-version: '3.12'\n\n            - name: Test Windows uv and Conda environment layouts\n              shell: pwsh\n              env:\n                  PYTHONPATH: server\n              run: |\n                  @'\n                  import os\n                  import tempfile\n                  from pathlib import Path\n                  from utils.environment_lifecycle import environment_path_entries\n                  from utils.environment_lifecycle import resolve_environment_python\n                  from utils.environment_lifecycle import resolve_environment_root\n                  from utils.venv import VirtualEnvManager\n\n                  with tempfile.TemporaryDirectory() as temp:\n                      root = Path(temp)\n\n                      uv_dir = root / 'uv-env'\n                      uv_python = uv_dir / 'Scripts' / 'python.exe'\n                      uv_python.parent.mkdir(parents=True)\n                      uv_python.touch()\n                      assert resolve_environment_python(uv_dir) == uv_python\n                      assert resolve_environment_root(uv_python) == uv_dir\n\n                      conda_dir = root / 'conda-env'\n                      conda_python = conda_dir / 'python.exe'\n                      (conda_dir / 'conda-meta').mkdir(parents=True)\n                      (conda_dir / 'Scripts').mkdir(parents=True)\n                      (conda_dir / 'Library' / 'bin').mkdir(parents=True)\n                      conda_python.touch()\n                      cli = conda_dir / 'Scripts' / 'pdf2zh_next.exe'\n                      cli.touch()\n\n                      assert resolve_environment_python(conda_dir) == conda_python\n                      assert resolve_environment_root(conda_python) == conda_dir\n                      path_entries = environment_path_entries(conda_dir, 'conda')\n                      assert conda_dir in path_entries\n                      assert conda_dir / 'Scripts' in path_entries\n                      assert conda_dir / 'Library' / 'bin' in path_entries\n\n                      names={'pdf2zh':'zotero-pdf2zh-venv','pdf2zh_next':'zotero-pdf2zh-next-venv'}\n                      manager = VirtualEnvManager('missing.json', names, 'conda', skip_install=True)\n                      manager.curr_envtool = 'conda'\n                      manager.curr_envname = names['pdf2zh_next']\n                      manager.ensure_env = lambda engine: True\n                      manager._existing = lambda engine, tool: ('conda', conda_dir, conda_python)\n                      final_cmd, env = manager._resolved_command(['pdf2zh_next', '--version'])\n                      assert Path(final_cmd[0]) == cli\n                      effective_path = env['PATH'].split(os.pathsep)\n                      assert str(conda_dir) in effective_path\n                      assert str(conda_dir / 'Scripts') in effective_path\n                      assert str(conda_dir / 'Library' / 'bin') in effective_path\n\n                  print('Windows uv/Conda path semantics OK')\n                  '@ | python -\n\n'''
    if text.count(marker) != 1:
        raise RuntimeError("CI lint marker not found")
    text = text.replace(marker, block + marker, 1)
    path.write_text(text, encoding="utf-8")


patch_environment_lifecycle()
patch_venv()
patch_ci()
print("Windows Conda environment hotfix applied")
