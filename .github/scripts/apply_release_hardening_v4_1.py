from pathlib import Path
import re


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, name: str) -> str:
    if old not in text:
        raise SystemExit(f"{name}: expected text not found")
    if text.count(old) != 1:
        raise SystemExit(f"{name}: expected one match, found {text.count(old)}")
    return text.replace(old, new, 1)


def replace_regex(text: str, pattern: str, repl: str, name: str, flags=0) -> str:
    result, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"{name}: expected one regex match, found {count}")
    return result


# ---------------------------------------------------------------------------
# P0: existing environment health must never execute heavy pdf2zh_next --help.
# P1: auto means preserve an existing manager; a fresh install selects one
#     manager once (uv preferred) and never falls through after install failure.
# ---------------------------------------------------------------------------
path = "server/utils/venv.py"
text = read(path)
text = replace_regex(
    text,
    r'''\n            if engine == "pdf2zh_next":\n                runtime = subprocess\.run\(\n                    \[str\(python_path\), "-m", "pdf2zh_next", "--help"\],\n                    capture_output=True,\n                    text=True,\n                    timeout=60,\n                \)\n                if runtime\.returncode != 0:\n                    print\("⚠️ 现有 pdf2zh_next 环境无法正常启动。"\)\n                    return False\n            return True''',
    '''\n            # Package presence is sufficient for an existing environment health
            # check.  Never launch ``pdf2zh_next --help`` here: pdf2zh_next 2.9
            # imports BabelDOC/high-level modules before CLI parsing, so --help is
            # a heavyweight operation and can exceed a minute on otherwise
            # healthy machines.  Capability checks are handled statically by
            # environment_lifecycle.runtime_supports_deepseek_thinking().
            return True''',
    "remove existing-runtime --help probe",
)
needle = '''    def _preferred_index(self) -> str | None:\n'''
insert = '''    def _install_tools(self) -> list[str]:
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

'''
if insert not in text:
    text = replace_once(text, needle, insert + needle, "insert install tool selector")
old = '''        # New user / no usable env. Explicit uv/conda never silently switches
        # package managers. Only `auto` can try the second manager.
        tools = self._preferred_tools()
        for index, envtool in enumerate(tools):
            if not self.check_envtool(envtool):
                continue
            print(f"🔧 首次创建 {engine} 环境，将使用 {envtool} staging 安装。")
            if self.install_packages(engine, envtool):
                return True
            if index + 1 < len(tools):
                print(f"⚠️ {envtool} 首次安装失败，auto 模式将尝试下一个环境工具。")
            else:
                print(f"⚠️ {envtool} 首次安装失败；不会自动切换到其他环境工具。")
'''
new = '''        # New user / no usable env. Auto chooses one manager once (uv
        # preferred) and never switches managers because an installation failed.
        tools = self._install_tools()
        for envtool in tools:
            if not self.check_envtool(envtool):
                continue
            print(f"🔧 首次创建 {engine} 环境，将使用 {envtool} staging 安装。")
            if self.install_packages(engine, envtool):
                return True
            print(f"⚠️ {envtool} 首次安装失败；不会自动切换到其他环境工具。")
'''
text = replace_once(text, old, new, "fresh install manager semantics")
text = text.replace(
    "Cross-tool discovery/fallback is allowed only\n    when the caller explicitly selects ``auto``. The Server default remains uv.",
    "``auto`` only discovers an existing manager; for a fresh install it picks\n    one manager (uv preferred) and never falls through after failure. The Server\n    default is auto so historical conda users are retained transparently.",
)
write(path, text)


# ---------------------------------------------------------------------------
# P0/P1: Server upload security, localhost binding, accurate env discovery,
#         and LR dual Crop -> real dual-cut.
# ---------------------------------------------------------------------------
path = "server/server.py"
text = read(path)
if "from utils.environment_lifecycle import find_existing_environment" not in text:
    text = replace_once(
        text,
        "from utils.venv import VirtualEnvManager\n",
        "from utils.venv import VirtualEnvManager\nfrom utils.environment_lifecycle import find_existing_environment\n",
        "server environment discovery import",
    )
