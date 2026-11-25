# Reference Skip (experimental)

This feature preserves bibliography entries as original PDF glyphs instead of
translating them. The **References** heading remains translatable, and content
after **Appendix**, **Supplementary Material** and similar headings is translated
again. Both normal text translation and automatic terminology extraction skip
the same entries. In-body citations (e.g., [1]) remain untouched.

## Support and compatibility

- Opt-in only. Off by default; old Server and old plugin requests stay native.
- Validated pairs: pdf2zh-next **2.9.0** / BabelDOC **0.6.4** (Python IL hooks),
  and pdf2zh-next **2.10.2** / BabelDOC **0.7.1** (native Rust layout adapter).
  Unknown pairs log a warning and use the native workflow.
- Windows standalone EXE, pdf2zh 1.x and unrelated engines continue native
  behavior, without installing hooks.
- No installed site-packages file is rewritten. Runtime hooks live only in the
  translation process and are restored in a finally block.
- Can be used together with Prettier tables. Parent and spawned/fork workers
  install the same policy order.
- The heuristic requires a standalone bibliography heading followed by at
  least two citation-like entries. Ambiguous input fails open (normal translation).
- A free-standing year such as "In 2020" is **not** citation evidence; numbered,
  DOI/arXiv or recognizable author-year records are required.
- Same-page lettered appendix headers (e.g. "A. Proof of Theorem 1") restore
  translation when BabelDOC marks them as a heading/title.
- A final **40% of valid document paragraphs** safeguard disables the skip
  entirely on suspiciously large regions; it can miss real bibliographies in
  very short papers, intentionally preferring fail-open behavior.
- Reference headings and appendix boundaries are not deleted from the source PDF.

## BabelDOC 0.7.1 adapter

The Rust pipeline no longer exposes the old Python paragraph hooks. The adapter
wraps `create_babeldoc_config` and its layout model, reads text and line bounds
from the source PDF, and applies the existing conservative bibliography detector.
It respects two-column reading order and retains native heading/caption labels
when looking for the end of the bibliography. Selected lines receive BabelDOC's
native `reference` layout label. Its paragraph finder keeps those glyphs outside
translatable paragraphs, so both translation and automatic term extraction skip
them and the native writer retains their placement. No masking/overlay is used.

The original model predictions are not mutated. RPC model character requirements
and font-mapper forwarding are preserved; hooks are restored after the job and
reinstalled in spawned workers. The adapter buffers the selected part's layout
predictions to make its document-wide safety decision. Separate split parts do
not share bibliography state. Rotated/cropped pages currently cause a warning
and native fallback for that part; OCR without a usable text layer may not detect
references. This is heuristic support, not a guarantee for every PDF.

## Tests

From the repository root (Python validation dependencies must be installed):

    PYTHONPATH=server python -m unittest discover -s server/tests -p 'test_*.py'

From plugin:

    npm test
    npm run build

**Before a release**, validate actual PDF output with Reference Skip off/on and
Prettier tables off/on, with both auto-term extraction modes, including
bibliographies followed by appendices and two-column papers. Unit tests do not
replace real engine end-to-end tests.

## Source and credit

The feature is independently implemented for Zotero PDF2zh. Its motivation
and the two-stage filtering requirement were informed by qianzhouji's public
Reference Skip discussion: https://github.com/qianzhouji/zotero-pdf2zh-patches .
No bundled modified BabelDOC installation files are used.

## Reproducible native-engine audit (#398)

Use the validated 2.10.2/0.7.1 environment and already-downloaded BabelDOC assets:

```sh
python server/tests/manual_reference_audit.py paper.pdf \
  --assets-cache /path/to/babeldoc-cache --output /tmp/reference-audit-on
```

Repeat with `--native` in a separate output directory for the off/control case,
and with `--no-terms` for automatic term extraction disabled. This script uses a
local marker translator, **not a real LLM translation**, and writes mono/dual PDFs
plus `audit.json` containing all translator and term-extractor inputs. It copies
assets into a temporary cache and does not modify the supplied PDF or user cache.
Treat the audit report as document content; do not publish confidential inputs.

On 2026-11-25, the issue's [Attention Is All You Need v7 sample](https://arxiv.org/pdf/1706.03762v7)
was exercised through the real ONNX/Rust/parser/typesetter/writer pipeline:
references begin after the conclusion on page 10, continue on pages 11–12, and
are followed by Attention Visualizations on page 13. The latter is classified as
`figure_caption` by the model, so retaining that label is necessary to stop the
skip. The adapter preserved 83 extracted text blocks; reference words on pages
10–12 matched the source, with maximum word-coordinate drift below 0.16 points
from native PDF rewriting. Output is **not byte- or pixel-identical** to the input.
Visual inspection confirmed separate entries and readable glyphs in mono and
side-by-side dual outputs; body and appendix captions still entered translation.
With the skip disabled, reference entries entered both translation and term
extraction. With the skip enabled and term extraction disabled, 83 blocks were
still preserved and zero term requests were issued. Real paid-model translation and
Zotero-host UI verification remain separate release checks.
