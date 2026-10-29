import unittest
from types import SimpleNamespace as NS

from utils.table_structure import (
    atomic_label_translation,
    group_table_runs,
    join_wrapped_text,
    keeps_identifier_words,
    translation_characters,
)


class TableStructureTests(unittest.TestCase):
    def test_atomic_names_allow_translated_qualifiers_but_no_partial_core(self):
        cases = [
            ("EPIC-Kitchens (Unseen)", "EPIC 厨房（未见）", "EPIC-Kitchens（未见）"),
            ("EPIC-Kitchens (Seen)", "厨房（已见）", "厨房（已见）"),
            ("EPIC-Kitchens (Seen)", "EPIC-Kitchens（已见）", "EPIC-Kitchens（已见）"),
            ("EPIC-Kitchens (Unseen)", "厨-房（未见）", "EPIC-Kitchens（未见）"),
            ("Human2Robot", "Human机器人", "Human2Robot"),
            ("Human2Robot", "人类到机器人", "人类到机器人"),
        ]
        for source, target, expected in cases:
            with self.subTest(target=target):
                self.assertEqual(atomic_label_translation(source, target), expected)

    def test_overprinted_hyphen_is_removed_only_from_input(self):
        self.fixture()
        letter = self.runs[0][0]
        letter.char_unicode = "K"
        dash = NS(char_unicode="-", visual_bbox=NS(box=NS(x=15, y=86, x2=17, y2=94)))
        self.assertEqual(translation_characters([letter, dash]), [letter])
        self.assertEqual(dash.char_unicode, "-")
        dash.visual_bbox.box.x = 31
        dash.visual_bbox.box.x2 = 33
        self.assertEqual(translation_characters([letter, dash]), [letter, dash])

    def test_recovered_words_cannot_be_split_during_layout(self):
        def unit(text, y):
            return NS(try_get_unicode=lambda: text, y=y)

        self.assertFalse(keeps_identifier_words([unit("Kitc", 10), unit("hens", 0)]))
        self.assertTrue(
            keeps_identifier_words(
                [unit("Kitchens", 10), unit(" ", 10), unit("Seen", 0)]
            )
        )
        self.assertTrue(
            keeps_identifier_words([unit("Kitchens", 10), unit("（", 0), unit("已见", 0)])
        )

    def fixture(self, labels=(("Human", 86), ("2Robot", 74))):
        def run(text, x, y, width=20):
            return [
                NS(
                    char_unicode=text,
                    box=NS(x=x, y=y, x2=x + width, y2=y + 8),
                    visual_bbox=NS(box=NS(x=x, y=y, x2=x + width, y2=y + 8)),
                    pdf_style=NS(font_size=10, font_id="f1"),
                    xobj_id=-1,
                )
            ]

        self.rule = lambda y, x=0, x2=200: NS(box=NS(x=x, y=y, x2=x2, y2=y))
        self.box = NS(x=0, y=55, x2=200, y2=105)
        self.curves = [self.rule(60), self.rule(100)]
        self.runs = [run(text, 10, y) for text, y in labels]
        for y in (90, 80, 70):
            self.runs.extend([run("Method", 50, y, 35)])
            self.runs.extend(run(str(x), x, y, 10) for x in (100, 125, 150))
        return [[r] for r in self.runs]

    def groups(self, lines, curves=None):
        return group_table_runs(
            lines,
            self.box,
            self.curves if curves is None else curves,
            lambda run: "".join(c.char_unicode for c in run),
        )

    def test_centered_spanning_label_is_one_unit_and_keeps_original_glyphs(self):
        lines = self.fixture()
        groups = self.groups(lines)
        joined = [g for g in groups if len(g) > 1]
        self.assertEqual(joined, [[self.runs[0], self.runs[1]]])
        self.assertIs(joined[0][0][0], self.runs[0][0])
        self.assertEqual(sum(len(g) for g in groups), len(self.runs))

    def test_regular_method_records_are_never_combined(self):
        lines = self.fixture((("Kling", 90), ("Mocha", 80), ("Aleph", 70)))
        self.assertTrue(all(len(g) == 1 for g in self.groups(lines)))

    def test_missing_records_do_not_make_row_aligned_labels_a_wrapped_name(self):
        lines = self.fixture((("Kling", 85), ("Mocha", 75)))
        self.assertTrue(all(len(g) == 1 for g in self.groups(lines)))

    def test_rule_through_leading_column_prevents_join(self):
        lines = self.fixture()
        for curves in [
            [],
            self.curves + [self.rule(80)],
            self.curves + [self.rule(80, 5, 35)],
        ]:
            with self.subTest(curves=curves):
                self.assertTrue(all(len(g) == 1 for g in self.groups(lines, curves)))

    def test_different_font_or_object_prevents_join(self):
        for field in ("font", "object"):
            lines = self.fixture()
            if field == "font":
                self.runs[1][0].pdf_style.font_id = "f2"
            else:
                self.runs[1][0].xobj_id = 2
            self.assertTrue(all(len(g) == 1 for g in self.groups(lines)))

    def test_off_center_or_non_aligned_labels_are_left_separate(self):
        for field in ("horizontal", "vertical"):
            lines = self.fixture()
            if field == "horizontal":
                self.runs[1][0].visual_bbox.box.x2 += 8
            else:
                self.runs[1][0].box.y -= 6
            self.assertTrue(all(len(g) == 1 for g in self.groups(lines)))

    def test_joining_is_generic_and_preserves_word_and_hyphen_boundaries(self):
        self.assertEqual(join_wrapped_text(["Human", "2Robot"]), "Human 2Robot")
        self.assertEqual(
            join_wrapped_text(["EPIC-", "Kitchens", "(Seen)"]), "EPIC-Kitchens (Seen)"
        )
        self.assertEqual(join_wrapped_text(["Human", "Preference"]), "Human Preference")

    def test_wrapping_does_not_invent_identifier_or_numeric_word_joins(self):
        for parts, expected in [
            (["There are", "2 groups"], "There are 2 groups"),
            (["Use", "3 methods"], "Use 3 methods"),
            (["25", "samples"], "25 samples"),
            (["value -", "2"], "value - 2"),
            (["co-", "author"], "co-author"),
            (["Group", "α1"], "Group α1"),
        ]:
            with self.subTest(parts=parts):
                self.assertEqual(join_wrapped_text(parts), expected)

    def test_identifier_check_supports_original_glyph_units_without_unicode_y(self):
        a = NS(try_get_unicode=lambda: "Kitc", y=None, box=NS(y=10))
        b = NS(try_get_unicode=lambda: "hens", y=None, box=NS(y=0))
        self.assertFalse(keeps_identifier_words([a, b]))
        b.box.y = 10
        self.assertTrue(keeps_identifier_words([a, b]))


if __name__ == "__main__":
    unittest.main()
