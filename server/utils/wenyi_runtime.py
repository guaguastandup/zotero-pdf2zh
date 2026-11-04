"""Own the dedicated Wenyi Python environment and its separate HTTP bridge."""

import atexit
import json
import math
import os
import queue
import subprocess
import threading
import urllib.request
from pathlib import Path


class ManagedWenyiRuntime:
    def __init__(self, env_manager, state_root, *, bridge_url=None, startup_timeout=60):
        if not math.isfinite(startup_timeout) or startup_timeout <= 0:
            raise ValueError("Bridge startup timeout must be positive and finite")
        self.env_manager = env_manager
        self.state_root = Path(state_root).resolve()
        self.external_bridge_url = bridge_url
        self.startup_timeout = startup_timeout
        self._lock = threading.RLock()
        self._process = None
        self._bridge_url = None
        self._closed = False
        atexit.register(self.close)

    def prepare(self):
        """Return a CLI prefix, isolated environment and live bridge URL."""
        with self._lock:
            if self._closed:
                raise RuntimeError("The managed Wenyi runtime has been shut down")
            python, environment = self.env_manager.get_python_and_env("wenyi")
            environment = environment.copy()
            if self.external_bridge_url:
                bridge_url = self.external_bridge_url
            else:
                if self._process is None or self._process.poll() is not None:
                    self._stop_bridge()
                    self._start_bridge(python, environment)
                bridge_url = self._bridge_url
                # The CLI's HTTP client must never send private local PDF traffic
                # through an ambient HTTP proxy. Preserve all other proxy rules.
                for key in ("NO_PROXY", "no_proxy"):
                    environment[key] = ",".join(
                        filter(None, (environment.get(key), "127.0.0.1", "localhost"))
                    )
            return [str(python), "-I", "-m", "wenyi_cli"], environment, bridge_url

    def _start_bridge(self, python, environment):
        self.state_root.mkdir(parents=True, exist_ok=True)
        bridge_environment = environment.copy()
        bridge_environment.pop("DEEPSEEK_API_KEY", None)
        bridge_environment["WENYI_BABELDOC_STATE_DIR"] = str(self.state_root / "sessions")
        command = [str(python), "-I", str(Path(__file__).with_name("wenyi_bridge.py"))]
        try:
            with (self.state_root / "bridge.log").open("ab") as log:
                self._process = subprocess.Popen(
                    command,
                    cwd=self.state_root,
                    env=bridge_environment,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            process = self._process
            ready = queue.Queue(maxsize=1)

            def read_ready():
                try:
                    line = process.stdout.readline(4097)
                    ready.put(line)
                except (OSError, ValueError):
                    ready.put(b"")

            threading.Thread(target=read_ready, daemon=True).start()
            line = ready.get(timeout=self.startup_timeout)
            if not line or len(line) > 4096:
                raise ValueError("Bridge did not return a valid readiness frame")
            frame = json.loads(line)
            port = frame.get("port")
            if (
                frame.get("protocol") != 1
                or frame.get("pid") != process.pid
                or isinstance(port, bool)
                or not isinstance(port, int)
                or not 1 <= port <= 65535
                or process.poll() is not None
            ):
                raise ValueError("Bridge returned an invalid readiness identity")
            url = f"http://127.0.0.1:{port}"
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url + "/health", timeout=5) as response:
                health = json.loads(response.read(4096))
            if health.get("ok") is not True:
                raise ValueError("Bridge health check failed")
            self._bridge_url = url
        except (OSError, ValueError, TypeError, AttributeError, queue.Empty) as error:
            self._stop_bridge()
            raise RuntimeError(
                "Cannot start the managed Wenyi bridge; check wenyi-runtime/bridge.log"
            ) from error

    def _stop_bridge(self):
        process, self._process = self._process, None
        self._bridge_url = None
        if process is None:
            return
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        finally:
            if process.stdout:
                process.stdout.close()

    def close(self):
        """Stop only a child owned by this Server, never an external service."""
        with self._lock:
            self._closed = True
            self._stop_bridge()
