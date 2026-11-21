"""Log server output without turning carriage returns into printed lines."""
import io
from pathlib import Path
import runpy
import sys
import threading


class LoggedStream(io.TextIOBase):
    def __init__(self, console, log, lock):
        self.console, self.log, self.lock = console, log, lock

    @property
    def encoding(self):
        return self.console.encoding

    def writable(self):
        return True

    def isatty(self):
        return self.console.isatty()

    def fileno(self):
        return self.console.fileno()

    def write(self, text):
        with self.lock:
            self.console.write(text)
            self.console.flush()
            self.log.write(text)
            self.log.flush()
        return len(text)

    def flush(self):
        with self.lock:
            self.console.flush()
            if not self.log.closed:
                self.log.flush()


def main():
    root = Path(__file__).resolve().parents[1]
    server = root / 'server.py'
    sys.path.insert(0, str(root))
    # Keep the absolute Server path in argv for the stop script's PID checks.
    if len(sys.argv) < 2 or Path(sys.argv[1]).resolve() != server:
        raise ValueError('Expected the absolute server.py path as the first argument')
    sys.argv = [str(server), *sys.argv[2:]]
    log_dir = root / 'work/logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    original_out, original_err = sys.stdout, sys.stderr
    with (log_dir / 'pdf2zh-server.log').open('a', encoding='utf-8') as log:
        lock = threading.RLock()
        sys.stdout = LoggedStream(original_out, log, lock)
        sys.stderr = LoggedStream(original_err, log, lock)
        try:
            runpy.run_path(str(server), run_name='__main__')
        finally:
            sys.stdout, sys.stderr = original_out, original_err


if __name__ == '__main__':
    main()
