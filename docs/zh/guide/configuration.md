# 配置说明

本文档对应 Zotero PDF2zh **v4.1.1**（含 v4.1.0 功能）。

## 插件设置

在 Zotero 中打开「工具 → PDF2zh 首选项」。

### Python Server IP

- 默认：`http://127.0.0.1:8890`
- 如果修改了 `server.py --port`，同步修改端口。
- Server v4.1.0 默认只监听 `127.0.0.1`。远程部署时需要显式启动：

```shell
python server.py --host 0.0.0.0
```

::: warning 远程访问
`0.0.0.0` 会允许网络中的其他设备访问 Server。请同时配置防火墙，并只在明确需要时启用。
:::

### 翻译引擎

| 对比项 | pdf2zh 1.x | pdf2zh_next 2.x |
|---|---|---|
| 状态 | 旧版兼容 | **推荐** |
| 配置文件 | `config.json` | `config.toml` |
| 自定义字体 | 支持 | 主要使用上游字体选择 |
| Dual 模式 | 基础支持 | LR 同页左右 / TB 交替页 |
| OCR / 表格 / 术语 | 功能较少 | 功能更完整 |
| DeepSeek V4 Thinking | 不适用 | v2.9.0+ 支持 |

除非依赖旧版特性，推荐使用 **pdf2zh_next**。

## LLM API 配置

在「LLM API 配置管理」中新增或编辑服务。

常用字段：

| 字段 | 说明 |
|---|---|
| Service | 翻译服务类型 |
| Model | 模型名称 |
| Base URL | API 基础地址 |
| API Key | 密钥 |
| Extra Parameters | 服务特定的 `extraData` 参数 |

v4.1.0 的编辑器支持**获取模型列表**。在线获取的模型会与插件默认模型、用户历史模型合并并去重；获取失败不会清空默认列表。

### API Key 日志

插件和 Server 日志会对 API Key / token / secret 等敏感字段脱敏，不会在正常 Debug Log 中打印明文密钥。

## DeepSeek

v4.1.0 默认提供：

- `deepseek-v4-flash`
- `deepseek-v4-pro`

旧的 `deepseek-chat` / `deepseek-reasoner` 不再作为可选项显示。已有配置会自动迁移：

```text
deepseek-chat
→ deepseek-v4-flash + thinking=disabled

deepseek-reasoner
→ deepseek-v4-flash + thinking=enabled + effort=high
```

### Thinking Mode

PDF 翻译默认：

```text
Thinking Mode = Disabled
```

开启后可选：

```text
Reasoning Effort = high / max
```

Thinking Control 需要实际 `pdf2zh_next` runtime 支持。默认不思考时，旧环境仍可翻译；只有用户手动开启思考且 runtime 不支持时，Server 才会在 API 请求前停止。详见 [额外参数](/zh/guide/extra-params) 与 [翻译环境更新](/zh/guide/package-update)。

## QPS 与 Pool Size

- **QPS**：限制翻译请求发送速率。
- **Pool Size**：限制并发 Worker 数。
- **Pool Size = 0（推荐）**：不显式指定 `pool_max_workers`，交给 `pdf2zh_next` 根据 QPS 处理。

旧版的 `pool size = qps × 10` 已废弃，不要继续使用。

## Dual PDF 布局

### Side by Side / LR

同一页左右排列。

默认顺序使用上游原文优先行为，通常是：

```text
原文 | 译文
```

开启「译文在前」后顺序相反。

### Alternating Pages / TB

原文页与译文页交替出现。

::: info 旧文案
历史 UI 曾把 TB 写成 “Top & Bottom / 上下对照”，但当前含义是 **Alternating Pages**，不是在同一页上下排版。
:::

## PDF 后处理操作

v4.1.0 会识别附件状态，避免重复处理：

```text
origin
→ mono / dual(LR/TB)
→ mono-cut / dual-cut / compare / crop-compare
```

`compare` 与 `crop-compare` 是终态；对结果文件再次执行同一操作会直接提示，不会再次上传/生成重复附件。

LR dual 执行 Crop 或 Crop-Compare 时，Server 会先内部转换为适合处理的 TB 结构，然后继续完成真正的 `dual-cut` / `crop-compare`，不会把“LR→TB”错误当成最终结果。

详见 [翻译选项](/zh/guide/translation-options)。

## 其他 pdf2zh_next 选项

### 仅保留实际翻译页面

仅在指定页码范围时有意义，例如使用「跳过最后几页」后，只保留实际参与翻译的页面。

### OCR Workaround

该选项主要改善已经具有文字层的特殊/扫描类 PDF 的兼容性，并不是完整 OCR 引擎。

### 增强兼容性

只建议在遇到渲染或文字层异常时开启。上游兼容模式可能同时改变部分布局/页序策略。

### 无水印

Zotero PDF2zh 默认生成无水印输出；Server 会将设置传给 `pdf2zh_next`。

## 配置文件迁移

v4.1.0 不再每次启动都用 `.example` 覆盖用户配置。

Server 会：

- 保留已有用户值；
- 保留未知自定义字段；
- 只补充新版缺失的默认字段；
- 更新项目托管的 `venv.json` package 约束，同时保留用户额外添加的包；
- 旧配置无法解析时先备份为 `.invalid.bak`。

当前 `config.toml.example` 以 `pdf2zh_next 2.9.0` schema 为基线，同时保留 Zotero PDF2zh 自己的安全默认，例如 DeepSeek V4、无水印和 `zh-CN`。

## Server 命令行参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--host` | `127.0.0.1` | 监听地址 |
| `--port` | `8890` | Server 端口 |
| `--enable_venv` | `True` | 托管翻译环境 |
| `--env_tool` | `auto` | 沿用已有 uv/conda；新环境优先 uv |
| `--check_update` | `True` | 启动时检查 Server 更新 |
| `--update_source` | `gitee` | 优先源 `gitee` / `github`；两个都会尝试 |
| `--enable_mirror` | `True` | 自动优化 Python 包下载源 |
| `--enable_winexe` | `False` | Windows standalone exe 模式 |
| `--skip_install` | `False` | 禁止自动创建/修复翻译环境 |

示例：

```shell
# 普通用户
python server.py

# 强制 conda
python server.py --env_tool=conda

# 强制 uv
python server.py --env_tool=uv

# 优先用 GitHub 更新源（失败会自动试 Gitee）
python server.py --update_source=github

# 局域网访问（高级）
python server.py --host 0.0.0.0
```

## 下一步

- [安装指南](/zh/guide/installation)
- [翻译选项](/zh/guide/translation-options)
- [额外参数](/zh/guide/extra-params)
- [翻译环境更新](/zh/guide/package-update)
