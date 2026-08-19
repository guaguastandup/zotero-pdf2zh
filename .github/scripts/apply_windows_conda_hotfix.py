from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing patch anchor: {label}")
    return text.replace(old, new, 1)


# The Windows Conda interpreter/PATH layout is already fixed on the review
# branch.  This migration adds the second safety invariant: a failed optional
# repair/update must not disable the old environment when it is still healthy.
venv_path = Path("server/utils/venv.py")
venv = venv_path.read_text(encoding="utf-8")
venv = replace_once(
    venv,
    '''            if self.install_packages(engine, repair_tool):\n                return True\n            print("⚠️ 安全修复失败；不会自动切换到另一个环境管理工具。")\n            return False\n''',
    '''            if self.install_packages(engine, repair_tool):\n                return True\n\n            # Updating/repairing is a maintenance action.  If the transactional\n            # attempt fails, re-discover the original environment and keep using\n            # it whenever it is still healthy.  A failed update must not turn a\n            # previously working runtime into a translation outage.\n            restored = self._existing(engine, repair_tool)\n            if restored and self._requirements_ok(\n                engine, repair_tool, restored[2]\n            ):\n                self._remember_environment(engine, repair_tool, restored[1])\n                print(\n                    f"⚠️ {repair_tool} 安全更新失败，但原有 {engine} 环境仍可用；"\n                    "本次继续使用原环境。"\n                )\n                return True\n\n            print("⚠️ 安全修复失败；不会自动切换到另一个环境管理工具。")\n            return False\n''',
    "repair fallback",
)
venv_path.write_text(venv, encoding="utf-8")

ci_path = Path(".github/workflows/ci.yml")
ci = ci_path.read_text(encoding="utf-8")
anchor = '''                  assert auto.ensure_env('pdf2zh')\n                  assert auto.curr_envtool == 'conda'\n                  print('Environment manager semantics OK')\n'''
replacement = '''                  assert auto.ensure_env('pdf2zh')\n                  assert auto.curr_envtool == 'conda'\n\n                  # A failed optional repair/update must fall back to the same\n                  # old environment when that runtime remains healthy.\n                  fallback = VirtualEnvManager('missing.json', names, 'conda', skip_install=True)\n                  fallback.skip_install = False\n                  old_conda = ('conda', Path('/tmp/old-conda'), Path(sys.executable))\n                  fallback._existing = lambda engine, tool: old_conda\n                  checks = iter([False, True])\n                  fallback._requirements_ok = lambda *args: next(checks)\n                  fallback.install_packages = lambda *args, **kwargs: False\n                  assert fallback.ensure_env('pdf2zh_next')\n                  assert fallback.curr_envtool == 'conda'\n\n                  # Windows-specific interpreter/PATH semantics are covered by\n                  # .github/workflows/windows-env-ci.yml on windows-latest.\n                  windows_ci = Path('.github/workflows/windows-env-ci.yml').read_text(encoding='utf-8')\n                  assert 'conda_python = conda_dir / \'python.exe\'' in windows_ci\n                  assert "runs-on: windows-latest" in windows_ci\n                  print('Environment manager semantics OK')\n'''
ci = replace_once(ci, anchor, replacement, "CI environment semantics")
ci_path.write_text(ci, encoding="utf-8")

print("Windows conda update-fallback hotfix applied")