text = replace_once(
    text,
    "default_env_tool = 'uv' # 默认使用uv管理venv",
    "default_env_tool = 'auto' # 自动沿用已有 uv/conda；新环境优先 uv",
    "server default env tool",
)
old_process = '''    def process_request(self):
        data = request.get_json() # 获取请求的data
        config = Config(data)

        file_content = data.get('fileContent', '')
        if file_content.startswith('data:application/pdf;base64,'):
            file_content = file_content[len('data:application/pdf;base64,'):]

        input_path = os.path.join(output_folder, data['fileName'])
        with open(input_path, 'wb') as f:
            f.write(base64.b64decode(file_content))

        # input_path表示保存的pdf源文件路径
        return input_path, config
'''
new_process = '''    @staticmethod
    def _safe_upload_filename(raw_name):
        if not isinstance(raw_name, str):
            raise ValueError("Invalid PDF filename")
        name = raw_name.strip()
        if (
            not name
            or name in {'.', '..'}
            or '/' in name
            or '\\\\' in name
            or os.path.basename(name) != name
        ):
            raise ValueError("Invalid PDF filename")
        if not name.lower().endswith('.pdf'):
            raise ValueError("Only PDF uploads are accepted")
        return name

    def process_request(self):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON request")
        config = Config(data)

        file_name = self._safe_upload_filename(data.get('fileName'))
        base = os.path.abspath(output_folder)
        input_path = os.path.abspath(os.path.join(base, file_name))
        try:
            if os.path.commonpath([base, input_path]) != base:
                raise ValueError("Invalid PDF filename")
        except ValueError:
            raise ValueError("Invalid PDF filename")

        file_content = data.get('fileContent', '')
        if not isinstance(file_content, str):
            raise ValueError("Invalid PDF content")
        if file_content.startswith('data:application/pdf;base64,'):
            file_content = file_content[len('data:application/pdf;base64,'):]
        try:
            decoded = base64.b64decode(file_content)
        except Exception as exc:
            raise ValueError(f"Invalid PDF content: {exc}") from exc

        with open(input_path, 'wb') as f:
            f.write(decoded)

        return input_path, config
'''
text = replace_once(text, old_process, new_process, "safe request upload")
old_crop = '''            if infile_type == 'dual' and self.get_dual_mode(input_path, config.dual_mode) == 'LR':
                _, new_path = self.cropper.pdf_dual_mode(input_path, 'LR', 'TB')
                if os.path.exists(new_path):
                    return jsonify({'status': 'success', 'fileList': [os.path.basename(new_path)]}), 200
                return jsonify({'status': 'error', 'message': f'Crop LR->TB failed: {new_path} not found'}), 500

            new_type = self.get_filetype_after_crop(input_path)
'''
new_crop = '''            source_path = input_path
            if infile_type == 'dual' and self.get_dual_mode(input_path, config.dual_mode) == 'LR':
                # Crop means a crop result, not merely a layout conversion.
                # Normalize LR -> alternating-page TB internally, then continue
                # through the normal dual -> dual-cut operation.
                _, source_path = self.cropper.pdf_dual_mode(input_path, 'LR', 'TB')

            new_type = self.get_filetype_after_crop(input_path)
'''
text = replace_once(text, old_crop, new_crop, "LR crop continues to dual-cut")
text = replace_once(
    text,
    "            self.cropper.crop_pdf(config, input_path, infile_type, new_path, new_type)\n            print(f\"🔍 [Zotero PDF2zh Server] 开始裁剪文件: {input_path}, {infile_type}, 裁剪类型: {new_type}, {new_path}\")",
    "            self.cropper.crop_pdf(config, source_path, infile_type, new_path, new_type)\n            print(f\"🔍 [Zotero PDF2zh Server] 开始裁剪文件: {source_path}, {infile_type}, 裁剪类型: {new_type}, {new_path}\")",
    "crop normalized source",
)
text = replace_once(
    text,
    "    def run(self, port, debug=False):\n        print(f\"🌐 Server将启动在: http://localhost:{port}\")",
    "    def run(self, host, port, debug=False):\n        print(f\"🌐 Server将启动在: http://{host}:{port}\")",
    "server run host signature",
)
text = replace_once(
    text,
    "        self.app.run(host='0.0.0.0', port=port, debug=debug)",
    "        self.app.run(host=host, port=port, debug=debug)",
    "localhost bind",
)
text = replace_once(
    text,
    "    parser.add_argument('--port', type=int, default=PORT, help='Port to run the server on')\n",
    "    parser.add_argument('--host', type=str, default='127.0.0.1', help='Server bind host; use 0.0.0.0 only when remote access is intentionally required')\n    parser.add_argument('--port', type=int, default=PORT, help='Port to run the server on')\n",
    "host CLI argument",
)
text = replace_once(
    text,
    "    parser.add_argument('--env_tool', type=str, default=default_env_tool, help='虚拟环境管理工具, 默认使用 uv')",
    "    parser.add_argument('--env_tool', choices=['auto', 'uv', 'conda'], default=default_env_tool, help='环境管理工具；auto 会沿用已有 uv/conda，新环境优先 uv')",
    "env tool CLI",
)
text = replace_once(
    text,
    "    translator.run(args.port, debug=args.debug)",
    "    translator.run(args.host, args.port, debug=args.debug)",
    "run call host",
)
start = "    # 4.4 虚拟环境检查\n"
end = "    # 检查总结\n"
start_i = text.find(start)
end_i = text.find(end, start_i)
if start_i < 0 or end_i < 0:
    raise SystemExit("server env check block markers not found")
new_env_check = '''    # 4.4 虚拟环境检查
    if args.enable_venv:
        print("\\n--- 虚拟环境检查 ---")
        print(f"🔧 环境管理模式: {args.env_tool}")
        if args.env_tool == 'auto':
            print("💡 auto: 优先沿用已有 uv/conda；没有已有环境时优先创建 uv。")

        found = []
        for engine_name in (pdf2zh, pdf2zh_next):
            existing = find_existing_environment(engine_name, args.env_tool)
            if existing:
                tool, env_dir, _ = existing
                found.append(engine_name)
                print(f"✅ {engine_name}: {tool} -> {env_dir}")
            else:
                print(f"ℹ️ {engine_name}: 暂无托管环境，首次使用时将通过 staging 安全创建。")
        if not found:
            print("💡 尚未创建翻译环境；Server 本身可以先正常启动。")

'''
text = text[:start_i] + new_env_check + text[end_i:]
write(path, text)


# ---------------------------------------------------------------------------
# P0: redact secret-like extraData in Server logs.
# ---------------------------------------------------------------------------
path = "server/utils/config.py"
text = read(path)
helper = '''
def _safe_log_value(key, value):
    name = str(key or '').lower()
    if any(token in name for token in ('key', 'token', 'secret', 'password', 'auth')):
        raw = str(value or '')
        if not raw:
            return ''
        return ('*' * 8 + raw[-4:]) if len(raw) > 4 else ('*' * len(raw))
    return value

'''
if "def _safe_log_value" not in text:
    text = replace_once(text, "pdf2zh_next = 'pdf2zh_next'\n", "pdf2zh_next = 'pdf2zh_next'\n" + helper, "secret log helper")
text = text.replace(
    'print(f"✏️ 更新 extraData: {key} = {value}")',
    'print(f"✏️ 更新 extraData: {key} = {_safe_log_value(key, value)}")',
)
write(path, text)


