#!/usr/bin/env python3
"""Build a Server archive from tracked, explicitly allowed files; never delete user data."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'server.py', 'requirements.txt', 'index.html', 'favicon.svg', 'bo.mp3',
              'notice.json', 'manage_packages.py', 'update_packages.py'}
EXAMPLES = {'config.json.example', 'config.toml.example', 'venv.json.example'}
REQUIRED = {'server/server.py', 'server/requirements.txt', 'server/index.html'} | {
    'server/config/' + name for name in EXAMPLES}


def allowed(name):
    path = PurePosixPath(name)
    parts = path.parts
    if len(parts) < 2 or parts[0] != 'server':
        return False
    if any(part.startswith('.') or part == '__pycache__' for part in parts):
        return False
    if len(parts) == 2:
        return parts[1] in ROOT_FILES
    if parts[1] == 'config':
        return len(parts) == 3 and parts[2] in EXAMPLES
    if parts[1] == 'utils':
        return path.suffix == '.py'
    if parts[1] == 'warmup':
        return len(parts) == 3 and parts[2] in {
            'install-with-conda.bat', 'install-with-conda.sh',
            'install-with-uv.bat', 'install-with-uv.sh'}
    return False


def build(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    names = subprocess.check_output(['git', 'ls-files', '-z', '--', 'server'], cwd=root).decode('utf-8').split('\0')
    files = sorted(name for name in names if name and allowed(name))
    if REQUIRED - set(files):
        raise ValueError('Missing required tracked files: ' + ', '.join(sorted(REQUIRED - set(files))))
    output.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    # Atomic replacement: a failed build never replaces a previous valid ZIP.
    fd, temporary = tempfile.mkstemp(suffix='.zip', dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in files:
                source = root / name
                if source.is_symlink() or any((root / parent).is_symlink() for parent in Path(name).parents if parent != Path(".")):
                    raise ValueError('Symlinks are not distributable: ' + name)
                data = source.read_bytes()
                archive.writestr(name, data)
                entries.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() or set(archive.namelist()) != set(files):
                raise ValueError('Archive verification failed')
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    manifest = output.with_suffix('.manifest.json')
    manifest.write_text(json.dumps({'files': entries, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2) + '\n', encoding='utf-8')
    print(f'Built {output}: {len(files)} files. Manifest: {manifest}')
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/server.zip')
    args = parser.parse_args()
    build(ROOT, args.output.resolve())
