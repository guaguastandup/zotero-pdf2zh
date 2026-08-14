from __future__ import annotations

import concurrent.futures
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

DEFAULT_INDEXES = [
    ("PyPI", "https://pypi.org/simple"),
    ("USTC", "https://mirrors.ustc.edu.cn/pypi/simple"),
    ("TUNA", "https://pypi.tuna.tsinghua.edu.cn/simple"),
    ("Aliyun", "https://mirrors.aliyun.com/pypi/simple"),
]

_USER_AGENT = "Zotero-PDF2zh-Package-Preflight/1.0"
_HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.IGNORECASE)
_PROXY_KEYS = (
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "ALL_PROXY",
    "all_proxy",
)


@dataclass(frozen=True)
class IndexProbeResult:
    name: str
    url: str
    package: str
    reachable: bool
    index_latency_ms: int | None = None
    artifact_latency_ms: int | None = None
    error: str | None = None

    @property
    def total_latency_ms(self) -> int:
        return (self.index_latency_ms or 0) + (self.artifact_latency_ms or 0)


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def normalize_index_url(url: str) -> str:
    return url.strip().rstrip("/")


def _short_error(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return str(exc.reason)
    return str(exc)


def _safe_proxy_display(value: str) -> str:
    """Show proxy host/port without leaking credentials."""
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.hostname:
            scheme = f"{parsed.scheme}://" if parsed.scheme else ""
            port = f":{parsed.port}" if parsed.port else ""
            return f"{scheme}{parsed.hostname}{port}"
    except Exception:
        pass
    return "<configured>"


def configured_proxies() -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key in _PROXY_KEYS:
        value = os.environ.get(key)
        if not value:
            continue
        item = (key, _safe_proxy_display(value))
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def probe_index(
    name: str,
    index_url: str,
    package: str,
    timeout: float = 4.0,
) -> IndexProbeResult:
    """Probe both package metadata and a small slice of one distribution file.

    The second request matters because PyPI metadata can be reachable while the
    actual distribution host is blocked or extremely slow. Only a small prefix
    is read; the package is not downloaded in full.
    """
    index_url = normalize_index_url(index_url)
    normalized_package = normalize_package_name(package)
    package_url = f"{index_url}/{normalized_package}/"

    try:
        start = time.monotonic()
        req = urllib.request.Request(
            package_url,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html, application/vnd.pypi.simple.v1+html",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(1024 * 1024).decode("utf-8", errors="ignore")
        index_latency_ms = max(1, int((time.monotonic() - start) * 1000))

        hrefs = _HREF_RE.findall(body)
        if not hrefs:
            return IndexProbeResult(
                name=name,
                url=index_url,
                package=normalized_package,
                reachable=False,
                index_latency_ms=index_latency_ms,
                error="package index returned no distribution links",
            )

        # Any distribution URL is enough to verify that the actual artifact host
        # used by this index is reachable. Read at most 64 KiB and close early.
        artifact_url = urllib.parse.urljoin(package_url, hrefs[-1])
        start = time.monotonic()
        artifact_req = urllib.request.Request(
            artifact_url,
            headers={
                "User-Agent": _USER_AGENT,
                "Range": "bytes=0-65535",
            },
        )
        with urllib.request.urlopen(artifact_req, timeout=timeout) as response:
            chunk = response.read(64 * 1024)
        artifact_latency_ms = max(1, int((time.monotonic() - start) * 1000))
        if not chunk:
            raise RuntimeError("distribution request returned no data")

        return IndexProbeResult(
            name=name,
            url=index_url,
            package=normalized_package,
            reachable=True,
            index_latency_ms=index_latency_ms,
            artifact_latency_ms=artifact_latency_ms,
        )
    except Exception as exc:
        return IndexProbeResult(
            name=name,
            url=index_url,
            package=normalized_package,
            reachable=False,
            error=_short_error(exc),
        )


def probe_indexes(
    package: str,
    preferred_index: str | None = None,
    timeout: float = 4.0,
) -> list[IndexProbeResult]:
    candidates: list[tuple[str, str]] = []
    if preferred_index:
        candidates.append(("Custom", normalize_index_url(preferred_index)))
    candidates.extend(DEFAULT_INDEXES)

    # Keep order stable while removing duplicate URLs.
    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, url in candidates:
        normalized = normalize_index_url(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append((name, normalized))

    results: list[IndexProbeResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(deduped)) as pool:
        future_map = {
            pool.submit(probe_index, name, url, package, timeout): (name, url)
            for name, url in deduped
        }
        for future in concurrent.futures.as_completed(future_map):
            try:
                results.append(future.result())
            except Exception as exc:
                name, url = future_map[future]
                results.append(
                    IndexProbeResult(
                        name=name,
                        url=url,
                        package=normalize_package_name(package),
                        reachable=False,
                        error=_short_error(exc),
                    )
                )

    order = {url: idx for idx, (_, url) in enumerate(deduped)}
    results.sort(key=lambda item: order.get(item.url, 999))
    return results


def usable_indexes(results: list[IndexProbeResult]) -> list[IndexProbeResult]:
    usable = [result for result in results if result.reachable]
    # An explicitly supplied index wins when it works. Otherwise choose the
    # fastest measured source instead of guessing the user's region.
    custom = [result for result in usable if result.name == "Custom"]
    others = sorted(
        [result for result in usable if result.name != "Custom"],
        key=lambda item: item.total_latency_ms,
    )
    return custom + others


def print_probe_report(results: list[IndexProbeResult]) -> None:
    print("\n🌐 Python 包下载网络预检")
    for result in results:
        if result.reachable:
            print(
                f"  ✅ {result.name:6s} {result.url} "
                f"(index {result.index_latency_ms} ms, artifact {result.artifact_latency_ms} ms)"
            )
        else:
            print(f"  ❌ {result.name:6s} {result.url} ({result.error or 'unreachable'})")

    ranked = usable_indexes(results)
    if ranked:
        print(f"  → 推荐源: {ranked[0].name} {ranked[0].url}")
        return

    print("  → 没有检测到可用的包下载源；不会开始安装或升级。")
    proxies = configured_proxies()
    if proxies:
        print("  ⚠️ 检测到代理环境变量；如果这些代理已失效，可能导致所有源同时失败：")
        for key, value in proxies:
            print(f"     {key}={value}")
        print("     请检查代理是否仍在运行，或在确认无需代理后清除失效的代理变量再重试。")
