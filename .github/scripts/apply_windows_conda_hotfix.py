from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing patch anchor: {label}")
    return text.replace(old, new, 1)


lifecycle_path = Path("server/utils/environment_lifecycle.py")
lifecycle = lifecycle_path.read_text(encoding="utf-8")

lifecycle = replace_once(
    lifecycle,
    '''def _python_in_env_dir(env_dir: Path) -> Path:\n    if platform.system() == "Windows":\n        return env_dir / "Scripts" / "python.exe"\n    return env_dir / "bin" / "python"\n''',
    '''def _python_in_env_dir(env_dir: Path, env_tool: str = "uv") -> Path:\n    """Return the interpreter path for a managed environment.\n\n    Windows virtualenv/uv environments place Python under ``Scripts``, while\n    conda environments place ``python.exe`` at the environment root.  Keeping\n    this distinction here prevents a healthy historical conda environment from\n    being mistaken for a missing/broken environment.\n    """\n    if platform.system() == "Windows":\n        if env_tool == "conda":\n            return env_dir / "python.exe"\n        return env_dir / "Scripts" / "python.exe"\n    return env_dir / "bin" / "python"\n''',
    "python path helper",
)

lifecycle = replace_once(
    lifecycle,
    '''        python_path = _python_in_env_dir(env_dir)\n        if python_path.exists():\n            return "uv", env_dir, python_path\n''',
    '''        python_path = _python_in_env_dir(env_dir, "uv")\n        if python_path.exists():\n            return "uv", env_dir, python_path\n''',
    "uv existing path",
)

lifecycle = replace_once(
    lifecycle,
    '''            python_path = _python_in_env_dir(env_dir)\n            if python_path.exists():\n                return "conda", env_dir, python_path\n''',
    '''            python_path = _python_in_env_dir(env_dir, "conda")\n            if python_path.exists():\n                return "conda", env_dir, python_path\n''',
    "conda existing path",
)

lifecycle = replace_once(
    lifecycle,
    '''    python_path = _python_in_env_dir(path)\n    if not python_path.exists():\n        raise RuntimeError(f"uv 环境没有生成 Python 可执行文件: {path}")\n''',
    '''    python_path = _python_in_env_dir(path, "uv")\n    if not python_path.exists():\n        raise RuntimeError(f"uv 环境没有生成 Python 可执行文件: {path}")\n''',
    "uv staging path",
)

lifecycle = replace_once(
    lifecycle,
    '''    python_path = _python_in_env_dir(staging_dir)\n    if not python_path.exists():\n        raise RuntimeError("staging conda 环境没有 Python 可执行文件")\n''',
    '''    python_path = _python_in_env_dir(staging_dir, "conda")\n    if not python_path.exists():\n        raise RuntimeError(\n            f"staging conda 环境没有 Python 可执行文件: {python_path}"\n        )\n''',
    "conda staging path",
)

lifecycle = replace_once(
    lifecycle,
    '''        final_python = _python_in_env_dir(final_dir)\n        if not validate_environment(\n''',
    '''        final_python = _python_in_env_dir(final_dir, "conda")\n        if not validate_environment(\n''',
    "conda activated path",
)

lifecycle_path.write_text(lifecycle, encoding="utf-8")

venv_path = Path("server/utils/venv.py")
venv = venv_path.read_text(encoding="utf-8")
venv = replace_once(
    venv,
    '''            if self.install_packages(engine, repair_tool):\n                return True\n            print("⚠️ 安全修复失败；不会自动切换到另一个环境管理工具。")\n            return False\n''',
    '''            if self.install_packages(engine, repair_tool):\n                return True\n\n            # A maintenance/update failure must never invalidate a previously\n            # usable environment.  Re-discover it after the transactional\n            # attempt and continue with it when the old runtime is still healthy.\n            restored = self._existing(engine, repair_tool)\n            if restored and self._requirements_ok(\n                engine, repair_tool, restored[2]\n            ):\n                self._remember_environment(engine, repair_tool, restored[1])\n                print(\n                    f"⚠️ {repair_tool} 安全更新失败，但原有 {engine} 环境仍可用；"\n                    "本次继续使用原环境。"\n                )\n                return True\n\n            print("⚠️ 安全修复失败；不会自动切换到另一个环境管理工具。")\n            return False\n''',
    "repair fallback",
)
venv_path.write_text(venv, encoding="utf-8")

ci_path = Path(".github/workflows/ci.yml")
ci = ci_path.read_text(encoding="utf-8")
anchor = '''                  assert auto.ensure_env('pdf2zh')\n                  assert auto.curr_envtool == 'conda'\n                  print('Environment manager semantics OK')\n'''
replacement = '''                  assert auto.ensure_env('pdf2zh')\n                  assert auto.curr_envtool == 'conda'\n\n                  # Windows conda keeps python.exe at the environment root; uv\n                  # and virtualenv-style environments keep it under Scripts/.\n                  from utils import environment_lifecycle as lifecycle\n                  win_env = Path('C:/Users/test/miniconda3/envs/zotero-pdf2zh-next-venv')\n                  with patch.object(lifecycle.platform, 'system', return_value='Windows'):\n                      assert lifecycle._python_in_env_dir(win_env, 'conda') == win_env / 'python.exe'\n                      assert lifecycle._python_in_env_dir(win_env, 'uv') == win_env / 'Scripts' / 'python.exe'\n\n                  lifecycle_source = Path('server/utils/environment_lifecycle.py').read_text(encoding='utf-8')\n                  assert '_python_in_env_dir(env_dir, "conda")' in lifecycle_source\n                  assert '_python_in_env_dir(staging_dir, "conda")' in lifecycle_source\n                  assert '_python_in_env_dir(final_dir, "conda")' in lifecycle_source\n\n                  # If a transactional repair fails but the original runtime is\n                  # still healthy, translation must continue on that runtime.\n                  fallback = VirtualEnvManager('missing.json', names, 'conda', skip_install=True)\n                  fallback.skip_install = False\n                  old_conda = ('conda', Path('/tmp/old-conda'), Path(sys.executable))\n                  fallback._existing = lambda engine, tool: old_conda\n                  checks = iter([False, True])\n                  fallback._requirements_ok = lambda *args: next(checks)\n                  fallback.install_packages = lambda *args, **kwargs: False\n                  assert fallback.ensure_env('pdf2zh_next')\n                  assert fallback.curr_envtool == 'conda'\n                  print('Environment manager semantics OK')\n'''
ci = replace_once(ci, anchor, replacement, "CI environment semantics")
ci_path.write_text(ci, encoding="utf-8")

print("Windows conda v4.1.0 hotfix applied")
