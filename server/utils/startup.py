"""Standard-library-only bootstrap, before importing server dependencies."""
import argparse
import os
from pathlib import Path
import sys
import subprocess


def safe_command(command):
    """Copy CLI arguments for diagnostics, masking credential flag values."""
    safe = []
    hide_next = False
    for argument in command:
        value = str(argument)
        if hide_next:
            safe.append('***')
            hide_next = False
            continue
        name, separator, _ = value.partition('=')
        sensitive = name.startswith('-') and any(
            word in name.lower() for word in ('key', 'token', 'secret', 'password')
        )
        if sensitive:
            safe.append(name + '=***' if separator else name)
            hide_next = not separator
        else:
            safe.append(value)
    return safe


def background_subprocess_options():
    """Hide Windows child consoles only for an explicit background launch."""
    if sys.platform == 'win32' and '--non-interactive' in sys.argv[1:]:
        return {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)}
    return {}


def subprocess_stdout():
    """Send background engine output to the configured log, not an absent console."""
    return sys.stdout if background_subprocess_options() else None


def configure_background(argv, server_root):
    """Provide stable paths and persistent UTF-8 diagnostics for pythonw."""
    if '--non-interactive' not in argv:
        return
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--non-interactive', action='store_true')
    parser.add_argument('--log-file')
    options, _ = parser.parse_known_args(argv)
    root = Path(server_root).resolve()
    log_path = Path(options.log_file).resolve() if options.log_file else root / 'logs' / 'server.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open('a', encoding='utf-8', buffering=1)
    sys.stdout = sys.stderr = log
    sys.stdin = open(os.devnull, 'r', encoding='utf-8')
    os.chdir(root)
