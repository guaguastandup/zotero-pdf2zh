"""Bounded local diagnostics reads; byte offsets never expose partial records."""
import hashlib
import hmac
import secrets as secure_random
import ipaddress
from pathlib import Path
import re
import threading


def is_loopback(address):
    try:
        ip = ipaddress.ip_address(address)
        return ip.is_loopback or bool(getattr(ip, 'ipv4_mapped', None) and ip.ipv4_mapped.is_loopback)
    except (ValueError, TypeError):
        return False


class LogStream:
    def __init__(self, path, max_bytes=65536, secrets=lambda: ()):
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.secrets = secrets
        self._signing_key = secure_random.token_bytes(32)
        self._identity = None
        self._lock = threading.Lock()

    def read(self, offset, cursor=None):
        if type(offset) is not int or offset < 0:
            raise ValueError('offset must be a non-negative integer')
        with self._lock:
            return self._read(offset, cursor)

    def _cursor(self, log, identity, offset):
        log.seek(max(0, offset - 64))
        preceding = log.read(min(offset, 64))
        payload = f'{identity[0]}:{identity[1]}:{offset}:'.encode() + preceding
        return hmac.new(self._signing_key, payload, hashlib.sha256).hexdigest()

    def _read(self, offset, cursor):
        reset = False
        try:
            log = self.path.open('rb')
        except FileNotFoundError:
            self._identity = None
            return dict(text='', offset=0, reset=offset != 0, cursor='')
        with log:
            import os
            stat = os.fstat(log.fileno())
            # Metadata timestamps can change on append on Windows too.
            # Device + file ID stays stable while the same file is extended.
            identity = (stat.st_dev, stat.st_ino)
            signed_mismatch = (cursor is not None and not (offset == 0 and cursor == '') and
                               (offset > stat.st_size or not isinstance(cursor, str) or
                                not hmac.compare_digest(cursor.encode('utf-8'),
                                    self._cursor(log, identity, offset).encode('ascii'))))
            if signed_mismatch or (self._identity is not None and identity != self._identity) or offset > stat.st_size:
                offset, reset = 0, True
            self._identity = identity
            def result(text, next_offset):
                return dict(text=text, offset=next_offset, reset=reset,
                            cursor=self._cursor(log, identity, next_offset))
            # An offset within an oversized record skips its remainder, boundedly.
            partial = False
            if offset:
                log.seek(offset - 1)
                partial = log.read(1) not in (b'\n', b'\r')
            log.seek(offset)
            raw = log.read(self.max_bytes)
            if partial:
                end = next((i + 1 for i, byte in enumerate(raw) if byte in (10, 13)), len(raw))
                return result('', offset + end)
            end = max(raw.rfind(b'\n'), raw.rfind(b'\r')) + 1
            if not end:
                # Hold unfinished records; discard oversized records without exposing them.
                advance = len(raw) if len(raw) == self.max_bytes else 0
                return result('', offset + advance)
            text = raw[:end].decode('utf-8', errors='replace')
            # Fail closed if configured secrets cannot be loaded.
            secrets = tuple(str(value) for value in self.secrets() if value)
            output = []
            for line in text.splitlines(keepends=True):
                sensitive = re.search(r'(?i)(api[ _-]?key|token|secret|password|authorization|bearer|sk-[a-z0-9_-]{8,}|https?://[^\s/]+:[^\s/@]+@)', line)
                if sensitive or any(value in line for value in secrets):
                    output.append('[sensitive log record hidden]\n')
                else:
                    output.append(line)
            return result(''.join(output), offset + end)
