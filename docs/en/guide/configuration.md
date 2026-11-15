# Configuration

This page describes Zotero PDF2zh **v4.1.1** configuration (including v4.1.0 features).

## Plugin Settings

Open **Tools → PDF2zh Preferences** in Zotero.

### Python Server IP

- Default: `http://127.0.0.1:8890`
- If you change `server.py --port`, update the plugin URL accordingly.
- v4.1.0 binds the Server to `127.0.0.1` by default. For intentional remote deployment, start it explicitly with:

```shell
python server.py --host 0.0.0.0
```

::: warning Remote access
`0.0.0.0` exposes the Server to other devices reachable on the current network. Configure firewall rules and enable it only when remote access is intended.
:::

### Translation Engine

| Feature | pdf2zh 1.x | pdf2zh_next 2.x |
|---|---|---|
| Status | Legacy compatibility | **Recommended** |
| Config | `config.json` | `config.toml` |
| Custom fonts | Supported | Primarily upstream font-family selection |
| Dual layouts | Basic | LR side-by-side / TB alternating pages |
| OCR / table / glossary features | Fewer | More complete |
| DeepSeek V4 Thinking | N/A | Supported in 2.9.0+ |

Use **pdf2zh_next** unless you specifically depend on a legacy feature.

### Wenyi engine (first version)

An optional whole-document engine for complete, text-layer PDFs, with monolingual
and optional side-by-side bilingual output. Cropping, separate comparison actions,
skipped pages and OCR are not supported.
Your PDF2zh settings are retained when switching back.

1. Update both the plugin and Server, then select **Wenyi** as the engine.
2. Add and activate **DeepSeek** in **LLM API Configuration Management**, supplying
   a key and choosing thinking mode and reasoning effort. The model is fixed to
   `deepseek-flash`; the configured model name, API URL and other extra parameters
   are ignored. There is no fallback to the Server's key environment variable.
   Missing thinking settings mean disabled / high.
3. Start the Server normally (`python server.py`) and translate a PDF. First use
   creates a dedicated Python 3.12 environment, `zotero-wenyi-venv`, installs the latest
   stable Wenyi packages from PyPI or a selected mirror and starts a local bridge.
   No manual installation is needed; initial setup and model-resource downloads can take time.

In **Wenyi Workflow Configuration**, the **Translation style** dropdown defaults
to **Academic** (`academic`); choose **Literary** (`literary`) for literary texts.
The choice is saved in the plugin and passed to the CLI as `--prompt-genre`
before the subcommand, not written into YAML. It does not change the CLI's own
default style.

Use the checkboxes to enable or disable each stage.
Prescan, polishing and whole-document Review default to checked;
three-draft precision defaults to unchecked. Three-draft precision
generates three drafts and combines them with polishing, locking polishing on
until disabled, then restoring your saved choice. These stages increase time and
usage; disabling them saves cost at the expense of context or quality checks.
Thinking controls appear only in the shared LLM configuration.

**Align annotation/link anchors** defaults to unchecked. It controls the CLI's
annotation/link placement stage (`pipeline.annotation_alignment`), not PDF page
geometry or side-by-side layout.

Under **Default Generated File**, monolingual output defaults to checked and
bilingual output to unchecked. Select either or both; at least one edition is
required. Each edition uses the same **Automatically Open After Generation**
preference as PDF2zh. Wenyi's edition choices are saved separately from PDF2zh's
generation settings.
Enabling bilingual output unlocks **Bilingual order (left to right)**:
**Translation first** (default) puts the translation on the left, and
**Original first** puts the original on the left. Disabling bilingual output
retains the selected order for next time. This requires a Wenyi CLI that applies
`output.bilingual_order` to PDF exports; older CLIs always put the original on
the left and must be updated to use this option.

