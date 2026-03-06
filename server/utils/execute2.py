import codecs
import os
import re
import select
import subprocess
import sys
import threading
from datetime import datetime

from utils.task_manager import task_manager


# 精准锁定主线进度，完美避开带有字母和括号的支线任务 (如 "Translate Paragraphs (1/1)")
MAIN_PROGRESS_RE = re.compile(
    r"\btranslate\s+[^a-zA-Z\(\)\r\n]*?(\d+)/(\d+)\b", 
    re.IGNORECASE
)

# Match step-like lines where only status message should be updated
STEP_PROGRESS_RE = re.compile(r"(.+?)\(\d+/\d+\)\s+.*?(\d+)/(\d+)")

# Legacy pdf2zh (1.x) progress format
LEGACY_PROGRESS_RE = re.compile(r"(?:translate|Running|Parse).*?(\d+)/(\d+)", re.IGNORECASE)

# Strip ANSI sequences before regex matching
ANSI_ESCAPE = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")

WINDOWS_MONITOR_INTERVAL = 0.05
WINDOWS_CONSOLE_SCAN_ROWS = 220
WINDOWS_MIN_COLUMNS = 160

DEBUG_PROGRESS_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "_debug_progress.log",
)
_DEBUG_PROGRESS_LOG_LOCK = threading.Lock()


def _debug_progress_log(stage, **fields):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        parts = []
        for key in sorted(fields.keys()):
            value = str(fields[key]).replace("\r", "\\r").replace("\n", "\\n")
            if len(value) > 260:
                value = value[:260] + "..."
            parts.append(f"{key}={value}")
        line = f"[{ts}] [{stage}] " + " ".join(parts)
        with _DEBUG_PROGRESS_LOG_LOCK:
            with open(DEBUG_PROGRESS_LOG_PATH, "a", encoding="utf-8", errors="replace") as fp:
                fp.write(line + "\n")
    except Exception:
        pass


def execute_with_progress(cmd, task_id, args, env_manager):
    """Execute translation command and update task progress in real time."""
    final_cmd = cmd
    final_env = os.environ.copy()
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
        _execute_with_inherit(final_cmd, final_env, task_id)


def _parse_progress(text, task_id):
    """Parse progress info from text and update task_manager."""
    if task_id is None:
        return

    clean = ANSI_ESCAPE.sub("", text)

    # 1. Main translation progress (preferred)
    match = MAIN_PROGRESS_RE.search(clean)
    if match:
        curr, total = int(match.group(1)), int(match.group(2))
        if total > 0:
            pct = int((curr / total) * 100)
            task_manager.update_task(task_id, {
                "progress": pct,
                "status": "running",
                "message": f"translate {curr}/{total}",
            })
        return

    # 2. Step status text (secondary)
    # 只更新 message 状态，绝对不碰 progress，防止覆盖主进度！
    match = STEP_PROGRESS_RE.search(clean)
    if match:
        step_name = match.group(1).strip()
        task_manager.update_task(task_id, {
            "status": "running",
            "message": step_name,
        })
        return

    # 3. Legacy format
    match = LEGACY_PROGRESS_RE.search(clean)
    if match:
        curr, total = int(match.group(1)), int(match.group(2))
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
        final_cmd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=final_env,
        bufsize=0,
        close_fds=True,
    )
    os.close(slave_fd)

    # 增量解码器：完美解决多字节字符（如进度条方块）被 os.read 截断导致的乱码问题
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
                            # 循环结束，清空解码器中可能残留的半个字符
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


