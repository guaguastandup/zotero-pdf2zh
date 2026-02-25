# 翻译服务问题

关于 API 配置、Token 消耗、服务选择等问题。

---

## 没配置 API，可以用吗？

### 问题描述

我没有配置 API Key，可以直接使用翻译功能吗？

### 原因

大多数翻译服务需要 API Key 才能使用，但项目提供了免费的翻译服务选项。

### 解决方案

**可以使用，但有限制：**

如果您选择 pdf2zh_next 引擎，并且使用 **siliconflowfree** 服务，就可以获得免费的服务。

::: warning 注意
免费服务可能存在以下限制：
- 可能会漏翻译一些内容
- 翻译质量可能不如付费服务
- 有并发数限制
:::

**建议配置自己的 API：**
为了获得更好的翻译体验和稳定性，建议您优先自己配置 API Key。

可用的免费/优惠服务：
- [siliconflowfree](/zh/guide/configuration.md#siliconflowfree) - 硅基流动免费服务
- [openaliked](/zh/guide/configuration.md#openaliked) - 火山引擎协作计划，每天赠送 50w token
- [silicon](/zh/guide/configuration.md#silicon) - 通过邀请好友获得赠送金额
- [zhipu](/zh/guide/configuration.md#zhipu) - 智谱部分模型免费调用

---

## Token 消耗过多

### 问题描述

感觉翻译消耗的 Token 很多，担心费用问题。

### 原因

1. PDF 页数较多
2. 开启了"提取术语表"功能
3. 重复翻译相同内容（虽然有缓存机制）

### 解决方案

### 了解正常消耗量

通常一篇 10 页的英文文献消耗 Token 量在 **7～10w** 左右，单页约 **5k** 左右。您可以先基于此数据进行检查。

### 减少消耗的方法

1. **关闭提取术语表**
   - 如果您正在使用 pdf2zh_next 引擎
   - 在 Zotero 插件配置中，关闭「提取术语表」选项
   - 这个选项会消耗较多 Token

2. **利用缓存机制**
   - 翻译引擎具有缓存设置
   - 重复对同一篇文献进行翻译时，可能不会消耗过多的 Token（不能保证完全不消耗）

3. **选择更经济的服务**
   - [deepseek](/zh/guide/configuration.md#deepseek) - 有缓存命中机制，性价比高
   - [openaliked](/zh/guide/configuration.md#openaliked) - 火山引擎协作计划，每天赠送额度

---

## 如何选择翻译服务？

### 问题描述

翻译服务太多，不知道该选择哪个。

### 原因

不同服务有不同的特点、价格和质量。

### 解决方案

### 免费服务（适合尝试）

| 服务 | 优点 | 缺点 |
|------|------|------|
| **siliconflowfree** | 完全免费，无需配置 | 可能漏翻译，仅支持 pdf2zh_next |
| **bing/google** | 完全免费 | 限流严重，不稳定 |

### 免费额度/优惠服务（适合轻度使用）

| 服务 | 优点 | 缺点 |
|------|------|------|
| **openaliked** | 每天 50w token 额度，高并发 | 需要注册火山引擎 |
| **silicon** | 邀请好友获得 14 元赠送 | 免费版线程数较低 |
| **zhipu** | 部分模型免费调用 | 免费服务并发数限制 |

### 高质量服务（推荐）

| 服务 | 优点 | 缺点 |
|------|------|------|
| **deepseek（推荐）** | 翻译效果好，有缓存机制 | 需要付费 |
| **aliyunDashScope** | 翻译效果好，新用户有赠送 | 需要付费 |

### 选择建议

- **初次尝试**：使用 siliconflowfree
- **轻度使用**：使用 openaliked（火山引擎）或 zhipu
- **长期使用**：使用 deepseek，性价比最高

---

## QPS 和 Pool Size 如何设置？

### 问题描述

不知道 QPS 和 Pool Size 该设置多少。

### 原因

不同的服务提供商有不同的限制规则。

### 解决方案

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

### 示例：智谱 AI

1. 查看官方文档：[智谱 AI 速率限制](https://www.bigmodel.cn/dev/howuse/rate-limits)
2. 假设 RPM = 60，则 `qps = 60 / 60 = 1`
3. `pool size = 1 * 10 = 10`

### 示例：DeepSeek

DeepSeek v3 的限制是 150 RPM，则：
- `qps = 150 / 60 = 2.5`，可以设置为 2
- `pool size = 2 * 10 = 20`

---

## API Key 配置后仍然报错

### 问题描述

已经配置了 API Key，但翻译时仍然报错提示没有 API Key。

### 原因

1. 配置没有保存或激活
2. 配置的服务名称与选择的不一致
3. API Key 或 URL 配置错误

### 解决方案

1. **检查配置是否激活**
   - 在 LLM API 配置管理中，确保配置已激活（点击"激活"按钮）

2. **检查服务是否已选择**
   - 配置 LLM API 后，还需要在"翻译服务"处选择您需要使用的服务

3. **检查 API Key 和 URL**
   - 确认 API Key 没有多余的空格
   - 确认 URL 格式正确（某些服务不需要配置 URL）
   - openailiked 服务的 URL 示例：
     - 火山引擎：`https://ark.cn-beijing.volces.com/api/v3`
     - SiliconFlow：`https://api.siliconflow.cn/v1`（注意不要有 completions 等后缀）

4. **查看终端日志**
   - 查看终端中的具体错误信息
   - 例如：`DeepSeek API Key is Required` 说明没有配置 DeepSeek API Key

---

## OpenAI 兼容服务如何配置？

### 问题描述

想使用 OpenAI 兼容的第三方服务，不知道如何配置。

### 原因

openaliked 服务选项可以填写所有兼容 OpenAI 格式的 LLM 服务。

### 解决方案

### 配置步骤

1. 在 LLM API 配置管理中选择服务类型为 **openaliked**
2. 填写以下信息：
   - **URL**：您的 LLM 服务供应商提供的 API 地址
   - **API Key**：您的 API 密钥
   - **Model**：模型名称

### 常见 OpenAI 兼容服务示例

| 服务 | URL |
|------|-----|
| 火山引擎 | `https://ark.cn-beijing.volces.com/api/v3` |
| SiliconFlow | `https://api.siliconflow.cn/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` |

::: tip 注意
URL 后面不要有 `/completions` 或 `/chat/completions` 等后缀，直接填入基础 API 地址即可。
:::

---

## 翻译质量不满意

### 问题描述

翻译结果质量不理想，有错译或漏译。

### 原因

1. 使用了免费但质量较低的服务
2. PDF 格式复杂（如扫描版、双栏）
3. 专业术语较多

### 解决方案

1. **更换高质量服务**
   - 使用 [deepseek](/zh/guide/configuration.md#deepseek) 或 [aliyunDashScope](/zh/guide/configuration.md#aliyunDashScope)
   - 这些服务翻译质量更好

2. **检查 PDF 质量**
   - 确保不是扫描版 PDF（如果是需要先 OCR）
   - 扫描版 PDF 需要用其他工具进行 OCR 处理

3. **调整引擎设置**
   - 尝试切换 pdf2zh 和 pdf2zh_next 引擎
   - 调整引擎的相关参数

4. **人工校对**
   - 任何机器翻译都无法保证 100% 准确
   - 重要内容建议人工校对

---

## siliconflowfree 漏翻译

### 问题描述

使用 siliconflowfree 服务时，有些内容没有被翻译。

### 原因

siliconflowfree 是基于硅基流动提供的 GLM4-9B 模型，可能存在漏翻译的情况。

### 解决方案

1. **这是已知限制**
   - 免费服务可能会漏翻译一些内容
   - 如果需要高质量翻译，请选择其他服务

2. **更换服务**
   - 配置自己的 API Key 使用付费服务
   - 或使用 openaliked 配置其他兼容服务

3. **重新翻译**
   - 有时候重新翻译一次可以改善结果
