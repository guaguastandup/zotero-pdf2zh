import io
import os
import re
import unittest
from unittest.mock import patch

from utils.progress_terminal import TerminalProgress, STAGES, GREEN, GRAY, RED, cells
from utils.progress_runner import create_progress_handler, PREFIX

ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


class TerminalStageBarsTest(unittest.TestCase):
    def make_display(self):
        return TerminalProgress(None, io.StringIO(), interactive=True)

    def test_all_stages_have_their_own_row_and_bar(self):
        display = self.make_display()
        display.update({'type': 'progress_start', 'stage': 'Parse Page Layout', 'stage_current': 7, 'stage_total': 34, 'overall_progress': 19})
        rows = [ANSI.sub('', r) for r in display.rows(display.clock(), 100)]
        self.assertEqual(len(rows), len(STAGES) + 1)
        layout = next(r for r in rows if '页面布局' in r)
        translation = next(r for r in rows if '翻译段落' in r)
        self.assertIn('7/34', layout)
        self.assertIn('20%', layout)
        self.assertIn('等待', translation)
        self.assertTrue(all('[' in r and ']' in r for r in rows))

    def test_completed_stage_stays_complete_when_another_stage_starts(self):
        display = self.make_display()
        display.update({'type': 'progress_end', 'stage': 'Parse Paragraphs', 'stage_current': 17, 'stage_total': 17})
        display.update({'type': 'progress_start', 'stage': 'Translate Paragraphs', 'stage_current': 12, 'stage_total': 256})
        self.assertEqual(display.stages['Parse Paragraphs']['percent'], 100)
        self.assertEqual(display.stages['Translate Paragraphs']['current'], 12)
        self.assertIn(GREEN, display.stream.getvalue())
        self.assertIn(GRAY, display.stream.getvalue())

    def test_next_frame_moves_back_to_same_block(self):
        display = self.make_display()
        display.draw(force=True)
        offset = len(display.stream.getvalue())
        display.draw(force=True)
        frame = display.stream.getvalue()[offset:]
        self.assertTrue(frame.startswith(f'\r\x1b[{len(STAGES)}A'))
        self.assertEqual(frame.count('\x1b[2K'), len(STAGES) + 1)
        self.assertNotIn('\n\n', frame)

    def test_failed_active_stage_is_red_and_does_not_claim_completion(self):
        display = self.make_display()
        display.update({'type': 'progress_start', 'stage': 'Translate Paragraphs', 'stage_current': 12, 'stage_total': 256})
        display.close(failed=True)
        self.assertEqual(display.stages['Translate Paragraphs']['state'], 'failed')
        self.assertIn(RED, display.stream.getvalue())
        self.assertNotIn('100%', display.stream.getvalue())

    def test_cjk_rows_fit_a_narrow_console(self):
        display = self.make_display()
        display.update({'type': 'progress_start', 'stage': 'Translate Paragraphs', 'stage_current': 1234, 'stage_total': 56789, 'part_index': 2, 'total_parts': 3})
        for width in [39, 44, 79, 119]:
            for row in display.rows(display.clock(), width):
                self.assertLessEqual(cells(ANSI.sub('', row)), width)

    def test_second_part_resets_stage_bars_and_preserves_overall_progress(self):
        display = self.make_display()
        display.update({'type': 'progress_end', 'stage': 'Save PDF', 'stage_current': 2, 'stage_total': 2, 'overall_progress': 50, 'part_index': 1, 'total_parts': 2})
        display.update({'type': 'progress_start', 'stage': 'Parse Page Layout', 'stage_current': 0, 'stage_total': 20, 'overall_progress': 50, 'part_index': 2, 'total_parts': 2})
        self.assertEqual(display.stages['Save PDF']['state'], 'waiting')
        self.assertEqual(display.part, 2)
        self.assertEqual(display.percent, 50)

    def test_event_bridge_preserves_part_numbers(self):
        import contextlib
        import json
        output = io.StringIO()
        context, handler = create_progress_handler(None)
        with context, contextlib.redirect_stdout(output):
            handler({'type': 'progress_update', 'part_index': 2, 'total_parts': 3})
        event = json.loads(output.getvalue()[len(PREFIX):])
        self.assertEqual((event['part_index'], event['total_parts']), (2, 3))


if __name__ == '__main__':
    unittest.main()
