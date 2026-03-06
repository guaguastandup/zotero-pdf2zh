import codecs
import os
import re
import select
import subprocess
import sys

from utils.task_manager import task_manager

# 1. 精准锁定主线进度，完美避开带有字母和括号的支线任务
MAIN_PROGRESS_RE = re.compile(
    r"\btranslate\s+[^a-zA-Z\(\)\r\n]*?(\d+)/(\d+)\b", 
    re.IGNORECASE
)

# 2. 锁定子步骤状态文本
STEP_PROGRESS_RE = re.compile(r"(.+?)\(\d+/\d+\)\s+.*?(\d+)/(\d+)")

# 3. 兼容历史遗留格式
LEGACY_PROGRESS_RE = re.compile(r"(?:translate|Running|Parse).*?(\d+)/(\d+)", re.IGNORECASE)

# 清理 ANSI 颜色和控制字符
ANSI_ESCAPE = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")


def execute_with_progress(cmd, task_id, args, env_manager):
    """Execute translation command and update task progress in real time."""
    final_cmd = cmd
    final_env = os.environ.copy()
    
    # 强制开启终端模式和颜色，这能保证底层工具使用 \r 覆盖刷新，防止 \n 疯狂刷屏滚动
    final_env["PYTHONUNBUFFERED"] = "1"
    final_env["COLUMNS"] = "200"
    final_env["FORCE_COLOR"] = "1"
    final_env["FORCE_TERMINAL"] = "1"
    final_env.pop("NO_COLOR", None)
    final_env["TERM"] = "xterm-256color"

    if args.enable_venv and env_manager:
        venv_cmd, venv_env = env_manager.get_command_and_env(cmd)
        final_cmd = venv_cmd
        final_env.update(venv_env)

    print(f"[execute_with_progress] {' '.join(final_cmd)}\n")

    if sys.platform != "win32":
        _execute_with_pty(final_cmd, final_env, task_id)
    else:
        # Windows 也彻底抛弃复杂的屏幕抓取，采用干净安全的管道模式
        _execute_with_pipe(final_cmd, final_env, task_id)


def _parse_progress(text, task_id):
    """Parse progress info from text and update task_manager."""
    if task_id is None:
        return

    clean = ANSI_ESCAPE.sub("", text)

    # 核心升级：使用 findall 而不是 search。
    # 当流式读取一次性读入一大块数据(可能包含多个进度)时，直接取最后一个[-1]，确保前端不掉帧！
    
    # 1. 处理主线进度
    main_matches = MAIN_PROGRESS_RE.findall(clean)
    if main_matches:
        curr, total = int(main_matches[-1][0]), int(main_matches[-1][1])
        if total > 0:
            pct = int((curr / total) * 100)
            task_manager.update_task(task_id, {
                "progress": pct,
                "status": "running",
                "message": f"translate {curr}/{total}",
            })

    # 2. 处理子步骤信息 (只更新 message，绝对不碰 progress)
    step_matches = STEP_PROGRESS_RE.findall(clean)
    if step_matches:
        step_name = step_matches[-1][0].strip()
        task_manager.update_task(task_id, {
            "status": "running",
            "message": step_name,
        })

    # 3. 如果前两个都没匹配到，再尝试遗留格式
    if not main_matches and not step_matches:
        legacy_matches = LEGACY_PROGRESS_RE.findall(clean)
        if legacy_matches:
            curr, total = int(legacy_matches[-1][0]), int(legacy_matches[-1][1])
            if total > 0:
                pct = int((curr / total) * 100)
                task_manager.update_task(task_id, {
                    "progress": pct,
                    "status": "running",
                })


def _execute_with_pty(final_cmd, final_env, task_id):
    """macOS/Linux: run command in PTY and parse progress from stream."""
    import pty

    master_fd, slave_fd = pty.openpty()
    try:
        import fcntl
        import termios
        import struct
        winsize = struct.pack("HHHH", 24, 200, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    except Exception:
        pass

    process = subprocess.Popen(
        final_cmd, stdout=slave_fd, stderr=slave_fd, env=final_env, bufsize=0, close_fds=True
    )
    os.close(slave_fd)

    # 增量解码器：完美解决截断乱码
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    try:
        while True:
            readable, _, _ = select.select([master_fd], [], [], 0.1)
            if master_fd in readable:
                try:
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    
                    text = decoder.decode(data)
                    if text:
                        sys.stdout.write(text)
                        sys.stdout.flush()
                        _parse_progress(text, task_id)
                except OSError:
                    break

            if process.poll() is not None:
                try:
                    import fcntl as _fcntl
                    fl = _fcntl.fcntl(master_fd, _fcntl.F_GETFL)
                    _fcntl.fcntl(master_fd, _fcntl.F_SETFL, fl | os.O_NONBLOCK)
                    while True:
                        data = os.read(master_fd, 4096)
                        if not data:
                            text = decoder.decode(b"", final=True)
                            if text:
                                sys.stdout.write(text)
                                sys.stdout.flush()
                                _parse_progress(text, task_id)
                            break
                        
                        text = decoder.decode(data)
                        if text:
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
    Windows: 抛弃复杂的屏幕抓取，采用安全可靠的管道流式读取。
    支持完美的并发执行，进程之间彻底隔离。
    """
    process = subprocess.Popen(
        final_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # 将错误日志也合并进来防止遗漏
        env=final_env,
        bufsize=0,
    )

    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    
    try:
        while True:
            # 兼容 Windows 的阻塞式管道读取
            data = process.stdout.read(4096)
            if not data:
                break
                
            text = decoder.decode(data)
            if text:
                sys.stdout.write(text)
                sys.stdout.flush()
                _parse_progress(text, task_id)

        # 清理最后残留的半个字符
        text = decoder.decode(b"", final=True)
        if text:
            sys.stdout.write(text)
            sys.stdout.flush()
            _parse_progress(text, task_id)
            
    except Exception:
        pass

    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, final_cmd)