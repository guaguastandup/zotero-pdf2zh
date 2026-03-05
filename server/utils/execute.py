# execute.py
# 带进度解析的命令执行器
# 用于在执行翻译命令时，实时从子进程输出中解析进度并更新 task_manager
# 从而让 index.html 前端通过 SSE 获取实时翻译进度
#
# 关键设计：
# - macOS/Linux 使用 PTY（伪终端）让子进程以为自己在终端中运行
#   这样 Rich/tqdm 等库会实时输出进度条（而非攒到结束才输出）
# - Windows 使用 ConPTY（Windows 伪终端 API）实现类似效果
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

# 步骤进度正则：匹配所有 "步骤名 (n/m) ━━━ x/y" 格式的行，同时捕获步骤名
# 例如: "Parse Page Layout (1/1) ━━━━━ 2/2 0:00:00"
#       "Translate Paragraphs (1/1) ━━━━━ 1/1 0:00:00"
STEP_PROGRESS_RE = re.compile(r'(.+?)\(\d+/\d+\)\s+.*?(\d+)/(\d+)')

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
        _execute_with_conpty(final_cmd, final_env, task_id)


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
                'status': '运行中',
                'message': f'翻译中 {curr}/{total}'
            })
        return

    # 其次匹配步骤进度行，提取步骤名作为 message
    match = STEP_PROGRESS_RE.search(clean)
    if match:
        step_name = match.group(1).strip()
        task_manager.update_task(task_id, {
            'status': '运行中',
            'message': step_name
        })
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


