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

### Wenyi 引擎（第一版）

可选的整篇翻译引擎，仅支持有文本层的完整 PDF，可输出单语和左右并列的双语 PDF；
不支持裁剪、单独的对照操作、跳页和 OCR。切回 PDF2zh 时原有设置保留。

1. 同步更新插件和 Server，在翻译引擎中选择 **Wenyi**。
2. 在 **LLM API 配置管理**中添加并激活 **DeepSeek**，填写密钥并设置思考模式和推理强度。
   模型固定为 `deepseek-flash`，不使用该配置的模型名、API URL 或其他额外参数，
   也不回退到 Server 的密钥环境变量。未设置思考参数时使用关闭 / 高。
3. 正常启动 Server（`python server.py`）后翻译 PDF。首次使用会自动创建专用
   Python 3.12 环境 `zotero-wenyi-venv`，从 PyPI 或所选镜像安装最新稳定版 Wenyi 包，
   并启动本机 bridge；无需手工安装。首次安装和模型资源下载可能较慢。

**翻译流程配置**中的**翻译文体**下拉框默认为**学术**（`academic`），
翻译文学文本时可切换为**文学**（`literary`）。选择保存在插件中，通过子命令前的
`--prompt-genre` 传给 CLI，不写入 YAML，也不改变 CLI 自身的默认文体。

勾选复选框即可开启对应阶段，取消勾选即可关闭。
全书预扫、译文润色和全书审校默认勾选，三译合润默认不勾选。
三译合润生成三份译稿再合成润色，开启时锁定润色，关闭后恢复原先选择。
这些阶段会增加耗时和用量；关闭阶段可节省成本，但会减少上下文或质量检查。
思考参数只在 LLM 配置中设置，不再重复显示。

**注释/链接对齐**默认关闭，对应 CLI 的注释和链接定位阶段
（`pipeline.annotation_alignment`），不控制 PDF 页面几何布局或左右拼页。

**默认生成文件**中单语默认开启，双语默认关闭。可以任选一种或同时生成两种，
但至少需要选择一种；每种文件的**生成后自动打开**沿用 PDF2zh 对应文件类型的选项，
Wenyi 的生成选项则独立保存，不覆盖 PDF2zh 的生成设置。
开启双语后可选择**双语顺序（从左到右）**：默认**译文在前**，即左侧译文、右侧原文；
选择**原文在前**则相反。关闭双语后仍保留已选顺序，供下次使用。
这需要 Wenyi CLI 支持将 `output.bilingual_order` 应用于 PDF 导出；
旧版 CLI 固定原文在左，需要更新后才能使用顺序选项。

