# 配置说明

本文档详细介绍 Zotero PDF2zh 插件的配置选项。

## 插件设置

在 Zotero 中打开「工具 → PDF2zh 首选项」进行配置。

![Zotero PDF2zh 首选项](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/preference.png)

## 基础配置

### Python Server IP

设置 Python 服务的地址。

- **默认值**：`http://127.0.0.1:8890`
- **说明**：如果您修改了服务端口或使用远程部署，需要修改此地址

### 翻译引擎

选择使用的翻译引擎。插件支持两种翻译引擎，请根据需求选择：

| 对比项 | PDF2ZH (旧版) | PDF2ZH Next (新版) |
|--------|---------------|-------------------|
| **维护状态** | ❌ 不再活跃维护 | ✅ 持续更新维护 |
| **翻译速度** | ⚡ 较快 | 稍慢 |
| **自定义字体** | ✅ 支持更换自定义字体 | ❌ 不支持 |
| **配置文件** | `config.json` | `config.toml` |
| **双语模式** | 仅支持基本双语对照 | 支持同页左右对照 / 原译文交替分页 |
| **术语表功能** | ❌ 不支持 | ✅ 自动提取并使用术语表 |
| **表格翻译** | ❌ 不支持 | ✅ 支持表格内容翻译 |
| **OCR 兼容** | ❌ 不支持 | ✅ 支持 OCR 兼容模式和自动 OCR |
| **去除水印** | ❌ 不支持 | ✅ 支持无水印模式 |
| **支持的翻译服务** | 相对较少 | 支持更多服务（含免费 siliconflowfree） |
| **上游项目** | [Byaidu/PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) | [PDFMathTranslate-next](https://github.com/PDFMathTranslate/PDFMathTranslate-next) |

::: tip 推荐
除非您有自定义字体需求或对速度有极高要求，否则建议优先使用 **PDF2ZH Next** 引擎。
:::

切换引擎后，界面将显示对应引擎的配置选项。

## 检查服务器连接

在插件设置页面中，点击"Python Server IP"输入框旁边的"检查连接"按钮，可测试与 Python 服务的连接状态。

- **连接成功**：服务正常运行
- **连接失败**：请检查：
  - server.py 脚本是否正在运行
  - 端口号是否正确（默认 8890）
  - 防火墙/杀毒软件是否阻止了连接

## 网页端查看翻译进度

服务启动后，可在浏览器中访问 `http://127.0.0.1:8890` 查看翻译进度：

- 实时显示当前翻译任务状态
- 查看翻译历史记录
- 预览和下载翻译后的文件

## QPS 和 Pool Size 配置

新版 `pdf2zh_next` 将两个参数分开处理：

- **QPS**：限制向翻译服务发送请求的速率。
- **Pool Size**：限制同时工作的翻译 Worker 数量。
- **Pool Size = 0（推荐默认）**：不额外指定 Worker 数，由 `pdf2zh_next` 按 QPS 使用对应的 Worker 数。

旧版本文档中的 `pool size = qps * 10` 已经不再适用于当前 `pdf2zh_next`，不要继续按该公式放大并发数，否则更容易触发供应商限流或造成不必要的本地资源压力。

::: tip 不确定如何设置？
通常只需要根据服务商限流设置 **QPS**，并将 **Pool Size 保持为 0**。只有服务商明确给出了独立的并发连接限制，或您确实需要限制本地 Worker 数时，才手动设置 Pool Size。
:::

如果服务商只给出了 RPM，可以粗略换算：

```text
qps = rpm / 60
```

实际限额可能随账号、模型和套餐变化，请优先参考对应服务商当前官方文档，不要依赖本文档中的固定历史数值。

## 翻译服务配置

单击「LLM API 配置管理」中的「新增」按钮，配置翻译服务。

![LLM API 编辑器](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/editor.png)

### 配置说明

- 您可以为同一个服务添加多种配置
- 每次只能激活一种配置，翻译时使用激活的配置
- 配置后需要在「翻译服务」处选择要使用的服务

### 字段说明

| 字段 | 说明 |
|------|------|
| 服务名称 | 自定义配置名称 |
| 服务类型 | 选择翻译服务提供商 |
| URL | API 端点地址（某些服务不需要） |
| API Key | API 密钥 |
| 模型 | 使用的模型名称 |
| 额外配置 | 其他可选参数 |

## 翻译服务介绍

### 免费 & 免配置服务

| 服务名称 | 服务介绍 | 注意事项 |
|----------|----------|----------|
| **siliconflowfree** | 基于硅基流动提供的免费翻译服务 | 1. 仅支持 pdf2zh_next 引擎<br>2. 无需 API Key<br>3. 免费服务可能存在限流或漏翻译情况 |
| **bing/google** | bing/google 的机器翻译服务 | 存在限流，翻译失败时请降低 QPS |

### 具有优惠/赠送的服务

各服务的免费额度、模型和限流策略变化较快，请以服务商当前页面为准。不要根据旧版文档中的固定并发数或赠送额度长期配置。

### 高质量服务

| 服务名称 | 服务介绍 | 推荐设置 |
|----------|----------|----------|
| **aliyunDashScope** | 翻译效果较好 | 在 LLM API 配置中选择当前可用模型 |
| **deepseek** | 翻译效果好，支持 DeepSeek V4 | 可选 `deepseek-v4-pro` / `deepseek-v4-flash`；PDF 翻译默认建议关闭思考以控制费用 |

DeepSeek V4 的思考模式和强度设置请参阅 [额外参数说明](/zh/guide/extra-params)。

### OpenAI 兼容服务

**openailiked** 服务选项可以填写所有兼容 OpenAI 格式的 LLM 服务。

您需要填写：
- **URL**：LLM 服务供应商提供的 API 地址
- **API Key**：您的 API 密钥
- **Model**：模型名称

::: tip 示例
火山引擎 URL 填写为：`https://ark.cn-beijing.volces.com/api/v3`

**常见 OpenAI 兼容服务 URL：**

| 服务 | URL |
|------|-----|
| 火山引擎 | `https://ark.cn-beijing.volces.com/api/v3` |
| SiliconFlow | `https://api.siliconflow.cn/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` |

::: warning 注意
URL 后面不要有 `/completions` 或 `/chat/completions` 等后缀，直接填入基础 API 地址即可。
:::

## 翻译服务选择建议

服务的价格、免费额度和限流策略会变化。选择服务时建议优先考虑：当前可用性、目标语言翻译质量、价格，以及您账号实际的 QPS/并发限制。

## pdf2zh 引擎配置

### 自定义字体

字体文件路径为本地路径。

::: warning 远程部署限制
如果采用远端服务器部署，暂时无法使用本配置，需要手动修改 `config.json` 文件中的 `NOTO_FONT_PATH` 字段。
:::

## pdf2zh_next 引擎配置

### 双语(Dual)文件显示模式与顺序

- **Side by Side / LR**：同一页左右对照。
- **Alternating Pages / TB**：原文页与译文页交替出现。历史 UI 曾把它写成 “Top & Bottom / 上下对照”，这是旧文案，并不是当前 BabelDOC 的实际含义。
- **译文在前**：默认关闭。关闭时使用上游默认顺序；在 LR 模式中通常表现为**原文在左、译文在右**。开启后顺序相反，即**译文在左、原文在右**。

::: warning 增强兼容性与页序
“增强兼容性”不是单纯的渲染开关。上游为了处理部分特殊 PDF，可能同时要求译文页在前。因此如果启用了增强兼容性，即使“译文在前”单独开关关闭，最终输出仍可能使用译文在前的顺序。这是上游兼容模式的行为。
:::

### 仅保留实际翻译页面

“仅保留实际翻译的页面”只有在指定了页码范围时才有意义。本项目目前最常见的触发方式是设置“最后几页跳过翻译”。例如跳过最后 2 页时，开启该选项可让输出 PDF 只保留实际参与翻译的页面。

### 提取术语表

开启后会提取文档中的术语表，但会消耗更多 Token。

### OCR 临时方案

- pdf2zh 和 pdf2zh_next 不直接提供完整的文档 OCR 功能
- 您可以先用其他工具对扫描版文件进行 OCR 处理
- 本插件中的 OCR 选项主要用于提高此类 PDF 的兼容性

::: tip 兼容模式
兼容模式可能改变部分处理策略。非必要情况不建议开启；如果遇到渲染错误、文字层异常等问题，再尝试开启。
:::

## 额外配置参数

额外配置参数名需要与配置文件中的字段相同。

例如在 pdf2zh_next 中，openai 对应的额外配置：
- `openai_temperature`
- `openai_send_temperature`

这些与 `config.toml` 文件中的字段相对应。

::: info 详细文档
更多关于额外配置的信息，请参考 [额外参数说明](/zh/guide/extra-params)。
:::

## 命令行参数

启动 `server.py` 时可用的参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--enable_venv` | `True` | 开启虚拟环境管理 |
| `--env_tool` | `uv` | 虚拟环境管理工具（uv/conda） |
| `--port` | `8890` | 服务端口号 |
| `--check_update` | `True` | 自动检查更新 |
| `--update_source` | `gitee` | 更新源（github/gitee） |
| `--enable_mirror` | `True` | 启用国内镜像 |
| `--mirror_source` | 中科大镜像 | 镜像源地址 |
| `--enable_winexe` | `False` | Windows exe 安装模式 |
| `--winexe_path` | - | Windows exe 可执行文件路径 |

### 使用示例

```shell
# 切换端口
python server.py --port=9999

# 关闭虚拟环境管理
python server.py --enable_venv=False

# 使用 conda 虚拟环境
python server.py --env_tool=conda

# 自定义镜像源
python server.py --mirror_source="https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"
```

## 下一步

- 阅读 [翻译选项](/zh/guide/translation-options) 了解各种翻译功能
- 阅读 [包更新](/zh/guide/package-update) 了解如何更新依赖包
- 遇到问题请查看 [常见问题](/zh/guide/faq/)