def _execute_with_conpty(final_cmd, final_env, task_id):
    """
    Windows: 使用 ConPTY（Windows 伪终端 API）执行命令。

    ConPTY 是 Windows 10 1809+ 提供的原生伪终端 API，
    让子进程以为自己在真正的终端中运行，Rich 会正确输出进度条。
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32

    # Windows API 常量
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    PIPE_ACCESS_DUPLEX = 0x00000003
    PIPE_TYPE_BYTE = 0x00000000
    PIPE_READMODE_BYTE = 0x00000000
    PIPE_WAIT = 0x00000000
    INFINITE = 0xFFFFFFFF

    # 创建管道用于 ConPTY 输入/输出
    def create_pipe():
        """创建匿名管道"""
        read_handle = wintypes.HANDLE()
        write_handle = wintypes.HANDLE()
        security_attributes = wintypes.SECURITY_ATTRIBUTES()
        security_attributes.nLength = ctypes.sizeof(security_attributes)
        security_attributes.bInheritHandle = True

        if not kernel32.CreatePipe(
            ctypes.byref(read_handle),
            ctypes.byref(write_handle),
            ctypes.byref(security_attributes),
            0
        ):
            raise ctypes.WinError()
        return read_handle.value, write_handle.value

    def close_handle(handle):
        """关闭 Windows 句柄"""
        if handle:
            kernel32.CloseHandle(handle)

    # ConPTY API 函数
    try:
        # 加载 ConPTY API
        create_pseudo_console = kernel32.CreatePseudoConsole
        create_pseudo_console.restype = wintypes.HANDLE
        create_pseudo_console.argtypes = [
            ctypes.c_ulonglong,  # COORD (packed as ULONGLONG)
            wintypes.HANDLE,     # hInput
            wintypes.HANDLE,     # hOutput
            wintypes.DWORD       # dwFlags
        ]

        resize_pseudo_console = kernel32.ResizePseudoConsole
        resize_pseudo_console.argtypes = [wintypes.HANDLE, ctypes.c_ulonglong]

        close_pseudo_console = kernel32.ClosePseudoConsole
        close_pseudo_console.argtypes = [wintypes.HANDLE]
    except AttributeError:
        # ConPTY 不可用，回退到普通 PIPE 模式
        return _execute_with_pipe_fallback(final_cmd, final_env, task_id)

    # 创建管道
    conpty_read, conpty_write = create_pipe()  # 从 ConPTY 读取
    conpty_input_read, conpty_input_write = create_pipe()  # 写入 ConPTY

    # 创建 ConPTY（窗口大小 24x200）
    # COORD 结构: X (列) 在低 16 位，Y (行) 在高 16 位
    coord = 200 | (24 << 16)  # 200 列，24 行

    hpc = create_pseudo_console(coord, conpty_input_read, conpty_write, 0)
    if hpc == -1 or hpc == 0:
        close_handle(conpty_read)
        close_handle(conpty_write)
        close_handle(conpty_input_read)
        close_handle(conpty_input_write)
        raise ctypes.WinError()

    # 关闭不需要的句柄
    close_handle(conpty_input_read)
    close_handle(conpty_write)

    # 初始化 STARTUPINFOEX
    class STARTUPINFOEX(ctypes.Structure):
        _fields_ = [
            ('cb', wintypes.DWORD),
            ('lpReserved', wintypes.LPWSTR),
            ('lpDesktop', wintypes.LPWSTR),
            ('lpTitle', wintypes.LPWSTR),
            ('dwX', wintypes.DWORD),
            ('dwY', wintypes.DWORD),
            ('dwXSize', wintypes.DWORD),
            ('dwYSize', wintypes.DWORD),
            ('dwXCountChars', wintypes.DWORD),
            ('dwYCountChars', wintypes.DWORD),
            ('dwFillAttribute', wintypes.DWORD),
            ('dwFlags', wintypes.DWORD),
            ('wShowWindow', wintypes.WORD),
            ('cbReserved2', wintypes.WORD),
            ('lpReserved2', ctypes.POINTER(wintypes.BYTE)),
            ('hStdInput', wintypes.HANDLE),
            ('hStdOutput', wintypes.HANDLE),
            ('hStdError', wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('hProcess', wintypes.HANDLE),
            ('hThread', wintypes.HANDLE),
            ('dwProcessId', wintypes.DWORD),
            ('dwThreadId', wintypes.DWORD),
        ]

    # 获取属性列表大小
    size = wintypes.SIZE()
    kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))

    # 分配属性列表
    attr_list = (ctypes.c_char * size.value)()
    attr_list_ptr = ctypes.cast(attr_list, ctypes.c_void_p)

    if not kernel32.InitializeProcThreadAttributeList(attr_list_ptr, 1, 0, ctypes.byref(size)):
        close_pseudo_console(hpc)
        close_handle(conpty_read)
        close_handle(conpty_input_write)
        raise ctypes.WinError()

    # 设置 ConPTY 属性
    PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
    if not kernel32.UpdateProcThreadAttribute(
        attr_list_ptr,
        0,
        PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
        hpc,
        ctypes.sizeof(wintypes.HANDLE),
        None,
        None
    ):
        kernel32.DeleteProcThreadAttributeList(attr_list_ptr)
        close_pseudo_console(hpc)
        close_handle(conpty_read)
        close_handle(conpty_input_write)
        raise ctypes.WinError()

    # 设置启动信息
    startup_info = STARTUPINFOEX()
    startup_info.cb = ctypes.sizeof(startup_info)
    startup_info.dwFlags = 0x00000100  # STARTF_USESTDHANDLES
    startup_info.lpAttributeList = attr_list_ptr

    process_info = PROCESS_INFORMATION()

    # 构建命令行
    cmdline = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in final_cmd)

    # 构建环境块
    env_block = '\0'.join(f'{k}={v}' for k, v in final_env.items()) + '\0\0'
    env_block = env_block.encode('utf-16le')

    # 创建进程
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    EXTENDED_STARTUPINFO_PRESENT = 0x00080000

    success = kernel32.CreateProcessW(
        None,
        cmdline,
        None,
        None,
        False,
        CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT,
        env_block,
        None,
        ctypes.byref(startup_info),
        ctypes.byref(process_info)
    )

    # 清理
    kernel32.DeleteProcThreadAttributeList(attr_list_ptr)

    if not success:
        close_pseudo_console(hpc)
        close_handle(conpty_read)
        close_handle(conpty_input_write)
        raise ctypes.WinError()

    # 关闭不需要的句柄
    close_handle(process_info.hThread)
    close_handle(conpty_input_write)

    try:
        # 读取 ConPTY 输出
        buffer = ctypes.create_string_buffer(4096)
        bytes_read = wintypes.DWORD()

        while True:
            # 检查进程是否结束
            exit_code = wintypes.DWORD()
            if kernel32.GetExitCodeProcess(process_info.hProcess, ctypes.byref(exit_code)):
                if exit_code.value != 259:  # STILL_ACTIVE = 259
                    # 进程已结束，读取剩余数据
                    while True:
                        if kernel32.ReadFile(conpty_read, buffer, 4096, ctypes.byref(bytes_read), None):
                            if bytes_read.value == 0:
                                break
                            text = buffer.raw[:bytes_read.value].decode('utf-8', errors='replace')
                            sys.stdout.write(text)
                            sys.stdout.flush()
                            _parse_progress(text, task_id)
                        else:
                            break
                    break

            # 读取输出
            if kernel32.ReadFile(conpty_read, buffer, 4096, ctypes.byref(bytes_read), None):
                if bytes_read.value > 0:
                    text = buffer.raw[:bytes_read.value].decode('utf-8', errors='replace')
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    _parse_progress(text, task_id)

        # 等待进程结束
        kernel32.WaitForSingleObject(process_info.hProcess, INFINITE)
        kernel32.GetExitCodeProcess(process_info.hProcess, ctypes.byref(exit_code))

        if exit_code.value != 0:
            raise subprocess.CalledProcessError(exit_code.value, final_cmd)

    finally:
        close_handle(process_info.hProcess)
        close_pseudo_console(hpc)
        close_handle(conpty_read)


def _execute_with_pipe_fallback(final_cmd, final_env, task_id):
    """
    Windows ConPTY 不可用时的回退方案：使用普通 PIPE 模式。
    注意：进度条会每次换行显示，这是 PIPE 模式的限制。
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
