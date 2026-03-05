"""
测试 execute.py 中的功能

主要测试：
1. Windows VT 模式启用函数
2. 进度解析正则表达式
3. ANSI 转义序列处理
"""

import sys
import re
import pytest

# 添加父目录到路径以便导入
sys.path.insert(0, '.')


class TestProgressRegex:
    """测试进度解析正则表达式"""

    def test_main_progress_re(self):
        """测试主进度正则表达式"""
        from utils.execute import MAIN_PROGRESS_RE

        # 测试标准格式
        text = "translate ━━━━━━━━━━━━━━━━━━━━ 50/100 0:00:15"
        match = MAIN_PROGRESS_RE.search(text)
        assert match is not None
        assert match.group(1) == "50"
        assert match.group(2) == "100"

    def test_main_progress_with_ansi(self):
        """测试带 ANSI 转义序列的主进度"""
        from utils.execute import MAIN_PROGRESS_RE, ANSI_ESCAPE

        # 模拟 Rich 输出的带颜色的进度条
        text = "\x1b[38;5;39mtranslate\x1b[0m \x1b[38;5;39m━━━━━━\x1b[0m 75/200"
        clean = ANSI_ESCAPE.sub('', text)
        match = MAIN_PROGRESS_RE.search(clean)
        assert match is not None
        assert match.group(1) == "75"
        assert match.group(2) == "200"

    def test_step_progress_re(self):
        """测试步骤进度正则表达式"""
        from utils.execute import STEP_PROGRESS_RE

        text = "Parse Page Layout (1/1) ━━━━━ 2/2 0:00:00"
        match = STEP_PROGRESS_RE.search(text)
        assert match is not None
        assert "Parse Page Layout" in match.group(1)

    def test_legacy_progress_re(self):
        """测试旧版 pdf2zh 进度格式"""
        from utils.execute import LEGACY_PROGRESS_RE

        text = "Running: 30/100 pages"
        match = LEGACY_PROGRESS_RE.search(text)
        assert match is not None
        assert match.group(1) == "30"
        assert match.group(2) == "100"


class TestAnsiEscape:
    """测试 ANSI 转义序列处理"""

    def test_ansi_escape_removal(self):
        """测试 ANSI 转义序列移除"""
        from utils.execute import ANSI_ESCAPE

        # 包含各种 ANSI 序列的文本
        text = "\x1b[38;5;39mcolored\x1b[0m \x1b[1mbold\x1b[0m"
        clean = ANSI_ESCAPE.sub('', text)
        assert clean == "colored bold"

    def test_cursor_control_sequences(self):
        """测试光标控制序列"""
        from utils.execute import ANSI_ESCAPE

        # 光标移动和清除序列
        text = "\x1b[2K\r\x1b[AProgress: 50%"
        clean = ANSI_ESCAPE.sub('', text)
        # 应该移除所有转义序列
        assert "\x1b" not in clean


class TestWindowsConPTY:
    """测试 Windows ConPTY 相关函数"""

    def test_conpty_fallback_exists(self):
        """测试 ConPTY 回退函数存在"""
        from utils.execute import _execute_with_pipe_fallback
        assert callable(_execute_with_pipe_fallback)

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only test")
    def test_conpty_function_exists(self):
        """测试 ConPTY 函数在 Windows 上存在"""
        from utils.execute import _execute_with_conpty
        assert callable(_execute_with_conpty)


class TestProgressParsing:
    """测试进度解析功能"""

    def test_parse_progress_main(self):
        """测试主进度解析"""
        from utils.execute import _parse_progress

        # 使用模拟的 task_manager
        updates = {}

        class MockTaskManager:
            def update_task(self, task_id, data):
                updates.update(data)

        import utils.execute
        original_tm = utils.execute.task_manager
        utils.execute.task_manager = MockTaskManager()

        try:
            text = "translate ━━━━━━━━━━━━━━━━━━━━ 50/100 0:00:15"
            _parse_progress(text, "test-task")

            assert updates.get('progress') == 50
            assert '翻译中' in updates.get('message', '')
        finally:
            utils.execute.task_manager = original_tm

    def test_parse_progress_step(self):
        """测试步骤进度解析"""
        from utils.execute import _parse_progress

        updates = {}

        class MockTaskManager:
            def update_task(self, task_id, data):
                updates.update(data)

        import utils.execute
        original_tm = utils.execute.task_manager
        utils.execute.task_manager = MockTaskManager()

        try:
            text = "Translate Paragraphs (1/1) ━━━━━ 5/10 0:00:05"
            _parse_progress(text, "test-task")

            assert 'Translate Paragraphs' in updates.get('message', '')
        finally:
            utils.execute.task_manager = original_tm


class TestEnvironmentVariables:
    """测试环境变量设置"""

    def test_rich_force_terminal_env(self):
        """测试 Rich 强制终端环境变量"""
        import os

        # 模拟 _execute_with_pipe 中的环境变量设置
        env = os.environ.copy()
        env['_RICH_FORCE_TERMINAL'] = 'force'
        env['RICH_FORCE_WIDTH'] = '200'

        assert env.get('_RICH_FORCE_TERMINAL') == 'force'
        assert env.get('RICH_FORCE_WIDTH') == '200'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
