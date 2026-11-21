"""Colored, stationary progress rows for each translation stage."""
import math
import os
import shutil
import sys
import time
import unicodedata

from utils.task_manager import task_manager

STAGES = {
    'Parse PDF and Create Intermediate Representation': '解析 PDF',
    'DetectScannedFile': '检测扫描页',
    'Parse Page Layout': '页面布局',
    'Parse Paragraphs': '解析段落',
    'Parse Formulas and Styles': '公式与样式',
    'Translate Paragraphs': '翻译段落',
    'Typesetting': '排版',
    'Add Fonts': '嵌入字体',
    'Generate drawing instructions': '生成页面',
    'Subset font': '处理字体',
    'Save PDF': '保存 PDF',
}
RESET, GREEN, BLUE, GRAY, RED = '\x1b[0m', '\x1b[92m', '\x1b[94m', '\x1b[90m', '\x1b[91m'
WHITE = '\x1b[97m'


def enable_terminal(stream):
    """Enable cursor movement and colors for this console, never globally."""
    if not stream.isatty():
        return False
    if os.name != 'nt':
        return True
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = wintypes.DWORD()
        return bool(kernel.GetConsoleMode(handle, ctypes.byref(mode)) and
                    kernel.SetConsoleMode(handle, mode.value | 0x0004))
    except (OSError, ValueError, AttributeError):
        return False


def cells(text):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in text)


def fit(text, width):
    result = ''
    for char in text:
        if cells(result + char) > width:
            break
        result += char
    return result


def duration(seconds):
    seconds = max(0, int(seconds))
    return f'{seconds // 60:02d}:{seconds % 60:02d}'


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


class TerminalProgress:
    def __init__(self, task_id, stream=None, clock=time.monotonic, interactive=None):
        self.task_id = task_id
        self.stream = stream or sys.stdout
        self.clock = clock
        self.started = clock()
        self.last_draw = 0
        self.percent = 0
        self.stage = '初始化翻译引擎'
        self.last_line = ''
        self.finished = False
        self.failed = False
        self.interactive = enable_terminal(self.stream) if interactive is None else interactive
        self.rendered_rows = 0
        self.part = 1
        self.total_parts = 1
        self.stages = {}
        self._reset_stages()

    def _reset_stages(self):
        self.stages = {name: {'state': 'waiting', 'current': 0, 'total': None,
                              'percent': 0, 'started': None, 'elapsed': 0}
                       for name in STAGES}

    def update(self, event):
        kind = event.get('type')
        if kind == 'error':
            raise RuntimeError(str(event.get('error') or '翻译引擎失败'))
        if kind == 'finish':
            self.finished = True
            self.percent = 99
            self.stage = '翻译排版完成，正在整理文件'
            for item in self.stages.values():
                if item['state'] == 'waiting':
                    item['state'] = 'skipped'
        else:
            value = event.get('overall_progress')
            if finite(value):
                self.percent = max(self.percent, min(99, max(0, int(value))))
            part = event.get('part_index', self.part)
            if isinstance(part, int) and part > self.part:
                self.part = part
                self._reset_stages()
            self.total_parts = event.get('total_parts', self.total_parts)
            raw = event.get('stage')
            if raw:
                if raw not in self.stages:
                    self.stages[raw] = {'state': 'waiting', 'current': 0, 'total': None,
                                        'percent': 0, 'started': None, 'elapsed': 0}
                item = self.stages[raw]
                now = self.clock()
                if kind == 'progress_start' or item['started'] is None:
                    item.update(state='running', current=0, percent=0, started=now, elapsed=0)
                current, total = event.get('stage_current'), event.get('stage_total')
                if finite(current):
                    item['current'] = max(0, int(current))
                if finite(total) and total > 0:
                    item['total'] = int(total)
                    item['percent'] = min(100, int(item['current'] * 100 / total))
                if kind == 'progress_end':
                    item.update(state='done', percent=100, elapsed=now - item['started'])
                self.stage = STAGES.get(raw, raw)
                if item['total']:
                    self.stage += f" {item['current']}/{item['total']}"
        if self.task_id:
            task_manager.update_task(self.task_id, {
                'progress': self.percent, 'status': 'running', 'message': self.stage,
            })
        self.draw(force=kind in {'progress_start', 'progress_end', 'finish'})

    def _bar(self, label, percent, count, elapsed, width, state, overall=False):
        # Bound every row to the visible width, including double-width CJK.
        label_width = min(14, max(8, width // 6))
        label = fit(label, label_width)
        label += ' ' * (label_width - cells(label))
        count = fit(count, 9)
        count = ' ' * (9 - cells(count)) + count
        suffix = f' {percent:3d}% {count} {elapsed}'
        bar_width = max(3, min(28, width - label_width - len(suffix) - 5))
        fill = min(bar_width, max(0, int(percent * bar_width / 100)))
        color = RED if state == 'failed' else (GRAY if state in {'waiting', 'skipped'} else GREEN)
        if overall and state != 'failed':
            color = BLUE
        bar = color + '━' * fill + GRAY + '─' * (bar_width - fill) + RESET
        label_color = color if overall else (GREEN if state == 'done' else WHITE)
        return label_color + label + RESET + ' [' + bar + '] ' + color + f'{percent:3d}%' + RESET + f' {count} {elapsed}'

    def rows(self, now, width):
        part = f'第{self.part}/{self.total_parts}段' if self.total_parts > 1 else ''
        overall_state = 'failed' if self.failed else 'running'
        rows = [self._bar('总体进度', self.percent, part, duration(now - self.started), width, overall_state, True)]
        for name, item in self.stages.items():
            state = item['state']
            label = STAGES.get(name, name)
            if state in {'waiting', 'skipped'}:
                status = '未使用' if state == 'skipped' else '等待'
                rows.append(self._bar(label, 0, status, '--:--', width, state))
                continue
            elapsed = now - item['started'] if state == 'running' else item['elapsed']
            count = f"{item['current']}/{item['total']}" if item['total'] else ''
            rows.append(self._bar(label, item['percent'], count, duration(elapsed), width, state))
        return rows

    def draw(self, force=False):
        now = self.clock()
        if not force and now - self.last_draw < 0.2:
            return
        self.last_draw = now
        width = max(40, shutil.get_terminal_size((100, 24)).columns - 1)
        if self.interactive:
            rows = self.rows(now, width)
            # Cursor stays on the final row between frames; reserve lines once.
            movement = f'\x1b[{self.rendered_rows - 1}A' if self.rendered_rows > 1 else ''
            self.stream.write('\r' + movement + '\n'.join('\x1b[2K' + row for row in rows) + '\r')
            self.rendered_rows = len(rows)
        else:
            bar_width = min(28, max(8, width // 4))
            fill = int(self.percent * bar_width / 100)
            bar = '#' * fill + '-' * (bar_width - fill)
            tail = f' | {duration(now - self.started)}'
            prefix = f'翻译 [{bar}] {self.percent:3d}% | '
            stage = fit(self.stage, max(0, width - cells(prefix + tail)))
            line = prefix + stage + tail
            self.stream.write('\r' + line + ' ' * max(0, cells(self.last_line) - cells(line)) + '\r')
            self.last_line = line
        self.stream.flush()

    def close(self, failed=False):
        self.failed = failed
        if failed:
            self.stage = '翻译失败，详情见日志'
            for item in self.stages.values():
                if item['state'] == 'running':
                    item.update(state='failed', elapsed=self.clock() - item['started'])
        elif self.finished:
            self.percent = 100
            self.stage = '翻译排版完成'
        self.draw(force=True)
        self.stream.write('\n')
        self.stream.flush()
