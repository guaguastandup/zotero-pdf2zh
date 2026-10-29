"""Optional checks against real BabelDOC IL objects; no model or API calls."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from utils.table_runtime import install_table_policy


@unittest.skipUnless(importlib.util.find_spec("babeldoc"), "BabelDOC is not installed")
class BabelDOCTablePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from importlib.metadata import version

        if version("BabelDOC") != "0.6.2":
            raise unittest.SkipTest("These adapters target BabelDOC 0.6.2")
        # translator.cache opens a SQLite database at import time. Do not write
        # to the user's translation cache while testing the adapter.
        import babeldoc.const as constants

        cls.cache_dir = tempfile.TemporaryDirectory()
        previous = constants.CACHE_FOLDER
        constants.CACHE_FOLDER = Path(cls.cache_dir.name)
        try:
            from babeldoc.translator import cache

            cls.cache = cache
        finally:
            constants.CACHE_FOLDER = previous
        from babeldoc.format.pdf.document_il import il_version_1 as il
        from babeldoc.format.pdf.document_il.midend.paragraph_finder import (
            ParagraphFinder,
        )
        from babeldoc.format.pdf.document_il.midend.typesetting import Typesetting

        cls.finder_class, cls.typesetter_class, cls.il = (
            ParagraphFinder,
            Typesetting,
            il,
        )

    @classmethod
    def tearDownClass(cls):
        cls.cache.db.close()
        cls.cache_dir.cleanup()

    def char(self, text, x=10, y=10):
        il = self.il
        return il.PdfCharacter(
            box=il.Box(x, y, x + 4, y + 8),
            visual_bbox=il.VisualBbox(box=il.Box(x, y, x + 4, y + 8)),
            pdf_style=il.PdfStyle(font_id="f1", font_size=10),
            char_unicode=text,
            vertical=False,
            xobj_id=-1,
        )

    def test_formula_measurement_and_repeated_alignment_preserve_glyph_offsets(self):
        from babeldoc.format.pdf.document_il.midend.typesetting import TypesettingUnit
        from utils.table_layout import measure_formula_units, move_positioned_unit

        char = self.char("5")
        char.visual_bbox.box = self.il.Box(11, 11, 12, 17)
        formula = self.il.PdfFormula(
            box=self.il.Box(11, 11, 12, 17),
            pdf_character=[char],
            x_offset=0.7,
            y_offset=1.4,
            x_advance=0,
        )
        unit = measure_formula_units([TypesettingUnit(formular=formula)])[0]
        self.assertEqual(unit.width, 4)
        placed = unit.relocate(30, 40, 0.9)
        glyph = placed.render()[0][0]
        old = (glyph.box.x, glyph.box.y, glyph.box.x2, glyph.box.y2)
        moved = move_positioned_unit(placed, placed.box.x + 7, placed.box.y)
        actual = moved.render()[0][0].box
        for a, b in zip(
            (actual.x, actual.y, actual.x2, actual.y2),
            (old[0] + 7, old[1], old[2] + 7, old[3]),
        ):
            self.assertAlmostEqual(a, b)
        self.assertGreaterEqual(moved.box.x2, actual.x2)

    def test_rigid_containment_corrects_placement_but_does_not_shrink(self):
        from babeldoc.format.pdf.document_il.midend.typesetting import TypesettingUnit
        from utils.table_layout import contain_cell_layout

        unit = TypesettingUnit(char=self.char("A", x=25, y=20))
        moved = contain_cell_layout([unit], self.il.Box(10, 10, 20, 30))[0]
        self.assertAlmostEqual(moved.box.x2, 20)
        self.assertAlmostEqual(moved.width, unit.width)
        self.assertIs(contain_cell_layout([unit], self.il.Box(10, 10, 12, 30))[0], unit)

    def test_center_alignment_includes_visible_formula_at_line_end(self):
        from babeldoc.format.pdf.document_il.midend.typesetting import TypesettingUnit
        from utils.table_layout import align_lines, measure_formula_units

        char = self.char("A", x=10, y=10)
        digit = self.char("5", x=20, y=10)
        formula = self.il.PdfFormula(
            box=digit.box, pdf_character=[digit], x_offset=0, y_offset=0, x_advance=0
        )
        units = measure_formula_units(
            [TypesettingUnit(char=char), TypesettingUnit(formular=formula)]
        )
        moved = align_lines([(10, units)], self.il.Box(0, 0, 40, 30))
        self.assertAlmostEqual(
            (min(u.box.x for u in moved) + max(u.box.x2 for u in moved)) / 2, 20
        )

    def page(self, chars):
        return self.il.Page(
            page_number=0,
            pdf_character=chars,
            page_layout=[
                self.il.PageLayout(
                    id=1, class_name="table", box=self.il.Box(0, 0, 100, 100)
                )
            ],
        )

    def finder(self):
        finder = object.__new__(self.finder_class)
        finder.translation_config = SimpleNamespace(ocr_workaround=False)
        return finder

    def test_fixed_paragraph_has_native_table_label_and_region_id(self):
        page = self.page([self.char("Dataset")])
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                self.finder().process_page(page)
                self.assertEqual(page.pdf_paragraph[0].layout_label, "table_text")
                self.assertEqual(page.pdf_paragraph[0].layout_id, 1)
            finally:
                restore()

    def test_character_trial_keeps_wrapped_peer_headers_separate(self):
        import json
        from utils.table_images import overlaps, rect

        glyphs = [
            self.char(c, x + i * 4, y)
            for text, x, y in [
                ("Goal", 10, 70),
                ("Action", 54, 70),
                ("Completion", 10, 60),
                ("Completion", 54, 60),
            ]
            for i, c in enumerate(text)
        ]
        page = self.page(glyphs.copy())
        response = {
            "is_code": False,
            "cells": [
                {
                    "ranges": [[0, 3], [10, 19]],
                    "source_text": "Goal Completion",
                    "kind": "sentence",
                },
                {
                    "ranges": [[4, 9], [20, 29]],
                    "source_text": "Action Completion",
                    "kind": "sentence",
                },
            ],
        }
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed", character_grouping=True)
            try:
                finder = self.finder()
                finder.translation_config.translator = SimpleNamespace(
                    llm_translate=lambda prompt: json.dumps(response)
                )
                finder.process_page(page)
                self.assertEqual(
                    [p.unicode for p in page.pdf_paragraph],
                    ["Goal Completion", "Action Completion"],
                )
                self.assertFalse(overlaps(*(rect(p.box) for p in page.pdf_paragraph)))
            finally:
                restore()

    def test_rotated_glyphs_are_retained_while_horizontal_header_translates(self):
        import json

        rotated = self.char("Group", 10, 20)
        rotated.vertical = True
        header = self.char("Quality", 30, 70)
        page = self.page([rotated, header])
        requests = []

        def analyze(prompt):
            requests.append(prompt)
            return '{"is_code":false,"merge_groups":[]}'

        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                finder = self.finder()
                finder.translation_config.translator = SimpleNamespace(
                    llm_translate=analyze
                )
                finder.process_page(page)
                self.assertEqual(page.pdf_character, [rotated])
                self.assertEqual([p.unicode for p in page.pdf_paragraph], ["Quality"])
                payload = json.loads(requests[0].split("## Table grouping input:\n")[1])
                self.assertEqual([f["text"] for f in payload["fragments"]], ["Quality"])
                self.assertEqual(len(payload["retained_text_obstacles"]), 1)
            finally:
                restore()

    def test_figure_detection_does_not_skip_table_and_real_image_overlay_is_kept(self):
        chars = [self.char("Title", 10, 70), self.char("Overlay", 10, 20)]
        page = self.page(chars.copy())
        page.page_layout.append(
            self.il.PageLayout(
                id=2, class_name="figure", box=self.il.Box(0, 0, 100, 100)
            )
        )
        image = self.il.PdfForm(form_type="image", box=self.il.Box(5, 15, 30, 35))
        page.pdf_form.append(image)
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                self.finder().process_page(page)
                self.assertEqual([p.unicode for p in page.pdf_paragraph], ["Title"])
                self.assertEqual(page.pdf_character, [chars[1]])
                self.assertIs(page.pdf_form[0], image)
            finally:
                restore()

    def test_centered_qualifier_expansion_cannot_cross_image(self):
        import json

        chars = [self.char(c, 20 + i * 4, 70) for i, c in enumerate("Example")]
        chars += [self.char(c, 22 + i * 4, 56) for i, c in enumerate("(Seen)")]
        page = self.page(chars.copy())
        page.pdf_form.append(
            self.il.PdfForm(form_type="image", box=self.il.Box(10, 54, 22, 65))
        )
        response = {
            "is_code": False,
            "merge_groups": [[0, 1]],
            "units": [
                {
                    "ids": [0, 1],
                    "kind": "label",
                    "parts": [
                        {"text": "Example", "translate": False},
                        {"text": " (Seen)", "translate": True},
                    ],
                }
            ],
        }

        def grouped(units, region, curves, textfn, translator, policies, **kwargs):
            # Bypass the earlier merge guard to exercise the final expansion
            # guard independently, even if a future grouping path changes.
            merged = [run for unit in units for run in unit]
            policies[frozenset(id(c) for run in merged for c in run)] = response[
                "units"
            ][0]["parts"]
            kwargs["status"]["success"] = True
            return [merged]

        with patch.object(
            self.finder_class, "process_page", lambda finder, p: None
        ), patch("utils.table_runtime.group_table_semantics", grouped):
            restore = install_table_policy("fixed")
            try:
                finder = self.finder()
                finder.translation_config.translator = SimpleNamespace(
                    llm_translate=lambda prompt: json.dumps(response)
                )
                finder.process_page(page)
                self.assertEqual(page.pdf_paragraph, [])
                self.assertCountEqual(
                    [id(c) for c in page.pdf_character], [id(c) for c in chars]
                )
            finally:
                restore()

    def test_semantic_header_is_one_translation_unit_without_name_rewrite(self):
        import json

        from babeldoc.format.pdf.document_il.midend.il_translator import ILTranslator

        page = self.page([self.char("Task-level", 10, 70), self.char("SR (%)", 10, 56)])
        requests = []

        def grouping(prompt):
            requests.append(prompt)
            return json.dumps(
                {
                    "is_code": False,
                    "merge_groups": [[0, 1]],
                    "units": [{"ids": [0, 1], "kind": "sentence"}],
                }
            )

        with (
            patch.object(self.finder_class, "process_page", lambda finder, p: None),
            patch.object(
                ILTranslator,
                "post_translate_paragraph",
                lambda self, paragraph, tracker, prepared, text: text,
            ),
        ):
            restore = install_table_policy("fixed")
            try:
                finder = self.finder()
                finder.translation_config.translator = SimpleNamespace(
                    llm_translate=grouping
                )
                finder.process_page(page)
                self.assertEqual(len(requests), 1)
                self.assertEqual(len(page.pdf_paragraph), 1)
                paragraph = page.pdf_paragraph[0]
                self.assertEqual(paragraph.unicode, "Task-level SR (%)")
                self.assertEqual(len(paragraph.pdf_paragraph_composition), 2)
                translator = object.__new__(ILTranslator)
                translator.translation_config = SimpleNamespace(lang_out="zh-CN")
                # A normal header may retain the metric abbreviation. Only
                # previously recovered name labels have atomic-name protection.
                self.assertEqual(
                    translator.post_translate_paragraph(
                        paragraph, None, None, "任务级 SR (%)"
                    ),
                    "任务级 SR (%)",
                )
            finally:
                restore()

    def test_preserve_mode_does_not_request_semantic_grouping(self):
        from unittest.mock import Mock

        page = self.page([self.char("Human", 10, 70), self.char("2Robot", 10, 56)])
        grouping = Mock(side_effect=AssertionError("must not call"))
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("preserve")
            try:
                finder = self.finder()
                finder.translation_config.translator = SimpleNamespace(
                    llm_translate=grouping
                )
                finder.process_page(page)
                grouping.assert_not_called()
                self.assertEqual(len(page.pdf_character), 2)
            finally:
                restore()

    def test_code_glyphs_bypass_cleaning_and_only_caption_is_translated(self):
        import json

        from utils.table_semantics import INPUT_MARKER

        chars = [self.char("Training", 10, 80)]
        chars += [self.char(c, 10 + i * 4, 50) for i, c in enumerate("x = x - loss")]
        page = self.page(chars.copy())
        requests = []

        def grouping(prompt):
            requests.append(prompt)
            fragments = json.loads(prompt.split(INPUT_MARKER)[1])["fragments"]
            return json.dumps(
                {
                    "is_code": True,
                    "merge_groups": [],
                    "caption_ids": [
                        f["id"] for f in fragments if f["text"] == "Training"
                    ],
                }
            )

        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                finder = self.finder()
                finder.translation_config.translator = SimpleNamespace(
                    llm_translate=grouping
                )
                finder.process_page(page)
                self.assertEqual(len(requests), 1)
                self.assertEqual([p.unicode for p in page.pdf_paragraph], ["Training"])
                self.assertEqual(
                    {id(c) for c in page.pdf_character}, {id(c) for c in chars[1:]}
                )
            finally:
                restore()

    def test_label_keeps_original_name_glyphs_and_only_translates_qualifier(self):
        import json

        for single_line, qualifier in [(False, "Seen"), (True, "Seen"), (True, "SEEN")]:
            with self.subTest(single_line=single_line, qualifier=qualifier):
                if single_line:
                    text = f"EPIC Kitchens ({qualifier})"
                    chars = [self.char(c, 5 + i * 4, 70) for i, c in enumerate(text)]
                    merge, ids = [], [0]
                else:
                    chars = [
                        self.char(c, x + i * 4, y)
                        for text, x, y in [
                            ("EPIC", 30, 70),
                            ("Kitchens", 22, 56),
                            (f"({qualifier})", 26, 42),
                        ]
                        for i, c in enumerate(text)
                    ]
                    merge, ids = [[0, 1, 2]], [0, 1, 2]
                page = self.page(chars)
                original = [
                    (c, c.box.x, c.box.y, c.pdf_style.font_id, c.pdf_style.font_size)
                    for c in chars
                ]
                response = {
                    "is_code": False,
                    "merge_groups": merge,
                    "units": [
                        {
                            "ids": ids,
                            "kind": "label",
                            "parts": [
                                {"text": "EPIC Kitchens", "translate": False},
                                {"text": f" ({qualifier})", "translate": True},
                            ],
                        }
                    ],
                }
                with patch.object(
                    self.finder_class, "process_page", lambda finder, p: None
                ):
                    restore = install_table_policy("fixed")
                    try:
                        finder = self.finder()
                        finder.translation_config.translator = SimpleNamespace(
                            llm_translate=lambda prompt, response=response: json.dumps(
                                response
                            )
                        )
                        finder.process_page(page)
                        self.assertEqual(
                            [p.unicode for p in page.pdf_paragraph], [f"({qualifier})"]
                        )
                        self.assertEqual(
                            "".join(c.char_unicode for c in page.pdf_character).strip(),
                            "EPIC Kitchens" if single_line else "EPICKitchens",
                        )
                        for c, x, y, font, size in original:
                            if c in page.pdf_character:
                                self.assertEqual(
                                    (
                                        c.box.x,
                                        c.box.y,
                                        c.pdf_style.font_id,
                                        c.pdf_style.font_size,
                                    ),
                                    (x, y, font, size),
                                )
                    finally:
                        restore()

    def test_sentence_with_english_name_stays_whole(self):
        import json

        text = "We evaluate Mitty on EPIC."
        page = self.page([self.char(c, 1 + i * 3, 50) for i, c in enumerate(text)])
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                finder = self.finder()
                finder.translation_config.translator = SimpleNamespace(
                    llm_translate=lambda prompt: json.dumps(
                        {
                            "is_code": False,
                            "merge_groups": [],
                            "units": [
                                {
                                    "ids": [0],
                                    "kind": "sentence",
                                    "parts": [{"text": text, "translate": False}],
                                }
                            ],
                        }
                    )
                )
                finder.process_page(page)
                self.assertEqual(page.pdf_character, [])
                self.assertEqual([p.unicode for p in page.pdf_paragraph], [text])
            finally:
                restore()

    def test_unchanged_translation_uses_native_original_glyph_passthrough(self):
        from babeldoc.format.pdf.document_il.midend.il_translator import ILTranslator

        chars = [self.char(c, 5 + i * 4, 50) for i, c in enumerate("Dataset")]
        page = self.page(chars)
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                self.finder().process_page(page)
                paragraph = page.pdf_paragraph[0]
                translator = object.__new__(ILTranslator)
                translator.translation_config = SimpleNamespace(lang_out="zh-CN")
                self.assertFalse(
                    translator.post_translate_paragraph(
                        paragraph, None, None, "Dataset"
                    )
                )
                typesetter = object.__new__(self.typesetter_class)
                units = typesetter.create_typesetting_units(paragraph, {})
                self.assertTrue(all(u.can_passthrough for u in units))
                self.assertEqual(
                    [
                        (u.char.char_unicode, u.char.box.x, u.char.pdf_style.font_id)
                        for u in units
                    ],
                    [(c.char_unicode, c.box.x, c.pdf_style.font_id) for c in chars],
                )
            finally:
                restore()

    def test_invalid_analysis_preserves_original_table_instead_of_word_translation(
        self,
    ):
        for response in ["invalid json", '{"is_code":false,"merge_groups":null}']:
            with self.subTest(response=response):
                chars = [
                    self.char("Description", 10, 70),
                    self.char("continued", 10, 56),
                ]
                page = self.page(chars)
                finder = self.finder()
                finder.translation_config.translator = SimpleNamespace(
                    llm_translate=lambda prompt, response=response: response
                )
                with patch.object(
                    self.finder_class, "process_page", lambda finder, p: None
                ):
                    restore = install_table_policy("fixed")
                    try:
                        finder.process_page(page)
                    finally:
                        restore()
                self.assertEqual(page.pdf_paragraph, [])
                self.assertCountEqual(
                    [id(c) for c in page.pdf_character], [id(c) for c in chars]
                )

    def test_llm_can_reject_a_local_spanning_label_candidate(self):
        import json

        chars = [self.char("Human", 10, 86), self.char("2Robot", 10, 74)]
        for y in (90, 80, 70):
            chars.append(self.char("Method", 50, y))
            chars.extend(self.char(str(x), x, y) for x in (100, 125, 150))
        page = self.page(chars)
        page.page_layout[0].box = self.il.Box(0, 55, 200, 105)
        page.pdf_curve = [
            self.il.PdfCurve(box=self.il.Box(0, y, 200, y)) for y in (60, 100)
        ]
        payloads = []

        def analyze(prompt):
            payloads.append(json.loads(prompt.split("## Table grouping input:\n")[1]))
            return '{"is_code":false,"merge_groups":[]}'

        finder = self.finder()
        finder.translation_config.translator = SimpleNamespace(llm_translate=analyze)
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                finder.process_page(page)
            finally:
                restore()
        self.assertEqual(len(payloads), 1)
        self.assertTrue(payloads[0]["merge_candidates"])
        texts = [f["text"] for f in payloads[0]["fragments"]]
        self.assertIn("Human", texts)
        self.assertIn("2Robot", texts)
        self.assertNotIn("Human 2Robot", texts)
        self.assertIn("Human", [p.unicode for p in page.pdf_paragraph])
        self.assertIn("2Robot", [p.unicode for p in page.pdf_paragraph])

    def test_spanning_label_keeps_multiple_source_lines_and_fallback_positions(self):
        from babeldoc.format.pdf.document_il.midend.il_translator import ILTranslator

        chars = [self.char("Human", 10, 86), self.char("2Robot", 10, 74)]
        for y in (90, 80, 70):
            chars.append(self.char("Method", 50, y))
            chars.extend(self.char(str(x), x, y) for x in (100, 125, 150))
        page = self.page(chars)
        page.page_layout[0].box = self.il.Box(0, 55, 200, 105)
        page.pdf_curve = [
            self.il.PdfCurve(box=self.il.Box(0, y, 200, y)) for y in (60, 100)
        ]
        with (
            patch.object(self.finder_class, "process_page", lambda finder, p: None),
            patch.object(
                ILTranslator, "post_translate_paragraph", return_value=True
            ) as post,
        ):
            restore = install_table_policy("fixed")
            try:
                self.finder().process_page(page)
                merged = next(
                    p for p in page.pdf_paragraph if p.unicode == "Human 2Robot"
                )
                self.assertEqual(len(merged.pdf_paragraph_composition), 2)
                translator = object.__new__(ILTranslator)
                for language, target, expected in [
                    ("zh-CN", "Human机器人", "Human2Robot"),
                    ("fr", "Humain2Robot", "Humain2Robot"),
                ]:
                    post.reset_mock()
                    translator.translation_config = SimpleNamespace(lang_out=language)
                    translator.post_translate_paragraph(merged, None, None, target)
                    if language == "zh-CN":
                        post.assert_not_called()
                    else:
                        post.assert_called_with(
                            translator, merged, None, None, expected
                        )
                self.assertEqual(
                    [
                        c.box.y
                        for comp in merged.pdf_paragraph_composition
                        for c in comp.pdf_line.pdf_character
                    ],
                    [86, 74],
                )
                typesetter = object.__new__(self.typesetter_class)
                typesetter._find_optimal_scale_and_layout(merged, page, [])
                self.assertEqual(
                    [
                        (c.pdf_character.char_unicode, c.pdf_character.box.y)
                        for c in merged.pdf_paragraph_composition
                    ],
                    [("Human", 86), ("2Robot", 74)],
                )
            finally:
                restore()

    def test_native_llm_batches_isolate_body_and_each_table_and_keep_real_pages(self):
        from babeldoc.format.pdf.document_il.midend.il_translator_llm_only import (
            ILTranslatorLLMOnly,
        )

        from utils.table_batching import paragraph_group

        translator = object.__new__(ILTranslatorLLMOnly)
        shared = SimpleNamespace(first_paragraph=None, recent_title_paragraph=None)
        translator.translation_config = SimpleNamespace(
            raise_if_cancelled=lambda: None,
            min_text_length=1,
            shared_context_cross_split_part=shared,
        )
        translator.shared_context_cross_split_part = shared
        translator.calc_token_count = lambda text: 1
        translator.mid = 0
        page = self.page([])
        for label, region_id, count in [
            ("text", 1, 7),
            ("table_text", 1, 8),
            ("table_text", 2, 2),
        ]:
            for index in range(count):
                page.pdf_paragraph.append(
                    self.il.PdfParagraph(
                        unicode=f"Example word {index}",
                        debug_id=f"paragraph-{len(page.pdf_paragraph)}",
                        layout_label=label,
                        layout_id=region_id,
                        pdf_paragraph_composition=[
                            self.il.PdfParagraphComposition(
                                pdf_character=self.char("E")
                            )
                        ],
                    )
                )
        original_paragraphs = page.pdf_paragraph
        tasks, trackers = [], []

        def new_tracker():
            result = object()
            trackers.append(result)
            return result

        executor = SimpleNamespace(submit=lambda *a, **kw: tasks.append((a, kw)))
        native = ILTranslatorLLMOnly.process_page
        restore = install_table_policy("fixed")
        try:
            translated_ids = set()
            translator.process_page(
                page,
                executor,
                tracker=SimpleNamespace(new_paragraph=new_tracker),
                translated_ids=translated_ids,
            )
        finally:
            restore()
        self.assertIs(ILTranslatorLLMOnly.process_page, native)
        self.assertIs(page.pdf_paragraph, original_paragraphs)
        self.assertEqual(len(translated_ids), 17)
        self.assertEqual([len(a[1].paragraphs) for a, _ in tasks], [6, 1, 6, 2, 2])
        self.assertEqual([kw["mp_id"] for _, kw in tasks], [1, 2, 3, 4, 5])
        self.assertEqual(
            [tracker for a, _ in tasks for tracker in a[1].trackers], trackers
        )
        for args, _ in tasks:
            batch = args[1]
            self.assertEqual(len({paragraph_group(p) for p in batch.paragraphs}), 1)
            self.assertTrue(all(p is page for p in batch.pages))
        # Asynchronous fallback annotations must survive on the real page.
        tasks[-1][0][1].pages[0].pdf_paragraph.append(self.il.PdfParagraph())
        self.assertEqual(len(page.pdf_paragraph), 18)

    def test_preserve_never_passes_table_characters_to_native_paragraph_extraction(
        self,
    ):
        table_char, body_char = self.char("T"), self.char("B", x=120)
        page = self.page([table_char, body_char])
        seen = []
        with patch.object(
            self.finder_class,
            "process_page",
            lambda finder, p: seen.extend(p.pdf_character),
        ):
            restore = install_table_policy("preserve")
            try:
                self.finder().process_page(page)
            finally:
                restore()
        self.assertEqual(seen, [body_char])
        self.assertEqual(page.pdf_character, [body_char, table_char])

    def test_fixed_falls_back_to_original_glyphs_when_translation_cannot_fit(self):
        original = self.char("Dataset")
        page = self.page([original])
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                self.finder().process_page(page)
                paragraph = page.pdf_paragraph[0]
                source_box = paragraph.box
                typesetter = object.__new__(self.typesetter_class)
                with patch.object(
                    self.typesetter_class,
                    "_layout_typesetting_units",
                    return_value=([], False),
                ):
                    scale, units = typesetter._find_optimal_scale_and_layout(
                        paragraph, page, []
                    )
                self.assertEqual(paragraph.box, source_box)
                self.assertEqual(paragraph.unicode, "Dataset")
                self.assertEqual(
                    paragraph.pdf_paragraph_composition[0].pdf_character, original
                )
                from babeldoc.format.pdf.document_il.backend.pdf_creater import (
                    PDFCreater,
                )

                creator = object.__new__(PDFCreater)
                self.assertEqual(
                    creator.render_paragraph_to_char(paragraph), [original]
                )
                self.assertEqual(scale, 1)
                self.assertIsNone(units)
            finally:
                restore()

    def test_fixed_layout_never_uses_native_space_expansion(self):
        page = self.page([self.char("Dataset")])
        with (
            patch.object(self.finder_class, "process_page", lambda finder, p: None),
            patch.object(
                self.typesetter_class,
                "_find_optimal_scale_and_layout",
                side_effect=AssertionError("expanded"),
            ),
        ):
            restore = install_table_policy("fixed")
            try:
                self.finder().process_page(page)
                paragraph = page.pdf_paragraph[0]
                unit = SimpleNamespace(
                    box=paragraph.box,
                    render=lambda: ([self.char("译")], [], []),
                )
                with patch.object(
                    self.typesetter_class,
                    "_layout_typesetting_units",
                    return_value=([unit], True),
                ):
                    typesetter = object.__new__(self.typesetter_class)
                    _, units = typesetter._find_optimal_scale_and_layout(
                        paragraph, page, [unit]
                    )
                self.assertEqual(units, [unit])
                self.assertEqual(
                    paragraph.pdf_paragraph_composition[0].pdf_character.char_unicode,
                    "译",
                )

            finally:
                restore()

    def test_balanced_cell_layout_with_real_chinese_font(self):
        import pymupdf
        from babeldoc.format.pdf.document_il.midend.typesetting import TypesettingUnit
        from utils.table_layout import balanced_cell_layout, text_lines

        font = pymupdf.Font("china-s")
        typesetter = object.__new__(self.typesetter_class)
        typesetter.font_mapper = SimpleNamespace(base_font=font)
        # Native greedy wrapping gives 7/7/2. Balanced wrapping should be 6/5/5.
        text = "每段文字属于单元格换行后居中对齐"
        for scale in (1.0, 0.75):
            box = self.il.Box(10, 10, 10 + 71 * scale, 60)
            paragraph = self.il.PdfParagraph(box=box, first_line_indent=False)
            units = [
                TypesettingUnit(
                    unicode=c,
                    font=font,
                    font_size=10,
                    xobj_id=-1,
                    style=self.il.PdfStyle(font_id="f1", font_size=10),
                )
                for c in text
            ]

            def layout(line, bounds):
                return typesetter._layout_typesetting_units(
                    line, bounds, scale, 1.0, paragraph, True
                )

            native, fits = layout(units, box)
            self.assertTrue(fits)
            result = balanced_cell_layout(units, native, box, scale, layout)
            lines = text_lines(result)
            self.assertEqual([len(line) for _, line in lines], [6, 5, 5])
            self.assertEqual("".join(u.try_get_unicode() for u in result), text)
            self.assertEqual([y for y, _ in lines], [y for y, _ in text_lines(native)])
            for _, line in lines:
                self.assertAlmostEqual(
                    (line[0].box.x + line[-1].box.x2) / 2, (box.x + box.x2) / 2
                )
                self.assertTrue(
                    all(
                        box.x <= u.box.x
                        and u.box.x2 <= box.x2
                        and box.y <= u.box.y
                        and u.box.y2 <= box.y2
                        for u in line
                    )
                )

        text = "表格 table layout，对齐保持稳定。"
        box = self.il.Box(10, 0, 91, 100)
        paragraph = self.il.PdfParagraph(box=box, first_line_indent=False)
        units = [
            TypesettingUnit(
                unicode=c,
                font=font,
                font_size=10,
                xobj_id=-1,
                style=self.il.PdfStyle(font_id="f1", font_size=10),
            )
            for c in text
        ]

        def layout(line, bounds):
            return typesetter._layout_typesetting_units(
                line, bounds, 1.0, 1.0, paragraph, True
            )

        native, fits = layout(units, box)
        self.assertTrue(fits)
        result = balanced_cell_layout(units, native, box, 1.0, layout)
        strings = [
            "".join(u.try_get_unicode() for u in line) for _, line in text_lines(result)
        ]
        for word in ("table", "layout"):
            self.assertTrue(any(word in line for line in strings), strings)
        self.assertTrue(all(not s.startswith(("，", "。")) for s in strings))
        self.assertEqual("".join(strings).replace(" ", ""), text.replace(" ", ""))

        # 17/16 would put a comma at the start of the final line. Prefer 18/15
        # over the more even 16/17, so that the last line stays shorter.
        text = "评估机器人存在、人类缺席、具身类别、末端执行器子类型以及时间结构。"
        box = self.il.Box(10, 0, 195, 100)
        paragraph = self.il.PdfParagraph(box=box, first_line_indent=False)
        units = [
            TypesettingUnit(
                unicode=c,
                font=font,
                font_size=10,
                xobj_id=-1,
                style=self.il.PdfStyle(font_id="f1", font_size=10),
            )
            for c in text
        ]
        native, fits = layout(units, box)
        self.assertTrue(fits)
        result = balanced_cell_layout(units, native, box, 1.0, layout)
        self.assertEqual([len(line) for _, line in text_lines(result)], [18, 15])
        for alignment in ("left", "right"):
            aligned = balanced_cell_layout(
                units, native, box, 1.0, layout, alignment=alignment
            )
            for _, line in text_lines(aligned):
                edge = line[0].box.x if alignment == "left" else line[-1].box.x2
                self.assertAlmostEqual(edge, box.x if alignment == "left" else box.x2)

    def test_mixed_glyph_heights_do_not_create_false_centered_lines(self):
        from babeldoc.format.pdf.document_il.midend.typesetting import TypesettingUnit
        from utils.table_layout import balanced_cell_layout, text_lines

        # Native formula/glyph boxes sit slightly above the text baseline.
        # Their horizontal progression still identifies a single physical line.
        units = [
            TypesettingUnit(char=self.char(c, x, y))
            for c, x, y in [
                ("核", 10, 20),
                ("95", 14, 20.6),
                ("%", 18, 20),
                ("CI", 22, 20.4),
            ]
        ]
        for unit in units:
            unit.y = None
            unit.scale = 1.0
        self.assertEqual(len(text_lines(units)), 1)
        result = balanced_cell_layout(
            units,
            units,
            self.il.Box(0, 0, 100, 40),
            1.0,
            lambda *args: self.fail("reflowed raw glyphs"),
        )
        self.assertIs(result, units)

        second = [
            TypesettingUnit(char=self.char(c, x, y))
            for c, x, y in [("次", 10, 8), ("2", 14, 8.6)]
        ]
        for unit in second:
            unit.y = None
            unit.scale = 1.0
        result = balanced_cell_layout(
            units + second,
            units + second,
            self.il.Box(0, 0, 100, 40),
            1.0,
            lambda *args: self.fail("reflowed raw glyphs"),
        )
        self.assertEqual(len(text_lines(result)), 2)
        self.assertEqual([u.box.y for u in result], [u.box.y for u in units + second])
        for _, line in text_lines(result):
            self.assertAlmostEqual((line[0].box.x + line[-1].box.x2) / 2, 50)

    def test_identifier_roster_bypasses_translation_and_layout(self):
        text = "Allegro, Revo2, DexHand021, Leap, Orca"
        chars = [self.char(c, 10 + i * 4, 70) for i, c in enumerate(text)]
        page = self.page(chars.copy())
        page.page_layout[0].box.x2 = 200
        before = [(id(c), c.box.x, c.box.y, c.pdf_style.font_id) for c in chars]
        with patch.object(self.finder_class, "process_page", lambda finder, p: None):
            restore = install_table_policy("fixed")
            try:
                self.finder().process_page(page)
                self.assertEqual(page.pdf_paragraph, [])
                self.assertEqual(
                    [
                        (id(c), c.box.x, c.box.y, c.pdf_style.font_id)
                        for c in page.pdf_character
                    ],
                    before,
                )
            finally:
                restore()


if __name__ == "__main__":
    unittest.main()
