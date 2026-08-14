DONE: 基础字段为 model、url、apikey，用户输入这三个字段（有些字段可以为空）。
TODO: 其他服务的额外字段仍需要根据 service 补充 key；目前用户可以自行填写 key 和 value。

## openai

**基础字段**

- openai_model
- openai_base_url
- openai_api_key

**额外字段**

- openai_temperature: Temperature for OpenAI service
- openai_reasoning_effort: Reasoning effort for OpenAI service (minimal/low/medium/high)
- openai_send_temprature: Send temperature to OpenAI service. `pdf2zh_next <= 2.9.0` intentionally keeps this historical misspelling for compatibility.
- openai_send_reasoning_effort: Send reasoning effort to OpenAI service

## deepseek

**基础字段**

- deepseek_model
- deepseek_api_key

**额外字段**

- deepseek_enable_json_mode: Enable JSON mode for DeepSeek service
- deepseek_thinking_mode: DeepSeek v4 思考模式，可选 `disabled` / `enabled`
- deepseek_reasoning_effort: DeepSeek v4 思考强度，可选 `high` / `max`，仅在 `deepseek_thinking_mode = enabled` 时生效

插件的 DeepSeek 配置界面会自动生成 `deepseek_thinking_mode` 和 `deepseek_reasoning_effort` 两个选项：

- 默认使用 `deepseek_thinking_mode = disabled`，避免翻译时产生额外的思考 token 与费用。
- 开启思考后，默认强度为 `high`，也可以选择 `max`。
- 关闭思考时，插件不会提交 `deepseek_reasoning_effort`，Server 配置中的思考模式仍会明确保持为 `disabled`。
- 显式 thinking 控制需要 `pdf2zh_next >= 2.9.0`；Server 不再为了这一可选功能强制升级已有环境。

对应的 BabelDOC CLI 参数为：

```shell
# 关闭思考（推荐作为默认配置）
uv run pdf2zh_next input.pdf \
  --deepseek \
  --deepseek-model deepseek-v4-flash \
  --deepseek-thinking-mode disabled \
  --output ./output

# 开启思考，并选择 high 强度
uv run pdf2zh_next input.pdf \
  --deepseek \
  --deepseek-model deepseek-v4-pro \
  --deepseek-thinking-mode enabled \
  --deepseek-reasoning-effort high \
  --output ./output
```

## ollama

**基础字段**

- ollama_model
- ollama_host

**额外字段**

- num_predict
  默认为2000, The max number of token to predict.

## azure-openai

**基础字段**

- azure_openai_model
- azure_openai_base_url
- azure_openai_api_key

**额外字段**

- azure_openai_api_version

## siliconflow

**基础字段**

- siliconflow_base_url
- siliconflow_model
- siliconflow_api_key

**额外字段**

- siliconflow_enable_thinking: Enable thinking for SiliconFlow service
- siliconflow_send_enable_thinking_param: Send enable thinking param for SiliconFlow service

## qwen-mt

**基础字段**

- qwenmt_model
- qwenmt_base_url
- qwenmt_api_key

**额外字段**

- ali_domains

## openailiked/openaicompatible

**基础字段**

- openai_compatible_model
- openai_compatible_base_url
- openai_compatible_api_key

**额外字段**

- openai_compatible_temperature
- openai_compatible_reasoning_effort
- openai_compatible_send_temperature
- openai_compatible_send_reasoning_effort
