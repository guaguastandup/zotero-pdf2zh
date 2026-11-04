# Reference Skip (experimental)

This feature preserves bibliography entries as original PDF glyphs instead of
translating them. The **References** heading remains translatable, and content
after **Appendix**, **Supplementary Material** and similar headings is translated
again. Both normal text translation and automatic terminology extraction skip
the same entries. In-body citations (e.g., [1]) remain untouched.

## Support and compatibility

- Opt-in only. Off by default; old Server and old plugin requests stay native.
- Python pdf2zh-next **2.9.0** with BabelDOC **0.6.4** is the initial supported
  environment. Unknown versions log a warning and use the native workflow.
- Windows standalone EXE, pdf2zh 1.x and unrelated engines continue native
  behavior, without installing hooks.
- No installed site-packages file is rewritten. Runtime hooks live only in the
  translation process and are restored in a finally block.
- Can be used together with Prettier tables. Parent and spawned/fork workers
  install the same policy order.
- The heuristic requires a standalone bibliography heading followed by at
  least two citation-like entries. Ambiguous input fails open (normal translation).
- Reference headings and appendix boundaries are not deleted from the source PDF.

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