# ---------------------------------------------------------------------------
# P0/P1: plugin log redaction, batch correctness/listener lifecycle, localization.
# ---------------------------------------------------------------------------
path = "plugin/src/modules/pdf2zhFileProcessor.ts"
text = read(path)
text = replace_once(
    text,
    '''    addEventListener(listener: (event: string, data: any) => void) {
        this.eventListeners.push(listener);
    }
''',
    '''    addEventListener(listener: (event: string, data: any) => void) {
        this.eventListeners.push(listener);
        return () => {
            this.eventListeners = this.eventListeners.filter(
                (candidate) => candidate !== listener,
            );
        };
    }
''',
    "listener disposer",
)
text = replace_once(
    text,
    "        this.eventListeners.forEach((listener) => {",
    "        [...this.eventListeners].forEach((listener) => {",
    "listener stable iteration",
)
write(path, text)

path = "plugin/src/modules/pdf2zhHelper.ts"
text = read(path)
text = replace_once(
    text,
    '            ztoolkit.getGlobal("alert")("请先选择一个条目或附件。");',
    '            ztoolkit.getGlobal("alert")(getString("operation-error-no-selection"));',
    "no selection localization",
)
text = replace_once(
    text,
    '''                const message =
                    error instanceof Error ? error.message : "未知错误";
                ztoolkit.getGlobal("alert")(`错误: ${message}`);
''',
    '''                const message =
                    error instanceof Error
                        ? error.message
                        : getString("operation-error-unknown");
                ztoolkit.getGlobal("alert")(
                    getString("operation-error-prefix", {
                        args: { message },
                    }),
                );
''',
    "task validation localization",
)
text = replace_once(
    text,
    '''        const fileProcessor = FileProcessor.getInstance();
        fileProcessor.addEventListener((event, data) => {
            switch (event) {
                case "batchStarted":
                    progressWindow.changeLine({
                        text: `开始处理 ${data.totalTasks} 个文件...`,
                        type: "default",
                        progress: 0,
                    });
                    break;
                case "batchCompleted":
                    progressWindow.changeLine({
                        text: `处理完成！成功: ${data.succeeded}, 失败: ${data.failed}`,
                        type: data.failed > 0 ? "error" : "success",
                        progress: 100,
                    });
                    break;
            }
        });
        // 处理任务
        await fileProcessor.processBatch(tasks);
''',
    '''        const fileProcessor = FileProcessor.getInstance();
        const removeListener = fileProcessor.addEventListener((event, data) => {
            switch (event) {
                case "batchStarted":
                    progressWindow.changeLine({
                        text: getString("operation-batch-started", {
                            args: { count: data.totalTasks },
                        }),
                        type: "default",
                        progress: 0,
                    });
                    break;
                case "batchCompleted":
                    progressWindow.changeLine({
                        text: getString("operation-batch-completed", {
                            args: {
                                succeeded: data.succeeded,
                                failed: data.failed,
                            },
                        }),
                        type: data.failed > 0 ? "error" : "success",
                        progress: 100,
                    });
                    break;
            }
        });
        try {
            await fileProcessor.processBatch(tasks);
        } finally {
            removeListener();
        }
''',
    "batch localization and listener cleanup",
)
text = replace_once(
    text,
    '''        } catch (error) {
            ztoolkit.log(`处理单个文件失败: ${fileName}, 错误: ${error}`);
            ztoolkit.getGlobal("alert")(
                `处理单个文件失败: ${fileName}\\n错误信息: ${error}`,
            );
        }
''',
    '''        } catch (error) {
            ztoolkit.log(`处理单个文件失败: ${fileName}, 错误: ${error}`);
            const message =
                error instanceof Error
                    ? error.message
                    : getString("operation-error-unknown");
            ztoolkit.getGlobal("alert")(
                getString("operation-error-single-file", {
                    args: { fileName, message },
                }),
            );
            // FileProcessor owns batch success/failure accounting. Propagate the
            // error after showing the per-file message so a failed task is not
            // counted as success.
            throw error;
        }
''',
    "batch error propagation",
)
text = text.replace(
    '                ztoolkit.log("llmApiConfig", llmApiConfig);\n',
    '                ztoolkit.log("llmApiConfig", {\n                    service: llmApiConfig.service,\n                    model: llmApiConfig.model,\n                    apiUrl: llmApiConfig.apiUrl,\n                    apiKey: llmApiConfig.apiKey ? "********" : "",\n                    extraDataKeys: Object.keys(llmApiConfig.extraData || {}),\n                });\n',
)
write(path, text)

locale_additions = {
    "plugin/addon/locale/zh-CN/addon.ftl": '''
operation-error-no-selection = 请先选择一个条目或 PDF 附件。
operation-error-unknown = 未知错误
operation-error-prefix = 错误：{ $message }
operation-error-single-file = 处理文件 { $fileName } 失败：{ $message }
operation-batch-started = 开始处理 { $count } 个文件...
operation-batch-completed = 处理完成！成功：{ $succeeded }，失败：{ $failed }
''',
    "plugin/addon/locale/en-US/addon.ftl": '''
operation-error-no-selection = Select an item or PDF attachment first.
operation-error-unknown = Unknown error
operation-error-prefix = Error: { $message }
operation-error-single-file = Failed to process { $fileName }: { $message }
operation-batch-started = Processing { $count } file(s)...
operation-batch-completed = Completed. Succeeded: { $succeeded }, failed: { $failed }
''',
}
for path, addition in locale_additions.items():
    text = read(path)
    if "operation-error-no-selection" not in text:
        text = text.rstrip() + "\n" + addition
    write(path, text)


