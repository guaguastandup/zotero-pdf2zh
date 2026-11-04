"""Regression coverage for the legacy 1.x one-time subset retry."""

import subprocess
import unittest
from unittest.mock import Mock

from utils.pdf2zh_font_retry import (
    execute_legacy_pdf_with_font_fallback,
    is_font_subsetting_failure,
)


def fail(log: str):
    return subprocess.CalledProcessError(
        1, ["pdf2zh", "test.pdf"], stderr=log,
    )


class LegacySubsetRetryTests(unittest.TestCase):
    def test_realistic_font_subset_errors_detected(self):
        cases = [
            "RuntimeError: Failed to subset font",
            "Font subsetting failed: invalid glyph",
            "Traceback ...\n    doc_zh.subset_fonts(fallback=True)\n"
            "pymupdf.mupdf.FzErrorFormat: cannot subset font",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(is_font_subsetting_failure(text))

    def test_api_and_environment_failures_do_not_retry(self):
        cases = [
            "HTTP 401 invalid_api_key",
            "RateLimitError: 429 Too Many Requests",
            "ConnectionError: timeout",
            "ModuleNotFoundError: No module named 'toml'",
            "ValueError: bad translation model",
            "",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(is_font_subsetting_failure(text))
                runner = Mock(side_effect=fail(text))
                with self.assertRaises(subprocess.CalledProcessError):
                    execute_legacy_pdf_with_font_fallback(
                        ["pdf2zh", "test.pdf"], runner,
                    )
                runner.assert_called_once()

    def test_subset_fail_retries_once_with_new_flag(self):
        runner = Mock(side_effect=[fail("Failed to subset font"), None])
        self.assertTrue(execute_legacy_pdf_with_font_fallback(
            ["pdf2zh", "test.pdf", "--service", "openai"], runner,
        ))
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(
            runner.call_args.args[0],
            ["pdf2zh", "test.pdf", "--service", "openai",
             "--skip-subset-fonts"],
        )

    def test_already_skipping_does_not_duplicate_or_retry(self):
        runner = Mock(side_effect=fail("Failed to subset font"))
        with self.assertRaises(subprocess.CalledProcessError):
            execute_legacy_pdf_with_font_fallback(
                ["pdf2zh", "test.pdf", "--skip-subset-fonts"], runner
            )
        runner.assert_called_once()

    def test_second_failure_is_propagated_without_third_call(self):
        runner = Mock(side_effect=[
            fail("Failed to subset font"),
            fail("RuntimeError: PDF generation failed"),
        ])
        with self.assertRaisesRegex(
            subprocess.CalledProcessError, "non-zero exit status"
        ):
            execute_legacy_pdf_with_font_fallback(["pdf2zh"], runner)
        self.assertEqual(runner.call_count, 2)

    def test_success_does_not_retry(self):
        runner = Mock()
        self.assertFalse(execute_legacy_pdf_with_font_fallback(
            ["pdf2zh"], runner
        ))
        runner.assert_called_once()


if __name__ == "__main__":
    unittest.main()
