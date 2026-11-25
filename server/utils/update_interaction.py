"""Keep container/service startup independent of interactive stdin."""
import os
import sys
from pathlib import Path


def is_container():
    return (
        os.environ.get('ZOTERO_PDF2ZH_CONTAINER') == '1'
        or Path('/.dockerenv').exists()
        or Path('/run/.containerenv').exists()
    )


def can_prompt_for_update():
    return not is_container() and bool(sys.stdin and sys.stdin.isatty())


def source_update_requested():
    if is_container():
        print('Docker 中不交互更新源码。请在宿主机 docker 目录运行 sh update.sh（Windows: .\\update.ps1）。')
        print('docker2 或自定义部署请按对应 Compose 配置重新构建并启动服务。')
        return False
    if not can_prompt_for_update():
        print('当前启动没有交互终端，跳过更新询问。请在维护窗口更新 Server。')
        return False
    try:
        return input('是否要立即更新? (y/n): ').strip().lower() in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        print('\n已取消更新。')
        return False
