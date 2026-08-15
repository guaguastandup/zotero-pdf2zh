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
| `deepseek_enable_json_mode` | Enable JSON mode | Depends on your BabelDOC/pdf2zh_next configuration |

These values still travel through the plugin's existing `extraData` mechanism. The dropdowns only populate and validate those generic extra fields for convenience.

When DeepSeek is selected in the plugin, the thinking mode and effort are shown as dropdowns. If thinking is disabled, the plugin does not send `deepseek_reasoning_effort`.

::: warning Version requirement
Explicit DeepSeek V4 thinking controls require `pdf2zh_next >= 2.9.0`. The server no longer forces every existing environment to upgrade solely for this optional feature. Older versions can still pass a V4 model name for ordinary translation, but they do not process the new thinking-control fields. Check the current upstream `pdf2zh_next` / BabelDOC dependency compatibility before upgrading.
:::

Equivalent CLI examples:

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
