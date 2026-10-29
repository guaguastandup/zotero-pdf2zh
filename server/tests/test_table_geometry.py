import unittest
from types import SimpleNamespace as NS

from utils.table_geometry import (
    isolated_spanning_line,
    numeric_column_centers,
    split_header_run,
    header_alignment_hints,
)
from utils.table_semantics import descriptive_metric_parts


def glyphs(text, x, y):
    return [
        NS(
            char_unicode=c,
            box=NS(x=x + i * 3, y=y, x2=x + i * 3 + 3, y2=y + 8),
            visual_bbox=NS(box=NS(x=x + i * 3, y=y, x2=x + i * 3 + 3, y2=y + 8)),
            pdf_style=NS(font_size=8),
        )
        for i, c in enumerate(text)
    ]


class EvidenceGeometryTests(unittest.TestCase):
    def test_header_tiers_share_source_center_but_never_cross_a_rule(self):
        lower = [glyphs("Response", 8, 90)]
        upper = [glyphs("Key", 15.5, 100)]
        hints = header_alignment_hints([lower], [lower, upper], [], [20, 50, 80])
        self.assertEqual(hints[frozenset(id(c) for c in lower[0])], (20, 8, 32))
        rule = NS(box=NS(x=0, x2=40, y=99, y2=99))
        self.assertFalse(
            header_alignment_hints([lower], [lower, upper], [rule], [20, 50, 80])
        )

    def test_metric_retention_override_requires_repeated_codes_and_numeric_peers(self):
        from utils.table_semantics import _label_policies
        from utils.table_geometry import bounds

        def policies(texts, units):
            entries = [
                {
                    "ids": [i],
                    "kind": "label",
                    "parts": [{"text": text, "translate": False}],
                }
                for i, text in enumerate(texts)
            ]
            return _label_policies(
                entries,
                {frozenset([i]) for i in range(len(units))},
                units,
                texts,
                [bounds(u[0]) for u in units],
            )

        product = "Some Product (V2)"
        unit = [glyphs(product, 10, 90)]
        self.assertEqual(
            list(policies([product], [unit]).values())[0],
            [{"text": product, "translate": False}],
        )
        texts = [
            "Alpha score (Q1)",
            "Beta score (Q2)",
            "Gamma score (Q3)",
            "1.0",
            "2.0",
            "3.0",
        ]
        units = [
            [glyphs(text, 10 if i < 3 else 100, 90 - (i % 3) * 15)]
            for i, text in enumerate(texts)
        ]
        result = policies(texts, units)
        self.assertTrue(result[frozenset(id(c) for c in units[0][0])][0]["translate"])

    def data(self):
        return [
            [glyphs("1.0", x - 4.5, y)] for x in [20, 50, 80, 110] for y in [50, 60, 70]
        ]

    def test_glued_headers_split_only_with_repeated_numeric_and_header_evidence(self):
        header = [
            sum(
                [
                    glyphs(word, x, 90)
                    for word, x in [
                        ("Total", 13),
                        ("Mean", 44),
                        ("Rate", 74),
                        ("Score", 103),
                    ]
                ],
                [],
            )
        ]
        tier = [[glyphs("Key", x - 4.5, 100)] for x in [20, 50, 80, 110]]
        units = [header, *tier, *self.data()]
        centers = numeric_column_centers(
            units, lambda r: "".join(c.char_unicode for c in r)
        )
        self.assertEqual(centers, [20, 50, 80, 110])
        split = split_header_run(header, units, [], centers)
        self.assertEqual(
            ["".join(c.char_unicode for c in u[0]) for u in split],
            ["Total", "Mean", "Rate", "Score"],
        )
        self.assertCountEqual(
            [id(c) for u in split for c in u[0]], [id(c) for c in header[0]]
        )
        self.assertIsNone(split_header_run(header, [header, *self.data()], [], centers))

    def test_spanning_title_is_blocked_by_actual_vertical_rule_or_parallel_cell(self):
        title = [glyphs("An independent section heading", 10, 90)]
        self.assertTrue(isolated_spanning_line(title, [title, *self.data()], []))
        peer = [glyphs("Peer", 110, 90)]
        self.assertFalse(isolated_spanning_line(title, [title, peer], []))
        rule = NS(box=NS(x=35, x2=35, y=85, y2=105))
        self.assertFalse(isolated_spanning_line(title, [title], [rule]))

    def test_long_header_words_may_overhang_midpoint_without_consuming_peer_center(
        self,
    ):
        centers = [20, 55, 80, 105]
        header = [
            sum(
                [
                    glyphs(word, x, 90)
                    for word, x in [
                        ("Aggregation", 5),
                        ("Measurement", 40),
                        ("Rate", 75),
                        ("Score", 100),
                    ]
                ],
                [],
            )
        ]
        tier = [[glyphs("Key", x - 4.5, 100)] for x in centers]
        split = split_header_run(header, [header, *tier], [], centers)
        self.assertEqual(len(split), 4)
        title = [
            sum(
                [
                    glyphs(word, x, 110)
                    for word, x in [("One", 15), ("Section", 43), ("Title", 73)]
                ],
                [],
            )
        ]
        self.assertIsNone(split_header_run(title, [title, *tier], [], centers))

    def test_metric_code_does_not_freeze_description_or_mutate_source(self):
        for source in [
            "Outcome consistency (Q7)",
            "ResponseStability (Q7)",
            "Average score (0–100)",
        ]:
            parts = descriptive_metric_parts([{"text": source, "translate": False}])
            self.assertEqual("".join(p["text"] for p in parts), source)
            self.assertTrue(parts[0]["translate"])
            self.assertFalse(parts[-1]["translate"])
        for source in ["Some Product (v2)", "Robot-X7", "23.5", "XY7 (Q7)"]:
            parts = [{"text": source, "translate": False}]
            self.assertEqual(descriptive_metric_parts(parts), parts)
        source = "H5Response (0–100)"
        parts = descriptive_metric_parts([{"text": source, "translate": False}])
        self.assertEqual(
            parts,
            [
                {"text": "H5", "translate": False},
                {"text": "Response", "translate": True},
                {"text": " (0–100)", "translate": False},
            ],
        )