密钥仅注入本次 CLI 子进程，不写入任务文件或交给 bridge。请只连接可信 Server，
远程连接使用 HTTPS。CLI 与 AGPL BabelDOC bridge 保持独立进程，通过 HTTP 通信。
环境维护见[引擎包更新](./package-update.md#wenyi-独立环境)。

需要手工管理时，使用 `--wenyi-python /path/to/environment/python` 指定安装了
`wenyi-cli` 和 `wenyi-core` 的 Python，使用 `--wenyi-bridge-url` 指定外部 bridge；
只指定后者仍使用托管 CLI。设置 `--enable_venv=False` 时，未指定 `--wenyi-python`
则使用 Server 自身的 Python，外部 bridge 默认 `http://127.0.0.1:8765`。
`--wenyi-timeout` 默认 10800 秒，不含环境准备时间。
所选安装必须支持 Core 的运行时 bridge 连接 API（`wenyi_core.pdf_bridge.connection`）；
不支持时明确提示更新环境或选择正确解释器，不回退到其他 CLI 或端口。

#### 检查点与再次提交

任务完成前请保持 Server 运行。中断后，使用相同源/目标语言和数据根目录再次提交同一份
PDF，即可接续 Core 检查点。每次提交仍创建新任务 ID，以及独立的进度/结果回执、
配置、日志和输出，不会在任务列表中重新打开旧任务。进度百分比表示当前阶段，
没有单独的恢复/取消界面。

插件按 SHA256 识别 PDF，向 Core 传递内部统一命名为 `source.pdf` 的原样副本，
不改写上传原文。改名不丢失检查点；即使文件名相同，不同内容也不共用翻译状态。
显式源语言与自动检测分别保存；`zh-CN` 和 `zh` 归一为同一目标语言，不同目标语言
由 Core 的目标目录和运行锁隔离。仅支持完整 PDF：跳页、OCR 和页面选择请求在执行前拒绝。
修改流程/模型选项不会强制重译已完成的译文。

Server 按需以新的本机随机端口启动托管 bridge，专用 launcher 将抽取和导出请求解析到
本次地址，不改变保存的 source hash、session ID、paragraph IDs、pages 和冻结版式快照。
状态中的 `zotero-wenyi://bridge` 是不可联网的逻辑身份，不是服务 URL；
不要用独立 CLI 直接执行生成的任务配置。没有 launcher/resolver 时它不能用于 HTTP。
独立 Wenyi CLI 行为不变。外部 bridge 须自行保持相同的持久
`WENYI_BABELDOC_STATE_DIR`。session 缺失或不兼容时明确失败，
不会静默重新抽取以替换旧段落映射。

#### 数据根目录与可清理缓存

Wenyi 数据仅归本插件所有，不放在 Server 安装目录中，也不共享 Wenyi Desktop/CLI/Web
项目。用 `--wenyi-data-dir` 或 `ZOTERO_WENYI_DATA_DIR` 设置，命令行优先。默认位置：

- Linux：`$XDG_DATA_HOME/zotero-pdf2zh/wenyi`，未设置则为 `~/.local/share/zotero-pdf2zh/wenyi`。
- macOS：`~/Library/Application Support/zotero-pdf2zh/wenyi`。
- Windows：`%LOCALAPPDATA%\zotero-pdf2zh\wenyi`，未设置则使用用户目录下的 `AppData\Local`。

| 数据根目录内路径 | 职责与保留规则 |
|---|---|
| `translations/` | 持久 Core 检查点、源文产物、术语和锁；续译需要保留。 |
| `bridge/sessions/` | 托管 bridge 的源 PDF、冻结版式/session 快照；恢复导出必需，**不是可清理缓存**，应与 `translations/` 一起备份。 |
| `tasks/<task-id>/` | 上传 PDF、内部输入副本、任务配置、回执、日志及输出 PDF；所有使用它的任务停止后，可手工清理已结束 attempt，再次提交会提供新副本。 |
| `runtime/` | 托管 bridge 诊断日志，不是翻译状态。 |
| `cache/` | 默认存放可下载的字体、模型和分词器资源；停止运行后可清理，缺失资源会重新下载。 |

用 `--wenyi-cache-dir` 或 `ZOTERO_WENYI_CACHE_DIR` 覆盖缓存位置，命令行优先。
缓存不能与检查点、任务、session 或运行时目录重叠，也不能包含数据根目录。
缓存设置仅注入 Wenyi CLI/托管 bridge 子进程，不修改 PDF2zh 或 Server 的全局缓存设置；
外部 bridge 自行管理资源缓存。专用 Python 环境仍属于安装管理范围
（`server/zotero-wenyi-venv/`），发布给附件下载的副本仍位于既有
`server/translated/` 下载目录。

不自动清理、迁移或发现旧 `server/wenyi-tasks/`、`server/wenyi-runtime/` 及 Desktop/CLI/Web
数据。更换数据根目录即选择独立状态；要继续翻译请保持相同路径。不要把缓存指向包含其他数据的目录。
仅数据所有者可在 Server/bridge 停止后手工清理；仍需续译/导出时先备份。
这些目录包含私有文档和日志，不要整体上传。不要用尚未支持 Wenyi 的上游 Server 包覆盖此适配版。

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
