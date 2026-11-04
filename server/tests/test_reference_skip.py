"""Reference Skip tests: region decisions, hook cleanup and CLI forwarding."""

import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from utils import reference_skip, table_runtime
from utils.config import Config


def paragraph(text, label="text"):
    return SimpleNamespace(
        unicode=text, layout_label=label, debug_id=text,
    )


def document(*pages):
    return SimpleNamespace(
        page=[
            SimpleNamespace(page_number=i, pdf_paragraph=list(paragraphs))
            for i, paragraphs in enumerate(pages)
        ]
    )


class ReferenceRegionTests(unittest.TestCase):
    def test_preserve_bibliography_but_translate_appendix(self):
        doc = document(
            [paragraph("Introduction"), paragraph("Main text.")],
            [
                paragraph("References", "title"),
                paragraph("[1] Chen, Efficient Systems, 2024"),
                paragraph("[2] Li, Algorithms, 2023"),
            ],
            [
                paragraph("[3] Xu, More Algorithms, 2022"),
                paragraph("Appendix A", "title"),
                paragraph("Implementation details"),
            ],
        )
        ids = reference_skip.find_reference_paragraph_ids(doc)
        self.assertEqual(
            [_t.unicode for page in doc.page for _t in page.pdf_paragraph
             if id(_t) in ids],
            [
                "[1] Chen, Efficient Systems, 2024",
                "[2] Li, Algorithms, 2023",
                "[3] Xu, More Algorithms, 2022",
            ],
        )
        self.assertIs(reference_skip._plan_for(doc), reference_skip._plan_for(doc))
        self.assertNotIn(id(doc.page[2].pdf_paragraph[-1]), ids)

    def test_do_not_skip_table_of_contents_or_body_mentions(self):
        doc = document([
            paragraph("References", "title"),
            paragraph("1 Introduction"),
            paragraph("2 Methods"),
            paragraph("We cite several references in this paper."),
            paragraph("No bibliography here."),
        ])
        self.assertEqual(reference_skip.find_reference_paragraph_ids(doc), frozenset())

    def test_unnumbered_references_and_new_page_heading(self):
        doc = document(
            [paragraph("Bibliography", "title"),
             paragraph("Smith, R. (2021) A paper about translation."),
             paragraph("Jones, A. (2023) Improved algorithms.")],
            [paragraph("References carry on", "header"),
             paragraph("404", "page number"),
             paragraph("Doe, J. (2024) Last paper.", "title")],
            [paragraph("Supplementary Material", "heading"),
             paragraph("Supplementary experiment.")],
        )
        ids = reference_skip.find_reference_paragraph_ids(doc)
        self.assertEqual(len(ids), 3)
        self.assertNotIn(id(doc.page[2].pdf_paragraph[0]), ids)

    def test_unknown_version_fails_closed(self):
        with patch("importlib.metadata.version", return_value="0.6.2"):
            self.assertFalse(reference_skip.policy_supported())

    def test_reference_only_command_and_original_legacy_path(self):
        old = ["pdf2zh_next", "file.pdf"]
        self.assertIs(table_runtime.prepare_table_runtime_command(old), old)
        command = [
            sys.executable, "-m", "pdf2zh_next", "file.pdf",
            "--zotero-reference-skip",
        ]
        wrapped = table_runtime.prepare_table_runtime_command(command)
        self.assertEqual(wrapped[:3], [
            sys.executable, "-u", str(table_runtime.Path(
                table_runtime.__file__
            ).with_name("table_runner.py"))
        ])
        self.assertEqual(
            wrapped[3:],
            ["none", "--zotero-reference-skip", "file.pdf"],
        )
        both = table_runtime.prepare_table_runtime_command(
            command + ["--zotero-table-mode", "fixed"]
        )
        self.assertEqual(both[3:5], ["fixed", "--zotero-reference-skip"])

    def test_reference_pref_off_for_old_requests_and_legacy_engine(self):
        with patch("sys.stdout", new_callable=__import__("io").StringIO):
            self.assertFalse(Config({"engine": "pdf2zh_next"}).skip_references)
            self.assertFalse(Config({
                "engine": "pdf2zh", "skipReferences": "true"
            }).skip_references)
            self.assertTrue(Config({
                "engine": "pdf2zh_next", "skipReferences": "true"
            }).skip_references)


