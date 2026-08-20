## auto_update.py
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
USER_AGENT = "zotero-pdf2zh-server-updater"
NOTICE_RELATIVE_PATH = "server/notice.json"
NOTICE_TIMEOUT = 8


def _version_tuple(value):
    parts = re.findall(r"\d+", str(value or ""))
    return tuple(int(part) for part in parts[:4]) or (0,)


def _server_version_from_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return match.group(1) if match else None


def _source_order(preferred):
    preferred = "gitee" if str(preferred).strip().lower() == "gitee" else "github"
    other = "github" if preferred == "gitee" else "gitee"
    return [preferred, other]


def _looks_like_zip(path):
    try:
        with open(path, "rb") as handle:
            magic = handle.read(4)
        if magic[:2] != b"PK":
            return False
        with zipfile.ZipFile(path, "r") as archive:
            archive.namelist()
        return True
    except Exception:
        return False


def _http_get(url, timeout=60):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", "")


def _payload_is_html(payload, content_type=""):
    if "html" in str(content_type).lower():
        return True
    head = payload[:200].lower()
    return b"<html" in head or b"<!doctype" in head


def _download_first(urls, destination, label):
    last_error = None
    for url in urls:
        try:
            print(f"  - 尝试下载 {label}: {url}")
            payload, content_type = _http_get(url)
            if _payload_is_html(payload, content_type):
                raise RuntimeError("下载内容是 HTML（可能是 Gitee 安全验证页）")
            with open(destination, "wb") as handle:
                handle.write(payload)
            if not _looks_like_zip(destination):
                raise RuntimeError("下载内容不是 zip")
            print(f"  - ✅ {label} 下载完成")
            return url
        except Exception as exc:
            last_error = exc
            print(f"  - ⚠️ 下载失败，尝试下一来源: {exc}")
            if os.path.exists(destination):
                os.remove(destination)
    raise RuntimeError(f"无法下载 {label}: {last_error}")


def get_xpi_info_from_repo(owner, repo, branch="main", expected_version=None, update_source="github"):
    """Return versioned Release XPI URLs, preferred source first.

    Zotero already supports plugin self-update, so failure here never blocks the
    Server update.
    """
    if not expected_version:
        return [], None
    tag = f"v{expected_version}"
    target_filename = "zotero-pdf-2-zh.xpi"
    github_url = f"https://github.com/{owner}/{repo}/releases/download/{tag}/{target_filename}"
    gitee_url = f"https://gitee.com/{owner}/{repo}/releases/download/{tag}/{target_filename}"
    urls = [
        gitee_url if source == "gitee" else github_url
        for source in _source_order(update_source)
    ]
    return urls, target_filename


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
    tag = f"v{expected_version}" if expected_version else None
    github_release = (
        f"https://github.com/{owner}/{repo}/releases/download/{tag}/server.zip"
        if tag
        else f"https://github.com/{owner}/{repo}/releases/latest/download/server.zip"
    )
    urls = []
    for source in _source_order(update_source):
        if source == "github":
            urls.append(github_release)
            if tag:
                urls.append(
                    f"https://raw.githubusercontent.com/{owner}/{repo}/{tag}/server.zip"
                )
            continue
        if tag:
            urls.append(
                f"https://gitee.com/{owner}/{repo}/releases/download/{tag}/server.zip"
            )
            urls.append(f"https://gitee.com/{owner}/{repo}/raw/{tag}/server.zip")
    seen = set()
    ordered = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


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
        xpi_urls, xpi_filename = get_xpi_info_from_repo(
            owner, repo, expected_version=expected_version, update_source=update_source
        )
        if xpi_urls and xpi_filename:
            xpi_path = os.path.join(project_root, xpi_filename)
            try:
                _download_first(xpi_urls, xpi_path, "插件 XPI")
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

        print("\n📊 同步统计:", stats)
        shutil.rmtree(backup_path, ignore_errors=True)
        if os.path.exists(archive_path):
            os.remove(archive_path)
        print("✅ Server 更新完成。请重新启动 server.py。")
        raise SystemExit(0)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"\n❌ 更新失败: {exc}")
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


