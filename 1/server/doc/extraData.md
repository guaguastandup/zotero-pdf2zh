DONE: 基础字段为model, url, apikey, 用户输入这三个字段(有些字段可以空)
TODO: 额外字段需要根据service来补充key, 用户目前可以自行填充key和value

## openai

**基础字段**

- openai_model
- openai_base_url
- openai_api_key

**额外字段**

- openai_temperature: Temperature for OpenAI service
- openai_reasoning_effort: Reasoning effort for OpenAI service (minimal/low/medium/high)
- openai_send_temprature: Send temprature to OpenAI service
- openai_send_reasoning_effort: Send reasoning effort to OpenAI service

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
- siliconflow_send_enable_thinking_param: Send enable thinking param to SiliconFlow service

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
