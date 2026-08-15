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

DeepSeek V4 模型（包括 `deepseek-v4-pro` 和 `deepseek-v4-flash`）支持显式控制思考模式。由于开启思考会产生额外的 reasoning token 与费用，Zotero PDF2zh 默认关闭 DeepSeek 思考模式。

### 基础字段

- `deepseek_model` - 模型名称，例如 `deepseek-v4-pro` 或 `deepseek-v4-flash`
- `deepseek_api_key` - API 密钥

### 额外字段

| 参数 | 说明 | 可选值 / 默认值 |
|------|------|-----------------|
| `deepseek_thinking_mode` | 是否开启 DeepSeek V4 思考模式 | `disabled` / `enabled`，默认 `disabled` |
| `deepseek_reasoning_effort` | 思考强度，仅在思考模式开启时生效 | `high` / `max`，开启后默认 `high` |
| `deepseek_enable_json_mode` | 是否启用 JSON mode | 依 `pdf2zh_next` 配置 |

这些值仍然使用插件原有的 `extraData` 保存和传递。下拉框只是帮助用户填写、校验字段，不是另一套协议。

### 实际执行方式

`pdf2zh_next 2.9.0` 在 `DeepSeekSettings` 中新增了 `deepseek_thinking_mode` 和 `deepseek_reasoning_effort`。它的 CLI 会由同一套设置模型自动生成：

```text
deepseek_thinking_mode     -> --deepseek-thinking-mode
deepseek_reasoning_effort  -> --deepseek-reasoning-effort
```

因此 Zotero PDF2zh 现在采用以下保护流程：

1. 插件通过 `extraData` 保存用户选择；
2. DeepSeek V4 没有显式设置时，Server 自动使用 `disabled`，避免依赖服务端默认 thinking；
3. Server 在真正翻译前定位**本次实际执行的** `pdf2zh_next` / Windows exe；
4. 通过该运行时的 `--help` 检查是否真的支持 `--deepseek-thinking-mode` 和 `--deepseek-reasoning-effort`；
5. 支持时，Server 将用户选择转换成上游正式 CLI 参数再启动翻译；
6. 不支持时，在任何翻译 API 调用之前停止，并提示运行 `python update_packages.py`；不会静默忽略 thinking 设置；
7. 非 DeepSeek V4 模型不会发送这两个 V4-only 参数。

如果不支持的旧运行时已经让 Server 临时写入了这些新字段，Server 会在报错前自动把它们从共享 `config.toml` 清理掉，避免影响其他翻译服务。

::: warning 版本与 BabelDOC 的区别
DeepSeek V4 thinking 控制由 **`pdf2zh_next` 运行时**提供，而不是由 BabelDOC 版本决定。`pdf2zh_next 2.8.2` 没有这两个字段；`pdf2zh_next 2.9.0` 才加入。BabelDOC / PyMuPDF 版本主要影响 PDF 解析和依赖兼容性，是另一类问题。

因此 Zotero PDF2zh 不只比较版本字符串，而是直接检查本次实际执行程序是否存在对应 CLI flag。实际运行时不支持时，DeepSeek V4 翻译会被安全阻止。
:::

上游 `pdf2zh_next` CLI 示例：

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
