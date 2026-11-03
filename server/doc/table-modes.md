# Table translation: current behavior

This document describes the current implementation. Earlier iteration-specific
rules and benchmark numbers are superseded by the validation section below.
See `table-translation-summary.zh-CN.md` for the Chinese review summary.

## Entry points and compatibility

The Zotero `translateTableText` checkbox remains the master switch. The new
`prettierTables` checkbox defaults to true and is disabled while the master is
off. The master switch defaults to false, so table processing is not enabled
by default. Only both boolean preferences being true sends `tableMode="fixed"`.
An unchecked option, an old dropdown/string preference, or an absent request
field keeps native behavior. The plugin checks `GET /health.tableModes` before
uploading a PDF that requests the new mode.

| Request mode | Current behavior |
| --- | --- |
| absent | Native engine path, without table policy hooks. |
| `preserve` | Retain original glyphs in detected table regions; captions stay on the normal path. Available through the API. |
| `fixed` | Text-only structural analysis, bounded translation and source-aware layout; restore source when replacement cannot fit safely. |
| `adaptive` | Reserved in the client type, not exposed in the UI and rejected by Server. |

The adapter targets the pdf2zh-next Python engine with BabelDOC **0.6.2 or 0.6.4**,
tested with pdf2zh-next **2.9.0**. Other BabelDOC versions fall back to the native
table-text path with a warning that includes the detected version. The CLI
enables `--translate-table-text` for that invocation because enhanced requests
disable the native option in their config. No private table hooks or worker
wrappers are installed on fallback, and saved preferences are unchanged.
This fallback applies to both explicit modes, including `preserve`; it uses
native behavior rather than promising to retain original table glyphs.
See `babeldoc-0.6.4-compatibility.md` for the 2026-11-02 comparison scope and limits.
Standalone Windows executables, other engines and OCR-workaround input are
explicitly unsupported. This is not complete grid/merged-cell reconstruction.

## Processing and grouping

1. Extract native table-region glyphs. Preserve rotated text as an obstacle.
2. Infer persistent gutters and conservative local cells/labels using repeated
   rows, source baselines, whitespace and actual PDF rules.
3. Send the original fragments, exact source text, stable fragment IDs, relative
   rectangles, rule segments and local merge proposals to the configured text
   LLM. The model returns structure and label policies, not translations or
   output coordinates. Document text is untrusted input, never instructions.
4. Validate IDs, unique glyph ownership, source alignment, intervening content,
   numerical values, images and real separators. Local proposals are fallible.
5. Turn verified units into native `table_text` translation paragraphs. Batch
   body text and each individual table separately while retaining native batch
   size limits, validation, trackers and fallback behavior.
6. Fit translated text into bounded envelopes and preserve the original source
   glyphs if replacement fails the constraints below.

Default grouping permits at most **1,200 fragments** and an **80,000-character
prompt**. Oversized, unavailable or malformed analysis preserves the table in
the LLM-enabled path; input is not silently truncated. Without an LLM interface,
the conservative local path remains available. Cancellation is checked around
analysis. The adapter adds no retries beyond the translator's existing transport
behavior. Empty/protected tables require no analysis request.

Verified same-column local merge candidates do not fail solely because word
spacing exceeds 1.5 font sizes. Baselines establish reading order instead of
unreliable glyph-top coordinates. Standalone numerical values remain protected;
an inline count can join a sentence only with both local and model support.

## Translation, names and source retention

- `sentence` units translate as a whole, including descriptions containing
  proper names. They are not fragmented to retain individual words.
- A `label` may supply exact `parts` with `translate` flags. Parts must cover the
  complete source and map to whole glyphs without ambiguity. Invalid policies
  use whole-unit translation; unsafe unresolved grouping retains source pieces.
- Ordinary headings, metric descriptions and technical descriptive phrases
  should translate. Actual names, identifiers, numerical values and ambiguous
  abbreviations may remain unchanged. A trailing period alone proves neither
  an abbreviation nor its meaning.
