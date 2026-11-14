"""Run Wenyi in a separate process; this adapter never imports its Python packages."""

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import toml
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from utils.environment_lifecycle import managed_python_env
from utils.wenyi_settings import llm_config


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("Wenyi machine output exceeds the size limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("protocol_version") != 1:
        raise ValueError("Unsupported Wenyi machine output protocol")
    return value


def language_code(value):
    value = {"zh-CN": "zh", "zh-TW": "zh-Hant", "zh-HK": "zh-Hant"}.get(value, value)
    if value not in {
        "auto",
        "zh",
        "zh-Hant",
        "en",
        "ja",
        "ko",
        "fr",
        "de",
        "es",
        "it",
        "pt",
        "ru",
        "vi",
    }:
        raise ValueError("This language is not supported by Wenyi")
    return value


class WenyiAdapter:
    """Own only process supervision and isolated task files, not translation logic."""

    def __init__(
        self,
        task_root,
        output_root,
        *,
        executable="wenyi",
        bridge_url="http://127.0.0.1:8765",
        timeout=10800,
        runtime=None,
    ):
        self.task_root = Path(task_root).resolve()
        self.output_root = Path(output_root).resolve()
        self.executable = executable
        self.bridge_url = bridge_url
        self.timeout = timeout
        self.runtime = runtime
        url = urlsplit(bridge_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Wenyi bridge URL must be HTTP(S) without credentials or query")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Wenyi timeout must be positive and finite")

    def workspace(self, task_id):
        # Task IDs come from the Server, never from client-supplied paths.
        key = UUID(str(task_id)).hex
        path = self.task_root / key
        path.mkdir(parents=True, exist_ok=True)
        return path

    def translate(self, input_path, config, task_id, on_progress):
        if config.skip_last_pages:
            raise ValueError("Wenyi v1 supports complete PDFs only; set Skip Last Pages to 0")
        if any((config.mono_cut, config.dual_cut, config.crop_compare, config.compare)):
            raise ValueError("Wenyi does not support cropping or comparison layouts")
        mono = config.mono and not config.no_mono
        bilingual = config.dual and not config.no_dual
        if not mono and not bilingual:
            raise ValueError("Select at least one Wenyi PDF output")
        if config.ocr or config.auto_ocr or config.only_include_translated_page:
            raise ValueError("Wenyi v1 does not support OCR or page selection")
        source = language_code(config.sourceLang)
        target = language_code(config.targetLang)
        if target == "auto" or source == target:
            raise ValueError("Wenyi requires different source and target languages")
        input_path = Path(input_path).resolve()
        workspace = self.workspace(task_id)
        if input_path.parent != workspace:
            raise ValueError("Wenyi input must belong to its isolated task directory")
        try:
            page_count = len(PdfReader(input_path).pages)
        except (OSError, PdfReadError) as error:
            raise ValueError("Wenyi input is not a readable PDF") from error
        if not page_count:
            raise ValueError("Wenyi input has no pages")
        digest = file_digest(input_path)
        output = workspace / "translation.mono.pdf"
        bilingual_output = workspace / "translation.mono-bi.pdf"
        outputs = {}
        if mono:
            outputs[output] = "mono"
        if bilingual:
            outputs[bilingual_output] = "dual"
        progress = workspace / "progress.json"
        result = workspace / "result.json"
        settings = workspace / "config.yaml"
        if any(path.exists() for path in (result, progress, output, bilingual_output)):
            raise ValueError("Wenyi task already has execution files; do not start it twice")
        if self.runtime is not None:
            on_progress(
                {"status": "running", "progress": 0, "message": "Preparing Wenyi environment"}
            )
            command, environment, bridge_url = self.runtime.prepare()
        else:
            executable = shutil.which(self.executable)
            if not executable:
                raise ValueError("Wenyi executable not found; configure --wenyi-executable")
            command = [executable]
            environment = managed_python_env()
            bridge_url = self.bridge_url
        environment = environment.copy()
        environment["DEEPSEEK_API_KEY"] = config.llm_api["apiKey"]
        # JSON is valid YAML. Keep provider defaults in Wenyi as the single source
        # of truth; the plugin sends only explicitly chosen non-secret overrides.
        settings.write_text(
            json.dumps(
                {
                    "language": {"source": source, "target": target},
                    "llm": llm_config(config.wenyi_options),
                    "pipeline": {
                        "pdf_backend": "babeldoc",
                        "babeldoc_bridge_url": bridge_url,
                        **config.wenyi_options.get("pipeline", {}),
                    },
                    "paths": {"state_dir": str(workspace / "state")},
                    "output": {
                        "mono": mono,
                        "bilingual": bilingual,
                        **config.wenyi_options["output"],
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        command = [
            *command,
            "--config",
            str(settings),
            "--prompt-genre",
            config.wenyi_options["prompt_genre"],
            "translate",
            str(input_path),
            "--format",
            "pdf",
            "--out",
            str(output),
            "--mono" if mono else "--no-mono",
            "--bilingual" if bilingual else "--no-bilingual",
            "--progress-json",
            str(progress),
            "--result-json",
            str(result),
        ]
        # 断点续传重放元数据: wenyi CLI 对同一 workspace 重复 translate 即续传。
        replay = {
            "args": command[command.index("--config"):],
            "input": input_path.name,
            "source_sha256": digest,
            "page_count": page_count,
            "outputs": {str(k): v for k, v in outputs.items()},
        }
        (workspace / "replay.json").write_text(
            json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"🚀 [wenyi {task_id[:8]}] 开始翻译: {input_path.name} | 主题={config.wenyi_options['prompt_genre']} | 输出={list(outputs.values())}")
        # A new task directory is required; old receipts must never be accepted if
        # the child cannot start or exits without writing the machine protocol.
        started = time.monotonic()
        run_id = None
        with (workspace / "wenyi.log").open("wb") as log:
            process = subprocess.Popen(
                command,
                cwd=workspace,
                shell=False,
                stdout=log,
                stderr=log,
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            try:
                while process.poll() is None:
                    if time.monotonic() - started > self.timeout:
                        raise TimeoutError("Wenyi timed out; completed checkpoints are retained")
                    run_id = self._progress(progress, run_id, on_progress)
                    time.sleep(0.25)
                if process.returncode != 0:
                    print(f"❌ [wenyi {task_id[:8]}] 退出码 {process.returncode}, 详见 {workspace / 'wenyi.log'}")
                    raise RuntimeError(
                        f"Wenyi exited with code {process.returncode}; check the task's wenyi.log "
                        "and use a CLI supporting --progress-json and --result-json"
                    )
                run_id = self._progress(progress, run_id, on_progress)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        try:
            receipt = read_json(result)
            entries = receipt.get("outputs")
            if (
                not run_id
                or receipt.get("run_id") != run_id
                or receipt.get("status") != "success"
                or receipt.get("source_sha256") != digest
                or file_digest(input_path) != digest
                or not isinstance(entries, list)
                or len(entries) != len(outputs)
            ):
                raise ValueError("Wenyi did not publish a matching success receipt")
            pending = set(outputs)
            for artifact in entries:
                if not isinstance(artifact, dict):
                    raise ValueError("Wenyi output receipt must describe a PDF")
                path = Path(artifact.get("path", "")).resolve()
                if path not in pending:
                    raise ValueError("Wenyi output receipt has an unexpected or duplicate PDF")
                pending.remove(path)
                if (
                    Path(artifact["path"]).is_symlink()
                    or path.stat().st_size != artifact.get("size")
                    or file_digest(path) != artifact.get("sha256")
                    or len(PdfReader(path).pages) != page_count
                ):
                    raise ValueError("Wenyi output failed PDF, page-count or checksum validation")
        except (OSError, KeyError, TypeError, json.JSONDecodeError, PdfReadError) as error:
            raise ValueError("Wenyi did not publish a valid output receipt") from error
        # Validate every requested edition before publishing any attachments.
        self.output_root.mkdir(parents=True, exist_ok=True)
        published = []
        for path, edition in outputs.items():
            name = f"{UUID(str(task_id)).hex}.{input_path.stem[:100]}.{target}.{edition}.pdf"
            destination = self.output_root / name
            descriptor, temporary = tempfile.mkstemp(prefix=".wenyi-", dir=self.output_root)
            os.close(descriptor)
            try:
                shutil.copyfile(path, temporary)
                os.replace(temporary, destination)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            published.append(str(destination))
        return published

    def resume(self, task_id, on_progress, api_key=""):
        """断点续传: wenyi CLI 对同一 workspace 重复 translate 会从 checkpoint 继续。

        运行时(bridge)与首次运行可能不是同一个实例, config.yaml 中的
        babeldoc_bridge_url 会用新地址重写; 旧的 result/progress 清空以便
        重新校验本次运行的回执。api_key 从 server 的 config.toml 读取。
        """
        workspace = self.workspace(task_id)
        replay = read_json(workspace / "replay.json")
        input_path = (workspace / replay["input"]).resolve()
        digest = replay["source_sha256"]
        page_count = replay["page_count"]
        outputs = {Path(k): v for k, v in replay["outputs"].items()}
        if not input_path.exists() or file_digest(input_path) != digest:
            raise ValueError("Wenyi resume input is missing or changed; start a new task")
        settings = workspace / "config.yaml"
        progress = workspace / "progress.json"
        result = workspace / "result.json"
        if self.runtime is not None:
            prefix, environment, bridge_url = self.runtime.prepare()
        else:
            executable = shutil.which(self.executable)
            if not executable:
                raise ValueError("Wenyi executable not found; configure --wenyi-executable")
            prefix = [executable]
            environment = managed_python_env()
            bridge_url = self.bridge_url
        environment = environment.copy()
        environment["DEEPSEEK_API_KEY"] = api_key or self._read_saved_api_key()
        # config.yaml 是 JSON 兼容 YAML; 只重写 bridge 地址, 其余保持首次配置。
        config_payload = read_json(settings)
        pipeline = config_payload.setdefault("pipeline", {})
        pipeline["babeldoc_bridge_url"] = bridge_url
        settings.write_text(
            json.dumps(config_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for stale in (result, progress):
            if stale.exists():
                stale.unlink()
        command = [*prefix, *replay["args"]]
        print(f"🔁 [wenyi {task_id[:8]}] 断点续传: {input_path.name} (checkpoints 保留在 state/)")
        started = time.monotonic()
        run_id = None
        with (workspace / "wenyi.log").open("ab") as log:
            process = subprocess.Popen(
                command, cwd=workspace, shell=False, stdout=log, stderr=log,
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            try:
                while process.poll() is None:
                    if time.monotonic() - started > self.timeout:
                        raise TimeoutError("Wenyi timed out; completed checkpoints are retained")
                    run_id = self._progress(progress, run_id, on_progress)
                    time.sleep(0.25)
                if process.returncode != 0:
                    print(f"❌ [wenyi {task_id[:8]}] 续传退出码 {process.returncode}, 详见 {workspace / 'wenyi.log'}")
                    raise RuntimeError(
                        f"Wenyi exited with code {process.returncode}; check the task's wenyi.log"
                    )
                run_id = self._progress(progress, run_id, on_progress)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        receipt = read_json(result)
        if (
            not run_id
            or receipt.get("run_id") != run_id
            or receipt.get("status") != "success"
            or receipt.get("source_sha256") != digest
            or file_digest(input_path) != digest
        ):
            raise ValueError("Wenyi resume did not publish a matching success receipt")
        self.output_root.mkdir(parents=True, exist_ok=True)
        published = []
        for path, edition in outputs.items():
            if not path.exists():
                raise ValueError(f"Wenyi resume output missing: {path.name}")
            name = f"{UUID(str(task_id)).hex}.{input_path.stem[:100]}.{edition}.pdf"
            destination = self.output_root / name
            descriptor, temporary = tempfile.mkstemp(prefix=".wenyi-", dir=self.output_root)
            os.close(descriptor)
            try:
                shutil.copyfile(path, temporary)
                os.replace(temporary, destination)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            published.append(str(destination))
        print(f"✅ [wenyi {task_id[:8]}] 续传完成, 发布 {len(published)} 个文件")
        return published

    def _read_saved_api_key(self):
        """从 server 的 config.toml 读取 DeepSeek API Key(续传时使用)。"""
        try:
            config_file = Path(__file__).resolve().parent.parent / "config" / "config.toml"
            if not config_file.exists():
                return ""
            data = toml.load(config_file)
            key = data.get("deepseek_detail", {}).get("deepseek_api_key", "")
            return str(key) if key and str(key).lower() not in ("null", "none") else ""
        except Exception:
            return ""

    def close(self):
        if self.runtime is not None:
            self.runtime.close()

    @staticmethod
    def _progress(path, run_id, callback):
        try:
            frame = read_json(path)
        except FileNotFoundError:
            return run_id
        identity = frame.get("run_id")
        if not isinstance(identity, str) or not identity or (run_id and run_id != identity):
            raise ValueError("Wenyi progress belongs to another invocation")
        done, total = frame.get("done"), frame.get("total")
        percent = 0
        if (
            isinstance(done, int)
            and not isinstance(done, bool)
            and isinstance(total, int)
            and not isinstance(total, bool)
            and total > 0
        ):
            percent = max(0, min(99, int(done / total * 100)))
        callback(
            {
                "status": "running",
                "progress": percent,
                "message": str(frame.get("label") or "Wenyi is running")[:300],
            }
        )
        return identity