# ---------------------------------------------------------------------------
# P1: automatic environment detection for normal maintenance commands.
# ---------------------------------------------------------------------------
for path in ("server/update_packages.py", "server/manage_packages.py"):
    text = read(path)
    text = text.replace('default="uv"', 'default="auto"')
    text = text.replace(
        "默认使用 uv，与 Server 默认行为一致；只有显式传入 conda 或 auto 时才会使用 conda / 跨工具探测。",
        "默认 auto：沿用已有 uv/conda；没有已有环境时优先 uv。显式指定 uv/conda 时严格使用所选工具。",
    )
    text = text.replace(
        "默认使用 uv；只有显式指定 conda 或 auto 时，才会使用 conda 或跨工具探测。",
        "默认 auto：沿用已有 uv/conda；没有已有环境时优先 uv。显式指定 uv/conda 时严格使用所选工具。",
    )
    text = text.replace(
        "The normal-user path follows the project's default environment manager: uv.\nConda or cross-tool auto-discovery must be selected explicitly.",
        "The normal-user path auto-detects an existing uv/conda environment.\nFor a fresh install uv is preferred; manager failures never trigger a silent switch.",
    )
    text = text.replace(
        "The normal/default environment manager is uv. Conda or cross-tool auto\nselection is only used when explicitly requested.",
        "The normal/default mode is auto: keep an existing uv/conda environment;\nfor a fresh install prefer uv. A failed install never silently switches managers.",
    )
    write(path, text)


# ---------------------------------------------------------------------------
# P0: rewrite Server source updater around versioned Release assets / tag
# archives and validate the downloaded Server version before touching files.
# ---------------------------------------------------------------------------
auto_update = r'''## auto_update.py
## Server source update helpers
import datetime
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile


OWNER = "guaguastandup"
REPO = "zotero-pdf2zh"


def _version_tuple(value):
    parts = re.findall(r"\d+", str(value or ""))
    return tuple(int(part) for part in parts[:4]) or (0,)


def _server_version_from_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return match.group(1) if match else None


def _download_first(urls, destination, label):
    last_error = None
    for url in urls:
        try:
            print(f"  - 尝试下载 {label}: {url}")
            urllib.request.urlretrieve(url, destination)
            print(f"  - ✅ {label} 下载完成")
            return url
        except Exception as exc:
            last_error = exc
            print(f"  - ⚠️ 下载失败，尝试下一来源: {exc}")
    raise RuntimeError(f"无法下载 {label}: {last_error}")


def get_xpi_info_from_repo(owner, repo, branch="main", expected_version=None, update_source="github"):
    """Return the versioned Release XPI when it can be verified.

    Zotero already supports plugin self-update, so failure here never blocks the
    Server update.  Do not use a raw-main XPI because it can disagree with the
    requested Server version.
    """
    if not expected_version:
        return None, None
    tag = f"v{expected_version}"
    target_filename = "zotero-pdf-2-zh.xpi"
    urls = []
    if update_source == "github":
        urls.append(
            f"https://github.com/{owner}/{repo}/releases/download/{tag}/{target_filename}"
        )
    else:
        # Gitee mirrors do not expose a stable GitHub-compatible release-asset
        # URL.  Avoid downloading an unversioned/raw XPI and let Zotero's own
        # updater handle the plugin.
        return None, None
    url = urls[0]
    try:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=30) as response:
            if 200 <= response.status < 400:
                return url, target_filename
    except Exception:
        pass
    return None, None


def smart_file_sync(source_dir, target_dir, stats, backup_dir, updated_files, new_files, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = []
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        rel_dir = os.path.relpath(root, source_dir)
        target_root = os.path.join(target_dir, rel_dir) if rel_dir != "." else target_dir
        os.makedirs(target_root, exist_ok=True)
        for file in files:
            source_file = os.path.join(root, file)
            target_file = os.path.join(target_root, file)
            rel_file_path = os.path.join(rel_dir, file) if rel_dir != "." else file
            if os.path.exists(target_file):
                with open(source_file, "rb") as sf, open(target_file, "rb") as tf:
                    same = sf.read() == tf.read()
                if same:
                    stats["unchanged"] += 1
                    continue
                backup_file = os.path.join(backup_dir, rel_file_path)
                os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                shutil.copy2(target_file, backup_file)
                shutil.copy2(source_file, target_file)
                stats["updated"] += 1
                updated_files.append(rel_file_path)
                print(f"    ✓ 更新: {rel_file_path}")
            else:
                shutil.copy2(source_file, target_file)
                stats["new"] += 1
                new_files.append(rel_file_path)
                print(f"    + 新增: {rel_file_path}")


def count_preserved_files(source_dir, target_dir, stats, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        rel_dir = os.path.relpath(root, target_dir)
        source_root = os.path.join(source_dir, rel_dir) if rel_dir != "." else source_dir
        for file in files:
            if not os.path.exists(os.path.join(source_root, file)):
                stats["preserved"] += 1


def _locate_server_source(temp_dir):
    candidates = []
    for root, _, files in os.walk(temp_dir):
        if "server.py" in files and os.path.basename(root) == "server":
            candidates.append(root)
    if not candidates:
        direct = os.path.join(temp_dir, "server.py")
        if os.path.exists(direct):
            return temp_dir
        raise RuntimeError("下载包中没有找到 server/server.py")
    return min(candidates, key=lambda path: len(os.path.relpath(path, temp_dir).split(os.sep)))


def _server_download_urls(owner, repo, expected_version, update_source):
    if not expected_version:
        return [f"https://github.com/{owner}/{repo}/releases/latest/download/server.zip"]
    tag = f"v{expected_version}"
    if update_source == "gitee":
        return [
            f"https://gitee.com/{owner}/{repo}/repository/archive/{tag}.zip",
            f"https://github.com/{owner}/{repo}/releases/download/{tag}/server.zip",
        ]
    return [f"https://github.com/{owner}/{repo}/releases/download/{tag}/server.zip"]


def perform_update_optimized(root_path, local_version, expected_version=None, update_source="github"):
    print("🚀 [自动更新] 开始安全同步 Server 源码...")
    owner, repo = OWNER, REPO
    project_root = os.path.dirname(root_path)
    exclude_directories = [
        "translated",
        "zotero-pdf2zh-next-venv",
        "zotero-pdf2zh-venv",
        "zotero-pdf2zh-next-venv.staging",
        "zotero-pdf2zh-venv.staging",
        "zotero-pdf2zh-next-venv.backup",
        "zotero-pdf2zh-venv.backup",
        "__pycache__",
    ]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(project_root, f"server_backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)
    archive_path = os.path.join(project_root, f"server_{expected_version or 'latest'}.zip")
    stats = {"updated": 0, "new": 0, "preserved": 0, "unchanged": 0}
    updated_files, new_files = [], []

    try:
        xpi_url, xpi_filename = get_xpi_info_from_repo(
            owner, repo, expected_version=expected_version, update_source=update_source
        )
        if xpi_url and xpi_filename:
            xpi_path = os.path.join(project_root, xpi_filename)
            try:
                _download_first([xpi_url], xpi_path, "插件 XPI")
                print(f"  - 📦 插件文件已保存: {xpi_path}")
            except Exception as exc:
                print(f"  - ⚠️ 插件下载失败，不影响 Server 更新: {exc}")

        _download_first(
            _server_download_urls(owner, repo, expected_version, update_source),
            archive_path,
            "Server 发布包",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            new_server_path = _locate_server_source(temp_dir)
            downloaded_version = _server_version_from_file(
                os.path.join(new_server_path, "server.py")
            )
            if expected_version and downloaded_version != expected_version:
                raise RuntimeError(
                    f"下载的 Server 版本不匹配: expected={expected_version}, got={downloaded_version}"
                )
            print(f"  - ✅ 已验证 Server 版本: {downloaded_version or 'unknown'}")
            smart_file_sync(
                new_server_path,
                root_path,
                stats,
                backup_path,
                updated_files,
                new_files,
                exclude_dirs=exclude_directories,
            )
            count_preserved_files(
                new_server_path,
                root_path,
                stats,
                exclude_dirs=exclude_directories,
            )

        print("\\n📊 同步统计:", stats)
        shutil.rmtree(backup_path, ignore_errors=True)
        if os.path.exists(archive_path):
            os.remove(archive_path)
        print("✅ Server 更新完成。请重新启动 server.py。")
        raise SystemExit(0)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"\\n❌ 更新失败: {exc}")
        print("  - 正在从备份回滚...")
        try:
            for rel_path in updated_files:
                backup_file = os.path.join(backup_path, rel_path)
                target_file = os.path.join(root_path, rel_path)
                if os.path.exists(backup_file):
                    os.makedirs(os.path.dirname(target_file), exist_ok=True)
                    shutil.copy2(backup_file, target_file)
            for rel_path in new_files:
                target_file = os.path.join(root_path, rel_path)
                if os.path.exists(target_file):
                    os.remove(target_file)
            print("  - ✅ 已回滚到更新前状态。")
        except Exception as rollback_error:
            print(f"  - ❌ 自动回滚失败: {rollback_error}")
            print(f"  - 💾 备份保留在: {backup_path}")
        raise SystemExit(1)
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)


def check_for_updates(local_version, update_source="github"):
    print("🔍 [自动更新] 正在检查 Server 更新...")
    try:
        if update_source == "github":
            url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
            with urllib.request.urlopen(url, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            remote_version = str(payload.get("tag_name", "")).lstrip("v")
        else:
            url = f"https://gitee.com/{OWNER}/{REPO}/raw/main/server/server.py"
            with urllib.request.urlopen(url, timeout=30) as response:
                remote_content = response.read().decode("utf-8")
            match = re.search(r'__version__\s*=\s*["\'](.+?)["\']', remote_content)
            remote_version = match.group(1) if match else ""
        if not remote_version:
            print("⚠️ [自动更新] 无法确定远程版本，已跳过。\\n")
            return None
        if _version_tuple(remote_version) > _version_tuple(local_version):
            return local_version, remote_version
        print("✅ [自动更新] 您的 Server 已是最新版本。\\n")
        return None
    except Exception as exc:
        print(f"⚠️ [自动更新] 检查失败，已跳过: {exc}\\n")
        return None
'''
write("server/utils/auto_update.py", auto_update)


