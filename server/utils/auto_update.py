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
