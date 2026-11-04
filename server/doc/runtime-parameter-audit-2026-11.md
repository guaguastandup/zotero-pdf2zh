# Engine parameter and backward-compatibility audit (2026-11-05)

This audit is about **released** upstream versions, not arbitrary GitHub main
commits. Do not silently switch dependencies for existing users.

## OpenAI reasoning_effort=none

- OpenAI Chat Completions accepts the JSON field reasoning_effort. The
  pdf2zh-next 2.9.0 OpenAI translator already forwards this value when
  openai_send_reasoning_effort is true. A runtime patch is NOT needed.
- The plugin exposes none, minimal, low, medium, high, xhigh and max, but model
  support is not universal. We validate explicit 'none' for the official
  OpenAI service against an evidence-based model allowlist before updating
  config.toml. Unsupported and unknown models fail closed with a Chinese
  message rather than generating a provider HTTP 400.
- **Selecting none alone does not send the parameter**: also enable the
  existing "Send reasoning effort" toggle. When that toggle is disabled the
  engine retains its historical behavior.
- For OpenAI-compatible third-party endpoints, support depends on that
  provider and cannot be inferred from OpenAI docs. No global assumption.
- Sending 'none' is not equivalent to DeepSeek's distinct
  extra_body.thinking.type='disabled'. Do not mix the protocols.

Official docs:
https://developers.openai.com/api/docs/guides/reasoning
https://developers.openai.com/api/docs/models/gpt-5.4
https://developers.openai.com/api/docs/models/gpt-5.6-sol

## PDF2ZH Next

As checked on 2026-11-05, the latest GitHub **release** is v2.9.0 and the
upstream default branch is identical to that tag. The Server specifies
pdf2zh_next>=2.9.0,<3.0.0, but individual managed environments may retain
older packages until users explicitly update them.

Known options already supported by the Server/plugin:
- language, QPS, pool size, model-specific extraData
- save/no automatic glossary extraction, font family
- native table OCR and the experimental pretty-table adapter
- ignore-cache, auto/manual OCR workaround, no mono/dual
- enhanced compatibility, skip-clean, disable-rich-text-translate
- dual translation order, alternating pages, page selection / skip last pages

Candidate options present in the upstream 2.9.0 settings but not surfaced as
dedicated plugin controls (do not change defaults without user testing):

| Setting | Intended use | Recommendation |
| --- | --- | --- |
| term_qps, term_pool_max_workers | Separate term extraction rate/concurrency | High priority after testing mixed services |
| short_line_split_factor | Paragraph short-line handling | Optional advanced setting; validate layout |
| max_pages_per_part | Split very long PDFs | Advanced setting, minimum 50 pages |
| figure_table_protection_threshold | Preserve figure/table regions | Experimental, needs visual PDFs |
| skip_formula_offset_calculation | Skip formula offset computation | Experimental, risk to formulas |
| no_merge_alternating_line_numbers | Prevent line number merging | Niche, add only with a repro |
| non_formula_line_iou_threshold | Formula/non-formula segmentation | Not a default user knob |

The official options may be passed through the upstream config.toml for
expert users when safe, but the Server writes some fields itself; do not
assume custom changes will survive a translation request.

## Legacy pdf2zh 1.x

The latest published pdf2zh version remains v1.9.11 (2025-07-11). Our
managed environment pins pdf2zh==1.9.11 and pdfminer-six==20250416; its own
published pyproject requires Python >=3.10,<3.13 and PyMuPDF<1.25.3.
The upstream repository main contains many post-tag changes, NOT a released
1.x upgrade recommendation.

Fresh unpinned pdf2zh==1.9.11 installs were observed on Linux/Windows to
fail *before CLI parsing*: tencentcloud-sdk-python-tmt 3.1.129 no longer exports
TextTranslateRequest. The managed venv config already constrains this SDK
below 3.1; this branch also enforces the bound in old custom venv configs,
checks the actual managed interpreter's import, and provides a Chinese hint.
It is a **startup dependency failure**, not a font-subsetting problem.

The legacy --skip-subset-fonts flag is valid, but the previous Server retried
EVERY CalledProcessError with that flag, even 401/429/API errors and repeated
flags. This branch now retries exactly once only on a strong font-subsetting
error signal, and prints an explicit warning about possible duplicated model
charges. Other errors retain the original exception and are not re-run.

CI can test CLI install/--help without API calls, but that cannot prove
end-to-end PDF success, fonts, services or rendering. For release testing use
a small PDF with a no-cost service or verified model cache and inspect the
dual/mono outputs on Windows/macOS/Linux separately.
