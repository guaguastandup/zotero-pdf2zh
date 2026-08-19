import re
from pathlib import Path

venv_path = Path("server/utils/venv.py")
venv = venv_path.read_text(encoding="utf-8")

if "安全更新失败，但原有" in venv:
    print("Fallback already present")
else:
    pattern = re.compile(
        r'''(?P<indent>\s{12})if self\.install_packages\(engine, repair_tool\):\s*\n'''
        r'''(?P=indent)    return True\s*\n'''
        r'''(?P=indent)print\("⚠️ 安全修复失败；不会自动切换到另一个环境管理工具。"\)\s*\n'''
        r'''(?P=indent)return False'''
    )
    match = pattern.search(venv)
    if not match:
        raise RuntimeError("could not locate repair-failure block in ensure_env")
    indent = match.group("indent")
    replacement = f'''{indent}if self.install_packages(engine, repair_tool):\n{indent}    return True\n\n{indent}# Updating/repairing is a maintenance action. If the transactional\n{indent}# attempt fails, re-discover the original environment and keep using\n{indent}# it whenever it is still healthy. A failed update must not turn a\n{indent}# previously working runtime into a translation outage.\n{indent}restored = self._existing(engine, repair_tool)\n{indent}if restored and self._requirements_ok(\n{indent}    engine, repair_tool, restored[2]\n{indent}):\n{indent}    self._remember_environment(engine, repair_tool, restored[1])\n{indent}    print(\n{indent}        f"⚠️ {{repair_tool}} 安全更新失败，但原有 {{engine}} 环境仍可用；"\n{indent}        "本次继续使用原环境。"\n{indent}    )\n{indent}    return True\n\n{indent}print("⚠️ 安全修复失败；不会自动切换到另一个环境管理工具。")\n{indent}return False'''
    venv = venv[: match.start()] + replacement + venv[match.end() :]
    venv_path.write_text(venv, encoding="utf-8")

print("Windows conda update-fallback hotfix applied")