class HookLifecycleTests(unittest.TestCase):
    def test_translation_and_glossary_skip_and_restore(self):
        class Progress:
            def __init__(self):
                self.count = 0

            def advance(self, count):
                self.count += count

        class Executor:
            def __init__(self):
                self.batches = []

            def submit(self, task, batch, *args, **kwargs):
                self.batches.append(batch)

        class Main:
            def translate(self, docs):
                self.seen = []
                self.progress = Progress()
                self.executor = Executor()
                translated = set()
                for page in docs.page:
                    self.process_page(
                        page, self.executor, self.progress,
                        object(), object(), translated,
                    )
                return self.seen

            def _should_translate_paragraph(self, paragraph, *args, **kwargs):
                return True

            def process_page(
                self, page, executor, pbar=None, tracker=None,
                executor2=None, translated_ids=None,
            ):
                selected = [
                    item for item in page.pdf_paragraph
                    if self._should_translate_paragraph(item)
                ]
                self.seen.extend(selected)
                if selected:
                    batch = SimpleNamespace(
                        paragraphs=selected, pages=[page] * len(selected)
                    )
                    executor.submit(lambda x: x, batch)

        class Terms:
            def procress(self, docs):
                self.seen = []
                self.progress = Progress()
                for page in docs.page:
                    self.process_page(page, Executor(), self.progress, object())
                return self.seen

            def process_page(self, page, executor, pbar=None, tracker=None):
                self.seen.extend(page.pdf_paragraph)

        original_translate = Main.translate
        original_process = Main.process_page
        original_terms = Terms.procress
        names = [
            "babeldoc",
            "babeldoc.format",
            "babeldoc.format.pdf",
            "babeldoc.format.pdf.document_il",
            "babeldoc.format.pdf.document_il.midend",
        ]
        modules = {name: ModuleType(name) for name in names}
        for module in modules.values():
            module.__path__ = []
        main_key = (
            "babeldoc.format.pdf.document_il.midend.il_translator_llm_only"
        )
        term_key = (
            "babeldoc.format.pdf.document_il.midend.automatic_term_extractor"
        )
        modules[main_key] = ModuleType(main_key)
        modules[main_key].ILTranslatorLLMOnly = Main
        modules[term_key] = ModuleType(term_key)
        modules[term_key].AutomaticTermExtractor = Terms
        doc = document(
            [paragraph("References", "title"),
             paragraph("[1] Wang, Research, 2022"),
             paragraph("[2] Zhang, More Research, 2023")],
            [paragraph("Appendix A", "title"),
             paragraph("Extra proof")],
        )
        with (
            patch.dict(sys.modules, modules),
            patch.object(reference_skip, "policy_supported", return_value=True),
        ):
            restore = reference_skip.install_reference_skip_policy()
            try:
                main = Main()
                visible = main.translate(doc)
                self.assertEqual(
                    [p.unicode for p in visible],
                    ["References", "Appendix A", "Extra proof"],
                )
                self.assertEqual(main.progress.count, 2)
                for batch in main.executor.batches:
                    expected_page = next(
                        page for page in doc.page
                        if any(
                            id(p) == id(q)
                            for p in batch.paragraphs
                            for q in page.pdf_paragraph
                        )
                    )
                    self.assertIs(batch.pages[0], expected_page)
                term = Terms()
                self.assertEqual(
                    [p.unicode for p in term.procress(doc)],
                    ["References", "Appendix A", "Extra proof"],
                )
                self.assertEqual(term.progress.count, 2)
            finally:
                restore()
            self.assertIs(Main.translate, original_translate)
            self.assertIs(Main.process_page, original_process)
            self.assertIs(Terms.procress, original_terms)


if __name__ == "__main__":
    unittest.main()
