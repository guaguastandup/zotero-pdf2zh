# execute.py
# 带进度解析的命令执行器
# 用于在执行翻译命令时，实时从子进程输出中解析进度并更新 task_manager
# 从而让 index.html 前端通过 SSE 获取实时翻译进度
#
# 关键设计：
# - macOS/Linux 使用 PTY（伪终端）让子进程以为自己在终端中运行
#   这样 Rich/tqdm 等库会实时输出进度条（而非攒到结束才输出）
# - Windows 使用 PIPE 模式（PTY 不可用）
# - 从输出中解析 "100/771" 这类进度数字，计算百分比后推送给前端

import re
import subprocess
import os
import sys
import select
from utils.task_manager import task_manager

# 主进度正则：匹配 "translate ━━━━ 50/100 0:00:15" 这种总进度行
# 这是 pdf2zh_next 的 Rich 总进度条，名称固定为 "translate"
MAIN_PROGRESS_RE = re.compile(r'(?:^|\s)translate\s+.*?(\d+)/(\d+)')

# 步骤进度正则：匹配所有 "步骤名 (n/m) ━━━ x/y" 格式的行
# 例如: "Parse Page Layout (1/1) ━━━━━ 2/2 0:00:00"
#       "Translate Paragraphs (1/1) ━━━━━ 1/1 0:00:00"
#       "Save PDF (1/1) ━━━━━ 2/2 0:00:05"
STEP_PROGRESS_RE = re.compile(r'.+?\(\d+/\d+\)\s+.*?(\d+)/(\d+)')

# pdf2zh (1.x) 的进度正则
LEGACY_PROGRESS_RE = re.compile(r'(?:translate|Running|Parse).*?(\d+)/(\d+)', re.IGNORECASE)

# 用于清除 ANSI 转义序列（颜色码等），以便正则匹配纯文本
ANSI_ESCAPE = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')


def execute_with_progress(cmd, task_id, args, env_manager):
    """
    执行翻译命令并实时解析进度，更新 task_manager 供前端显示。

    参数:
        cmd: 命令列表，如 ['pdf2zh', 'input.pdf', '--service', 'google', ...]
        task_id: 任务唯一标识，用于 task_manager.update_task()（可为 None）
        args: argparse 解析后的启动参数（需要 args.enable_venv）
        env_manager: VirtualEnvManager 实例（可为 None）
    """
    final_cmd = cmd
    final_env = os.environ.copy()
    final_env['PYTHONUNBUFFERED'] = '1'  # 强制子进程无缓冲输出
    # 设置终端宽度，避免 Rich 把进度条和时间拆成两行
    final_env['COLUMNS'] = '200'
    # 启用彩色输出（Rich 需要）
    final_env['FORCE_COLOR'] = '1'
    final_env.pop('NO_COLOR', None)
    final_env['TERM'] = 'xterm-256color'

    # 如果启用了虚拟环境，通过 env_manager 获取处理后的命令和环境变量
    if args.enable_venv and env_manager:
        venv_cmd, venv_env = env_manager.get_command_and_env(cmd)
        final_cmd = venv_cmd
        final_env.update(venv_env)

    print(f"🚀 执行命令: {' '.join(final_cmd)}\n")

    if sys.platform != 'win32':
        _execute_with_pty(final_cmd, final_env, task_id)
    else:
        _execute_with_pipe(final_cmd, final_env, task_id)


def _parse_progress(text, task_id):
    """从一段文本中解析进度百分比并更新 task_manager"""
    if task_id is None:
        return

    clean = ANSI_ESCAPE.sub('', text)

    # 优先匹配主进度行（translate 50/100）
    match = MAIN_PROGRESS_RE.search(clean)
    if match:
        curr, total = int(match.group(1)), int(match.group(2))
        if total > 0:
            pct = int((curr / total) * 100)
            task_manager.update_task(task_id, {
                'progress': pct,
                'status': '运行中'
            })
        return

    # 其次匹配步骤进度行
    match = STEP_PROGRESS_RE.search(clean)
    if match:
        # 步骤进度不更新百分比（避免覆盖总进度），只更新状态文本
        task_manager.update_task(task_id, {'status': '运行中'})
        return

    # 最后尝试 pdf2zh 1.x 的旧格式
    match = LEGACY_PROGRESS_RE.search(clean)
    if match:
        curr, total = int(match.group(1)), int(match.group(2))
        if total > 0:
            pct = int((curr / total) * 100)
            task_manager.update_task(task_id, {
                'progress': pct,
                'status': '运行中'
            })


def _execute_with_pty(final_cmd, final_env, task_id):
    """
    macOS/Linux: 使用 PTY（伪终端）执行命令。
    PTY 让子进程以为自己在真实终端中运行，Rich/tqdm 会实时输出进度条。
    """
    import pty

    master_fd, slave_fd = pty.openpty()

    # 设置 PTY 窗口大小（200 列），避免 Rich 折行
    try:
        import fcntl
        import termios
        import struct
        winsize = struct.pack('HHHH', 24, 200, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    except Exception:
        pass

    process = subprocess.Popen(
        final_cmd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=final_env,
        bufsize=0,
        close_fds=True
    )
    os.close(slave_fd)

    try:
        while True:
            readable, _, _ = select.select([master_fd], [], [], 0.1)
            if master_fd in readable:
                try:
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    text = data.decode('utf-8', errors='replace')
                    # 写回终端
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    # 解析进度
                    _parse_progress(text, task_id)
                except OSError:
                    break
            if process.poll() is not None:
                # 进程结束，读取剩余输出
                try:
                    import fcntl as _fcntl
                    fl = _fcntl.fcntl(master_fd, _fcntl.F_GETFL)
                    _fcntl.fcntl(master_fd, _fcntl.F_SETFL, fl | os.O_NONBLOCK)
                    while True:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        text = data.decode('utf-8', errors='replace')
                        sys.stdout.write(text)
                        sys.stdout.flush()
                        _parse_progress(text, task_id)
                except Exception:
                    pass
                break

        os.close(master_fd)
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, final_cmd)

    except Exception:
        if process.poll() is None:
            process.kill()
        try:
            os.close(master_fd)
        except Exception:
            pass
        raise


def _execute_with_pipe(final_cmd, final_env, task_id):
    """
    Windows: 使用 PIPE 模式执行命令。
    PTY 在 Windows 上不可用，回退到 PIPE 模式（进度更新可能不如 PTY 实时）。
    """
    process = subprocess.Popen(
        final_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=final_env,
        bufsize=0,
        text=False
    )

    try:
        while True:
            output = process.stdout.read(1024)
            if output == b'' and process.poll() is not None:
                break
            if output:
                text = output.decode('utf-8', errors='replace')
                sys.stdout.write(text)
                sys.stdout.flush()
                _parse_progress(text, task_id)

        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, final_cmd)

    except Exception:
        if process.poll() is None:
            process.kill()
        raise
