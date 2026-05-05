import os
import re
import select
import subprocess
import sys
import threading
from datetime import datetime

from utils.task_manager import task_manager

# Codex review #298 P1: subprocess.Popen handle 存在这个 module-level dict, 不放进
# task_manager.active_tasks (那里要 JSON-serializable, 否则 /events SSE 序列化失败).
_proc_handles: dict = {}
_proc_handles_lock = threading.Lock()


class UserCancelledError(Exception):
    """Codex review #298 P1 round 7: 用户主动 abort 的独立异常类型, 与
    `subprocess.CalledProcessError` 严格区分. server.py translate_pdf 的 retry
    逻辑只 catch CalledProcessError, 不会把这个 UserCancelledError 当 transient
    failure 重试; worker finally 也能精确识别"是用户取消"vs"真失败".
    """
    pass



# Codex #298 P1: pre-spawn cancellation set. abort_task 调用时如果 _proc 还没注册
# (即 worker 还没真正 Popen), 把 task_id 加到这里; execute_with_progress 入口检查
# 后立即 raise CalledProcessError, worker finally 标 task failed
_cancelled_tasks: set = set()
_cancelled_lock = threading.Lock()


def _check_cancelled(task_id):
    if task_id is None: return False
    with _cancelled_lock:
        return task_id in _cancelled_tasks


def _consume_cancelled(task_id):
    with _cancelled_lock:
        _cancelled_tasks.discard(task_id)




# Match lines like: "translate ... 10/100"
# MAIN_PROGRESS_RE = re.compile(r"\btranslate\b[^\r\n]*?(\d+)/(\d+)\b", re.IGNORECASE)

# pdf2zh_next
# 核心修改：在 translate 和 分数 之间，严禁出现英文字母 (a-z) 和括号
# 这样就能完美避开类似 "Translate Paragraphs (1/1)" 这种子任务。
MAIN_PROGRESS_RE = re.compile(
    r"\btranslate\s+[^a-z\(\)\r\n]*?(\d+)/(\d+)\b", 
    re.IGNORECASE
)

# Match step-like lines where only status message should be updated
STEP_PROGRESS_RE = re.compile(r"(.+?)\(\d+/\d+\)\s+.*?(\d+)/(\d+)")

# 详细阶段进度：抓 babeldoc rich progress 行
# 例: "Automatic Term Extraction (1/1) ━━━━━━╸━━ 2274/2404 0:08:58 0:00:33"
# 解析阶段名 / 当前 / 总数 / 已用时间 / 预计剩余
STAGE_DETAIL_RE = re.compile(
    r"([A-Z][A-Za-z ]+?)\s+\(\d+/\d+\)[^0-9\r\n]*?(\d+)/(\d+)\s+(\d+:\d+:\d+)(?:\s+(\d+:\d+:\d+))?",
)

# Legacy pdf2zh (1.x) progress format
LEGACY_PROGRESS_RE = re.compile(r"(?:translate|Running|Parse).*?(\d+)/(\d+)", re.IGNORECASE)

# Strip ANSI sequences before regex matching
ANSI_ESCAPE = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")


# 🌟 新增：专门针对 pdf2zh (tqdm) 进度条的精准捕获！
# 特征：匹配竖线 "|" 加上 " 3/17 [" 这样的格式
PDF2ZH_TQDM_RE = re.compile(r"\|\s*(\d+)/(\d+)\s+\[")

WINDOWS_MONITOR_INTERVAL = 0.05
WINDOWS_CONSOLE_SCAN_ROWS = 220
WINDOWS_MIN_COLUMNS = 160

# DEBUG_PROGRESS_LOG_PATH = os.path.join(
#     os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
#     "_debug_progress.log",
# )
# _DEBUG_PROGRESS_LOG_LOCK = threading.Lock()


