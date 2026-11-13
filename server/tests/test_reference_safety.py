"""Fail-open bibliography detection, including adjacent appendix headings."""

import unittest
from types import SimpleNamespace

from utils.reference_skip import find_reference_paragraph_ids


def para(text, label="text"):
    return SimpleNamespace(unicode=text, layout_label=label, debug_id=text)


def ids(*pages):
    doc = SimpleNamespace(page=[
        SimpleNamespace(pdf_paragraph=list(p)) for p in pages
    ])
    skipped = find_reference_paragraph_ids(doc)
    return [
        p.unicode for page in doc.page for p in page.pdf_paragraph
        if id(p) in skipped
    ]


class ReferenceSafetyTests(unittest.TestCase):
    def test_body_section_named_references_with_prose_years(self):
        result = ids(
            [para("Introduction"), para("This is a research document.")],
            [para("3 References", "heading"),
             para("In 2020, the interface changed for all users."),
             para("After 2022, more systems adopted the method."),
             para("We discuss this change in detail."),
             para("Additional measurements are described below.")],
        )
        self.assertEqual(result, [])

    def test_appendix_same_page_lettered_title_resumes(self):
        result = ids(
            [para("Introduction"), para("Methods"), para("Results"),
             para("Discussion"), para("Conclusion")],
            [para("References", "heading"),
             para("[1] Chen, Better Systems, 2022"),
             para("[2] Li, New Algorithms, 2023"),
             para("A. Proof of Theorem 1", "heading"),
             para("The proof starts here."),
             para("It continues here.")],
        )
        self.assertEqual(
            result, ["[1] Chen, Better Systems, 2022",
                     "[2] Li, New Algorithms, 2023"],
        )

    def test_appendix_letter_heading_without_period(self):
        result = ids(
            [para("Intro"), para("Methods"), para("Results"),
             para("Conclusion"), para("One more body paragraph")],
            [para("Bibliography", "heading"),
             para("[1] Research Paper, 2019"),
             para("[2] Research Paper, 2020"),
             para("B Experimental Details", "title"),
             para("Further results follow.")],
        )
        self.assertEqual(len(result), 2)

    def test_appendix_A_on_same_page(self):
        result = ids(
            [para("Intro"), para("Methods"), para("Results")],
            [para("References", "title"),
             para("[1] Paper, 2021"), para("[2] Paper, 2022"),
             para("Appendix A", "title"),
             para("A new proof")],
        )
        self.assertEqual(len(result), 2)

    def test_proportion_fuse_disables_suspicious_large_skip(self):
        result = ids(
            [para("References", "heading"),
             para("[1] One"), para("[2] Two"),
             para("[3] Three"), para("[4] Four"),
             para("[5] Five")],
        )
        self.assertEqual(result, [])  # 5/6 > 40%, fail open.

    def test_realistic_author_year_entries_but_not_prose_years(self):
        result = ids(
            [para("Intro"), para("Main content"), para("Conclusion"),
             para("Acknowledgment")],
            [para("Bibliography", "title"),
             para("Smith, R. (2021) A paper about translation."),
             para("Jones, A. (2023) Improved algorithms."),
             para("Appendix B", "heading"),
             para("Additional data")],
        )
        self.assertEqual(len(result), 2)

    def test_no_heading_does_not_skip(self):
        self.assertEqual(ids(
            [para("Our study references other work."), para("[1] One"),
             para("[2] Two")],
        ), [])


if __name__ == "__main__":
    unittest.main()
