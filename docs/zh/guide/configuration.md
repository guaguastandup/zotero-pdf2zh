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
| **双语模式** | 仅支持基本双语对照 | 支持 Left&Right / Top&Bottom 多种模式 |
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

请参考您的翻译服务提供商的限制设置。

### 计算公式

```
qps = rpm / 60
```

### Pool Size 设置规则

| 限制类型 | 计算公式 |
|----------|----------|
| qps/rpm 限速 | `pool size = qps * 10` |
| 并发数限制 | `pool size = max(向下取整(0.9*官方并发数限制), 官方并发数限制-20)`，`qps = pool size` |

::: tip 不确定如何设置？
如果您不知道怎么设置，请直接设置 qps 即可，pool size 设置为默认值 0。
:::

### 示例

#### 智谱 AI

- 查看官方文档：[智谱 AI 速率限制](https://www.bigmodel.cn/dev/howuse/rate-limits)
- 假设 RPM = 60，则 `qps = 60 / 60 = 1`
- `pool size = 1 * 10 = 10`

#### DeepSeek

DeepSeek v3 的限制是 150 RPM，则：
- `qps = 150 / 60 = 2.5`，可以设置为 2
- `pool size = 2 * 10 = 20`

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
| **siliconflowfree** | 基于硅基流动提供的 GLM4-9B 模型，由硅基流动、pdf2zh_next 和 BabelDOC 联合提供服务 | 1. 仅支持 pdf2zh_next引擎<br>2. 无需选择 qps，默认为 40<br>3. 可能存在漏翻译情况 |
| **bing/google** | bing/google 的官方机器翻译 | 存在限流，翻译失败请将并发数调至 2 及以下 |

### 具有优惠/赠送的服务

| 服务名称 | 服务介绍 | 注意事项 |
|----------|----------|----------|
| **openaliked** | 火山引擎协作计划，个人用户每天最多赠送 50w token | 1. 额度按前一天使用量等额计算<br>2. 支持高并发：500~1000<br>3. URL：`https://ark.cn-beijing.volces.com/api/v3` |
| **silicon** | 通过邀请好友获得 14 元赠送金额 | 1. URL：`https://api.siliconflow.cn/v1`<br>2. 免费版线程数较低，建议设置为 6 左右 |
| **zhipu** | 智谱部分模型可支持免费调用 | 免费服务并发数不要设置过高，建议 6 以内 |

### 高质量服务

| 服务名称 | 服务介绍 | 推荐设置 |
|----------|----------|----------|
| **aliyunDashScope** | 翻译效果较好，新用户有赠送额度 | 选择 LLM API 配置中的默认模型选项 |
| **deepseek** | 翻译效果好，有缓存命中机制（推荐） | 使用 deepseek v3 服务 |

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

### 按使用场景选择

| 使用场景 | 推荐服务 | 原因 |
|----------|----------|------|
| **初次尝试** | siliconflowfree | 完全免费，无需配置 |
| **轻度使用** | openaliked / zhipu | 有免费额度，性价比高 |
| **长期使用** | deepseek（推荐） | 翻译质量好，有缓存机制 |
| **高质量需求** | deepseek / aliyunDashScope | 翻译效果最好 |

### 按预算选择

- **零预算**：siliconflowfree（可能漏翻译）
- **低预算**：openaliked（每天 50w token 赠送）或 zhipu（部分模型免费）
- **中等预算**：deepseek（性价比高，有缓存机制）
- **高质量优先**：aliyunDashScope 或 deepseek

## pdf2zh 引擎配置

### 自定义字体

字体文件路径为本地路径。

::: warning 远程部署限制
如果采用远端服务器部署，暂时无法使用本配置，需要手动修改 `config.json` 文件中的 `NOTO_FONT_PATH` 字段。
:::

## pdf2zh_next 引擎配置

### 双语(Dual)文件显示模式

- **Left&Right**：左右对照模式
- **Up&Down**：上下对照模式

### 提取术语表

开启后会提取文档中的术语表，但会消耗更多 Token。

### OCR 临时方案

- pdf2zh 和 pdf2zh_next 不直接提供文档 OCR 功能
- 您需要用其他工具对扫描版文件进行 OCR 处理
- 此选项只是一个对于 OCR 后文件的兼容方案

::: tip 兼容模式
兼容模式生成的文件大小会更大，非必要情况不需要开启。
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