# ---------------------------------------------------------------------------
# P0: Release archive structure and validation. README expects server/ root.
# ---------------------------------------------------------------------------
path = ".github/workflows/release.yml"
text = read(path)
text = replace_once(
    text,
    "      - name: Build\n        run: |\n          cd plugin/ && npm run build\n",
    "      - name: Pre-release checks\n        run: |\n          python -m compileall -q server\n          cd plugin/ && npm run lint:check\n\n      - name: Build\n        run: |\n          cd plugin/ && npm run build\n",
    "release preflight",
)
text = replace_regex(
    text,
    r'''      - name: Build server\.zip from current source\n        run: \|\n(?:          .*\n)+?          cd \.\.\n          unzip -l server\.zip \| head -80\n''',
    '''      - name: Build server.zip from current source
        run: |
          rm -f server.zip
          zip -r server.zip server \\
            -x 'server/translated/*' \\
            -x 'server/zotero-pdf2zh-venv/*' \\
            -x 'server/zotero-pdf2zh-next-venv/*' \\
            -x 'server/zotero-pdf2zh-venv.staging/*' \\
            -x 'server/zotero-pdf2zh-next-venv.staging/*' \\
            -x 'server/zotero-pdf2zh-venv.backup/*' \\
            -x 'server/zotero-pdf2zh-next-venv.backup/*' \\
            -x 'server/config/package_update_state.json' \\
            -x 'server/config/*.invalid.bak' \\
            -x 'server/config/*.invalid.*.bak' \\
            -x 'server/__pycache__/*' \\
            -x 'server/*/__pycache__/*' \\
            -x '*.pyc' \\
            -x '.DS_Store'
          unzip -l server.zip | head -80
          unzip -l server.zip | grep -q 'server/server.py'
''',
    "release server archive layout",
    flags=re.MULTILINE,
)
text = replace_once(
    text,
    "      - name: Upload server.zip to Release\n        run: gh release upload ${{ github.ref_name }} server.zip --clobber\n",
    "      - name: Upload canonical Release assets\n        run: |\n          test -f plugin/build/zotero-pdf-2-zh.xpi\n          gh release upload ${{ github.ref_name }} plugin/build/zotero-pdf-2-zh.xpi --clobber\n          gh release upload ${{ github.ref_name }} server.zip --clobber\n",
    "canonical release assets",
)
write(path, text)