- A local metric override requires at least three distinct parenthesized codes
  in the same source column with corresponding numerical rows. It translates
  descriptive prefixes while retaining code/range suffix glyphs. A code suffix
  alone is insufficient evidence to override name protection.
- Technical identifier rosters bypass translation and reflow. Unchanged content,
  including whitespace/punctuation-only changes, uses source-glyph passthrough.
- Retained parts keep their glyph IDs, font family, geometry and line breaks.
  A translated inline part uses its source baseline/anchor and cannot push a
  retained name or wrap into a neighbouring row.
- Chinese output has a limited atomic-name guard for locally recovered labels:
  partial translation of a name core restores that core rather than mixing
  original and translated name fragments. It is not a general name recognizer.
- Word joining preserves source separators; only an explicitly printed hyphen
  between letters supports tight joining. Overprinted hyphens have a separate
  conservative cleanup path. Snapshots share native paint/clip state rather
  than recursively copying potentially very deep clipping chains.

Code/pseudocode classification is part of the same analysis call. When
`is_code=true`, source glyphs, comments, indentation and operators are retained;
only clearly separate caption IDs can translate. Ordinary tables use the normal
path. This does not provide per-cell code recognition within arbitrary tables.

## Layout constraints

| Concern | Rule |
| --- | --- |
| Horizontal alignment | Infer left/center/right from source edges and peer evidence; uncertainty defaults to the source left edge. |
| Vertical alignment | Source baselines identify rows; peers share a top anchor. Equal-source-font, multi-line peers coordinate preflight scales. |
| Wrapping | For supported Unicode runs, balance non-whitespace character counts without increasing line count; prefer longer earlier lines and preserve Latin words/punctuation. Formula-containing unsupported partitions retain native breaks. |
| Scale | Try 100% through 70% in 5% steps. No uncoordinated paragraph-space expansion. |
| Placement recovery | If the complete emitted glyph union fits the allocation, rigidly translate it back inside before rejection. Do not shrink or distort it during this step. |
| Formula metrics | Include logical advances and visual bounds; repeated alignment must not reapply formula offsets. Visible formulas count toward line alignment. |
| Final containment | Check unit and emitted glyph bounds with 0.05 pt tolerance. |
| Text obstacles | Permit shallow bounding-box intersection up to min(0.3 pt, 4% of source font size). |
| Images/rotated text | Strict protection; do not move/translate images or send image contents to the model. |
| Peer cells | Divide shared whitespace and validate the complete peer envelope, not just individual source glyphs. |

A confirmed complete sentence may span inferred columns when it owns its source
row and no actual vertical rule separates it. Glued, unclassified headers may
be split using repeated numerical column centers, nearby short header tiers and
consistent word assignments. No glyph may be split or another column center
consumed. Matching source centers across recovered tiers supply common anchors
and text envelopes. Ambiguous runs keep the source. Neither path depends on a
page number, vocabulary whitelist, italic font or document caption context.

Fallback logs identify the source fragment and failed constraint at every
attempted scale: native layout, label anchor, unit bounds, identifier word break,
image/text obstacle, rendered glyph bounds, or absent typesetting units.

## Runtime isolation and module responsibilities

The optional private CLI marker is resolved after selecting the actual engine
interpreter and DeepSeek runtime flags. `table_runner.py` loads the installed
console entry point. `table_process.py` installs/restores hooks in spawned
workers, handles inherited fork hooks, and supports debug/in-process execution.
Installed packages are never edited. Legacy requests install no table hooks.
The native legacy table OCR parser is disabled for explicit table modes.

| Modules | Responsibility |
| --- | --- |
| `table_mode`, plugin `pdf2zhTableMode` | Preference/request validation, capability negotiation and compatibility. |
| `table_runner`, `table_process`, `table_runtime` | CLI/worker lifecycle, extraction, translation integration and bounded fitting. |
| `table_batching` | Keep body and separate tables out of the same native batch. |
| `table_structure`, `table_columns`, `table_semantics` | Source recovery, local candidates, semantic validation and retention policies. |
| `table_labels`, `table_code`, `table_images` | Partial-label ownership, code preservation and obstacles. |
| `table_layout`, `table_geometry` | Alignment, wrapping, formula metrics, containment and supported header recovery. |
| `table_characters` | Internal experimental glyph-range grouping; not the default/UI path. |