def _version_from_json_release(payload):
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("tag_name", "") or "").lstrip("v")


def _version_from_server_py(text):
    match = re.search(r'__version__\s*=\s*["\'](.+?)["\']', text)
    return match.group(1) if match else ""


def _latest_version_from_github():
    versions = []
    try:
        payload_bytes, content_type = _http_get(
            f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest",
            timeout=30,
        )
        if _payload_is_html(payload_bytes, content_type):
            raise RuntimeError("GitHub API 返回了 HTML")
        version = _version_from_json_release(json.loads(payload_bytes.decode("utf-8")))
        if version:
            versions.append(version)
    except Exception as exc:
        print(f"  - ⚠️ GitHub Release API 不可用: {exc}")
    try:
        payload_bytes, content_type = _http_get(
            f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/server/server.py",
            timeout=30,
        )
        if _payload_is_html(payload_bytes, content_type):
            raise RuntimeError("GitHub raw 返回了 HTML")
        version = _version_from_server_py(payload_bytes.decode("utf-8"))
        if version:
            versions.append(version)
    except Exception as exc:
        print(f"  - ⚠️ GitHub raw 版本检查不可用: {exc}")
    if not versions:
        raise RuntimeError("GitHub 无法确定远程版本")
    return max(versions, key=_version_tuple)


def _latest_version_from_gitee():
    versions = []
    try:
        payload_bytes, content_type = _http_get(
            f"https://gitee.com/api/v5/repos/{OWNER}/{REPO}/releases/latest",
            timeout=30,
        )
        if _payload_is_html(payload_bytes, content_type):
            raise RuntimeError("Gitee API 返回了 HTML 安全验证页")
        version = _version_from_json_release(json.loads(payload_bytes.decode("utf-8")))
        if version:
            versions.append(version)
    except Exception as exc:
        print(f"  - ⚠️ Gitee Release API 不可用: {exc}")
    try:
        payload_bytes, content_type = _http_get(
            f"https://gitee.com/{OWNER}/{REPO}/raw/main/server/server.py",
            timeout=30,
        )
        if _payload_is_html(payload_bytes, content_type):
            raise RuntimeError("Gitee raw 返回了 HTML 安全验证页")
        version = _version_from_server_py(payload_bytes.decode("utf-8"))
        if version:
            versions.append(version)
    except Exception as exc:
        print(f"  - ⚠️ Gitee raw 版本检查不可用: {exc}")
    if not versions:
        raise RuntimeError("Gitee 无法确定远程版本")
    return max(versions, key=_version_tuple)


def _notice_urls(update_source="gitee"):
    gitee_url = f"https://gitee.com/{OWNER}/{REPO}/raw/main/{NOTICE_RELATIVE_PATH}"
    github_url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{NOTICE_RELATIVE_PATH}"
    return [
        gitee_url if source == "gitee" else github_url
        for source in _source_order(update_source)
    ]


def _notice_applies(notice, local_version):
    if not isinstance(notice, dict):
        return False
    if notice.get("enabled") is False:
        return False
    local = str(local_version or "").strip().lstrip("v")
    affects = notice.get("affects")
    if isinstance(affects, str):
        affects = [affects]
    if affects:
        normalized = [str(item).strip().lstrip("v") for item in affects if str(item).strip()]
        if normalized and "*" not in normalized and "all" not in normalized:
            if local not in normalized:
                return False
    local_tuple = _version_tuple(local)
    min_version = notice.get("min_version")
    max_version = notice.get("max_version")
    if min_version and local_tuple < _version_tuple(min_version):
        return False
    if max_version and local_tuple > _version_tuple(max_version):
        return False
    return True


def _select_notices(data, local_version):
    notices = data.get("notices") if isinstance(data, dict) else None
    if not isinstance(notices, list):
        return []
    return [notice for notice in notices if _notice_applies(notice, local_version)]