# ---------------------------------------------------------------------------
# P2 + upstream 2.9 schema: keep Zotero-specific behavioral defaults, but add
# every schema field/section present in the user's real pdf2zh_next 2.9 config.
# ---------------------------------------------------------------------------
path = "server/config/config.toml.example"
text = read(path)
if "clitranslator = false" not in text:
    text = replace_once(
        text,
        "claudecode = false\n",
        '''claudecode = false
clitranslator = false
term_siliconflowfree = false
term_openai = false
term_aliyundashscope = false
term_deepseek = false
term_ollama = false
term_xinference = false
term_azureopenai = false
term_modelscope = false
term_zhipu = false
term_siliconflow = false
term_gemini = false
term_grok = false
term_groq = false
term_openaicompatible = false
''',
        "2.9 top-level translator flags",
    )
if "term_qps" not in text:
    text = replace_once(
        text,
        'pool_max_workers = "null"\n',
        'pool_max_workers = "null"\nterm_qps = "null"\nterm_pool_max_workers = "null"\n',
        "2.9 term worker fields",
    )
if "siliconflow_free_enable_json_mode" not in text:
    text = replace_once(
        text,
        'support_llm = "yes"\n\n[openai_detail]',
        'support_llm = "yes"\nsiliconflow_free_enable_json_mode = false\n\n[openai_detail]',
        "siliconflowfree json mode",
    )
if "deepseek_thinking_mode" not in text:
    text = replace_once(
        text,
        'deepseek_enable_json_mode = "null"\n',
        'deepseek_enable_json_mode = "null"\ndeepseek_thinking_mode = "null"\ndeepseek_reasoning_effort = "null"\n',
        "DeepSeek 2.9 schema fields",
    )
if "siliconflow_enable_json_mode" not in text:
    text = replace_once(
        text,
        "siliconflow_send_enable_thinking_param = false\n",
        "siliconflow_send_enable_thinking_param = false\nsiliconflow_enable_json_mode = false\n",
        "SiliconFlow json mode",
    )
text = text.replace('support_llm = "yes"\nqwenmt_model = "qwen-mt-turbo"', 'support_llm = "no"\nqwenmt_model = "qwen-mt-plus"')
text = text.replace(
    'openai_compatible_model = ""\nopenai_compatible_base_url = ""\nopenai_compatible_api_key = ""',
    'openai_compatible_model = "gpt-4o-mini"\nopenai_compatible_base_url = "null"\nopenai_compatible_api_key = "null"',
)
if "[clitranslator_detail]" not in text:
    term_sections = r'''

[clitranslator_detail]
translate_engine_type = "CLITranslator"
support_llm = "no"
clitranslator_command = ""
clitranslator_timeout = 60
clitranslator_postprocess_command = "null"

[term_siliconflowfree_detail]
translate_engine_type = "SiliconFlowFree"
support_llm = "yes"
term_siliconflow_free_enable_json_mode = false

[term_openai_detail]
translate_engine_type = "OpenAI"
support_llm = "yes"
term_openai_model = "gpt-4o-mini"
term_openai_base_url = "null"
term_openai_api_key = "null"
term_openai_timeout = "null"
term_openai_temperature = "null"
term_openai_reasoning_effort = "null"
term_openai_enable_json_mode = "null"
term_openai_send_temprature = "null"
term_openai_send_reasoning_effort = "null"

[term_aliyundashscope_detail]
translate_engine_type = "AliyunDashScope"
support_llm = "yes"
term_aliyun_dashscope_model = "qwen-plus-latest"
term_aliyun_dashscope_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
term_aliyun_dashscope_api_key = "null"
term_aliyun_dashscope_timeout = "500"
term_aliyun_dashscope_temperature = "0.0"
term_aliyun_dashscope_send_temperature = "null"
term_aliyun_dashscope_enable_json_mode = "null"

[term_deepseek_detail]
translate_engine_type = "DeepSeek"
support_llm = "yes"
term_deepseek_model = "deepseek-v4-flash"
term_deepseek_api_key = "null"
term_deepseek_enable_json_mode = "null"
term_deepseek_thinking_mode = "null"
term_deepseek_reasoning_effort = "null"

[term_ollama_detail]
translate_engine_type = "Ollama"
support_llm = "yes"
term_ollama_model = "gemma2"
term_ollama_host = "http://localhost:11434"
term_num_predict = 2000

[term_xinference_detail]
translate_engine_type = "Xinference"
support_llm = "yes"
term_xinference_model = "gemma-2-it"
term_xinference_host = "null"

[term_azureopenai_detail]
translate_engine_type = "AzureOpenAI"
support_llm = "yes"
term_azure_openai_model = "gpt-4o-mini"
term_azure_openai_base_url = "null"
term_azure_openai_api_key = "null"
term_azure_openai_api_version = "2024-06-01"

[term_modelscope_detail]
translate_engine_type = "ModelScope"
support_llm = "yes"
term_modelscope_model = "Qwen/Qwen2.5-32B-Instruct"
term_modelscope_api_key = "null"
term_modelscope_enable_json_mode = "null"

[term_zhipu_detail]
translate_engine_type = "Zhipu"
support_llm = "yes"
term_zhipu_model = "glm-4-flash"
term_zhipu_api_key = "null"
term_zhipu_enable_json_mode = "null"

[term_siliconflow_detail]
translate_engine_type = "SiliconFlow"
support_llm = "yes"
term_siliconflow_base_url = "https://api.siliconflow.cn/v1"
term_siliconflow_model = "Qwen/Qwen2.5-7B-Instruct"
term_siliconflow_api_key = "null"
term_siliconflow_enable_thinking = false
term_siliconflow_send_enable_thinking_param = false
term_siliconflow_enable_json_mode = false

[term_gemini_detail]
translate_engine_type = "Gemini"
support_llm = "yes"
term_gemini_model = "gemini-1.5-flash"
term_gemini_api_key = "null"
term_gemini_enable_json_mode = "null"

[term_grok_detail]
translate_engine_type = "Grok"
support_llm = "yes"
term_grok_model = "grok-2-1212"
term_grok_api_key = "null"
term_grok_enable_json_mode = "null"

[term_groq_detail]
translate_engine_type = "Groq"
support_llm = "yes"
term_groq_model = "llama-3-3-70b-versatile"
term_groq_api_key = "null"
term_groq_enable_json_mode = "null"

[term_openaicompatible_detail]
translate_engine_type = "OpenAICompatible"
support_llm = "yes"
term_openai_compatible_model = "gpt-4o-mini"
term_openai_compatible_base_url = "null"
term_openai_compatible_api_key = "null"
term_openai_compatible_timeout = "null"
term_openai_compatible_temperature = "null"
term_openai_compatible_reasoning_effort = "null"
term_openai_compatible_send_temperature = "null"
term_openai_compatible_send_reasoning_effort = "null"
term_openai_compatible_enable_json_mode = "null"
'''
    text = text.rstrip() + term_sections + "\n"
