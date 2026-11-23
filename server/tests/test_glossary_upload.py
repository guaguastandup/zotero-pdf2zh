import unittest
from pathlib import Path

from utils.glossary_upload import temporary_glossary, validate_glossary_csv


class GlossaryUploadTests(unittest.TestCase):
    def test_csv_preserves_quoted_commas_and_chinese_text(self):
        csv = 'source,target,tgt_lng\r\n"gain, phase",增益相位,zh-CN\r\n'
        content = validate_glossary_csv("\ufeff" + csv)
        with temporary_glossary(content) as filename:
            path = Path(filename)
            self.assertEqual(path.read_bytes().decode("utf-8-sig"), csv)
        self.assertFalse(path.exists())

    def test_invalid_uploads_are_rejected(self):
        for content in (
            None,
            "/path/on/server.csv",
            "source,target\n",
            "source,target\nx,\n",
            'source,target\n"unclosed,x',
            "source,target\nx,y,z",
            "x" * (1024 * 1024 + 1),
        ):
            with self.subTest(name=str(content)[:35]), self.assertRaises(ValueError):
                validate_glossary_csv(content)

    def test_overlapping_jobs_get_distinct_paths_and_clean_up_on_error(self):
        with temporary_glossary("source,target\na,b") as first:
            with self.assertRaisesRegex(RuntimeError, "engine failed"):
                with temporary_glossary("source,target\nc,d") as second:
                    self.assertNotEqual(first, second)
                    raise RuntimeError("engine failed")
            self.assertTrue(Path(first).is_file())
            self.assertFalse(Path(second).exists())
