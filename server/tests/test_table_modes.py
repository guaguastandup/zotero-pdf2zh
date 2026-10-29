import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import toml

from utils.config import Config
from utils.table_mode import parse_table_mode, validate_table_runtime
from utils.table_runtime import (
    FLAG,
    bounded_run_box,
    prepare_table_runtime_command,
    protected_run,
    snapshot_character,
    split_table_lines,
)


class TableModeTests(unittest.TestCase):
    def test_incomplete_engine_commands_raise_a_clear_validation_error(self):
        for command in (
            [FLAG, "fixed"],
            ["python", "-m", FLAG, "fixed"],
            ["python", FLAG, "fixed"],
        ):
            with self.subTest(command=command), self.assertRaises(ValueError):
                prepare_table_runtime_command(command)

    def test_glyph_snapshot_does_not_recurse_into_deep_clip_state(self):
        clip = None
        for _ in range(2000):
            clip = SimpleNamespace(previous=clip)
        source = SimpleNamespace(
            box=SimpleNamespace(x=1),
            visual_bbox=SimpleNamespace(box=SimpleNamespace(x=1)),
            pdf_style=SimpleNamespace(font_size=10, graphic_state=clip),
        )
        saved = snapshot_character(source)
        source.box.x = 20
        source.visual_bbox.box.x = 30
        source.pdf_style.font_size = 40
        self.assertEqual(saved.box.x, 1)
        self.assertEqual(saved.visual_bbox.box.x, 1)
        self.assertEqual(saved.pdf_style.font_size, 10)
        self.assertIs(saved.pdf_style.graphic_state, clip)

    def test_available_whitespace_stops_before_other_cells_and_rules(self):
        def char(x, y):
            return SimpleNamespace(
                visual_bbox=SimpleNamespace(
                    box=SimpleNamespace(x=x, y=y, x2=x + 10, y2=y + 8)
                ),
                pdf_style=SimpleNamespace(font_size=10),
            )

        source, neighbour, next_row = char(10, 20), char(30, 20), char(10, 8)
        table = SimpleNamespace(x=0, y=0, x2=100, y2=100)
        rule = SimpleNamespace(box=SimpleNamespace(x=0, x2=100, y=30, y2=30))
        left, bottom, right, top = bounded_run_box(
            [source], [source, neighbour, next_row], table, [rule]
        )
        self.assertEqual(left, 10)
        self.assertEqual(right, 25)
        self.assertGreater(bottom, next_row.visual_bbox.box.y2)
        self.assertLess(top, rule.box.y)

    def setUp(self):
        output = redirect_stdout(StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_legacy_requests_keep_their_table_switch(self):
        config = Config({"engine": "pdf2zh_next", "translateTableText": True})
        self.assertIsNone(config.table_mode)
        self.assertTrue(config.translate_table_text)

    def test_table_switch_overwrites_previous_persisted_setting(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.toml"
            for enabled, mode, expected_ocr in (
                (False, None, False),
                (True, None, True),
                (True, "fixed", False),
            ):
                with self.subTest(enabled=enabled, mode=mode):
                    path.write_text(
                        "[pdf]\ntranslate_table_text = true\n", encoding="utf-8"
                    )
                    request = {
                        "engine": "pdf2zh_next",
                        "next_service": "openai",
                        "translateTableText": enabled,
                        "tableMode": mode,
                    }
                    Config(request).update_config_file(path)
                    self.assertIs(
                        toml.load(path)["pdf"]["translate_table_text"], expected_ocr
                    )

    def test_explicit_modes_disable_legacy_table_ocr(self):
        for mode in ("preserve", "fixed"):
            config = Config(
                {"engine": "pdf2zh_next", "tableMode": mode, "translateTableText": True}
            )
            self.assertEqual(config.table_mode, mode)
            self.assertFalse(config.translate_table_text)

    def test_unsupported_modes_and_runtimes_fail_explicitly(self):
        for mode in ("adaptive", "unknown", False, [], {}):
            with self.assertRaises(ValueError):
                parse_table_mode(mode)
        with self.assertRaises(ValueError):
            Config({"engine": "pdf2zh", "tableMode": "fixed"})
        with self.assertRaises(ValueError):
            validate_table_runtime("fixed", engine="pdf2zh_next", winexe=True)

    def test_legacy_command_is_unchanged(self):
        command = ["pdf2zh_next", "input.pdf"]
        self.assertIs(prepare_table_runtime_command(command), command)

    def test_adapter_uses_the_selected_engine_interpreter(self):
        with tempfile.TemporaryDirectory() as temp:
            scripts = Path(temp) / "Scripts"
            scripts.mkdir()
            engine = scripts / "pdf2zh_next.exe"
            python = scripts / "python.exe"
            engine.touch()
            python.touch()
            command = [str(engine), "paper.pdf", "--deepseek", FLAG, "fixed"]
            with patch("utils.table_runtime.shutil.which", return_value=str(engine)):
                wrapped = prepare_table_runtime_command(command)
            self.assertEqual(wrapped[0], str(python))
            self.assertEqual(wrapped[3:], ["fixed", "paper.pdf", "--deepseek"])
            self.assertNotIn(FLAG, wrapped)

    def test_numerical_values_and_metric_arrows_are_protected(self):
        for text in ("0.0084", "13.40", "96.5%", "FVD↓", "PSNR↑", "SR (%)", "✓ × △"):
            self.assertTrue(protected_run(text), text)
        self.assertFalse(protected_run("Dataset"))
        self.assertFalse(protected_run("without reference video"))

    def test_columns_split_at_gutters_without_splitting_normal_word_spacing(self):
        def char(x, y=20):
            return SimpleNamespace(
                box=SimpleNamespace(y=y),
                visual_bbox=SimpleNamespace(box=SimpleNamespace(x=x, x2=x + 3)),
                pdf_style=SimpleNamespace(font_size=10),
            )

        chars = [char(0), char(5), char(25), char(30), char(0, 5)]
        lines = list(split_table_lines(chars))
        self.assertEqual([len(run) for run in lines[0]], [2, 2])
        self.assertEqual([len(run) for run in lines[1]], [1])


if __name__ == "__main__":
    unittest.main()