write(path, text)


# ---------------------------------------------------------------------------
# P2 docs + localhost/auto behavior + truthful static validation wording.
# ---------------------------------------------------------------------------
for path in ("docs/zh/guide/package-update.md", "docs/en/guide/package-update.md"):
    text = read(path)
    text = text.replace("检查依赖完整性和 `pdf2zh_next --help`；", "检查依赖完整性和 CLI 入口；")
    text = text.replace("check dependency completeness and `pdf2zh_next --help`;", "check dependency completeness and the CLI entry point;")
    text = text.replace(
        "直接检查 runtime capability，而不是只相信版本字符串。",
        "通过已安装 distribution 的静态 metadata/source 检查 runtime capability；不会为了检查能力启动 `pdf2zh_next --help`。",
    )
    text = text.replace(
        "directly checks runtime capability instead of trusting only the version string.",
        "checks runtime capability from the installed distribution metadata/source without launching `pdf2zh_next --help`.",
    )
    text = text.replace(
        "这是普通用户需要记住的唯一维护命令。",
        "这是普通用户需要记住的唯一维护命令。它会自动沿用已有 uv/conda 环境；没有已有环境时优先使用 uv。",
    )
    text = text.replace(
        "This is the only maintenance command normal users need to remember.",
        "This is the only maintenance command normal users need to remember. It keeps an existing uv/conda environment automatically and prefers uv for a fresh install.",
    )
    write(path, text)

path = "README.md"
text = read(path)
if "`--host`" not in text:
    text = text.replace(
        "| `--port` | 服务端口号 | `8890` |",
        "| `--host` | Server 监听地址；默认仅本机访问，远程部署时才使用 `0.0.0.0` | `127.0.0.1` |\n| `--port` | 服务端口号 | `8890` |",
    )
text = text.replace(
    "- **conda 用户**：环境存储在 conda 的 envs 目录中，可以安全移动 `server` 文件夹。",
    "- **conda 用户**：环境存储在 conda 的 envs 目录中，可以安全移动 `server` 文件夹。新版 Server/`update_packages.py` 会自动沿用已有 conda 环境；新安装仍优先 uv。\n- **远程 Server 用户**：默认只监听 `127.0.0.1`。确实需要其他设备访问时显式添加 `--host 0.0.0.0`，并自行配置防火墙/可信网络。",
)
write(path, text)


