"""Contracts for the opt-in glyph grouping experiment, without network calls."""

import json
import unittest
from types import SimpleNamespace as NS

from utils.table_characters import expand_ranges, group_table_characters
from utils.table_semantics import INPUT_MARKER


def box(x, y, x2, y2):
    return NS(x=x, y=y, x2=x2, y2=y2)


def chars(text, x, y):
    return [
        NS(
            char_unicode=c,
            box=box(x + 4 * i, y, x + 4 * i + 4, y + 8),
            visual_bbox=NS(box=box(x + 4 * i, y, x + 4 * i + 4, y + 8)),
            pdf_style=NS(font_size=10),
            xobj_id=0,
        )
        for i, c in enumerate(text)
    ]


class CharacterGroupingTests(unittest.TestCase):
    def test_ranges_reject_duplicates_and_out_of_bounds(self):
        self.assertEqual(expand_ranges([[0, 2], [4, 4]], 5), [0, 1, 2, 4])
        for spans in [[[0, 2], [2, 3]], [[0, 5]], [[2, 1]], [[True, 2]]]:
            with self.assertRaises(ValueError):
                expand_ranges(spans, 5)

    def group(self, glyphs, cells):
        units = [[[c]] for c in glyphs]
        policies, status = {}, {}
        prompts = []

        def analyze(prompt):
            prompts.append(prompt)
            return json.dumps({"is_code": False, "cells": cells})

        result = group_table_characters(
            units,
            box(0, 0, 150, 100),
            [],
            lambda run: "".join(c.char_unicode for c in run),
            NS(llm_translate=analyze),
            policies,
            status,
        )
        return result, status, prompts

    def test_cells_can_wrap_without_consuming_adjacent_column(self):
        glyphs = (
            chars("Parallel-Jaw", 5, 70)
            + chars("Video", 56, 70)
            + chars("Gripper", 15, 56)
        )
        cells = [
            {
                "ranges": [[0, 11], [17, 23]],
                "kind": "label",
                "source_text": "Parallel-Jaw Gripper",
            },
            {"ranges": [[12, 16]], "kind": "label", "source_text": "Video"},
        ]
        result, status, prompts = self.group(glyphs, cells)
        self.assertEqual(status["accepted_cells"], 2)
        self.assertEqual(
            [
                " ".join("".join(c.char_unicode for c in row) for row in u)
                for u in result
            ],
            ["Parallel-Jaw Gripper", "Video"],
        )
        payload = json.loads(prompts[0].split(INPUT_MARKER)[1])
        self.assertEqual(len(payload["characters"]), len(glyphs))
        self.assertTrue(all(len(row[1]) == 1 for row in payload["characters"]))

    def test_omitted_and_conflicting_ids_keep_every_original_glyph(self):
        glyphs = chars("Label", 5, 70) + chars("123", 70, 70)
        result, status, _ = self.group(
            glyphs,
            [
                {"ranges": [[0, 4]], "kind": "label"},
                {"ranges": [[0, 3]], "kind": "label"},
            ],
        )
        self.assertEqual(status["accepted_cells"], 0)
        self.assertEqual(status["preserve_ids"], list(range(len(glyphs))))
        self.assertEqual(
            [id(c) for u in result for row in u for c in row], [id(c) for c in glyphs]
        )

    def test_rectangle_cannot_enclose_unselected_cell(self):
        glyphs = chars("Left", 5, 70) + chars("Right", 60, 70) + chars("lower", 5, 56)
        _, status, _ = self.group(
            glyphs, [{"ranges": [[0, 8], [9, 13]], "kind": "label"}]
        )
        # These ranges select every glyph; a large same-line gap still proves
        # a geometrically unsafe proposal, independently of model semantics.
        self.assertEqual(status["accepted_cells"], 0)

    def test_incorrect_source_quote_cannot_translate_wrong_id_range(self):
        glyphs = chars("Label", 5, 70)
        _, status, _ = self.group(
            glyphs, [{"ranges": [[0, 4]], "source_text": "Other", "kind": "label"}]
        )
        self.assertEqual(status["accepted_cells"], 0)
