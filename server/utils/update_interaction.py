"""Keep container/service startup independent of interactive stdin."""
import argparse
import os
import sys
from pathlib import Path


def is_container():
    return (
        os.environ.get('ZOTERO_PDF2ZH_CONTAINER') == '1'
        or Path('/.dockerenv').exists()
        or Path('/run/.containerenv').exists()
    )


def update_mode(argv=None):
    """Legacy check_update=False wins; retain prompt for existing desktop scripts."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--update-mode', choices=('notify', 'prompt', 'off'), default='prompt')
    parser.add_argument('--check_update', default='true')
    args, _ = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    if str(args.check_update).lower() in {'false', 'f', '0', 'no', 'n'}:
        return 'off'
    return args.update_mode


def can_prompt_for_update():
    return update_mode() == 'prompt' and not is_container() and bool(sys.stdin and sys.stdin.isatty())


def source_update_requested():
    if update_mode() == 'off':
        return False
    if is_container():
        print('Docker 中不交互更新源码。请在宿主机 docker 目录运行 sh update.sh（Windows: .\\update.ps1）。')
        print('内置引擎或自定义部署请按对应 Compose 配置重新构建并启动服务。')
        return False
    if not can_prompt_for_update():
        print('已保留当前版本；需要更新时请使用对应安装方式的更新命令。')
        return False
    try:
        return input('是否要立即更新? (y/n): ').strip().lower() in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        print('\n已取消更新。')
        return False
