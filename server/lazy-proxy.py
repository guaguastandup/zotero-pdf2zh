"""pdf2zh lazy launch proxy.

Resident on the public server port (8890 by default) using ~5 MB of memory
and 0% CPU when idle. On the first incoming request it spawns the real
server.py on a backend port (8891) and forwards traffic to it. After
IDLE_TIMEOUT seconds of no requests, the backend server is terminated.

This lets users keep the python server "always available" via a launchd /
systemd / autostart entry without paying the 200-300 MB resident cost of
the real server when not translating.

Usage:
    python lazy-proxy.py [--port PORT] [--backend-port PORT] [--idle SECS]
                         [--server-cmd 'python server.py'] [--server-cwd DIR]

The proxy is OpenAI-compatible style: it streams chunked responses (so SSE
/events keeps working) and uses a thread pool so concurrent clients
(translate + dashboard SSE + history fetch) don't block each other.
"""
from __future__ import annotations

import argparse
import http.server
import os
import shlex
import signal
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

# ---- defaults; can be overridden via CLI ----
DEFAULT_PROXY_PORT = 8890
DEFAULT_BACKEND_PORT = 8891
DEFAULT_IDLE_TIMEOUT = 600  # 10 min
DEFAULT_FORWARD_TIMEOUT = 7200  # 2 hours - long PDFs

# Filled by main()
CFG: dict = {}

_server_proc: subprocess.Popen | None = None
_proc_lock = threading.Lock()
_backend_ready = threading.Event()  # set when backend /health passed
_last_request_time = 0.0
_active_request_count = 0
_active_lock = threading.Lock()


# Codex review #302 P1 round 2: 调本地 backend 时强制不走环境 http_proxy / https_proxy.
# 否则 NO_PROXY 没包含 127.0.0.1 的环境会把 loopback 请求打到外部 proxy.
#
# GitHub @codex review #302 round 2 (P2): build_opener 默认装 HTTPRedirectHandler,
# 自动 follow 30x → 客户端永远看不到 Location, 还会把 POST 改 GET (RFC 7231 §6.4.x).
# 反向代理必须把 redirect 透传给上层 client. 用一个 do-nothing redirect handler 关掉.
class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers): return None
    def http_error_302(self, req, fp, code, msg, headers): return None
    def http_error_303(self, req, fp, code, msg, headers): return None
    def http_error_307(self, req, fp, code, msg, headers): return None
    def http_error_308(self, req, fp, code, msg, headers): return None
_local_opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    _NoRedirectHandler(),
)