def _monitor_windows_console_translate_progress(task_id, stop_event):
    """
    Windows-only monitor:
    Read console buffer and parse only "translate ... x/y".
    This keeps native progress bars untouched while enabling SSE updates.
    """
    if task_id is None:
        return

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        _debug_progress_log("MONITOR_IMPORT_ERROR", task_id=task_id)
        return

    STD_OUTPUT_HANDLE = -11
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class COORD(ctypes.Structure):
        _fields_ = [
            ("X", wintypes.SHORT),
            ("Y", wintypes.SHORT),
        ]

    class SMALL_RECT(ctypes.Structure):
        _fields_ = [
            ("Left", wintypes.SHORT),
            ("Top", wintypes.SHORT),
            ("Right", wintypes.SHORT),
            ("Bottom", wintypes.SHORT),
        ]

    class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
        _fields_ = [
            ("dwSize", COORD),
            ("dwCursorPosition", COORD),
            ("wAttributes", wintypes.WORD),
            ("srWindow", SMALL_RECT),
            ("dwMaximumWindowSize", COORD),
        ]

    try:
        kernel32 = ctypes.windll.kernel32

        get_std_handle = kernel32.GetStdHandle
        get_std_handle.argtypes = [wintypes.DWORD]
        get_std_handle.restype = wintypes.HANDLE

        get_csbi = kernel32.GetConsoleScreenBufferInfo
        get_csbi.restype = wintypes.BOOL

        read_console = kernel32.ReadConsoleOutputCharacterW
        read_console.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            COORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        read_console.restype = wintypes.BOOL
    except Exception as e:
        _debug_progress_log("MONITOR_WINAPI_ERROR", task_id=task_id, error=str(e))
        return

    handle = get_std_handle(STD_OUTPUT_HANDLE)
    if handle in (None, 0, INVALID_HANDLE_VALUE):
        _debug_progress_log("MONITOR_HANDLE_INVALID", task_id=task_id)
        return

    _debug_progress_log("MONITOR_STARTED", task_id=task_id)

    locked_total = None
    last_curr = None
    last_row = None
    last_step = None
    idle_ticks = 0
    last_error = ""

    while not stop_event.is_set():
        try:
            csbi = CONSOLE_SCREEN_BUFFER_INFO()
            if not get_csbi(handle, ctypes.byref(csbi)):
                _debug_progress_log("MONITOR_CSBI_FAIL", task_id=task_id)
                break

            width = max(int(csbi.dwSize.X), 1)
            buffer_rows = max(int(csbi.dwSize.Y), 1)
            cursor_y = int(csbi.dwCursorPosition.Y)

            start_row = max(0, cursor_y - WINDOWS_CONSOLE_SCAN_ROWS)
            end_row = min(buffer_rows - 1, cursor_y + 2)
            if end_row < start_row:
                start_row, end_row = 0, min(buffer_rows - 1, WINDOWS_CONSOLE_SCAN_ROWS)

            pair_candidates = []
            latest_step = None
            latest_step_row = -1
            translate_line_sample = None

            for row in range(start_row, end_row + 1):
                buf = ctypes.create_unicode_buffer(width)
                chars_read = wintypes.DWORD(0)
                ok = read_console(
                    handle,
                    buf,
                    width,
                    COORD(0, row),
                    ctypes.byref(chars_read),
                )
                if not ok or chars_read.value <= 0:
                    continue

                line = buf.value[: chars_read.value].strip()
                if not line:
                    continue

                if translate_line_sample is None and "translate" in line.lower():
                    translate_line_sample = line[:220]

                step_m = STEP_PROGRESS_RE.search(line)
                if step_m and row >= latest_step_row:
                    latest_step = step_m.group(1).strip()
                    latest_step_row = row

                m = MAIN_PROGRESS_RE.search(line)
                if not m:
                    continue

                curr, total = int(m.group(1)), int(m.group(2))
                if total <= 0:
                    continue
                if locked_total is not None and total != locked_total:
                    continue

                pair_candidates.append((row, curr, total))

            if pair_candidates:
                idle_ticks = 0
                if locked_total is None:
                    max_total = max(c[2] for c in pair_candidates)
                    pair_candidates = [c for c in pair_candidates if c[2] == max_total]
                    pair_candidates.sort(key=lambda c: (abs(c[0] - cursor_y), -c[0], -c[1]))
                    row, curr, total = pair_candidates[0]
                    locked_total = total
                    _debug_progress_log("LOCK_TOTAL", task_id=task_id, row=row, total=total)
                else:
                    def _rank(candidate):
                        row = candidate[0]
                        dist_prev = abs(row - last_row) if last_row is not None else abs(row - cursor_y)
                        dist_cursor = abs(row - cursor_y)
                        return (dist_prev, dist_cursor, -row)

                    pair_candidates.sort(key=_rank)
                    row, curr, total = pair_candidates[0]

                if last_curr is None or curr >= last_curr:
                    last_row = row
                    if last_curr is None or curr != last_curr:
                        last_curr = curr
                        # Keep 100% for final completion update only.
                        pct = 99 if curr >= total else int((curr / total) * 100)
                        task_manager.update_task(task_id, {
                            "progress": pct,
                            "status": "running",
                            "message": f"translate {curr}/{total}",
                        })
                        _debug_progress_log(
                            "PARSE_PROGRESS",
                            task_id=task_id,
                            row=row,
                            curr=curr,
                            total=total,
                            pct=pct,
                            locked_total=locked_total,
                        )
            else:
                idle_ticks += 1
                if idle_ticks % 40 == 0:
                    _debug_progress_log(
                        "PARSE_IDLE",
                        task_id=task_id,
                        cursor=cursor_y,
                        start=start_row,
                        end=end_row,
                        locked_total=locked_total,
                        sample=translate_line_sample,
                    )

            if latest_step and latest_step != last_step:
                last_step = latest_step
                task_manager.update_task(task_id, {
                    "status": "running",
                    "message": latest_step,
                })
                _debug_progress_log("PARSE_STEP", task_id=task_id, step=latest_step)
        except Exception as e:
            err_text = str(e)
            if err_text != last_error:
                last_error = err_text
                _debug_progress_log("MONITOR_ERROR", task_id=task_id, error=err_text)

        stop_event.wait(WINDOWS_MONITOR_INTERVAL)


