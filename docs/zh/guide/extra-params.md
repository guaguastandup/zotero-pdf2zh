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

```text
openai_temperature=0.3
openai_send_temprature=true
```

---

## DeepSeek

DeepSeek V4 模型（包括 `deepseek-v4-pro` 和 `deepseek-v4-flash`）支持显式控制思考模式。由于开启思考会产生额外 reasoning token 与费用，Zotero PDF2zh 默认关闭 DeepSeek 思考模式。

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

`pdf2zh_next 2.9.0` 在 `DeepSeekSettings` 中新增了 `deepseek_thinking_mode` 和 `deepseek_reasoning_effort`，对应 CLI 参数为：

```text
deepseek_thinking_mode     -> --deepseek-thinking-mode
deepseek_reasoning_effort  -> --deepseek-reasoning-effort
```

Zotero PDF2zh v4.1.0 的保护流程：

1. 插件通过 `extraData` 保存用户选择；
2. DeepSeek V4 没有显式设置时，Server 自动使用 `disabled`；
3. 对 uv / conda / system Python，Server 从**本次实际 Python 环境中已安装的 `pdf2zh_next` distribution metadata/source**静态确认 Thinking capability，不启动重型 `pdf2zh_next --help`；
4. 支持时，将用户选择转换为上游正式 CLI 参数；
5. 不支持时，在任何翻译 API 调用之前停止并提示更新；
6. Windows standalone exe 无法通过 Python distribution 静态检查时，才使用独立的 exe capability 检查；
7. 非 DeepSeek V4 不发送这些 V4-only 参数。

::: warning 为什么不执行 pdf2zh_next --help？
`pdf2zh_next 2.9.0` 在 CLI 参数解析前可能加载 BabelDOC / high-level 模块，因此 `--help` 并不是轻量健康检查，在部分机器上可能需要很长时间。v4.1.0 的正常 Python 环境路径改为静态检查，避免把一个已经安装成功的环境误判成失败。
:::

::: warning 版本与 BabelDOC 的区别
DeepSeek V4 thinking 控制由 **`pdf2zh_next` 运行时**提供，而不是由 BabelDOC 版本决定。`pdf2zh_next 2.8.2` 没有这两个字段；`pdf2zh_next 2.9.0` 才加入。BabelDOC / PyMuPDF 主要影响 PDF 解析和依赖兼容性。
:::

上游 CLI 示例：

```bash
# 推荐默认：关闭思考
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

DeepLX 通过旧版 `pdf2zh` 引擎配置。`pdf2zh` 1.x 的 `DEEPLX_ACCESS_TOKEN` 值可以为空，但字段本身必须存在；当前版本会保留这个可选字段。

- `DEEPLX_ENDPOINT`：DeepLX 自定义翻译端点，可填写为 Base URL。
- `DEEPLX_ACCESS_TOKEN`：可选访问 token，不需要时可留空。

如果日志最终请求的是 `https://api.deepl.com/v2/translate`，请先确认实际服务选择的是 `deeplx` 而不是 `deepl`。

---

## Ollama

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `num_predict` | 最大预测 token 数 | 2000 |

## Azure OpenAI

| 参数 | 说明 |
|------|------|
| `azure_openai_api_version` | API 版本 |

## SiliconFlow

| 参数 | 说明 |
|------|------|
| `siliconflow_enable_thinking` | 启用思考模式 |
| `siliconflow_send_enable_thinking_param` | 是否发送思考模式参数 |

## Qwen MT

| 参数 | 说明 |
|------|------|
| `ali_domains` | Qwen MT 的领域/上下文提示 |

## 使用建议

1. 布尔值使用 `true` / `false`。
2. 可选参数不确定时留空，使用上游默认值。
3. 服务 API 和模型参数会变化；遇到参数被拒绝时，应同时核对当前 `pdf2zh_next` 版本和上游文档。

::: info 相关文档
- [配置说明](/zh/guide/configuration)
- [翻译环境更新](/zh/guide/package-update)
- [翻译服务问题](/zh/guide/faq/translation-service)
:::
