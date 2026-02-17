#!/usr/bin/env python3
"""Windows tray launcher for packaged PDF2ZH server.

The launcher keeps a tray icon alive, can show live backend logs, and exits by
stopping the backend server process.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path


APP_NAME = "Zotero-PDF2ZH Server"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8890
HEALTH_TIMEOUT_SECONDS = 2
START_TIMEOUT_SECONDS = 40
HEALTH_POLL_INTERVAL_SECONDS = 0.5
STOP_TIMEOUT_SECONDS = 8
DATA_DIRNAME = "PDF2ZH Server"
LOG_FILENAME = "server.log"
SERVER_CORE_EXE_NAME = "pdf2zh-server-core.exe"

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = r"Global\ZoteroPDF2ZHServerTraySingleton"
TRAY_WINDOW_CLASS_NAME = "ZoteroPDF2ZHTrayWindow"

WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_CONTEXTMENU = 0x007B
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
SM_CXSMICON = 49
SM_CYSMICON = 50
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIM_SETVERSION = 0x00000004
NOTIFYICON_VERSION_4 = 4
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x0002
TPM_BOTTOMALIGN = 0x0020

ID_TRAY_SHOW_LOG = 1001
ID_TRAY_EXIT = 1002
NIN_SELECT = 0x0400
NIN_KEYSELECT = 0x0401

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def default_data_root() -> Path:
    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    return Path(program_data) / DATA_DIRNAME


def log_file_path(data_root: Path) -> Path:
    return data_root / "logs" / LOG_FILENAME


def health_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/health"


def show_message(text: str, title: str, is_error: bool = False) -> None:
    flags = 0x10 if is_error else 0x40
    user32.MessageBoxW(0, text, title, flags)


def is_server_healthy(host: str, port: int) -> bool:
    req = urllib.request.Request(health_url(host, port), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                return False
            data = json.loads(response.read().decode("utf-8"))
            return data.get("status") == "ok"
    except Exception:
        return False


def is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=HEALTH_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


def run_quiet_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def build_engine_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    if os.name != "nt":
        return env

    # Avoid loky physical-core probes that may spawn transient PowerShell
    # windows on some bundled runtimes.
    if "LOKY_MAX_CPU_COUNT" not in env:
        logical_cores = os.cpu_count() or 1
        env["LOKY_MAX_CPU_COUNT"] = str(max(1, logical_cores - 1))
    return env


def find_listening_pid(port: int) -> int | None:
    import socket as _socket

    AF_INET = 2
    TCP_TABLE_OWNER_PID_LISTENER = 3

    class _MIB_TCPROW_OWNER_PID(ctypes.Structure):
        _fields_ = [
            ("dwState", wintypes.DWORD),
            ("dwLocalAddr", wintypes.DWORD),
            ("dwLocalPort", wintypes.DWORD),
            ("dwRemoteAddr", wintypes.DWORD),
            ("dwRemotePort", wintypes.DWORD),
            ("dwOwningPid", wintypes.DWORD),
        ]

    _iphlpapi = ctypes.WinDLL("iphlpapi")
    size = wintypes.DWORD(0)
    _iphlpapi.GetExtendedTcpTable(
        None,
        ctypes.byref(size),
        False,
        AF_INET,
        TCP_TABLE_OWNER_PID_LISTENER,
        0,
    )
    buf = (ctypes.c_byte * size.value)()
    ret = _iphlpapi.GetExtendedTcpTable(
        buf,
        ctypes.byref(size),
        False,
        AF_INET,
        TCP_TABLE_OWNER_PID_LISTENER,
        0,
    )
    if ret != 0:
        return None

    num_entries = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0]
    rows_offset = ctypes.sizeof(wintypes.DWORD)
    row_size = ctypes.sizeof(_MIB_TCPROW_OWNER_PID)
    target_port_net = _socket.htons(port) & 0xFFFF

    for i in range(num_entries):
        row = _MIB_TCPROW_OWNER_PID.from_buffer_copy(
            buf,
            rows_offset + i * row_size,
        )
        if (row.dwLocalPort & 0xFFFF) == target_port_net:
            return row.dwOwningPid
    return None


def taskkill_by_pid(pid: int) -> None:
    run_quiet_command(["taskkill", "/PID", str(pid), "/T", "/F"])


def taskkill_by_image_name(name: str) -> None:
    run_quiet_command(["taskkill", "/IM", name, "/T", "/F"])


def process_image_name_by_pid(pid: int) -> str | None:
    if pid <= 0:
        return None

    result = run_quiet_command(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]
    )
    if result.returncode != 0:
        return None

    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not rows:
        return None
    first = rows[0]
    if first.upper().startswith("INFO:"):
        return None

    try:
        row = next(csv.reader([first]))
    except Exception:
        return None
    if len(row) < 2:
        return None
    try:
        actual_pid = int(row[1])
    except ValueError:
        return None
    if actual_pid != pid:
        return None
    return row[0].strip() or None


def is_core_server_pid(pid: int) -> bool:
    image = process_image_name_by_pid(pid)
    if not image:
        return False
    return image.lower() == SERVER_CORE_EXE_NAME.lower()


def stop_server(host: str, port: int, managed_pid: int | None = None) -> None:
    pid_to_kill: int | None = None
    if managed_pid is not None and managed_pid > 0 and managed_pid != os.getpid():
        pid_to_kill = managed_pid
    else:
        listener_pid = find_listening_pid(port)
        if (
            listener_pid is not None
            and listener_pid != os.getpid()
            and is_core_server_pid(listener_pid)
        ):
            pid_to_kill = listener_pid

    if pid_to_kill is not None:
        taskkill_by_pid(pid_to_kill)
    else:
        taskkill_by_image_name(SERVER_CORE_EXE_NAME)

    deadline = time.time() + STOP_TIMEOUT_SECONDS
    while time.time() < deadline:
        if not is_port_open(host, port):
            return
        time.sleep(0.2)


def start_server(port: int, host: str, data_root: Path) -> int:
    install_dir = app_dir()
    core_exe = install_dir / SERVER_CORE_EXE_NAME
    engine_root = install_dir / "engine"
    log_dir = data_root / "logs"
    log_file = log_file_path(data_root)

    if not core_exe.exists():
        raise FileNotFoundError(f"Missing server core executable: {core_exe}")
    if not engine_root.exists():
        raise FileNotFoundError(f"Missing engine folder: {engine_root}")

    log_dir.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(core_exe),
        f"--port={port}",
        "--packaged_mode=true",
        f"--engine_root={engine_root}",
        f"--data_root={data_root}",
        "--check_update=false",
        "--debug=false",
    ]

    create_new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE

    with open(log_file, "a", encoding="utf-8") as log_fp:
        process_env = build_engine_subprocess_env()
        proc = subprocess.Popen(
            cmd,
            cwd=str(install_dir),
            stdin=subprocess.DEVNULL,
            stdout=log_fp,
            stderr=log_fp,
            env=process_env,
            startupinfo=si,
            creationflags=create_new_process_group,
            close_fds=False,
        )

    deadline = time.time() + START_TIMEOUT_SECONDS
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Server process exited early with code {proc.returncode}. "
                f"Check log file: {log_file}"
            )
        if is_server_healthy(host, port):
            return proc.pid
        time.sleep(HEALTH_POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"Server did not become healthy within {START_TIMEOUT_SECONDS} seconds. "
        f"Check log file: {log_file}"
    )


def open_external_log_viewer(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.touch(exist_ok=True)

    escaped_path = str(log_file).replace("'", "''")
    follow_script = (
        f"$logPath = '{escaped_path}'; "
        "if (-not (Test-Path -LiteralPath $logPath)) { "
        "  New-Item -Path $logPath -ItemType File -Force | Out-Null "
        "}; "
        "Get-Content -LiteralPath $logPath -Tail 200 -Wait"
    )

    errors: list[str] = []
    launch_candidates = [
        (
            [
                "powershell.exe",
                "-NoLogo",
                "-NoExit",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                follow_script,
            ],
            getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        ),
        (
            [
                "notepad.exe",
                str(log_file),
            ],
            0,
        ),
    ]

    for cmd, flags in launch_candidates:
        try:
            subprocess.Popen(cmd, creationflags=flags, close_fds=False)
            return
        except Exception as exc:
            errors.append(f"{cmd[0]}: {exc}")

    details = "\n".join(errors) if errors else "No log viewer launcher available."
    raise RuntimeError(details)


class LogViewer:
    POLL_INTERVAL_MS = 500
    MAX_LINES = 5000
    TAIL_BYTES = 512 * 1024

    def __init__(self, log_file: Path) -> None:
        self._log_file = log_file
        self._queue: queue.Queue[str] = queue.Queue()
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._thread_main, name="pdf2zh-log-viewer", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=5)

    @property
    def available(self) -> bool:
        return getattr(self, "_available", False)

    def show(self) -> None:
        self._queue.put("show")

    def shutdown(self) -> None:
        if not self.available:
            return
        self._queue.put("shutdown")
        self._thread.join(timeout=2)

    def _thread_main(self) -> None:
        try:
            import tkinter as tk
            from tkinter import scrolledtext
        except Exception:
            self._available = False
            self._ready.set()
            return

        self._available = True
        self._tk = tk
        self._scrolledtext = scrolledtext
        self._root = tk.Tk()
        self._root.withdraw()
        self._window = None
        self._text = None
        self._offset = 0
        self._ready.set()
        self._root.after(100, self._process_queue)
        self._root.mainloop()

    def _process_queue(self) -> None:
        while True:
            try:
                cmd = self._queue.get_nowait()
            except queue.Empty:
                break

            if cmd == "show":
                self._show_window()
            elif cmd == "shutdown":
                self._shutdown_ui()
                return

        self._root.after(100, self._process_queue)

    def _show_window(self) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.deiconify()
            self._window.lift()
            self._window.focus_force()
            return

        self._window = self._tk.Toplevel(self._root)
        self._window.title(f"{APP_NAME} - 后端日志")
        self._window.geometry("980x620")
        self._window.protocol("WM_DELETE_WINDOW", self._close_window)

        self._text = self._scrolledtext.ScrolledText(
            self._window,
            wrap="none",
            font=("Consolas", 9),
            state="disabled",
        )
        self._text.pack(fill="both", expand=True)
        self._load_initial_tail()
        self._poll_log()

    def _close_window(self) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.destroy()
        self._window = None
        self._text = None

    def _shutdown_ui(self) -> None:
        self._close_window()
        if self._root is not None:
            self._root.quit()
            self._root.destroy()

    def _load_initial_tail(self) -> None:
        if self._text is None:
            return
        text = self._read_initial_tail()
        self._append_text(text)

    def _read_initial_tail(self) -> str:
        if not self._log_file.exists():
            self._offset = 0
            return f"[等待日志输出] {self._log_file}\n"

        size = self._log_file.stat().st_size
        start = max(0, size - self.TAIL_BYTES)
        with open(self._log_file, "rb") as fp:
            fp.seek(start)
            data = fp.read()
        self._offset = size
        prefix = ""
        if start > 0:
            prefix = "...(仅显示最新日志片段)\n"
        return prefix + data.decode("utf-8", errors="replace")

    def _poll_log(self) -> None:
        if self._window is None or not self._window.winfo_exists():
            return

        try:
            if not self._log_file.exists():
                self._offset = 0
            else:
                with open(self._log_file, "rb") as fp:
                    fp.seek(0, os.SEEK_END)
                    size = fp.tell()
                    if size < self._offset:
                        self._offset = 0
                    if size > self._offset:
                        fp.seek(self._offset)
                        chunk = fp.read()
                        self._offset = fp.tell()
                        if chunk:
                            self._append_text(chunk.decode("utf-8", errors="replace"))
        except Exception as exc:
            self._append_text(f"\n[日志读取失败] {exc}\n")

        self._root.after(self.POLL_INTERVAL_MS, self._poll_log)

    def _append_text(self, text: str) -> None:
        if not text or self._text is None:
            return
        self._text.configure(state="normal")
        self._text.insert("end", text)
        line_count = int(self._text.index("end-1c").split(".")[0])
        if line_count > self.MAX_LINES:
            excess = line_count - self.MAX_LINES
            self._text.delete("1.0", f"{excess + 1}.0")
        self._text.configure(state="disabled")
        self._text.see("end")


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HANDLE),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HANDLE),
    ]


class TrayApp:
    WINDOW_CLASS_NAME = TRAY_WINDOW_CLASS_NAME

    def __init__(
        self,
        host: str,
        port: int,
        data_root: Path,
        single_instance_mutex: int,
        managed_server_pid: int | None,
        should_stop_server_on_exit: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._data_root = data_root
        self._log_file = log_file_path(data_root)
        self._mutex = single_instance_mutex
        self._managed_server_pid = managed_server_pid
        self._should_stop_server_on_exit = should_stop_server_on_exit

        self._hinstance = kernel32.GetModuleHandleW(None)
        self._wnd_proc = WNDPROC(self._window_proc)
        self._class_atom = 0
        self._hwnd = None
        self._nid = NOTIFYICONDATAW()
        self._tray_icon = self._load_tray_icon()
        self._icon_added = False
        self._exiting = False
        self._log_viewer = LogViewer(self._log_file)

    def run(self) -> int:
        try:
            self._register_window_class()
            self._create_hidden_window()
            self._add_tray_icon()
            return self._message_loop()
        finally:
            self._cleanup()

    def _register_window_class(self) -> None:
        wndclass = WNDCLASSW()
        wndclass.lpfnWndProc = self._wnd_proc
        wndclass.hInstance = self._hinstance
        wndclass.lpszClassName = self.WINDOW_CLASS_NAME
        self._class_atom = user32.RegisterClassW(ctypes.byref(wndclass))
        if not self._class_atom:
            raise ctypes.WinError(ctypes.get_last_error())

    def _create_hidden_window(self) -> None:
        self._hwnd = user32.CreateWindowExW(
            0,
            self.WINDOW_CLASS_NAME,
            APP_NAME,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            self._hinstance,
            0,
        )
        if not self._hwnd:
            raise ctypes.WinError(ctypes.get_last_error())

    def _load_tray_icon(self) -> int:
        for icon_path in self._candidate_icon_files():
            hicon = self._load_icon_from_file(icon_path)
            if hicon:
                return hicon

        small_icon = wintypes.HANDLE()
        extracted = shell32.ExtractIconExW(
            str(sys.executable), 0, None, ctypes.byref(small_icon), 1
        )
        if extracted and small_icon.value:
            return int(small_icon.value)

        hicon = shell32.ExtractIconW(None, str(sys.executable), 0)
        if hicon and hicon > 1:
            return hicon
        fallback = shell32.ExtractIconW(None, r"C:\Windows\System32\shell32.dll", 220)
        if fallback and fallback > 1:
            return fallback
        return 0

    def _candidate_icon_files(self) -> list[Path]:
        install_dir = app_dir()
        runtime_dir = Path(__file__).resolve().parent
        candidates = [
            install_dir / "zotero-pdf2zh-server.ico",
            install_dir / "assets" / "zotero-pdf2zh-server.ico",
            runtime_dir / "assets" / "zotero-pdf2zh-server.ico",
        ]
        unique: list[Path] = []
        seen: set[str] = set()
        for path in candidates:
            key = str(path).lower()
            if key in seen:
                continue
            seen.add(key)
            if path.exists():
                unique.append(path)
        return unique

    def _load_icon_from_file(self, icon_path: Path) -> int:
        width = int(user32.GetSystemMetrics(SM_CXSMICON)) or 16
        height = int(user32.GetSystemMetrics(SM_CYSMICON)) or 16
        hicon = user32.LoadImageW(
            None,
            str(icon_path),
            IMAGE_ICON,
            width,
            height,
            LR_LOADFROMFILE,
        )
        return int(hicon) if hicon else 0

    def _add_tray_icon(self) -> None:
        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hWnd = self._hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_MESSAGE | NIF_TIP
        if self._tray_icon:
            self._nid.uFlags |= NIF_ICON
            self._nid.hIcon = self._tray_icon
        self._nid.uCallbackMessage = WM_TRAYICON
        self._nid.szTip = APP_NAME
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid)):
            raise ctypes.WinError(ctypes.get_last_error())
        self._icon_added = True
        self._nid.uVersion = NOTIFYICON_VERSION_4
        shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(self._nid))

    def _show_tray_menu(self) -> None:
        menu = user32.CreatePopupMenu()
        if not menu:
            return

        try:
            user32.AppendMenuW(menu, MF_STRING, ID_TRAY_SHOW_LOG, "查看后端日志")
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, ID_TRAY_EXIT, "退出")

            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(self._hwnd)
            user32.TrackPopupMenu(
                menu,
                TPM_RIGHTBUTTON | TPM_BOTTOMALIGN,
                pt.x,
                pt.y,
                0,
                self._hwnd,
                None,
            )
            user32.PostMessageW(self._hwnd, 0, 0, 0)
        finally:
            user32.DestroyMenu(menu)

    def _on_show_log(self) -> None:
        if not self._log_viewer.available:
            try:
                open_external_log_viewer(self._log_file)
            except Exception as exc:
                show_message(
                    "当前运行环境不支持内置日志窗口，且打开外部日志查看器失败。\n"
                    f"日志文件位置:\n{self._log_file}\n\n错误详情:\n{exc}",
                    f"{APP_NAME} - 日志窗口不可用",
                    is_error=True,
                )
            return
        self._log_viewer.show()

    def _on_exit(self) -> None:
        if self._exiting:
            return
        self._exiting = True
        try:
            if self._should_stop_server_on_exit:
                stop_server(
                    self._host, self._port, managed_pid=self._managed_server_pid
                )
        except Exception as exc:
            show_message(
                f"停止后端服务时发生错误:\n{exc}",
                f"{APP_NAME} - 退出提示",
                is_error=True,
            )
        finally:
            user32.DestroyWindow(self._hwnd)

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            # With NOTIFYICON_VERSION_4, event code is in LOWORD(lparam).
            tray_event = int(lparam) & 0xFFFF
            if tray_event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self._show_tray_menu()
                return 0
            if tray_event in (
                WM_LBUTTONUP,
                WM_LBUTTONDBLCLK,
                NIN_SELECT,
                NIN_KEYSELECT,
            ):
                self._on_show_log()
                return 0

        if msg == WM_COMMAND:
            command_id = wparam & 0xFFFF
            if command_id == ID_TRAY_SHOW_LOG:
                self._on_show_log()
                return 0
            if command_id == ID_TRAY_EXIT:
                self._on_exit()
                return 0

        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _message_loop(self) -> int:
        msg = wintypes.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if result == 0:
                return 0
            if result == -1:
                raise ctypes.WinError(ctypes.get_last_error())
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _cleanup(self) -> None:
        if self._icon_added:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            self._icon_added = False

        if self._log_viewer is not None:
            self._log_viewer.shutdown()

        if self._tray_icon:
            user32.DestroyIcon(self._tray_icon)
            self._tray_icon = 0

        if self._hwnd:
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None

        if self._class_atom:
            user32.UnregisterClassW(self.WINDOW_CLASS_NAME, self._hinstance)
            self._class_atom = 0

        if self._mutex:
            kernel32.CloseHandle(self._mutex)
            self._mutex = 0


def acquire_single_instance_mutex() -> int | None:
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return handle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start packaged PDF2ZH tray server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", type=str, default=DEFAULT_HOST)
    parser.add_argument("--data_root", type=str, default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_root = (
        Path(args.data_root).resolve() if args.data_root else default_data_root()
    )
    mutex_handle = 0

    try:
        mutex_handle = acquire_single_instance_mutex() or 0
        if not mutex_handle:
            # A duplicate launch should quietly exit; callers may probe this exe.
            return 0

        managed_server_pid: int | None = None
        should_stop_server_on_exit = False
        if not is_server_healthy(args.host, args.port):
            if is_port_open(args.host, args.port):
                raise RuntimeError(
                    f"Port {args.port} is already in use, but /health is unavailable. "
                    "Please close the existing process using this port and retry."
                )
            managed_server_pid = start_server(args.port, args.host, data_root)
            should_stop_server_on_exit = True
        else:
            listener_pid = find_listening_pid(args.port)
            if (
                listener_pid
                and listener_pid != os.getpid()
                and is_core_server_pid(listener_pid)
            ):
                managed_server_pid = listener_pid
                should_stop_server_on_exit = True

        tray_app = TrayApp(
            host=args.host,
            port=args.port,
            data_root=data_root,
            single_instance_mutex=mutex_handle,
            managed_server_pid=managed_server_pid,
            should_stop_server_on_exit=should_stop_server_on_exit,
        )
        mutex_handle = 0
        return tray_app.run()
    except Exception as exc:
        show_message(
            f"Failed to start {APP_NAME}.\n\n{exc}",
            f"{APP_NAME} - Startup Error",
            is_error=True,
        )
        return 1
    finally:
        if mutex_handle:
            kernel32.CloseHandle(mutex_handle)


if __name__ == "__main__":
    raise SystemExit(main())