def _guard_windows_console_min_width(stop_event, min_cols=WINDOWS_MIN_COLUMNS):
    """
    Best-effort width guard for accidental terminal shrinking on Windows.
    If width becomes too small, restore it quickly to reduce rich/tqdm wrap spam.
    """
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return

    STD_OUTPUT_HANDLE = -11
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class COORD(ctypes.Structure):
        _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

    class SMALL_RECT(ctypes.Structure):
        _fields_ = [
            ("Left", wintypes.SHORT),
            ("Top", wintypes.SHORT),
            ("Right", wintypes.SHORT),
            ("Bottom", wintypes.SHORT),
        ]

    class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
        _fields_ = [
            ("dwSize", COORD),
            ("dwCursorPosition", COORD),
            ("wAttributes", wintypes.WORD),
            ("srWindow", SMALL_RECT),
            ("dwMaximumWindowSize", COORD),
        ]

    try:
        kernel32 = ctypes.windll.kernel32

        get_std_handle = kernel32.GetStdHandle
        get_std_handle.argtypes = [wintypes.DWORD]
        get_std_handle.restype = wintypes.HANDLE

        get_csbi = kernel32.GetConsoleScreenBufferInfo
        get_csbi.restype = wintypes.BOOL

        set_buffer_size = kernel32.SetConsoleScreenBufferSize
        set_buffer_size.argtypes = [wintypes.HANDLE, COORD]
        set_buffer_size.restype = wintypes.BOOL

        set_window_info = kernel32.SetConsoleWindowInfo
        set_window_info.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(SMALL_RECT)]
        set_window_info.restype = wintypes.BOOL
    except Exception:
        return

    handle = get_std_handle(STD_OUTPUT_HANDLE)
    if handle in (None, 0, INVALID_HANDLE_VALUE):
        return

    while not stop_event.is_set():
        try:
            csbi = CONSOLE_SCREEN_BUFFER_INFO()
            if not get_csbi(handle, ctypes.byref(csbi)):
                break

            win = csbi.srWindow
            width = int(win.Right - win.Left + 1)
            height = int(win.Bottom - win.Top + 1)

            if width < min_cols:
                target_width = int(min_cols)
                target_height = max(int(csbi.dwSize.Y), height, 200)
                target_buffer_width = max(int(csbi.dwSize.X), target_width)

                set_buffer_size(handle, COORD(target_buffer_width, target_height))

                new_top = max(0, min(int(win.Top), target_height - height))
                new_rect = SMALL_RECT(
                    0,
                    new_top,
                    target_width - 1,
                    new_top + height - 1,
                )
                set_window_info(handle, True, ctypes.byref(new_rect))
        except Exception:
            pass

        stop_event.wait(0.08)


def _execute_with_inherit(final_cmd, final_env, task_id):
    """
    Windows: inherit stdout/stderr so terminal keeps native multi-progress UI.
    Progress parsing is done by a side monitor reading console buffer.
    """
    process = subprocess.Popen(
        final_cmd,
        stdout=None,
        stderr=None,
        env=final_env,
        bufsize=0,
        text=False,
    )

    _debug_progress_log("EXECUTE_START", task_id=task_id, cmd=" ".join(final_cmd))

    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=_monitor_windows_console_translate_progress,
        args=(task_id, stop_event),
        daemon=True,
    )
    monitor_thread.start()

    width_guard_thread = threading.Thread(
        target=_guard_windows_console_min_width,
        args=(stop_event, WINDOWS_MIN_COLUMNS),
        daemon=True,
    )
    width_guard_thread.start()

    return_code = None
    try:
        return_code = process.wait()
    finally:
        stop_event.set()
        monitor_thread.join(timeout=1.5)
        width_guard_thread.join(timeout=1.0)

    _debug_progress_log("EXECUTE_END", task_id=task_id, return_code=return_code)

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, final_cmd)