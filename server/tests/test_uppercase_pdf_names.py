"""Uppercase source names (``.PDF``) must resolve the same products as ``.pdf``.

Zotero stores the filename it downloaded, so a source can arrive as
``Paper.PDF``.  Every suffix decision used a case-sensitive
``str.endswith``/``str.replace``; on such files the expected product path kept
the whole ``.PDF`` stem, the completion check found nothing, and ``/translate``
reported "操作失败，请查看详细日志。" even though the PDFs had been generated.
``compare`` was worse: it resolved to the input path and removed the source.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server


class UppercaseSourceNameTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.translator = server.PDFTranslator(SimpleNamespace(enable_venv=False))

    def resolve(self, name, outtype, engine):
        return self.translator.get_filename_after_process(
            os.path.join(self.directory, name), outtype, engine
        )

    def test_origin_products_drop_uppercase_extension(self):
        for engine, separator in (
            (server.pdf2zh_next, "."),
            (server.pdf2zh, "-"),
        ):
            for outtype, suffix in (
                ("mono", "mono"),
                ("dual", "dual"),
                ("origin-cut", "cut"),
            ):
                with self.subTest(engine=engine, outtype=outtype):
                    expected = os.path.join(
                        self.directory, f"Paper{separator}{suffix}.pdf"
                    )
                    self.assertEqual(
                        self.resolve("Paper.PDF", outtype, engine), expected
                    )
                    self.assertEqual(
                        self.resolve("Paper.pdf", outtype, engine), expected
                    )

    def test_compare_never_resolves_to_the_source_file(self):
        for name in ("Paper.PDF", "Paper.pdf", "Paper.PdF"):
            with self.subTest(name=name):
                source = os.path.join(self.directory, name)
                resolved = self.resolve(name, "compare", server.pdf2zh_next)
                self.assertEqual(
                    resolved,
                    os.path.join(self.directory, "Paper.compare.pdf"),
                )
                self.assertNotEqual(
                    os.path.normcase(resolved), os.path.normcase(source)
                )

    def test_dual_layout_suffixes_are_case_insensitive(self):
        cases = {
            "Paper.LR_dual.PDF": "LR",
            "Paper.lr_dual.pdf": "LR",
            "Paper.TB_dual.PDF": "TB",
            "Paper.tb_dual.PDF": "TB",
        }
        for name, mode in cases.items():
            with self.subTest(name=name):
                path = os.path.join(self.directory, name)
                self.assertEqual(self.translator.get_filetype(path), "dual")
                self.assertEqual(self.translator.get_dual_mode(path), mode)

    def test_dual_products_rebuild_the_layout_suffix(self):
        for name in ("Paper.LR_dual.PDF", "Paper.LR_dual.pdf"):
            with self.subTest(name=name):
                self.assertEqual(
                    self.resolve(name, "crop-compare", server.pdf2zh_next),
                    os.path.join(self.directory, "Paper.crop-compare.pdf"),
                )

    def test_translate_job_accepts_uppercase_source(self):
        """The whole translate path must resolve its products for ``.PDF``."""
        source = os.path.join(self.directory, "Paper.PDF")
        Path(source).write_bytes(b"%PDF-1.4\n")

        def fake_translate_pdf_next(input_path, config, task_id=None):
            stem = os.path.splitext(input_path)[0]
            mono = f"{stem}.no_watermark.zh-CN.mono.pdf"
            dual = f"{stem}.no_watermark.zh-CN.dual.pdf"
            Path(mono).write_bytes(b"%PDF-1.4\n")
            Path(dual).write_bytes(b"%PDF-1.4\n")
            return [mono, dual]

        config = SimpleNamespace(
            targetLang="zh-CN",
            sourceLang="en",
            no_watermark=True,
            no_mono=False,
            no_dual=False,
            mono=True,
            dual=True,
            dual_mode="LR",
            dual_cut=False,
            crop_compare=False,
            compare=False,
            mono_cut=False,
            skip_last_pages=0,
        )
        with patch.object(
            self.translator,
            "translate_pdf_next",
            side_effect=fake_translate_pdf_next,
        ):
            payload = self.translator._execute_translate_job(
                "task-id", source, config, server.pdf2zh_next
            )

        self.assertEqual(payload["status"], "success")
        self.assertEqual(len(payload["fileList"]), 2)
        for name in payload["fileList"]:
            self.assertNotIn(".PDF.", name)
            self.assertTrue(os.path.exists(os.path.join(self.directory, name)))


if __name__ == "__main__":
    unittest.main()