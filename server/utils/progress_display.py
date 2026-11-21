"""Compact terminal progress driven by BabelDOC events, without console scraping."""
import json
from pathlib import Path
import shutil
import subprocess
import time

from utils.progress_terminal import TerminalProgress

PREFIX = 'PDF2ZH_PROGRESS '



def progress_command(command, env):
    """Preserve the chosen environment and every CLI argument."""
    if not command:
        return None
    exe = Path(command[0])
    name = exe.stem.lower()
    if name.startswith('python') and len(command) > 2:
        script_index = next((i for i, value in enumerate(command[1:], 1)
                             if Path(value).name == 'table_runner.py'), None)
        if script_index is not None:
            runner = str(Path(__file__).with_name('progress_runner.py'))
            return [str(exe), *command[1:script_index], runner,
                    '--wrapped-script', *command[script_index:]]
    if name.startswith('python') and '-m' in command:
        index = command.index('-m')
        if command[index + 1:index + 2] != ['pdf2zh_next']:
            return None
        python = str(exe)
        arguments = command[index + 2:]
        options = command[1:index]
    elif name == 'pdf2zh_next':
        resolved = Path(shutil.which(str(exe), path=env.get('PATH')) or exe)
        candidate = resolved.parent / 'python.exe'
        if not candidate.is_file():
            return None
        python, options, arguments = str(candidate), [], command[1:]
    else:
        return None
    runner = str(Path(__file__).with_name('progress_runner.py'))
    return [python, *options, '-u', runner, *arguments]


def execute_progress(command, env, task_id, on_output=None):
    """Consume newline-framed progress and retain full engine diagnostics."""
    log_dir = Path(__file__).resolve().parents[1] / 'work' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_id = ''.join(c for c in str(task_id or time.time_ns()) if c.isalnum() or c in '-_')
    log_path = log_dir / f'translation-{safe_id}.log'
    print(f'详细翻译日志：{log_path}', flush=True)
    display = TerminalProgress(task_id)
    display.draw(force=True)
    runtime_env = dict(env, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=runtime_env, text=True, encoding='utf-8', errors='replace', bufsize=1,
    )
    error = None
    try:
        with log_path.open('w', encoding='utf-8') as log:
            for line in process.stdout:
                if on_output:
                    on_output(line)
                log.write(line)
                log.flush()
                if line.startswith(PREFIX):
                    try:
                        event = json.loads(line[len(PREFIX):])
                    except json.JSONDecodeError:
                        continue
                    try:
                        display.update(event)
                    except RuntimeError as exc:
                        error = str(exc)
                else:
                    display.draw()
        code = process.wait()
        if error:
            raise RuntimeError(f'{error}（详细日志：{log_path}）')
        if code:
            raise subprocess.CalledProcessError(code, command)
    except BaseException:
        if process.poll() is None:
            process.terminate()
            process.wait()
        display.close(failed=True)
        raise
    else:
        display.close()
    finally:
        process.stdout.close()
