DONE: 基础字段为 model、url、apikey，用户输入这三个字段（有些字段可以为空）。
额外字段白名单与 `server/utils/config_map.py` 的 `pdf2zh_next_config_map` 保持同步，对照上游 `pdf2zh_next` `translate_engine_model.py`。
插件 LLM 编辑器会展示当前服务支持的额外字段；不填则使用上游默认值。不要默认打开 JSON mode。

## openai

**基础字段**

- openai_model
- openai_base_url
- openai_api_key

**额外字段**

- openai_timeout: Timeout (seconds) for OpenAI service
- openai_temperature: Temperature for OpenAI service
- openai_reasoning_effort: Reasoning effort for OpenAI service (minimal/low/medium/high)
- openai_enable_json_mode: Enable JSON mode for OpenAI service（默认关闭）
- openai_send_temprature: Send temperature to OpenAI service. `pdf2zh_next` intentionally keeps this historical misspelling for compatibility; the Server migrates the old `openai_send_temperature` alias automatically.
- openai_send_reasoning_effort: Send reasoning effort to OpenAI service

## deepseek

**基础字段**

- deepseek_model
- deepseek_api_key

**额外字段**

- deepseek_enable_json_mode: Enable JSON mode for DeepSeek service（默认关闭）
- deepseek_thinking_mode: DeepSeek V4 思考模式，可选 `disabled` / `enabled`
- deepseek_reasoning_effort: DeepSeek V4 思考强度，可选 `high` / `max`，仅在 `deepseek_thinking_mode = enabled` 时生效

插件的 DeepSeek 配置界面仍使用项目已有的 `extraData` 机制保存这些字段；下拉框仅负责减少手工输入和非法值。

Server 的实际执行策略：

- DeepSeek V4 没有显式 thinking 设置时，自动归一化为 `disabled`，避免依赖 provider 默认行为。
- `pdf2zh_next 2.9.0` 会从同名设置字段生成 `--deepseek-thinking-mode` / `--deepseek-reasoning-effort` CLI 参数。
- Server 在 API 调用前检查**本次实际执行的** `pdf2zh_next` / Windows exe 的 `--help`，而不是只检查某个环境中的版本字符串。
- 运行时支持时，将 extraData 中的用户选择转换成上述上游 CLI 参数后执行。
- 运行时不支持时，在翻译/API 调用前直接停止，并提示用户运行 `python update_packages.py`；不会静默忽略 thinking 设置。
- 非 V4 DeepSeek 模型不会发送这两个 V4-only 参数。
- 如果旧运行时不支持这些字段，Server 会清理共享 `config.toml` 中临时写入的 thinking 字段，避免影响其他服务。

thinking 参数是否存在由 **pdf2zh_next** 决定，不由 BabelDOC 版本决定：`pdf2zh_next 2.8.2` 没有这些字段，2.9.0 才新增；BabelDOC/PyMuPDF 的版本问题属于 PDF parser 与依赖兼容问题。

上游 `pdf2zh_next` CLI 示例：

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
- siliconflow_enable_json_mode: Enable JSON mode for SiliconFlow service（默认关闭）

## siliconflowfree

**额外字段**

- siliconflow_free_enable_json_mode: Enable JSON mode for SiliconFlow Free service（默认关闭）

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

- openai_compatible_timeout
- openai_compatible_temperature
- openai_compatible_reasoning_effort
- openai_compatible_send_temperature
- openai_compatible_send_reasoning_effort
- openai_compatible_enable_json_mode（默认关闭）

## AliyunDashScope

**基础字段**

- aliyun_dashscope_model
- aliyun_dashscope_base_url
- aliyun_dashscope_api_key

**额外字段**

- aliyun_dashscope_timeout
- aliyun_dashscope_temperature
- aliyun_dashscope_send_temperature
- aliyun_dashscope_enable_json_mode（默认关闭）

## modelscope / zhipu / gemini / grok / groq

**额外字段**

- modelscope_enable_json_mode
- zhipu_enable_json_mode
- gemini_enable_json_mode
- grok_enable_json_mode
- groq_enable_json_mode

以上 JSON mode 字段均默认关闭，由用户按需添加。
