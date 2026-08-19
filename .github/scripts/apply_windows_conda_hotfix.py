from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing patch anchor: {label}")
    return text.replace(old, new, 1)


# Windows Conda interpreter/PATH layout is already fixed on the review branch.
# This patch adds the second invariant: a failed optional update must not disable
# the old environment when that runtime is still healthy.
venv_path = Path("server/utils/venv.py")
venv = venv_path.read_text(encoding="utf-8")
venv = replace_once(
    venv,
    '''            if self.install_packages(engine, repair_tool):\n                return True\n            print("⚠️ 安全修复失败；不会自动切换到另一个环境管理工具。")\n            return False\n''',
    '''            if self.install_packages(engine, repair_tool):\n                return True\n\n            # Updating/repairing is a maintenance action. If the transactional\n            # attempt fails, re-discover the original environment and keep using\n            # it whenever it is still healthy. A failed update must not turn a\n            # previously working runtime into a translation outage.\n            restored = self._existing(engine, repair_tool)\n            if restored and self._requirements_ok(\n                engine, repair_tool, restored[2]\n            ):\n                self._remember_environment(engine, repair_tool, restored[1])\n                print(\n                    f"⚠️ {repair_tool} 安全更新失败，但原有 {engine} 环境仍可用；"\n                    "本次继续使用原环境。"\n                )\n                return True\n\n            print("⚠️ 安全修复失败；不会自动切换到另一个环境管理工具。")\n            return False\n''',
    "repair fallback",
)
venv_path.write_text(venv, encoding="utf-8")
print("Windows conda update-fallback hotfix applied")