# def _debug_progress_log(stage, **fields):
#     try:
#         ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
#         parts = []
#         for key in sorted(fields.keys()):
#             value = str(fields[key]).replace("\r", "\\r").replace("\n", "\\n")
#             if len(value) > 260:
#                 value = value[:260] + "..."
#             parts.append(f"{key}={value}")
#         line = f"[{ts}] [{stage}] " + " ".join(parts)
#         with _DEBUG_PROGRESS_LOG_LOCK:
#             with open(DEBUG_PROGRESS_LOG_PATH, "a", encoding="utf-8", errors="replace") as fp:
#                 fp.write(line + "\n")
#     except Exception:
#         pass


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

    # Codex #298 P1: pre-spawn cancellation. Use distinct exception so the
    # outer retry / fallback logic in translate_pdf() doesn't treat it as failure.
    if _check_cancelled(task_id):
        _consume_cancelled(task_id)
        raise UserCancelledError(f"task {task_id} cancelled before subprocess spawn")
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
    
    # 【新增调试日志】把每次 PTY 读取到的"大块头"文本极其原貌（包括 \r 和 \n）打出来
    # _debug_progress_log("MAC_PTY_READ", raw_chunk=repr(clean))

    # 以下完全恢复成你的原始代码！
    # Main translation progress (preferred)
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
            # 【新增调试日志】记录 Main 正则抓到了什么
            # _debug_progress_log("MATCH_MAIN", curr=curr, total=total, pct=pct)
        return

    # 详细阶段进度: 抓 babeldoc 子进程 rich 输出, 反向找最后一个未完成阶段
    # （多阶段同时输出时, 已完成的阶段也在文本里, 不能取第一个匹配）
    all_matches = STAGE_DETAIL_RE.findall(clean)
    if all_matches:
        chosen = None
        for m in reversed(all_matches):
            try:
                if int(m[1]) < int(m[2]):
                    chosen = m
                    break
            except Exception:
                pass
        if chosen is None:
            chosen = all_matches[-1]
        stage_name = chosen[0].strip()
        try:
            stage_curr = int(chosen[1])
            stage_total = int(chosen[2])
        except Exception:
            stage_curr = stage_total = 0
        elapsed = chosen[3]
        eta = chosen[4] if len(chosen) > 4 else ""
        if stage_total > 0:
            task_manager.update_task(task_id, {
                "status": "running",
                "message": stage_name,
                "stageName": stage_name,
                "stageCurr": stage_curr,
                "stageTotal": stage_total,
                "stageElapsed": elapsed,
                "stageEta": eta,
            })
            return

    # Step status text (secondary)
    match = STEP_PROGRESS_RE.search(clean)
    if match:
        step_name = match.group(1).strip()
        task_manager.update_task(task_id, {
            "status": "running",
            "message": step_name,
        })
        # 【新增调试日志】
        # _debug_progress_log("MATCH_STEP", step=step_name)
        return

    # 🌟 3. 处理 pdf2zh 原生引擎的 tqdm 进度条
    tqdm_matches = PDF2ZH_TQDM_RE.findall(clean)
    if tqdm_matches:
        curr, total = int(tqdm_matches[-1][0]), int(tqdm_matches[-1][1])
        if total > 0:
            task_manager.update_task(task_id, {
                "progress": int((curr / total) * 100),
                "status": "running",
                "message": f"translate {curr}/{total}",
            })

    # Legacy format
    match = LEGACY_PROGRESS_RE.search(clean)
    if match:
        curr, total = int(match.group(1)), int(match.group(2))
        if total > 0:
            pct = int((curr / total) * 100)
            task_manager.update_task(task_id, {
                "progress": pct,
                "status": "running",
            })
            # 【新增调试日志】记录 Legacy 正则是不是抓错了
            # _debug_progress_log("MATCH_LEGACY", curr=curr, total=total, pct=pct)

# def _parse_progress(text, task_id):
#     """Parse progress info from text and update task_manager."""
#     if task_id is None:
#         return

#     clean = ANSI_ESCAPE.sub("", text)

#     # Main translation progress (preferred)
#     # 子步骤状态文本 (次要)
#     # 子步骤状态文本 (次要)
#     match = STEP_PROGRESS_RE.search(clean)
#     if match:
#         # 只提取当前正在做什么，比如 "Parse PDF and Create Intermediate Representation"
#         step_name = match.group(1).strip() 
        
#         # ⚠️ 绝对不要在这里计算和更新 progress！只更新 message！
#         task_manager.update_task(task_id, {
#             "status": "running",
#             "message": step_name,
#         })
#         return

#     # Step status text (secondary)
#     match = STEP_PROGRESS_RE.search(clean)
#     if match:
#         step_name = match.group(1).strip()
#         task_manager.update_task(task_id, {
#             "status": "running",
#             "message": step_name,
#         })
#         return

