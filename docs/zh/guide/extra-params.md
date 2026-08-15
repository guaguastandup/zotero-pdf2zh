# 额外参数说明

本文档介绍各个翻译服务的额外配置参数。额外参数用于设置不同服务的特定选项。

::: tip 参数格式
额外配置参数名需要与配置文件中的字段相同。在 Zotero 插件的「额外配置」字段中填写。插件本身已经提供通用 `extraData` 传参机制；部分常用字段会额外提供下拉框，只是为了减少手工输入和误配，并不是另一套传参协议。
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
| `openai_send_temprature` / `openai_compatible_send_temperature` | 是否发送 temperature 参数 | true |
| `openai_reasoning_effort` / `openai_compatible_reasoning_effort` | 推理强度 (minimal/low/medium/high) | low |
| `openai_send_reasoning_effort` / `openai_compatible_send_reasoning_effort` | 是否发送 reasoning effort 参数 | true |

::: warning OpenAI 参数兼容拼写
`pdf2zh_next` 2.9.0 及更早版本为了兼容历史配置，原生 OpenAI 服务仍使用拼写为 `openai_send_temprature` 的字段；这是上游有意保留的兼容字段。`openai_compatible_send_temperature` 则使用正常拼写。
:::

### 示例配置

```
openai_temperature=0.3
openai_send_temprature=true
```

---

## DeepSeek

DeepSeek v4 模型（包括 `deepseek-v4-pro` 和 `deepseek-v4-flash`）支持显式控制思考模式。由于开启思考会产生额外的 reasoning token 与费用，zotero-pdf2zh 默认关闭 DeepSeek 思考模式。

### 基础字段

- `deepseek_model` - 模型名称，例如 `deepseek-v4-pro` 或 `deepseek-v4-flash`
- `deepseek_api_key` - API 密钥

### 额外字段

| 参数 | 说明 | 可选值 / 默认值 |
|------|------|-----------------|
| `deepseek_thinking_mode` | 是否开启 DeepSeek v4 思考模式 | `disabled` / `enabled`，默认 `disabled` |
| `deepseek_reasoning_effort` | 思考强度，仅在思考模式开启时生效 | `high` / `max`，开启后默认 `high` |
| `deepseek_enable_json_mode` | 是否启用 JSON mode | 依 BabelDOC 配置 |

这些字段最终仍然通过插件原有的 `extraData` 发送。插件中的下拉框只是自动填入并校验这些参数；高级用户也可以直接使用额外参数字段。

在插件中选择 DeepSeek 服务后，会自动出现思考模式和思考强度的下拉选项。关闭思考时，思考强度不会发送给翻译请求。

::: warning 版本要求
显式 DeepSeek V4 thinking 控制需要 `pdf2zh_next >= 2.9.0`。Server 不再为了这一可选功能强制升级所有已有环境；使用较旧版本时仍可以填写 V4 模型名进行普通翻译，但 thinking 开/关参数不会由旧版 `pdf2zh_next` 处理。升级前建议先检查当前上游 `pdf2zh_next` / BabelDOC 的依赖兼容性。
:::

对应 BabelDOC CLI 参数：

```bash
# 默认推荐：关闭思考
uv run pdf2zh_next input.pdf \
  --deepseek \
  --deepseek-model deepseek-v4-flash \
  --deepseek-thinking-mode disabled \
  --output ./output

# 开启思考，并使用 high 强度
uv run pdf2zh_next input.pdf \
  --deepseek \
  --deepseek-model deepseek-v4-flash \
  --deepseek-thinking-mode enabled \
  --deepseek-reasoning-effort high \
  --output ./output
```

---

## DeepLX（pdf2zh 1.x）

DeepLX 目前通过旧版 `pdf2zh` 引擎配置。`pdf2zh` 1.x 的 `DEEPLX_ACCESS_TOKEN` **值可以为空，但字段本身必须存在**；旧版 Zotero PDF2zh Server 在 API Key 留空时会误删该字段，导致 `KeyError: 'DEEPLX_ACCESS_TOKEN'`。当前版本已保留这个可选字段。

- `DEEPLX_ENDPOINT`：DeepLX 自定义翻译端点。在插件中可填写到 Base URL。
- `DEEPLX_ACCESS_TOKEN`：可选访问 token。可以填写在 API Key，也可以作为额外参数填写；不需要 token 时可留空。

示例：

```text
服务: deeplx
Base URL: https://your-deeplx.example/translate
API Key: （可留空）
```

如果日志最终请求的是 `https://api.deepl.com/v2/translate`，请先确认实际服务选择的是 `deeplx` 而不是 `deepl`；两者是不同 translator，不能仅凭该现象判断为 Zotero 插件 bug。

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
