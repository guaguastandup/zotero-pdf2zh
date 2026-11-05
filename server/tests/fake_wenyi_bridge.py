"""A tiny HTTP/owner-pipe fixture; it never imports Wenyi or BabelDOC."""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass


mode = os.environ.get("WENYI_BRIDGE_TEST_MODE")
if mode == "exit":
    raise SystemExit(2)
if mode == "stall":
    sys.stdin.buffer.read()
    raise SystemExit(0)
with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
    frame = {
        "protocol": 99 if mode == "invalid" else 1,
        "port": server.server_port,
        "pid": os.getpid(),
    }
    print(json.dumps(frame), flush=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    sys.stdin.buffer.read()
    server.shutdown()
