# execute.py
# 带进度解析的命令执行器

import re
import subprocess
import os
import sys
import select
from utils.task_manager import task_manager

# Windows VT 模式启用标志
_WINDOWS_VT_ENABLED = False

def _enable_windows_vt_mode():
    """
    在 Windows 上启用虚拟终端序列（VT mode）支持。
    让终端能够正确渲染 PTY 传过来的 ANSI 颜色和光标控制码。
    """
    global _WINDOWS_VT_ENABLED
    if sys.platform != 'win32':
        return True
    if _WINDOWS_VT_ENABLED:
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        if handle == -1: return False
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0: return False
        if kernel32.SetConsoleMode(handle, mode.value | 0x0004) == 0: return False
        _WINDOWS_VT_ENABLED = True
        return True
    except Exception:
        return False

# 进度条正则匹配
MAIN_PROGRESS_RE = re.compile(r'(?:^|\s)translate\s+.*?(\d+)/(\d+)')
STEP_PROGRESS_RE = re.compile(r'(.+?)\(\d+/\d+\)\s+.*?(\d+)/(\d+)')
LEGACY_PROGRESS_RE = re.compile(r'(?:translate|Running|Parse).*?(\d+)/(\d+)', re.IGNORECASE)
ANSI_ESCAPE = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')


def execute_with_progress(cmd, task_id, args, env_manager):
    """
    执行翻译命令并实时解析进度。
    """
    final_cmd = cmd
    final_env = os.environ.copy()
    final_env['PYTHONUNBUFFERED'] = '1'
    final_env['COLUMNS'] = '200'
    final_env['FORCE_COLOR'] = '1'
    final_env.pop('NO_COLOR', None)
    final_env['TERM'] = 'xterm-256color'

    # 完全保留原有的 venv 逻辑，精准定位虚拟环境
    if args.enable_venv and env_manager:
        venv_cmd, venv_env = env_manager.get_command_and_env(cmd)
        final_cmd = venv_cmd
        final_env.update(venv_env)

    print(f"🚀 执行命令: {' '.join(final_cmd)}\n")

    if sys.platform != 'win32':
        # macOS/Linux 原生 PTY
        _execute_with_pty(final_cmd, final_env, task_id)
    else:
        # Windows 分支：尝试加载 pywinpty
        try:
            import winpty
            _execute_with_winpty(final_cmd, final_env, task_id)
        except ImportError:
            print("⚠️ [提示] 未检测到 pywinpty 库。")
            print("💡 为获得不刷屏、带颜色的完美多行进度条 UI，建议执行: pip install pywinpty")
            print("⏳ 暂时降级为基础管道模式（终端会出现滚屏换行）...")
            _execute_with_pipe_fallback(final_cmd, final_env, task_id)


def _parse_progress(text, task_id):
    """进度解析发往前端"""
    if task_id is None: return
    clean = ANSI_ESCAPE.sub('', text)

    match = MAIN_PROGRESS_RE.search(clean)
    if match:
        curr, total = int(match.group(1)), int(match.group(2))
        if total > 0:
            task_manager.update_task(task_id, {
                'progress': int((curr / total) * 100),
                'status': '运行中',
                'message': f'翻译中 {curr}/{total}'
            })
        return

    match = STEP_PROGRESS_RE.search(clean)
    if match:
        task_manager.update_task(task_id, {'status': '运行中', 'message': match.group(1).strip()})
        return

    match = LEGACY_PROGRESS_RE.search(clean)
    if match:
        curr, total = int(match.group(1)), int(match.group(2))
        if total > 0:
            task_manager.update_task(task_id, {'progress': int((curr / total) * 100), 'status': '运行中'})


def _execute_with_pty(final_cmd, final_env, task_id):
    """macOS/Linux 原生 PTY 实现"""
    import pty
    master_fd, slave_fd = pty.openpty()
    try:
        import fcntl, termios, struct
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 200, 0, 0))
    except Exception: pass

    process = subprocess.Popen(final_cmd, stdout=slave_fd, stderr=slave_fd, env=final_env, bufsize=0, close_fds=True)
    os.close(slave_fd)

    try:
        while True:
            readable, _, _ = select.select([master_fd], [], [], 0.1)
            if master_fd in readable:
                try:
                    data = os.read(master_fd, 4096)
                    if not data: break
                    text = data.decode('utf-8', errors='replace')
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    _parse_progress(text, task_id)
                except OSError: break
            if process.poll() is not None:
                try:
                    import fcntl as _fcntl
                    fl = _fcntl.fcntl(master_fd, _fcntl.F_GETFL)
                    _fcntl.fcntl(master_fd, _fcntl.F_SETFL, fl | os.O_NONBLOCK)
                    while True:
                        data = os.read(master_fd, 4096)
                        if not data: break
                        text = data.decode('utf-8', errors='replace')
                        sys.stdout.write(text)
                        sys.stdout.flush()
                        _parse_progress(text, task_id)
                except Exception: pass
                break
        os.close(master_fd)
        if process.wait() != 0: raise subprocess.CalledProcessError(process.returncode, final_cmd)
    except Exception:
        if process.poll() is None: process.kill()
        try: os.close(master_fd)
        except Exception: pass
        raise


def _execute_with_winpty(final_cmd, final_env, task_id):
    """
    Windows 完美实现：借助 pywinpty 创建真实的伪终端。
    多行任务、颜色、光标控制码将完全等同于 Mac 表现。
    """
    from winpty import PtyProcess
    
    # 必须开启 VT 模式，父终端才能解析 winpty 传出来的 ANSI 颜色码
    _enable_windows_vt_mode()
    
    # 启动进程，设置足够的宽高避免被挤换行 (rows=24, cols=200)
    process = PtyProcess.spawn(final_cmd, env=final_env, dimensions=(24, 200))

    try:
        while True:
            try:
                # read() 会捕获子进程在伪终端里绘制的原生字节，包括进度条覆盖动画
                text = process.read()
                if not text:
                    continue
                # 直接输出，不需要任何正则过滤，UI 100% 完美
                sys.stdout.write(text)
                sys.stdout.flush()
                # 扔给清洗器处理前端数据
                _parse_progress(text, task_id)
            except EOFError:
                # 进程输出结束
                break
        
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, final_cmd)
            
    except Exception:
        process.terminate()
        raise


def _execute_with_pipe_fallback(final_cmd, final_env, task_id):
    """
    Windows 降级预案：如果没有安装 pywinpty，回退到普通打日志模式。
    保证前端绝对不挂，仅仅是终端 UI 会滚屏而已。
    """
    _enable_windows_vt_mode()
    final_env['RICH_FORCE_WIDTH'] = '200'

    process = subprocess.Popen(
        final_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=final_env,
        bufsize=1,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    try:
        # 逐行读取，老老实实滚屏，不乱改光标
        for line in iter(process.stdout.readline, ''):
            sys.stdout.write(line)
            sys.stdout.flush()
            _parse_progress(line, task_id)

        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, final_cmd)
    except Exception:
        if process.poll() is None:
            process.kill()
        raise