# ---------------------------------------------------------------------------
# Permanent CI regression coverage for every release blocker fixed above.
# ---------------------------------------------------------------------------
path = ".github/workflows/ci.yml"
text = read(path)
text = text.replace(
    "python -m pip install toml packaging pymupdf",
    "python -m pip install toml packaging pymupdf flask pypdf",
)
text = text.replace(
    "                  assert '\"--help\"' not in validate_block\n",
    "                  assert '\"--help\"' not in validate_block\n                  venv_text = Path('server/utils/venv.py').read_text(encoding='utf-8')\n                  req_block = venv_text.split('def _requirements_ok(', 1)[1].split('def check_envtool', 1)[0]\n                  assert 'pdf2zh_next\", \"--help' not in req_block\n",
)
text = replace_regex(
    text,
    r'''            - name: Test explicit environment manager selection\n(?:              .*\n)+?                  PY\n            - name: Test maintenance commands default to uv\n(?:              .*\n)+?                  PY\n''',
    '''            - name: Test environment manager selection
              env:
                  PYTHONPATH: server
              run: |
                  python - <<'PY'
                  from unittest.mock import patch
                  from utils.venv import VirtualEnvManager

                  names={'pdf2zh':'zotero-pdf2zh-venv','pdf2zh_next':'zotero-pdf2zh-next-venv'}
                  uv=VirtualEnvManager('missing.json', names, 'uv', skip_install=True)
                  conda=VirtualEnvManager('missing.json', names, 'conda', skip_install=True)
                  auto=VirtualEnvManager('missing.json', names, 'auto', skip_install=True)
                  assert uv._preferred_tools() == ['uv']
                  assert conda._preferred_tools() == ['conda']
                  assert auto._preferred_tools() == ['uv', 'conda']
                  with patch('utils.venv.shutil.which', side_effect=lambda name: '/bin/uv' if name == 'uv' else '/bin/conda'):
                      assert auto._install_tools() == ['uv']
                  with patch('utils.venv.shutil.which', side_effect=lambda name: None if name == 'uv' else '/bin/conda'):
                      assert auto._install_tools() == ['conda']
                  print('Environment manager selection OK')
                  PY
            - name: Test maintenance commands auto-detect existing manager
              run: |
                  python - <<'PY'
                  from pathlib import Path
                  server=Path('server/server.py').read_text(encoding='utf-8')
                  assert "default_env_tool = 'auto'" in server
                  for path in ('server/update_packages.py', 'server/manage_packages.py'):
                      text=Path(path).read_text(encoding='utf-8')
                      pos=text.index('"--env-tool"')
                      block=text[pos:pos+520]
                      assert 'default="auto"' in block, f'{path}: --env-tool must default to auto'
                  print('Maintenance auto-detection defaults OK')
                  PY
''',
    "replace environment CI tests",
    flags=re.MULTILINE,
)
text = text.replace(
    "                  print('PDF operation state transitions OK')\n",
    '''                  dual_cut = root / 'paper.dual-cut.pdf'
                  cropper.crop_pdf(config, tb_path, 'dual', str(dual_cut), 'dual-cut')
                  assert dual_cut.exists()
                  with fitz.open(dual_cut) as cut:
                      assert len(cut) == 4
                      assert cut[0].rect.width == 200

                  crop_route = server.split('def crop(self):', 1)[1].split('def crop_compare(self):', 1)[0]
                  assert 'source_path = input_path' in crop_route
                  assert "_, source_path = self.cropper.pdf_dual_mode(input_path, 'LR', 'TB')" in crop_route
                  assert 'self.cropper.crop_pdf(config, source_path, infile_type, new_path, new_type)' in crop_route
                  print('PDF operation state transitions OK')
''',
)
security_step = '''            - name: Test Server security and release packaging invariants
              env:
                  PYTHONPATH: server
              run: |
                  python - <<'PY'
                  from pathlib import Path
                  import toml
                  from server import PDFTranslator

                  assert PDFTranslator._safe_upload_filename('paper.pdf') == 'paper.pdf'
                  for bad in ('../paper.pdf', 'a/b.pdf', r'a\\b.pdf', '..', 'note.txt'):
                      try:
                          PDFTranslator._safe_upload_filename(bad)
                      except ValueError:
                          pass
                      else:
                          raise AssertionError(f'unsafe filename accepted: {bad}')

                  server = Path('server/server.py').read_text(encoding='utf-8')
                  assert "default='127.0.0.1'" in server
                  assert "self.app.run(host=host" in server
                  config = Path('server/utils/config.py').read_text(encoding='utf-8')
                  assert '_safe_log_value' in config

                  release = Path('.github/workflows/release.yml').read_text(encoding='utf-8')
                  assert 'zip -r server.zip server' in release
                  assert "grep -q 'server/server.py'" in release
                  updater = Path('server/utils/auto_update.py').read_text(encoding='utf-8')
                  assert '/releases/download/{tag}/server.zip' in updater
                  assert '下载的 Server 版本不匹配' in updater

                  cfg = toml.load('server/config/config.toml.example')
                  for key in ('clitranslator','term_deepseek','term_openaicompatible'):
                      assert key in cfg
                  for section in ('clitranslator_detail','term_deepseek_detail','term_openaicompatible_detail'):
                      assert section in cfg
                  assert 'deepseek_thinking_mode' in cfg['deepseek_detail']
                  assert 'deepseek_reasoning_effort' in cfg['deepseek_detail']
                  assert cfg['qwenmt_detail']['support_llm'] == 'no'
                  assert cfg['qwenmt_detail']['qwenmt_model'] == 'qwen-mt-plus'
                  for doc in ('docs/zh/guide/package-update.md','docs/en/guide/package-update.md'):
                      assert 'pdf2zh_next --help`；' not in Path(doc).read_text(encoding='utf-8')
                  print('Server security/release/config invariants OK')
                  PY
'''
if "Test Server security and release packaging invariants" not in text:
    text = text.replace("\n    lint:\n", "\n" + security_step + "\n    lint:\n")
text = text.replace(
    "                  helper = Path('plugin/src/modules/pdf2zhHelper.ts').read_text(encoding='utf-8')\n",
    "                  helper = Path('plugin/src/modules/pdf2zhHelper.ts').read_text(encoding='utf-8')\n                  processor = Path('plugin/src/modules/pdf2zhFileProcessor.ts').read_text(encoding='utf-8')\n",
)
text = text.replace(
    "                  assert 'operation-error-compare-terminal' in helper\n",
    "                  assert 'operation-error-compare-terminal' in helper\n                  assert 'throw error;' in helper\n                  assert 'removeListener();' in helper\n                  assert 'apiKey: llmApiConfig.apiKey ? \"********\" : \"\"' in helper\n                  assert 'return () =>' in processor\n",
)
text = text.replace(
    "                      'operation-error-compare-terminal',\n",
    "                      'operation-error-compare-terminal',\n                      'operation-error-no-selection',\n                      'operation-error-single-file',\n                      'operation-batch-started',\n                      'operation-batch-completed',\n",
)
write(path, text)

print('v4.1.0 release hardening migration applied')
