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
