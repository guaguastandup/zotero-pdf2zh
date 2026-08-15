# Extra Parameters

This page documents service-specific options used by `pdf2zh_next` and legacy `pdf2zh` where noted. Extra parameter names must match the corresponding configuration fields.

::: tip Plugin behavior
The Zotero LLM API editor already stores arbitrary values in **Extra Parameters** / `extraData`. Some common fields, such as DeepSeek V4 thinking controls, expose validated dropdowns only to reduce manual typing and configuration errors; they still use the same `extraData` transport.
:::

## OpenAI / OpenAI-compatible

### Base fields

- `openai_model` / `openai_compatible_model`
- `openai_base_url` / `openai_compatible_base_url`
- `openai_api_key` / `openai_compatible_api_key`

### Extra fields

| Parameter | Description | Example |
|---|---|---|
| `openai_temperature` / `openai_compatible_temperature` | Sampling temperature | `0.3` |
| `openai_send_temprature` / `openai_compatible_send_temperature` | Whether to send temperature | `true` |
| `openai_reasoning_effort` / `openai_compatible_reasoning_effort` | Reasoning effort for supported models | `low` |
| `openai_send_reasoning_effort` / `openai_compatible_send_reasoning_effort` | Whether to send reasoning effort | `true` |

::: warning OpenAI compatibility spelling
`pdf2zh_next` 2.9.0 and earlier intentionally keep the historical `openai_send_temprature` spelling for the native OpenAI service. This is an upstream compatibility field, not a documentation typo. `openai_compatible_send_temperature` uses the normal spelling.
:::

## DeepSeek

DeepSeek V4 models, including `deepseek-v4-pro` and `deepseek-v4-flash`, support explicit thinking controls. Zotero PDF2zh keeps thinking **disabled by default** to avoid unexpected reasoning-token cost during PDF translation.

### Base fields

- `deepseek_model`
- `deepseek_api_key`

### Extra fields

| Parameter | Description | Values / default |
|---|---|---|
| `deepseek_thinking_mode` | Enable DeepSeek V4 thinking | `disabled` / `enabled`; default `disabled` |
| `deepseek_reasoning_effort` | Thinking effort, used only when thinking is enabled | `high` / `max`; default `high` when enabled |
| `deepseek_enable_json_mode` | Enable JSON mode | Depends on the `pdf2zh_next` configuration |

These values still travel through the plugin's existing `extraData` mechanism. The dropdowns only populate and validate those generic extra fields for convenience.

### How the setting is executed

`pdf2zh_next` 2.9.0 added `deepseek_thinking_mode` and `deepseek_reasoning_effort` to its `DeepSeekSettings`. The CLI options are generated from the same settings model:

```text
deepseek_thinking_mode     -> --deepseek-thinking-mode
deepseek_reasoning_effort  -> --deepseek-reasoning-effort
```

Zotero PDF2zh therefore applies the following safety flow:

1. The plugin stores the user's choice through `extraData`.
2. For DeepSeek V4, an omitted choice is normalized to `disabled`, so the provider's default thinking behavior is never relied upon.
3. Immediately before translation, the Server resolves the **actual `pdf2zh_next` executable or Windows exe that will run**.
4. It probes that runtime's `--help` output for both thinking CLI flags.
5. If supported, the Server converts the saved choice into the official upstream CLI options and starts translation.
6. If unsupported, the request is stopped before any translation API call and the user is told to run `python update_packages.py`; the setting is never silently ignored.
7. Non-V4 DeepSeek models never receive the V4-only thinking parameters.

If an unsupported runtime caused the Server to temporarily write the new fields into the shared `config.toml`, those fields are removed again before the error is returned so other services remain usable with the older runtime.

::: warning pdf2zh_next vs. BabelDOC versions
DeepSeek V4 thinking support is provided by the **`pdf2zh_next` runtime**, not by the BabelDOC version. `pdf2zh_next` 2.8.2 does not define these fields; 2.9.0 does. BabelDOC and PyMuPDF versions primarily affect PDF parsing and dependency compatibility, which is a separate issue.

For this reason the Server does not rely only on a version string. It directly verifies that the exact executable being launched exposes the required CLI flags. If it does not, DeepSeek V4 translation is safely blocked.
:::

Upstream `pdf2zh_next` CLI examples:

```bash
# Recommended default for PDF translation: thinking disabled
uv run pdf2zh_next input.pdf \
  --deepseek \
  --deepseek-model deepseek-v4-flash \
  --deepseek-thinking-mode disabled \
  --output ./output

# Thinking enabled with high effort
uv run pdf2zh_next input.pdf \
  --deepseek \
  --deepseek-model deepseek-v4-pro \
  --deepseek-thinking-mode enabled \
  --deepseek-reasoning-effort high \
  --output ./output
```

## DeepLX (legacy pdf2zh 1.x)

DeepLX is configured through the legacy `pdf2zh` engine. In `pdf2zh` 1.x, the value of `DEEPLX_ACCESS_TOKEN` is optional, but the key itself is indexed directly by the translator and therefore must remain present. Older Zotero PDF2zh Server logic could delete this key when the API Key field was empty, causing `KeyError: 'DEEPLX_ACCESS_TOKEN'`. The current configuration mapping preserves the optional field.

- `DEEPLX_ENDPOINT`: custom DeepLX translation endpoint; enter it as the plugin Base URL.
- `DEEPLX_ACCESS_TOKEN`: optional token; enter it as API Key or as an extra parameter. Leave it empty when the endpoint does not require a token.

Example:

```text
Service: deeplx
Base URL: https://your-deeplx.example/translate
API Key: (optional)
```

If logs show requests to `https://api.deepl.com/v2/translate`, first verify that the selected service is actually `deeplx` rather than `deepl`. They are different translators, so that symptom alone does not prove a Zotero plugin bug.

## Ollama

| Parameter | Description | Default |
|---|---|---|
| `num_predict` | Maximum number of generated tokens | `2000` |

## Azure OpenAI

| Parameter | Description |
|---|---|
| `azure_openai_api_version` | Azure OpenAI API version |

## SiliconFlow

| Parameter | Description |
|---|---|
| `siliconflow_enable_thinking` | Enable thinking when supported |
| `siliconflow_send_enable_thinking_param` | Whether to send the thinking parameter |

## Qwen MT

| Parameter | Description |
|---|---|
| `ali_domains` | Domain/context hint used by Qwen MT |

## General Notes

- Enter boolean values as `true` or `false`.
- Leave an optional value empty when you want the upstream default.
- Service APIs and accepted model-specific parameters change over time; when a parameter is rejected, compare your installed `pdf2zh_next` version with the current upstream documentation.

::: info Related documentation
- [Configuration](/en/guide/configuration)
- [Translation Service FAQ](/en/guide/faq/translation-service)
:::
