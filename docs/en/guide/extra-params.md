# Extra Parameters

This page documents service-specific options used by `pdf2zh_next`. Extra parameter names must match the corresponding fields in `config.toml`.

::: tip Plugin behavior
The Zotero LLM API editor stores these values in **Extra Parameters**. Some services, such as DeepSeek V4, expose validated dropdowns so you do not need to type the parameter names manually.
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
| `openai_send_temperature` / `openai_compatible_send_temperature` | Whether to send temperature | `true` |
| `openai_reasoning_effort` / `openai_compatible_reasoning_effort` | Reasoning effort for supported models | `low` |
| `openai_send_reasoning_effort` / `openai_compatible_send_reasoning_effort` | Whether to send reasoning effort | `true` |

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

When DeepSeek is selected in the plugin, the thinking mode and effort are shown as dropdowns. If thinking is disabled, the plugin does not send `deepseek_reasoning_effort`.

::: warning Version requirement
DeepSeek V4 thinking controls require `pdf2zh_next >= 2.9.0`. The updated server dependency configuration enforces this minimum version.
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