The glyph experiment uses `install_table_policy("fixed", character_grouping=True)`
and exact quoted ranges. Its limits are 16,000 characters and a 650,000-character
prompt. Missing/conflicting/unsafe selections retain source. It is not a claim
that general cell recognition is solved.

## Verification snapshot — 2026-10-22

The results below record the 2026-10-22 validation session; they are not a
fresh test run for each subsequent commit. The documentation review on
2026-10-29 did not rerun tests, builds or PDF visual validation. Reproduce the
relevant checks in the target environment before treating them as current PR
validation. The optional CLI integration test was skipped in the recorded run.

- Table suite: **127 tests; 126 passed, 1 optional CLI integration test skipped**.
- Plugin: **7 tests passed**; TypeScript check and packaged build passed; ESLint
  and Prettier for changed source files passed.
- Full Server suite on Windows: **140 tests; 139 passed, 1 skipped**.
  The managed-environment tests now mock both PTY and inherited-console paths;
  the two earlier Windows test errors are resolved. A new malformed-command
  regression verifies clear validation errors instead of `IndexError`.
- Black checks all 29 table source/test/fixture files; Ruff basic checks
  (`E4,E7,E9,F`) pass. The 14-module table dependency graph has no cycles and
  no top-level engine imports.
- Whole-plugin Prettier only flags the local, Git-ignored `plugin/ast.json`.
  It is not part of the proposed submission.
- User-provided PDF pack: **23 pages, 35 tables, 507 layout units**, including
  438 units with translated fonts and 79 multi-line units.
- All pages rendered with Poppler and inspected as full-page images; selected
  tables inspected enlarged. Automatic checks found zero overflow, horizontal
  alignment, inter-cell collision or substantial adjacent mixed-font collision
  flags. **6,170 standalone numerical glyphs** retained their positions.
- Final full-document layout replay used saved responses. Four table analyses
  on pages 4 and 17 were separately refreshed with the current prompt. This is
  not a fresh-model end-to-end run of every table, nor a full semantic proofread.
- Four layout fallbacks remain: three EPIC Kitchens Seen/Unseen labels on page
  1 and `(ours)` on page 2. Other source English can be an intentional name,
  abbreviation, formula or model retention decision.
- The mixed `Parallel-Jaw Video` source fragment still lacks sufficient numeric
  row evidence for the guarded splitter. No full merged-cell reconstruction,
  adaptive resizing or raster-text translation is provided.
- Body characters/fonts/positions outside table regions match the source.
  Pages 1 and 16 have local pixel differences; whole-page pixel identity is not
  claimed. This is one PDF pack plus structural counterexamples, not a broad
  independent benchmark.

Local visual artifacts live under `output/pdf/table-layout-general-validation/`
and are not proposed repository contents. The two helper scripts under
`server/tests/fixtures/` are source fixtures, not the uploaded literature PDFs.

## Reproduction

From `server`, using the tested engine environment:

```powershell
python -m unittest discover -s tests -p 'test_table_*.py'
python -m unittest discover -s tests
```

From `plugin`:

```powershell
npm test
npm run build
npx eslint .
```

The compact server suite contains 10 tests covering source preservation, cell
boundaries, model-response fallback, table switches, child-process installation,
version fallback, engine layout, and environment isolation. The two real-engine
checks require a supported BabelDOC environment; all tests avoid external API
calls. The fixture-dependent CLI/Flask end-to-end test has been removed.

The build's update notifier initially hit the sandbox's user-cache restriction;
rerunning with `LOCALAPPDATA` temporarily redirected to a workspace cache passed.
No dependency or application source was changed for that workaround.
