"""Bounded, request-scoped title translation using the selected PDF service."""

import hashlib
import json
import re
import subprocess
import tempfile
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future
from pathlib import Path

from utils.config_map import pdf2zh_next_config_map, pdf2zh_next_service_aliases
from utils.environment_lifecycle import managed_python_env

SUPPORTED_SERVICES = ('siliconflowfree', 'openai', 'openaicompatible')
TIMEOUT_SECONDS = 90


class TitleTranslationError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def clean_title(value):
    if not isinstance(value, str):
        return ''
    return re.sub(r'\s+', ' ', value).strip()


def prepare_request(data, saved_config=None):
    if not isinstance(data, dict):
        raise TitleTranslationError('invalid_request')
    title = clean_title(data.get('title'))
    target = clean_title(data.get('targetLang') or 'zh-CN')
    source = clean_title(data.get('sourceLang') or 'en')
    if not title or len(title) > 1200 or len(target) > 32 or len(source) > 32:
        raise TitleTranslationError('invalid_request')
    if data.get('engine') != 'pdf2zh_next':
        raise TitleTranslationError('unsupported_engine')
    service = data.get('next_service') or data.get('service')
    if not isinstance(service, str):
        raise TitleTranslationError('invalid_request')
    service = pdf2zh_next_service_aliases.get(service, service)
    if service not in SUPPORTED_SERVICES:
        raise TitleTranslationError('unsupported_service')
    detail = dict((saved_config or {}).get(f'{service}_detail', {}))
    mapping = pdf2zh_next_config_map[service]
    api = data.get('llm_api')
    if api is not None:
        if not isinstance(api, dict):
            raise TitleTranslationError('invalid_request')
        # An explicitly selected profile must not inherit credentials or options
        # from another profile previously used by the PDF worker.
        detail = {}
        for key in ('apiKey', 'apiUrl', 'model'):
            if key in mapping and api.get(key):
                detail[mapping[key]] = api[key]
        extra = api.get('extraData') or {}
        if not isinstance(extra, dict):
            raise TitleTranslationError('invalid_request')
        for key in mapping.get('extraData', []):
            value = extra.get(key)
            if value is not None and value != '':
                detail[key] = value
    detail = {key: value for key, value in detail.items() if value != 'null'}
    return dict(title=title, sourceLang=source, targetLang=target,
                service=service, detail=detail)


def validate_result(value, request):
    title = clean_title(value)
    if not title or len(title) > 1200:
        raise TitleTranslationError('invalid_result')
    if request['targetLang'].lower().startswith('zh'):
        if not re.search(r'[\u3400-\u9fff]', title) or re.search(r'[\u3040-\u30ff]', title):
            raise TitleTranslationError('invalid_result')
    return title


def run_worker(request, python_path, runtime_root, timeout=TIMEOUT_SECONDS):
    root = Path(runtime_root)
    root.mkdir(parents=True, exist_ok=True)
    # Credentials travel through stdin only. All engine imports and temporary
    # files are isolated from the user's default configuration/cache directories.
    with tempfile.TemporaryDirectory(prefix='title-', dir=root) as directory:
        env = managed_python_env()
        for key in ('HOME', 'USERPROFILE', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME',
                    'TEMP', 'TMP', 'TMPDIR'):
            env[key] = directory
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
            result = subprocess.run(
                [str(python_path), '-B', str(Path(__file__).with_name('title_worker.py'))],
                input=json.dumps(request), capture_output=True, text=True,
                encoding='utf-8', env=env, cwd=directory, timeout=timeout,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        except subprocess.TimeoutExpired:
            raise TitleTranslationError('timeout') from None
        except OSError:
            raise TitleTranslationError('runtime_unavailable') from None
        if result.returncode:
            # Engine errors may contain credentials, URLs or request bodies.
            raise TitleTranslationError('translation_failed')
        try:
            response = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise TitleTranslationError('invalid_result') from None
        if response.get('status') != 'success':
            code = response.get('code')
            raise TitleTranslationError(code if code in (
                'unsupported_version', 'translation_failed',
            ) else 'translation_failed')
        return validate_result(response.get('title'), request)


class TitleTranslator:
    """Deduplicate in-flight requests and keep a small, expiring memory cache."""

    def __init__(self, worker=run_worker, ttl=600, max_entries=128):
        self.worker = worker
        self.ttl = ttl
        self.max_entries = max_entries
        self.cache = OrderedDict()
        self.pending = {}
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(2)

    def translate(self, request, python_path, runtime_root):
        key = hashlib.sha256(json.dumps(
            [str(python_path), request], sort_keys=True, ensure_ascii=False,
        ).encode()).hexdigest()
        with self.lock:
            cached = self.cache.get(key)
            if cached and cached[0] > time.monotonic():
                self.cache.move_to_end(key)
                return cached[1]
            future = self.pending.get(key)
            owner = future is None
            if owner:
                future = self.pending[key] = Future()
        if not owner:
            try:
                return future.result(timeout=TIMEOUT_SECONDS + 2)
            except TimeoutError:
                raise TitleTranslationError('timeout') from None
        acquired = self.slots.acquire(blocking=False)
        try:
            if not acquired:
                raise TitleTranslationError('busy')
            title = validate_result(self.worker(request, python_path, runtime_root), request)
            with self.lock:
                self.cache[key] = (time.monotonic() + self.ttl, title)
                while len(self.cache) > self.max_entries:
                    self.cache.popitem(last=False)
            future.set_result(title)
            return title
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            if acquired:
                self.slots.release()
            with self.lock:
                self.pending.pop(key, None)