The key is injected only into the task's CLI process, not task files or the bridge.
Use a trusted Server and HTTPS for remote connections. The CLI and AGPL BabelDOC
bridge remain separate processes communicating over HTTP.
See [engine-package updates](./package-update.md#dedicated-wenyi-environment) for maintenance.

For manual management, use `--wenyi-python /path/to/environment/python` to select
the Python containing `wenyi-cli` and `wenyi-core`, and `--wenyi-bridge-url` for an
external bridge. Setting only the latter keeps the managed CLI. With
`--enable_venv=False`, the Server's Python is used unless `--wenyi-python` is set,
and the external bridge defaults to `http://127.0.0.1:8765`.
`--wenyi-timeout` defaults to 10800 seconds, excluding environment setup.
The selected Wenyi installation must provide Core's runtime bridge connection API
(`wenyi_core.pdf_bridge.connection`); an incompatible installation fails with an
update/interpreter-selection message instead of falling back to another CLI or port.

#### Checkpoints and repeated submissions

Keep the Server running until completion. After an interruption, submit the same
PDF again with the same source/target languages and data root to continue from
Core's checkpoints. Each submission has a new task ID, progress/result receipts,
configuration, logs and outputs; it does not reopen an old task in the task list.
Progress percentages describe the current stage. There is no separate resume/cancel UI.

The plugin identifies PDFs by SHA256 and passes an unchanged copy named internally
`source.pdf` to Core. Renaming a PDF does not lose its checkpoints; different bytes,
even under the same filename, never share translation state. Explicit source
languages and automatic detection have separate state; `zh-CN` and `zh` normalize
to the same target, while different target languages use Core's separate target
directories and run locks. Only complete PDFs are supported: skipped pages, OCR
and page-selection requests are rejected before execution. Workflow/model changes
do not force already completed translations to be regenerated.

The Server starts the managed bridge on a new private port as needed. Its launcher
resolves extraction and export requests to the current address without changing
the saved source hash, session ID, paragraph IDs, pages or frozen layout snapshot.
The saved `zotero-wenyi://bridge` address is a non-network identity, not a service
URL; do not invoke generated task configs directly with a standalone CLI. Without
the launcher/resolver, this address cannot be used for HTTP. Standalone Wenyi CLI
behavior is unchanged. External bridges must keep their own persistent
`WENYI_BABELDOC_STATE_DIR` across restarts. A missing or incompatible session fails
explicitly; the plugin never silently re-extracts it to replace an old paragraph mapping.

#### Data root and disposable caches

Wenyi data belongs to this plugin alone, not the Server installation directory or
Wenyi Desktop/CLI/Web projects. Set `--wenyi-data-dir` or `ZOTERO_WENYI_DATA_DIR`;
the flag takes precedence. Defaults are:

- Linux: `$XDG_DATA_HOME/zotero-pdf2zh/wenyi`, or `~/.local/share/zotero-pdf2zh/wenyi`.
- macOS: `~/Library/Application Support/zotero-pdf2zh/wenyi`.
- Windows: `%LOCALAPPDATA%\zotero-pdf2zh\wenyi`, or the profile's `AppData\Local` equivalent.

| Within the data root | Purpose and retention |
|---|---|
| `translations/` | Persistent Core checkpoints, source artifacts, terminology and locks. Retain for continued translation. |
| `bridge/sessions/` | Persistent managed-bridge source PDFs and frozen layout/session snapshots. Required for resumed export; **not a disposable cache**. Back up together with `translations/`. |
| `tasks/<task-id>/` | Uploaded PDF, internal input copy, task config, receipts, logs and output PDFs. Completed attempts may be removed manually after all using tasks stop; a new submission supplies a fresh input copy. |
| `runtime/` | Managed-bridge diagnostic log. Not translation state. |
| `cache/` | Default location for downloadable fonts, models and tokenizer resources. May be cleared while stopped; missing resources are downloaded again. |

Override the cache with `--wenyi-cache-dir` or `ZOTERO_WENYI_CACHE_DIR` (flag first).
It must not overlap checkpoints, tasks, sessions or runtime directories, or contain
the data root. Cache settings affect only the Wenyi CLI/managed bridge child
processes, not PDF2zh or Server-global cache settings. An external bridge manages
its own asset cache. The dedicated Python environment remains installation-managed
(`server/zotero-wenyi-venv/`); published attachment copies remain in the Server's
existing `server/translated/` download directory.

No automatic cleanup, migration or discovery of old `server/wenyi-tasks/`,
`server/wenyi-runtime/` or Desktop/CLI/Web data occurs. Changing data roots selects
independent state; keep the same root for continuity. Do not point the cache at a
directory containing unrelated data. Only the owner should manually remove data,
with the Server/bridge stopped and a backup if continued translation/export is needed.
These directories contain private documents and logs; do not upload them wholesale.
Do not overwrite this adaptation with an upstream Server package that does not yet support Wenyi.

## LLM API Configuration

Create or edit providers in **LLM API Configuration Management**.

| Field | Description |
|---|---|
| Service | Translation provider |
| Model | Model name |
| Base URL | API base endpoint |
| API Key | Credential |
| Extra Parameters | Service-specific `extraData` fields |

v4.1.0 can **fetch model lists** from supported providers. Fetched models are merged with built-in defaults and user history, then deduplicated. A failed fetch never removes the default list.

### Secret logging

Plugin and Server logs mask API keys, tokens, secrets and password-like fields instead of printing plaintext credentials.

## DeepSeek

v4.1.0 exposes:

- `deepseek-v4-flash`
- `deepseek-v4-pro`

Deprecated `deepseek-chat` / `deepseek-reasoner` choices are removed from the UI. Existing saved configurations are migrated as follows:

```text
deepseek-chat
→ deepseek-v4-flash + thinking=disabled

deepseek-reasoner
→ deepseek-v4-flash + thinking=enabled + effort=high
```

### Thinking Mode

The cost-conscious PDF translation default is:

```text
Thinking Mode = Disabled
```

When enabled:

```text
Reasoning Effort = high / max
```

Thinking Control requires a compatible actual `pdf2zh_next` runtime. Default no-thinking still translates on an older environment. The Server only stops before an API request when the user explicitly enables thinking and the runtime cannot honor it. See [Extra Parameters](/en/guide/extra-params) and [Translation Environment Updates](/en/guide/package-update).

## QPS and Pool Size

- **QPS** limits translation request rate.
- **Pool Size** limits concurrent workers.
- **Pool Size = 0 (recommended)** leaves `pool_max_workers` unset so `pdf2zh_next` follows its normal QPS-based behavior.

The old `pool size = qps × 10` guidance is obsolete.

## Dual PDF Layouts

### Side by Side / LR

Original and translated content share one page side by side.

With the upstream default order, this normally means:

```text
Original | Translation
```

Enabling **Translation First** reverses the order.

### Alternating Pages / TB

Original and translated pages alternate.

::: info Historical label
Older UI/docs called TB “Top & Bottom”. In the current upstream behavior it means **Alternating Pages**, not a same-page vertical layout.
:::

## PDF Post-processing

v4.1.0 tracks PDF operation state to avoid invalid repeated processing:

```text
origin
→ mono / dual(LR/TB)
→ mono-cut / dual-cut / compare / crop-compare
```

`compare` and `crop-compare` are terminal results. Repeating the same operation on a terminal file is blocked before upload.

When Crop or Crop-Compare is requested for an LR dual PDF, the Server first normalizes the layout internally and then completes the real `dual-cut` / `crop-compare` operation. The internal LR→TB conversion is no longer mistaken for the final result.

See [Translation Options](/en/guide/translation-options).

## Other pdf2zh_next Options

### Keep Only Actually Translated Pages

Useful only when a page range is active, for example together with **Skip Last Pages**.

### OCR Workaround

This primarily improves compatibility with scanned/special PDFs that already contain a text layer; it is not a complete OCR engine.

### Enhance Compatibility

Enable only when you encounter rendering or text-layer problems. The upstream compatibility path may also change ordering/layout behavior.

### Watermark-free Output

Zotero PDF2zh defaults to watermark-free output and forwards that choice to `pdf2zh_next`.

## Configuration Migration

v4.1.0 no longer overwrites user configuration from `.example` files on every startup.

The Server:

- preserves existing user values;
- preserves unknown custom fields;
- adds missing defaults;
- refreshes project-managed `venv.json` package constraints while keeping additional user packages;
- backs up an unparseable old config as `.invalid.bak`.

`config.toml.example` follows the `pdf2zh_next 2.9.0` schema while keeping Zotero PDF2zh product defaults such as DeepSeek V4, watermark-free output and `zh-CN`.

## Server Command-line Arguments

| Parameter | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8890` | Server port |
| `--enable_venv` | `True` | Managed translation environments |
| `--env_tool` | `auto` | Keep existing uv/conda; prefer uv for a fresh environment |
| `--check_update` | `True` | Check Server updates on startup |
| `--update_source` | `gitee` | Preferred `gitee` / `github`; both are tried |
| `--enable_mirror` | `True` | Optimize package download sources |
| `--enable_winexe` | `False` | Windows standalone exe mode |
| `--skip_install` | `False` | Disable automatic environment creation/repair |

Examples:

```shell
# Normal use
python server.py

# Force conda
python server.py --env_tool=conda

# Force uv
python server.py --env_tool=uv

# Prefer GitHub for Server updates (Gitee is still tried if GitHub fails)
python server.py --update_source=github

# LAN access (advanced)
python server.py --host 0.0.0.0
```

## Next Steps

- [Installation](/en/guide/installation)
- [Translation Options](/en/guide/translation-options)
- [Extra Parameters](/en/guide/extra-params)
- [Translation Environment Updates](/en/guide/package-update)
