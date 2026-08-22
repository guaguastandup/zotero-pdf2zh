# Extra Parameters

This page describes Zotero PDF2zh **v4.1.1** (including v4.1.0 features).

This page documents service-specific options used by `pdf2zh_next` and legacy `pdf2zh` where noted. Extra parameter names must match the corresponding configuration fields.

::: tip Plugin behavior
The Zotero LLM API editor stores values in **Extra Parameters** / `extraData`. Opening the editor lists the extra fields supported for the current service. Click **Add Parameter** to pick from that list, or type a custom key. Leave a field unset to keep the upstream default. JSON mode is not enabled by default.
:::

## OpenAI / OpenAI-compatible

### Base fields

- `openai_model` / `openai_compatible_model`
- `openai_base_url` / `openai_compatible_base_url`
- `openai_api_key` / `openai_compatible_api_key`

### Extra fields

| Parameter | Description | Example |
|---|---|---|
| `openai_timeout` / `openai_compatible_timeout` | Request timeout in seconds | `600` |
| `openai_temperature` / `openai_compatible_temperature` | Sampling temperature | `0.3` |
| `openai_send_temprature` / `openai_compatible_send_temperature` | Whether to send temperature | `true` |
| `openai_reasoning_effort` / `openai_compatible_reasoning_effort` | Reasoning effort for supported models | `low` |
| `openai_send_reasoning_effort` / `openai_compatible_send_reasoning_effort` | Whether to send reasoning effort | `true` |
| `openai_enable_json_mode` / `openai_compatible_enable_json_mode` | Enable JSON mode; off by default | `true` |

::: warning OpenAI compatibility spelling
`pdf2zh_next` intentionally keeps the historical `openai_send_temprature` spelling for the native OpenAI service. The Server automatically migrates the old `openai_send_temperature` alias used by earlier plugin releases, while `openai_compatible_send_temperature` keeps the normal spelling.
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

These values still travel through the plugin's existing `extraData` mechanism.

### How the setting is executed

`pdf2zh_next 2.9.0` added `deepseek_thinking_mode` and `deepseek_reasoning_effort`, corresponding to:

```text
deepseek_thinking_mode     -> --deepseek-thinking-mode
deepseek_reasoning_effort  -> --deepseek-reasoning-effort
```

Zotero PDF2zh v4.1.0 applies this safety flow (unchanged in v4.1.1):

1. the plugin stores the choice through `extraData`;
2. an omitted DeepSeek V4 choice is normalized to `disabled`;
3. for uv / conda / system Python, the Server checks the **installed `pdf2zh_next` distribution metadata/source in the exact Python environment that will run**, without launching the heavyweight CLI just for capability detection;
4. supported settings are converted to the official upstream CLI flags;
5. default no-thinking on an old runtime strips those fields and still translates;
6. user-enabled thinking on an unsupported runtime is stopped before any translation API call;
7. Windows standalone executables, which cannot be inspected through Python distribution metadata, use a separate executable capability check;
8. non-V4 DeepSeek models do not receive V4-only parameters.

::: warning Why not run `pdf2zh_next --help`?
`pdf2zh_next 2.9.0` may import BabelDOC/high-level modules before CLI parsing, so even help output can be a heavyweight operation on some systems. v4.1.0 uses a static capability probe for normal Python environments to avoid misclassifying a successfully installed runtime as broken simply because help startup took too long.
:::

::: warning pdf2zh_next vs. BabelDOC versions
DeepSeek V4 thinking support is provided by the **`pdf2zh_next` runtime**, not by the BabelDOC version. `pdf2zh_next 2.8.2` does not define these fields; 2.9.0 does. BabelDOC and PyMuPDF primarily affect PDF parsing and dependency compatibility.
:::

Upstream CLI examples:

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

DeepLX is configured through the legacy `pdf2zh` engine. In `pdf2zh` 1.x, the value of `DEEPLX_ACCESS_TOKEN` is optional, but the key itself must remain present. The current configuration mapping preserves this optional field.

- `DEEPLX_ENDPOINT`: custom DeepLX endpoint; enter it as Base URL.
- `DEEPLX_ACCESS_TOKEN`: optional token; leave it empty if the endpoint does not require one.

If logs show requests to `https://api.deepl.com/v2/translate`, first verify that the selected service is `deeplx` rather than `deepl`.

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
| `siliconflow_enable_json_mode` | Enable JSON mode; off by default |

## SiliconFlow Free

| Parameter | Description |
|---|---|
| `siliconflow_free_enable_json_mode` | Enable JSON mode; off by default |

## Qwen MT

| Parameter | Description |
|---|---|
| `ali_domains` | Domain/context hint used by Qwen MT |

## General Notes

- Enter boolean values as `true` or `false`.
- Leave optional values empty when you want the upstream default.
- Service APIs and accepted model-specific parameters change over time; when a parameter is rejected, compare your installed `pdf2zh_next` version with the current upstream documentation.

::: info Related documentation
- [Configuration](/en/guide/configuration)
- [Translation Environment Updates](/en/guide/package-update)
- [Translation Service FAQ](/en/guide/faq/translation-service)
:::
