# 额外参数说明

本文档介绍各个翻译服务的额外配置参数。额外参数用于设置不同服务的特定选项。

::: tip 参数格式
额外配置参数名需要与配置文件中的字段相同。在 Zotero 插件的「额外配置」字段中填写。
:::

---

## OpenAI / OpenAI 兼容服务

### 基础字段

- `openai_model` / `openai_compatible_model` - 模型名称
- `openai_base_url` / `openai_compatible_base_url` - API 地址
- `openai_api_key` / `openai_compatible_api_key` - API 密钥

### 额外字段

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `openai_temperature` / `openai_compatible_temperature` | 控制随机性，0-1 之间 | 0.3 |
| `openai_send_temperature` / `openai_compatible_send_temperature` | 是否发送 temperature 参数 | true |
| `openai_reasoning_effort` / `openai_compatible_reasoning_effort` | 推理强度 (minimal/low/medium/high) | low |
| `openai_send_reasoning_effort` / `openai_compatible_send_reasoning_effort` | 是否发送 reasoning effort 参数 | true |

### 示例配置

```
openai_temperature=0.3
openai_send_temperature=true
```

---

## Ollama

### 基础字段

- `ollama_model` - 模型名称
- `ollama_host` - 服务地址

### 额外字段

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `num_predict` | 最大预测 token 数 | 2000 |

### 示例配置

```
num_predict=2000
```

---

## Azure OpenAI

### 基础字段

- `azure_openai_model` - 模型名称
- `azure_openai_base_url` - API 地址
- `azure_openai_api_key` - API 密钥

### 额外字段

| 参数 | 说明 |
|------|------|
| `azure_openai_api_version` | API 版本 |

### 示例配置

```
azure_openai_api_version=2024-02-01
```

---

## SiliconFlow

### 基础字段

- `siliconflow_base_url` - API 地址
- `siliconflow_model` - 模型名称
- `siliconflow_api_key` - API 密钥

### 额外字段

| 参数 | 说明 |
|------|------|
| `siliconflow_enable_thinking` | 启用思考模式 |
| `siliconflow_send_enable_thinking_param` | 是否发送思考模式参数 |

---

## Qwen MT (阿里云)

### 基础字段

- `qwenmt_model` - 模型名称
- `qwenmt_base_url` - API 地址
- `qwenmt_api_key` - API 密钥

### 额外字段

| 参数 | 说明 |
|------|------|
| `ali_domains` | 阿里云域名配置 |

---

## 使用建议

1. **参数值格式**：参数值不需要加引号，直接填写值即可
2. **布尔值**：使用 `true` 或 `false`（小写）
3. **多参数配置**：每行一个参数，格式为 `参数名=参数值`
4. **不确定参数**：留空即可使用默认值

::: info 相关文档
更多配置信息请参考：
- [配置说明](/zh/guide/configuration) - 基础配置
- [翻译服务问题](/zh/guide/faq/translation-service) - 翻译服务相关问题
:::
