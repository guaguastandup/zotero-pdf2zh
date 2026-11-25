#!/usr/bin/env python3
"""Prepare locally by default; commit selected paths or publish only with explicit flags."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from package_server import ROOT, build


def run(*args, capture=False):
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'server')}
    return subprocess.check_output(args, cwd=ROOT, env=env, text=True).strip() if capture else subprocess.run(args, cwd=ROOT, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit-message', help='Commit only explicitly named --paths after validation')
    parser.add_argument('--paths', nargs='+', help='Repository-relative files to include in the commit')
    parser.add_argument('--publish', action='store_true', help='Publish the current clean main HEAD using the existing version-tag workflow')
    args = parser.parse_args()
    if bool(args.commit_message) != bool(args.paths):
        parser.error('--commit-message and --paths must be used together')
    if args.publish and args.commit_message:
        parser.error('Commit and publication are separate steps; review the commit before --publish')
    if not shutil.which('gitleaks'):
        parser.error('Install gitleaks first; secret scanning is required (https://github.com/gitleaks/gitleaks)')
    # Existing staged changes must never be silently swept into a release commit.
    if run('git', 'diff', '--cached', '--name-only', capture=True):
        parser.error('Index already contains staged changes; commit or unstage them first')
    if args.paths:
        for name in args.paths:
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or not (ROOT / path).is_file():
                parser.error('Each --paths entry must be an existing repository-relative file')
            if any(part.startswith('.env') or part in {'translated', 'wenyi-tasks', 'node_modules'} for part in path.parts) or path.suffix in {'.zip', '.xpi', '.pem', '.key'}:
                parser.error('Refusing private data or built artifact: ' + name)
            if str(path) in {'server/config/config.json', 'server/config/config.toml', 'server/config/venv.json'}:
                parser.error('Refusing local configuration: ' + name)
    if args.publish:
        if run('git', 'branch', '--show-current', capture=True) != 'main':
            parser.error('Publish only from main after manual testing and merge')
        if run('git', 'status', '--porcelain', capture=True):
            parser.error('Publish requires a clean checkout (including untracked files)')
        run('git', 'fetch', 'origin')
        if run('git', 'rev-parse', 'HEAD', capture=True) != run('git', 'rev-parse', 'origin/main', capture=True):
            parser.error('Push/reconcile main first; publication must reference the reviewed remote main')
    run('git', 'diff', '--check')
    (ROOT / 'dist').mkdir(exist_ok=True)
    # Scan a clean export of all tracked current files, not the user's local credentials.
    with tempfile.TemporaryDirectory(prefix='pdf2zh-release-scan-') as directory:
        export = Path(directory)
        names = run('git', 'ls-files', '-z', capture=True).split('\0')
        for name in set(names + (args.paths or [])) - {''}:
            source = ROOT / name
            if not source.exists():
                continue
            if source.is_symlink():
                parser.error('Tracked symlink requires manual release review: ' + name)
            destination = export / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        run('gitleaks', 'dir', str(export), '--redact=100', '--no-banner', '--max-archive-depth=2', '--report-format=json', '--report-path=' + str(ROOT / 'dist/secret-scan.json'))
    if args.commit_message:
        run('git', 'add', '--', *args.paths)
        run('gitleaks', 'git', '--staged', '--redact=100', '--no-banner')
        build(ROOT, ROOT / 'dist/server.zip')
        run('git', 'commit', '-m', args.commit_message)
        print('Committed selected files. No push, tag or publication performed.')
    elif args.publish:
        build(ROOT, ROOT / 'dist/server.zip')
        # Check before creating a tag; no version is bumped automatically.
        version = json.loads((ROOT / 'plugin/package.json').read_text())['version']
        server = re.search(r'^__version__\s*=\s*[\'\"]([^\'\"]+)', (ROOT / 'server/server.py').read_text(), re.M).group(1)
        if server != version:
            parser.error('Plugin and Server versions must match')
        tag = 'v' + version
        if run('git', 'tag', '--list', tag, capture=True) or run('git', 'ls-remote', '--tags', 'origin', 'refs/tags/' + tag, capture=True):
            parser.error('Version tag already exists; never overwrite a release')
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tools/tests')
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'server/tests')
        run('npm', '--prefix', 'plugin', 'test')
        run('npm', '--prefix', 'plugin', 'run', 'build')
        run('git', 'tag', '-a', tag, '-m', 'Release ' + tag)
        run('git', 'push', 'origin', 'refs/tags/' + tag)
        print('Tag pushed. Publication is performed by GitHub Actions; check its result.')
    else:
        build(ROOT, ROOT / 'dist/server.zip')
        print('Prepared and scanned locally. No commit, push, tag or publication performed.')


if __name__ == '__main__':
    main()
