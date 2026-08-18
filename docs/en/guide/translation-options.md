# Translation Options

Select a paper item or PDF attachment in Zotero, then open the **PDF2zh** context menu.

v4.1.0 tracks the current PDF operation state so already-processed files are not sent into incompatible operations again.

## PDF States

A typical flow is:

```text
origin
→ mono / dual(LR/TB)
→ mono-cut / dual-cut / compare / crop-compare
```

`compare` and `crop-compare` are terminal results. Repeating the same operation on a terminal file is blocked before upload.

## Translate PDF

**Input:** original PDF / paper item.

Generates mono, dual, and any additional outputs enabled in plugin settings.

Running Translate PDF on an already generated mono / dual / compare / crop-compare attachment is rejected. Select the original attachment when you want to translate again.

## Crop PDF

**Supported input:**

- origin
- mono
- dual

Typical output:

- `mono-cut`
- `dual-cut`

For a `pdf2zh_next` **LR dual** (side-by-side), v4.1.0 first normalizes the layout internally, then continues through the real crop operation:

```text
LR dual
→ internal LR→TB normalization
→ actual crop
→ dual-cut
```

The internal layout conversion is no longer mistaken for the final Crop result.

## Compare PDF

**Supported input:**

- origin
- dual

Output: `compare`.

When the input is an original PDF, the Server first generates the required dual PDF and then builds the compare result.

`compare` is terminal; running Compare on an existing compare result is blocked.

## Crop-Compare PDF

**Supported input:**

- origin
- dual
- dual-cut

This is intended for two-column papers: normalize/crop to a single-column structure and then generate the bilingual comparison result.

For an LR dual:

```text
LR dual
→ internal LR→TB normalization
→ actual crop-compare
→ crop-compare
```

v4.1.0 fixes the old behavior where the first Crop-Compare could stop after the LR→TB conversion while naming that intermediate file as a crop-compare result.

`crop-compare` is also terminal. The plugin and Server both reject a repeated Crop-Compare operation.

## What are LR and TB?

### LR / Side by Side

Original and translated content share one page side by side.

### TB / Alternating Pages

Original and translated pages alternate.

::: info Historical label
Older UI/docs called TB “Top & Bottom”. In current `pdf2zh_next` / BabelDOC behavior it means **Alternating Pages**, not a vertical same-page layout.
:::

## When should I return to the original PDF?

Return to the original PDF (or the original dual result) when you want to:

- change model or language;
- change Thinking settings;
- generate another layout;
- rebuild a terminal compare / crop-compare result.

Avoid repeatedly chaining post-processing operations on an already processed result.

## Batch Processing

Multiple items or attachments can be selected and processed together.

v4.1.0 fixes batch accounting: a failed file is counted in `failed` instead of being swallowed and reported as success, and the temporary batch event listener is removed after completion.

## Recommended Operation

| Goal | Recommended action |
|---|---|
| Normal translation | Translate PDF |
| Single-column/mobile reading | Crop |
| Original/translation comparison | Compare |
| Two-column paper with cropped comparison | Crop-Compare |
| Rebuild an existing terminal result | Return to original/dual and regenerate |

## Related Documentation

- [Configuration](/en/guide/configuration)
- [Installation](/en/guide/installation)
- [Translation Environment Updates](/en/guide/package-update)
