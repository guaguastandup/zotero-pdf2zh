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

选择 **Wenyi**，使用 Wenyi 的完整翻译工作流，而不是 PDF2zh
的逐段翻译器。首版仅支持有文本层的完整 PDF 和单语 PDF 输出，不支持双语布局、
裁剪、跳过页面、OCR 或其他模型供应商；切回 PDF2zh 后原有设置仍然保留。
Wenyi 模式隐藏“默认生成文件”设置，始终生成单语 PDF。

安装包含 `translate --progress-json` 和 `--result-json` 的 Wenyi CLI，
并单独启动 `wenyi-babeldoc-bridge`。在 **Server 进程的环境变量**中设置
`DEEPSEEK_API_KEY`，不要填入插件的 LLM 编辑器，也不要把密钥写入命令、
配置文件或任务文件。

bridge 使用本插件已有的 `pdf2zh_next` 环境，不另设固定版本组合。在 `server`
目录运行 `python manage_packages.py status --engine pdf2zh_next` 查看解释器路径，
然后从 bridge 仓库用该解释器安装 `-e '.[zotero]'`。该选项沿用本插件的
`pdf2zh-next>=2.9.0,<3.0.0` 和 `bitstring>=4.3.0,<5` 约束，由同一次解析
确定 BabelDOC、PyMuPDF。安装后运行 `uv pip check --python <解释器路径>`，
并使用同一环境的 `wenyi-babeldoc-bridge` 启动服务；不要用另一个项目环境的
`uv run` 重新安装。Wenyi CLI 仍使用自己的环境，通过 HTTP 调用 bridge。
同一系统用户下，字体和模型共用 BabelDOC 缓存。

在 `server` 目录中启动：

```shell
python server.py --wenyi-executable /absolute/path/to/wenyi \
  --wenyi-bridge-url http://127.0.0.1:8765
```

Windows 可以传入 `wenyi.exe` 的绝对路径。`--wenyi-timeout` 默认 10800 秒。
可执行文件和 bridge 地址仅由 Server 管理者配置，客户端不能指定命令或模型凭据。

切换到 Wenyi 后，PDF2zh 专属设置和 LLM 凭据编辑器会替换为 **翻译流程配置**
与 **模型参数**：

| 设置 | Wenyi 字段 | 可选值 |
|---|---|---|
| 全书预扫 | `pipeline.book_understanding` | 开启 / 关闭，初始为开启 |
| 三译合润 | `pipeline.translation_mode` | 开启（`best_of_three`）/ 关闭（`standard`），初始为关闭 |
| 译文润色 | `pipeline.polish` | 开启 / 关闭，初始为开启 |
| 全书审校 | `pipeline.review` | 开启 / 关闭，初始为开启 |
| 思考模式 | `options.thinking` | 开启 / 关闭，初始为关闭 |
| 推理强度 | `options.reasoning_effort` | 高 / 最高，初始为高 |

插件会显式发送上述选择，不再继承 CLI 的思考设置；Wenyi 自身的 DeepSeek preset
保持不变，所有档位仍使用 `deepseek-flash`。用户已明确选择的值会保留，
旧版空值会替换为上表的初始值；开关不再提供“默认”选项。
开启三译合润会先生成三份译稿，再合成润色；通常每批使用四次调用，而普通翻译加润色
使用两次，会增加耗时和用量。此模式锁定润色为开启，关闭后恢复原先的润色选择。
全书预扫、润色和审校可能显著增加耗时和 token 消耗；关闭审校也会跳过其自动修复。
关闭阶段可以节省成本，但也会失去相应的全书上下文、润色或质量检查。
模型参数同时作用于三个档位；关闭思考时保留推理强度选项，但不会将其发送给模型。
并发由 Wenyi 自身管理，插件不再提供或发送并发设置。
切换引擎时两套设置分别保留。

这些设置需要同步更新插件和 Server。Server 只接受请求中 `wenyi` 对象的上述类型化参数，
未知字段、PDF2zh 风格键名及非法值会报错，不会静默忽略；不支持客户端指定密钥、
模型名、URL 或任意 `extra_body`。此 preset 与下文 PDF2zh_next 的
`deepseek-v4-flash` 选项不同。

继续复用原有的异步任务协议、进度弹窗、HTTP 下载和附件导入。原文、无密钥配置、
检查点、机器回执及 `wenyi.log` 保存在 `server/wenyi-tasks/<task-id>/`；
发布的附件名带任务前缀，避免同名覆盖。百分比表示当前阶段进度，不是全流程耗时预测。
只有本次运行身份、原文和输出哈希、PDF 页数均校验通过后才报告成功。

完成前请保持 Server 和 bridge 运行。首版 Server 的任务及历史记录仍仅保存在内存，
重启后不会恢复插件轮询身份；Wenyi 检查点会保留，但尚未实现插件侧续跑和取消。
任务目录和日志包含原文、译文，分享前请自行检查，不要整体上传。

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
