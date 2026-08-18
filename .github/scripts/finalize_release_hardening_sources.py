from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'{path}: expected block not found')
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected one block, found {text.count(old)}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


old = '''        # Prefer an already usable environment even when it is older than the
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
'''
new = '''        # Discover first, mutate second. In auto mode a healthy existing conda
        # environment must be usable even if an unrelated uv environment is
        # broken. Only after all existing candidates have been checked do we
        # select one candidate for transactional repair.
        repair_candidates = []
        for envtool in self._preferred_tools():
            existing = self._existing(engine, envtool)
            if not existing:
                continue
            if self.skip_install or self._requirements_ok(engine, envtool, existing[2]):
                self._remember_environment(engine, envtool, existing[1])
                print(f"✅ 使用 {envtool} 环境: {existing[1]}")
                return True
            repair_candidates.append((envtool, existing))

        if self.skip_install:
'''
replace_once('server/utils/venv.py', old, new)

old = '''        # New user / no usable env. Auto chooses one manager once (uv
        # preferred) and never switches managers because an installation failed.
        tools = self._install_tools()
'''
new = '''        if repair_candidates:
            repair_tool, _ = repair_candidates[0]
            print(f"🔧 检测到 {repair_tool} 环境不完整，将通过 staging 安全修复。")
            if self.install_packages(engine, repair_tool):
                return True
            print("⚠️ 安全修复失败；不会自动切换到另一个环境管理工具。")
            return False

        # New user / no existing managed env. Auto chooses exactly one manager
        # (uv preferred) and never switches because an installation failed.
        tools = self._install_tools()
'''
replace_once('server/utils/venv.py', old, new)

replace_once(
    'server/utils/venv.py',
    'print("如需改用另一环境工具，请显式传入 --env_tool=conda 或 --env_tool=auto。")',
    'print("如需强制指定环境工具，请显式传入 --env_tool=uv 或 --env_tool=conda。")',
)

p = Path('server/config/config.toml.example')
text = p.read_text(encoding='utf-8')
comment = '''# Schema baseline: pdf2zh_next 2.9.0. Zotero PDF2zh intentionally keeps
# product-safe defaults (for example DeepSeek V4 instead of deprecated aliases,
# no-watermark output, and zh-CN target language) rather than copying every
# upstream runtime default verbatim.
'''
if not text.startswith('# Schema baseline:'):
    p.write_text(comment + text, encoding='utf-8')

p = Path('docs/zh/guide/package-update.md')
text = p.read_text(encoding='utf-8')
needle = '''python update_packages.py --network-timeout 8
```
'''
if 'python update_packages.py --env-tool conda' not in text:
    text = text.replace(needle, needle + '''
如果要强制指定环境管理工具：

```shell
python update_packages.py --env-tool uv
python update_packages.py --env-tool conda
```
''')
text = text.replace(
    '检查源码版本。源码更新与 Python 翻译环境更新仍然是两个独立动作。',
    'GitHub 更新会使用对应版本的 Release `server.zip`，并在覆盖本地文件前校验下载到的 Server 版本。源码更新与 Python 翻译环境更新仍然是两个独立动作。',
)
p.write_text(text, encoding='utf-8')

print('final source refinements applied')