def _wait_health(port: int, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with _local_opener.open(
                f"http://127.0.0.1:{port}/health", timeout=1.5
            ) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_backend() -> bool:
    """Spawn the backend server.py if not already running. Returns True on ready.

    Concurrent callers (e.g. dashboard SSE + first translate) all wait on
    _backend_ready; only the first caller actually spawns. This prevents a
    race where caller-2 sees `_server_proc.poll() is None` and forwards
    before /health passed.
    """
    global _server_proc
    spawn_done_by_us = False
    with _proc_lock:
        if _server_proc and _server_proc.poll() is None and _backend_ready.is_set():
            return True
        if _server_proc is None or _server_proc.poll() is not None:
            # 只有第一个 caller 进入这里实际 spawn; 其他 caller 跳过 spawn 直接去等 event
            _backend_ready.clear()
            cmd = CFG["server_cmd"]
            cmd_argv = shlex.split(cmd) + ["--port", str(CFG["backend_port"])]
            kwargs = dict(cwd=CFG["server_cwd"], env=os.environ.copy())
            log_fp = None
            if CFG.get("log_file"):
                # GitHub @codex review (P2): open() 之前在 try 外, 失败 (路径不存在 / 没
                # 权限) 抛 FileNotFoundError 沿调用栈向上, handler thread 直接挂掉, 客户
                # 端收到 connection reset. 改成: 套独立 try, 失败时 fallback 到 inherit
                # parent stderr (log 不可写不应阻塞代理本身).
                try:
                    log_fp = open(CFG["log_file"], "a", encoding="utf-8", errors="replace")
                    kwargs["stdout"] = log_fp
                    kwargs["stderr"] = subprocess.STDOUT
                except OSError as e:
                    print(f"[lazy-proxy] cannot open log file {CFG['log_file']!r}: {e}; "
                          f"backend stdout/stderr will inherit parent's", flush=True)
                    log_fp = None
            if sys.platform != "win32":
                kwargs["start_new_session"] = True
            else:
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            try:
                _server_proc = subprocess.Popen(cmd_argv, **kwargs)
                spawn_done_by_us = True
            except Exception as e:
                print(f"[lazy-proxy] failed to start backend: {e}", flush=True)
                if log_fp is not None:
                    try: log_fp.close()
                    except Exception: pass
                return False
            finally:
                # Codex review #302 P2 round 3: parent 不需要保留 log_fp - subprocess 已经
                # 继承了它的 fd, parent 这边持有只会在每次 spawn 累积泄漏直到 EMFILE
                if log_fp is not None:
                    try: log_fp.close()
                    except Exception: pass
        # else: 已有 proc 在 spawning 中, 不动

    if spawn_done_by_us:
        # 仅 spawner 跑 health 探测, 然后 set event 唤醒所有 waiter (成功或失败都唤醒)
        if _wait_health(CFG["backend_port"], CFG["spawn_timeout"]):
            print(
                f"[lazy-proxy] backend up on :{CFG['backend_port']} (pid={_server_proc.pid})",
                flush=True,
            )
            _backend_ready.set()
            return True
        print("[lazy-proxy] backend health check failed, killing partial process", flush=True)
        stop_backend()  # 这会 _backend_ready.clear()
        # Codex #302 P1 fix: 即使 health 失败也要 set event 唤醒 waiter, 否则
        # waiter 会傻等到 spawn_timeout+5 秒. waiter 检查 _server_proc 状态判断失败
        _backend_ready.set()
        return False

    # waiter: 等 spawn 完成
    if _backend_ready.wait(timeout=CFG["spawn_timeout"] + 5):
        # 还要再确认 proc 真存活 (spawner 可能失败导致 _server_proc=None)
        with _proc_lock:
            return _server_proc is not None and _server_proc.poll() is None
    return False


def stop_backend() -> None:
    """Stop the backend and its entire process group.

    The backend was spawned with start_new_session=True (Unix) /
    CREATE_NEW_PROCESS_GROUP (Windows), so it owns an independent
    process group. We kill the whole group so that any worker
    processes / threads it spawned (e.g. babeldoc subprocesses)
    don't outlive the parent.
    """
    global _server_proc
    with _proc_lock:
        if not (_server_proc and _server_proc.poll() is None):
            _server_proc = None
            return
        proc = _server_proc
        _server_proc = None
    print(f"[lazy-proxy] stopping backend pid={proc.pid}", flush=True)
    try:
        if sys.platform == "win32":
            try:
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            except Exception:
                proc.terminate()
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if sys.platform != "win32":
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    proc.kill()
            else:
                proc.kill()
    except Exception:
        pass
    # 清 ready event, 让下次 request 走完整 spawn 流程
    _backend_ready.clear()


def idle_watcher() -> None:
    """Stop backend after IDLE_TIMEOUT of *no in-flight requests AND no recent traffic*."""
    while True:
        time.sleep(30)
        with _proc_lock:
            running = _server_proc is not None and _server_proc.poll() is None
        if not running:
            continue
        with _active_lock:
            in_flight = _active_request_count
        idle_for = time.time() - _last_request_time
        if in_flight == 0 and idle_for > CFG["idle_timeout"]:
            stop_backend()


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """HTTPServer that handles each request in its own thread.

    Required because translate + SSE + status polling can run concurrently;
    a single-threaded server would block the SSE stream while translate
    holds the request open.
    """

    daemon_threads = True
    allow_reuse_address = True


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    # Use HTTP/1.1 so chunked responses (SSE) work without buffering everything.
    protocol_version = "HTTP/1.1"

    # Limit log noise; lazy-proxy is meant to be invisible.
    def log_message(self, fmt, *args):  # noqa: D401 - stdlib API
        return

    def do_GET(self): self._proxy("GET")
    def do_POST(self): self._proxy("POST")
    def do_HEAD(self): self._proxy("HEAD")
    def do_PUT(self): self._proxy("PUT")
    def do_DELETE(self): self._proxy("DELETE")
    def do_OPTIONS(self): self._proxy("OPTIONS")
    def do_PATCH(self): self._proxy("PATCH")

    def _proxy(self, method: str) -> None:
        global _last_request_time
        _last_request_time = time.time()
        with _active_lock:
            global _active_request_count
            _active_request_count += 1
        try:
            self._proxy_inner(method)
        finally:
            with _active_lock:
                _active_request_count -= 1
            _last_request_time = time.time()

    def _proxy_inner(self, method: str) -> None:
        if not start_backend():
            self.send_error(502, "Failed to start pdf2zh backend")
            return

        # Codex review #302 P1 round 3: 把 body 流式 spool 到临时文件而不是一次性读
        # 进内存. 8MB 内仍在内存里 (SpooledTemporaryFile 默认), 超过自动落盘.
        # 这样大 PDF 上传不会让 proxy 进程额外占用一份完整 body 大小的内存.
        import tempfile as _tempfile
        content_len_header = self.headers.get("Content-Length")
        transfer_encoding = (self.headers.get("Transfer-Encoding") or "").lower()
        body_spool = None
        body_size = 0
        if "chunked" in transfer_encoding:
            body_spool = _tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
            try:
                while True:
                    line = self.rfile.readline()
                    if not line:
                        break
                    size_hex = line.strip().split(b";", 1)[0]
                    size = int(size_hex, 16) if size_hex else 0
                    if size == 0:
                        while True:
                            tline = self.rfile.readline()
                            if not tline or tline in (b"\r\n", b"\n", b""):
                                break
                        break
                    remaining = size
                    while remaining > 0:
                        piece = self.rfile.read(min(remaining, 64 * 1024))
                        if not piece:
                            break
                        body_spool.write(piece)
                        body_size += len(piece)
                        remaining -= len(piece)
                    self.rfile.read(2)  # CRLF after chunk
                body_spool.seek(0)
            except Exception as _chunk_err:
                # GitHub @codex review #302 round 5 (P2): malformed chunked upload 之前
                # silently 当成 empty body 转发, state-changing POST 会被 backend 当合法
                # 请求处理. 改成: spool close + 400 给客户端, 不再透传 broken body.
                try: body_spool.close()
                except Exception: pass
                try:
                    self.send_error(400, f"malformed chunked request body: {_chunk_err}")
                except Exception:
                    pass
                return
        elif content_len_header is not None:
            try:
                content_len = int(content_len_header)
            except ValueError:
                content_len = 0
            if content_len > 0:
                body_spool = _tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
                remaining = content_len
                while remaining > 0:
                    piece = self.rfile.read(min(remaining, 64 * 1024))
                    if not piece:
                        break
                    body_spool.write(piece)
                    body_size += len(piece)
                    remaining -= len(piece)
                body_spool.seek(0)

        # urllib.Request 接受 file-like data + Content-Length header for streaming POST
        body = body_spool  # 用 file-like 给 urllib, 它会 stream 不会一次性 read

        url = f"http://127.0.0.1:{CFG['backend_port']}{self.path}"
        req = urllib.request.Request(url, data=body, method=method)
        # Forward most headers; strip hop-by-hop and ones urllib will set.
        skip = {"host", "content-length", "connection", "keep-alive",
                "proxy-authenticate", "proxy-authorization", "te", "trailers",
                "transfer-encoding", "upgrade"}
        # GitHub @codex review #302 round 2 (P2): RFC 7230 §6.1, Connection header
        # 可以声明额外的 hop-by-hop header 名 (e.g. "Connection: Foo, Bar" 表示 Foo
        # 和 Bar 是 hop-by-hop). 反向代理必须 strip 这些, 否则下游 backend 会看到本
        # 不应见到的 client 自定义 hop header → header confusion / smuggling 风险.
        # round 5 (P2): HTTP 允许多个 Connection 字段, 不只一个. self.headers 是
        # email.message.Message, get_all('Connection') 返回所有 field-value list.
        # 老逻辑用 .get() 只读第一个, 后续 hop-by-hop token 漏掉.
        try:
            conn_lines = self.headers.get_all("Connection") or self.headers.get_all("connection") or []
        except AttributeError:
            conn_lines = [self.headers.get("Connection") or self.headers.get("connection") or ""]
        for conn_hdr in conn_lines:
            if not conn_hdr:
                continue
            for token in conn_hdr.split(","):
                t = token.strip().lower()
                if t and t not in ("close", "keep-alive", "upgrade"):
                    skip.add(t)
        for k, v in self.headers.items():
            if k.lower() not in skip:
                req.add_header(k, v)
        # 给 urllib 显式 Content-Length, 让它 stream 上传 file-like body
        if body is not None and body_size > 0:
            req.add_header("Content-Length", str(body_size))

        try:
            try:
                resp = _local_opener.open(req, timeout=CFG["forward_timeout"])
            except urllib.error.HTTPError as e:
                self._stream_response(e, e.code, getattr(e, "headers", {}))
                return
            except Exception as e:
                try:
                    self.send_error(502, f"backend unreachable: {e}")
                except Exception:
                    pass
                return

            self._stream_response(resp, resp.status, resp.getheaders())
        finally:
            # 关闭 body spool (释放内存或临时文件)
            if body_spool is not None:
                try: body_spool.close()
                except Exception: pass

    def _stream_response(self, fp, status, headers) -> None:
        """Stream backend response chunk-by-chunk so SSE (Content-Type:
        text/event-stream) and large file downloads work without buffering."""
        try:
            self.send_response(status)
            # Reflect headers but drop hop-by-hop ones - HTTPServer will
            # write its own Content-Length / Transfer-Encoding as needed.
            skip = {"transfer-encoding", "connection", "keep-alive"}
            try:
                items = list(headers.items()) if hasattr(headers, "items") else list(headers)
            except Exception:
                items = []
            # GitHub @codex review #302 round 3-4 (P2): 对称问题 — 响应方向也要尊重 backend
            # 用 Connection header 声明的 hop-by-hop list.
            # round 4: 之前 round 3 写的版本只走 headers.get() 分支, 但成功路径调
            # _stream_response 时传的是 resp.getheaders() (list of tuples), 没 .get,
            # 实际 conn_resp 永远是 None — 修复无效. 改成统一从已有的 items 里找.
            conn_resp = ""
            for k, v in items:
                if k.lower() == "connection":
                    conn_resp = str(v)
                    break
            if conn_resp:
                for token in conn_resp.split(","):
                    t = token.strip().lower()
                    if t and t not in ("close", "keep-alive", "upgrade"):
                        skip.add(t)
            # GitHub @codex review (P2): RFC 7230 §3.3.3 — HEAD method 和 1xx/204/304
            # status 必须 header-terminated, 不能有 message-body 或 trailer (含 chunk
            # marker 0\r\n\r\n). 之前无条件 emit 0-chunk 会让严格 HTTP/1.1 client 在
            # keep-alive 连接上把下一个 response 错位解析. 这两类 case 跳过 chunked
            # framing 和 body read.
            no_body = (
                getattr(self, "command", "").upper() == "HEAD"
                or (100 <= int(status) <= 199)
                or int(status) in (204, 304)
            )
            wrote_chunked = False
            for k, v in items:
                if k.lower() in skip:
                    continue
                self.send_header(k, v)
            # Force chunked so we can stream without knowing total size up front,
            # 但 no-body 响应不能有任何 framing.
            if not no_body and not any(k.lower() == "content-length" for k, _ in items):
                self.send_header("Transfer-Encoding", "chunked")
                wrote_chunked = True
            self.end_headers()
            if no_body:
                # 不读 body, 不发任何 framing. 直接结束.
                return
            # Codex #302 P1 fix: read1() 不会等满 buffer, 收到任何数据立即返回,
            # SSE 心跳/小事件能实时透传, 避免 64K buffer 卡住流式响应
            read_fn = getattr(fp, "read1", None) or fp.read
            while True:
                try:
                    chunk = read_fn(64 * 1024) if read_fn is fp.read else read_fn(64 * 1024)
                except (ValueError, OSError):
                    break
                except Exception:
                    break
                if not chunk:
                    break
                try:
                    if wrote_chunked:
                        self.wfile.write(f"{len(chunk):x}\r\n".encode("ascii"))
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()  # 立即 flush 让 SSE 客户端实时收到
                    else:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
            if wrote_chunked:
                try:
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
        except (BrokenPipeError, ConnectionResetError):
            # client gave up; not our problem
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="pdf2zh lazy launch proxy")
    parser.add_argument("--port", type=int, default=DEFAULT_PROXY_PORT,
                        help=f"port to listen on (default {DEFAULT_PROXY_PORT})")
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT,
                        help=f"port for spawned server.py (default {DEFAULT_BACKEND_PORT})")
    parser.add_argument("--idle", type=int, default=DEFAULT_IDLE_TIMEOUT,
                        help=f"idle seconds before stopping backend (default {DEFAULT_IDLE_TIMEOUT})")
    parser.add_argument("--forward-timeout", type=int, default=DEFAULT_FORWARD_TIMEOUT,
                        help=f"max seconds for a forwarded request (default {DEFAULT_FORWARD_TIMEOUT})")
    parser.add_argument("--spawn-timeout", type=int, default=60,
                        help="max seconds to wait for backend /health on spawn (default 60)")
    parser.add_argument("--server-cmd", default="python server.py",
                        help="command to spawn backend (default 'python server.py'); "
                             "user is responsible for activating any venv")
    parser.add_argument("--server-cwd", default=os.path.dirname(os.path.abspath(__file__)),
                        help="working directory for backend command")
    parser.add_argument("--log-file", default=None,
                        help="redirect backend stdout+stderr to this file (default: inherit)")
    parser.add_argument("--bind", default="127.0.0.1",
                        help="bind address (default 127.0.0.1; use 0.0.0.0 only on trusted networks)")
    args = parser.parse_args()

    CFG.update(
        proxy_port=args.port,
        backend_port=args.backend_port,
        idle_timeout=args.idle,
        forward_timeout=args.forward_timeout,
        spawn_timeout=args.spawn_timeout,
        server_cmd=args.server_cmd,
        server_cwd=args.server_cwd,
        log_file=args.log_file,
        bind=args.bind,
    )

    def _shutdown(*_):
        stop_backend()
        sys.exit(0)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    watcher = threading.Thread(target=idle_watcher, daemon=True)
    watcher.start()

    try:
        httpd = ThreadingHTTPServer((args.bind, args.port), ProxyHandler)
    except OSError as e:
        print(f"[lazy-proxy] failed to bind {args.bind}:{args.port}: {e}", flush=True)
        return 1
    print(
        f"[lazy-proxy] listening on http://{args.bind}:{args.port} -> "
        f"backend :{args.backend_port} (idle={args.idle}s)",
        flush=True,
    )
    try:
        httpd.serve_forever()
    finally:
        stop_backend()
    return 0


if __name__ == "__main__":
    sys.exit(main())