#     # Legacy format
#     match = LEGACY_PROGRESS_RE.search(clean)
#     if match:
#         curr, total = int(match.group(1)), int(match.group(2))
#         if total > 0:
#             pct = int((curr / total) * 100)
#             task_manager.update_task(task_id, {
#                 "progress": pct,
#                 "status": "running",
#             })


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

    # Codex #298 P1 round 3: 第二次 cancel check, 关掉 enter→Popen 之间的 race window
    if _check_cancelled(task_id):
        _consume_cancelled(task_id)
        try: os.close(master_fd)
        except Exception: pass
        try: os.close(slave_fd)
        except Exception: pass
        raise UserCancelledError(f"task {task_id} cancelled before Popen (PTY)")
    # 关键: start_new_session=True 让子进程独立 process group, /api/abort 用 killpg 时
    # 不会误杀 server 自己的 process group
    try:
        process = subprocess.Popen(
            final_cmd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=final_env,
            bufsize=0,
            close_fds=True,
            start_new_session=True,
        )
    except Exception:
        # Popen 失败 (例如 macOS EDEADLK) 时关闭 PTY fd, 避免 fd 泄漏后被 PR-6 重试放大
        try: os.close(master_fd)
        except Exception: pass
        try: os.close(slave_fd)
        except Exception: pass
        raise
    os.close(slave_fd)
    # 把子进程 PID + Popen 对象注册到 task_manager
    if task_id is not None:
        try:
            task_manager.update_task(task_id, {"_pid": process.pid})
            with _proc_handles_lock:
                _proc_handles[task_id] = process
        except Exception:
            pass

    try:
        while True:
            readable, _, _ = select.select([master_fd], [], [], 0.1)
            if master_fd in readable:
                try:
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace")
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
                            break
                        text = data.decode("utf-8", errors="replace")
                        sys.stdout.write(text)
                        sys.stdout.flush()
                        _parse_progress(text, task_id)
                except Exception:
                    pass
                break

        os.close(master_fd)
        return_code = process.wait()
        # Codex #298 P2 round 13: 只清 _proc_handles, NOT 清 cancel marker.
        # Reason: SIGTERM-induced non-zero exit需要保留 marker, 让 translate_pdf 的
        # retry path 检查到并 raise UserCancelledError. Worker 终态 (_translate_worker.finally)
        # 兜底清 marker, 防止累积泄漏.
        if task_id is not None:
            with _proc_handles_lock:
                _proc_handles.pop(task_id, None)
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, final_cmd)

    except Exception:
        if process.poll() is None:
            process.kill()
        try:
            os.close(master_fd)
        except Exception:
            pass
        if task_id is not None:
            with _proc_handles_lock:
                _proc_handles.pop(task_id, None)
            # round 13: NOT 清 cancel marker, 让 caller retry guard 看到. worker finally 兜底.
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
        # _debug_progress_log("MONITOR_IMPORT_ERROR", task_id=task_id)
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
        # _debug_progress_log("MONITOR_WINAPI_ERROR", task_id=task_id, error=str(e))
        return

    handle = get_std_handle(STD_OUTPUT_HANDLE)
    if handle in (None, 0, INVALID_HANDLE_VALUE):
        # _debug_progress_log("MONITOR_HANDLE_INVALID", task_id=task_id)
        return

    # _debug_progress_log("MONITOR_STARTED", task_id=task_id)

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
                # _debug_progress_log("MONITOR_CSBI_FAIL", task_id=task_id)
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
                    # _debug_progress_log("LOCK_TOTAL", task_id=task_id, row=row, total=total)
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
                        # _debug_progress_log(
                        #     "PARSE_PROGRESS",
                        #     task_id=task_id,
                        #     row=row,
                        #     curr=curr,
                        #     total=total,
                        #     pct=pct,
                        #     locked_total=locked_total,
                        # )
            else:
                idle_ticks += 1
                if idle_ticks % 40 == 0:
                    pass  # _debug_progress_log(
                    #     "PARSE_IDLE",
                    #     task_id=task_id,
                    #     cursor=cursor_y,
                    #     start=start_row,
                    #     end=end_row,
                    #     locked_total=locked_total,
                    #     sample=translate_line_sample,
                    # )

            if latest_step and latest_step != last_step:
                last_step = latest_step
                task_manager.update_task(task_id, {
                    "status": "running",
                    "message": latest_step,
                })
                # _debug_progress_log("PARSE_STEP", task_id=task_id, step=latest_step)
        except Exception as e:
            err_text = str(e)
            if err_text != last_error:
                last_error = err_text
                # _debug_progress_log("MONITOR_ERROR", task_id=task_id, error=err_text)

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
    # Codex review #298 P1 round 5: Windows 路径也要 pre-spawn cancel check
    if _check_cancelled(task_id):
        _consume_cancelled(task_id)
        raise UserCancelledError(f"task {task_id} cancelled before Popen (Windows)")
    # CREATE_NEW_PROCESS_GROUP 让 Windows 子进程独立 group, 方便 /api/abort 用 CTRL_BREAK_EVENT
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(
        final_cmd,
        stdout=None,
        stderr=None,
        env=final_env,
        bufsize=0,
        text=False,
        creationflags=creationflags,
    )
    # 让 /api/abort 能找到子进程 (Windows 也注册)
    if task_id is not None:
        try:
            task_manager.update_task(task_id, {"_pid": process.pid})
            with _proc_handles_lock:
                _proc_handles[task_id] = process
        except Exception:
            pass

    # _debug_progress_log("EXECUTE_START", task_id=task_id, cmd=" ".join(final_cmd))

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
        # Codex #298 P2: 清 _proc_handles 防泄漏 (cancel marker 由 worker finally 清)
        if task_id is not None:
            with _proc_handles_lock:
                _proc_handles.pop(task_id, None)

    # _debug_progress_log("EXECUTE_END", task_id=task_id, return_code=return_code)

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, final_cmd)