def _print_notices(notices):
    print("📢 项目通知")
    for notice in notices:
        level = str(notice.get("level") or "info").strip().lower()
        prefix = {"error": "❌", "warn": "⚠️", "warning": "⚠️"}.get(level, "ℹ️")
        title = str(notice.get("title") or "").strip() or "通知"
        message = notice.get("message") or ""
        if isinstance(message, list):
            message = "\n".join(str(line) for line in message)
        print(f"{prefix} {title}")
        for line in str(message).strip().splitlines():
            print(f"   {line}")
    print()


def _print_community(community):
    if not isinstance(community, dict) or not community:
        return False
    groups = community.get("qq_groups") or []
    open_groups = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        status = str(group.get("status") or "open").strip().lower()
        if status in {"full", "满", "已满"}:
            continue
        label = " ".join(
            part for part in (str(group.get("name") or "").strip(), str(group.get("id") or "").strip()) if part
        )
        if label:
            open_groups.append(label)
    print("👥 交流")
    if open_groups:
        print("   QQ群: " + "  |  ".join(open_groups))
    else:
        print("   QQ群请看 GitHub 主页最新群号")
    answer = str(community.get("qq_answer") or "github").strip()
    print(f"   入群口令: {answer}")
    ask = str(community.get("ask") or "").strip()
    if ask:
        print(f"   {ask}")
    github = str(community.get("github") or "").strip()
    gitee = str(community.get("gitee") or "").strip()
    docs = str(community.get("docs") or "").strip()
    if github:
        print(f"   GitHub: {github}")
    if gitee:
        print(f"   Gitee:  {gitee}")
    if docs:
        print(f"   文档:   {docs}")
    print()
    return True


def _local_notice_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notice.json")


def _load_notice_payload(update_source="gitee"):
    for url in _notice_urls(update_source):
        try:
            payload_bytes, content_type = _http_get(url, timeout=NOTICE_TIMEOUT)
            if _payload_is_html(payload_bytes, content_type):
                continue
            payload = json.loads(payload_bytes.decode("utf-8"))
            if isinstance(payload, dict):
                return payload, url
        except Exception:
            continue
    local_path = _local_notice_path()
    try:
        with open(local_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return payload, local_path
    except Exception:
        pass
    return None, None


def fetch_and_show_notices(local_version, update_source="gitee"):
    """Fetch live notices from the repo. Network failures never block startup."""
    try:
        payload, _source = _load_notice_payload(update_source)
        if not isinstance(payload, dict):
            print("📢 项目通知暂时获取不到，已跳过。\n")
            return
        _print_community(payload.get("community"))
        notices = _select_notices(payload, local_version)
        if notices:
            _print_notices(notices)
    except Exception:
        print("📢 项目通知检查失败，已跳过。\n")


def check_for_updates(local_version, update_source="github"):
    print("🔍 [自动更新] 正在检查 Server 更新...")
    print("   将同时尝试 GitHub 与 Gitee，优先使用配置的更新源。")
    found = []
    for source in _source_order(update_source):
        try:
            if source == "github":
                version = _latest_version_from_github()
            else:
                version = _latest_version_from_gitee()
            print(f"  - {source}: {version}")
            found.append((source, version))
        except Exception as exc:
            print(f"  - ⚠️ {source} 检查失败: {exc}")
    if not found:
        print("⚠️ [自动更新] 所有更新源都无法确定远程版本，已跳过。\n")
        return None
    source, remote_version = max(found, key=lambda item: _version_tuple(item[1]))
    if _version_tuple(remote_version) > _version_tuple(local_version):
        if source != _source_order(update_source)[0]:
            print(f"💡 配置源没有更新的版本，将使用 {source} 上的 {remote_version}。")
        return local_version, remote_version
    print("✅ [自动更新] 您的 Server 已是最新版本。\n")
    return None
