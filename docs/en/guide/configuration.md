# Configuration

This document describes the configuration options for Zotero PDF2zh plugin.

## Plugin Settings

Open "Tools → PDF2zh Preferences" in Zotero to configure the plugin.

![Zotero PDF2zh Preferences](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/preference.png)

## Basic Configuration

### Python Server IP

Set the Python server address.

- **Default**: `http://127.0.0.1:8890`
- **Description**: Modify this if you changed the port or use remote deployment

### Translation Engine

Select the translation engine. The plugin supports two translation engines:

| Feature | PDF2ZH (Legacy) | PDF2ZH Next (New) |
|---------|----------------|-------------------|
| **Maintenance Status** | ❌ No longer actively maintained | ✅ Continuously updated |
| **Translation Speed** | ⚡ Faster | Slightly slower |
| **Custom Fonts** | ✅ Supports custom fonts | ❌ Not supported |
| **Config File** | `config.json` | `config.toml` |
| **Dual Layout Modes** | Basic dual layout only | Supports Left&Right / Top&Bottom modes |
| **Glossary Feature** | ❌ Not supported | ✅ Auto-extract and use glossary |
| **Table Translation** | ❌ Not supported | ✅ Supports table content translation |
| **OCR Compatibility** | ❌ Not supported | ✅ Supports OCR compatibility & auto-OCR |
| **Watermark Removal** | ❌ Not supported | ✅ Supports watermark-free mode |
| **Supported Services** | Relatively fewer | Supports more services (including free siliconflowfree) |
| **Upstream Project** | [Byaidu/PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) | [PDFMathTranslate-next](https://github.com/PDFMathTranslate/PDFMathTranslate-next) |

::: tip Recommendation
Unless you need custom fonts or require maximum speed, we recommend using **PDF2ZH Next** engine.
:::

Switching engines will display the corresponding engine's configuration options.

## Check Server Connection

In the plugin settings page, click the "Check Connection" button next to the "Python Server IP" field to test the connection to the Python service.

- **Connection Successful**: Service is running normally
- **Connection Failed**: Please check:
  - server.py script is running
  - Port number is correct (default 8890)
  - Firewall/antivirus is blocking the connection

## Web Progress Monitoring

After starting the service, visit `http://127.0.0.1:8890` in your browser to monitor translation progress:
- Real-time display of current translation task status
- View translation history
- Preview and download translated files

## QPS and Pool Size Configuration

Refer to your translation service provider's limitations for settings.

### Calculation Formula

```
qps = rpm / 60
```

### Pool Size Rules

| Limit Type | Formula |
|------------|---------|
| qps/rpm limit | `pool size = qps * 10` |
| Concurrency limit | `pool size = max(floor(0.9*official_limit), official_limit-20)`, `qps = pool size` |

::: tip Not sure how to set?
If you don't know how to set it, just set qps and leave pool size at default value 0.
:::

### Examples

#### Zhipu AI

- Check official docs: [Zhipu AI Rate Limits](https://www.bigmodel.cn/dev/howuse/rate-limits)
- Assume RPM = 60, then `qps = 60 / 60 = 1`
- `pool size = 1 * 10 = 10`

#### DeepSeek

DeepSeek v3 has a limit of 150 RPM:
- `qps = 150 / 60 = 2.5`, can be set to 2
- `pool size = 2 * 10 = 20`

## Translation Service Configuration

Click "Add" in "LLM API Configuration Management" to configure translation services.

![LLM API Editor](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/editor.png)

### Configuration Notes

- You can add multiple configurations for the same service
- Only one configuration can be activated at a time
- After configuration, you need to select the service in "Translation Service"

### Field Descriptions

| Field | Description |
|-------|-------------|
| Service Name | Custom configuration name |
| Service Type | Select translation service provider |
| URL | API endpoint address (not required for some services) |
| API Key | API key |
| Model | Model name to use |
| Extra Config | Other optional parameters |

## Translation Service Overview

### Free & No-Configuration Services

| Service Name | Description | Notes |
|--------------|-------------|-------|
| **siliconflowfree** | Based on SiliconFlow's GLM4-9B model, jointly provided by SiliconFlow, pdf2zh_next, and BabelDOC | 1. pdf2zh_next engine only<br>2. No need to select qps, default 40<br>3. May have missing translations |
| **bing/google** | Official machine translation from bing/google | Rate limiting exists, set concurrency to 2 or below if translation fails |

### Services with Benefits/Free Credits

| Service Name | Description | Notes |
|--------------|-------------|-------|
| **openaliked** | Volcano Engine collaboration plan, up to 500k free tokens daily | 1. Credit calculated based on previous day's usage<br>2. Supports high concurrency: 500~1000<br>3. URL: `https://ark.cn-beijing.volces.com/api/v3` |
| **silicon** | Get 14 yuan credit by inviting friends | 1. URL: `https://api.siliconflow.cn/v1`<br>2. Free version has lower thread count, suggest setting to ~6 |
| **zhipu** | Some Zhipu models support free calls | Don't set concurrency too high for free service, suggest within 6 |

### High-Quality Services

| Service Name | Description | Recommended Settings |
|--------------|-------------|---------------------|
| **aliyunDashScope** | Good translation quality, new users get free credits | Select default model option in LLM API configuration |
| **deepseek** | Good translation quality with cache hit mechanism (recommended) | Use deepseek v3 service |

### OpenAI Compatible Services

**openailiked** service option can fill in all LLM services compatible with OpenAI format.

You need to provide:
- **URL**: API address from your LLM service provider
- **API Key**: Your API key
- **Model**: Model name

::: tip Example
For Volcano Engine, URL填写为: `https://ark.cn-beijing.volces.com/api/v3`

**Common OpenAI Compatible Service URLs:**

| Service | URL |
|---------|-----|
| Volcano Engine | `https://ark.cn-beijing.volces.com/api/v3` |
| SiliconFlow | `https://api.siliconflow.cn/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Zhipu AI | `https://open.bigmodel.cn/api/paas/v4` |

::: warning Warning
Don't include `/completions` or `/chat/completions` suffixes in the URL. Just enter the base API address.
:::

## Translation Service Selection Recommendations

### By Use Case

| Use Case | Recommended Service | Reason |
|----------|-------------------|--------|
| **First Try** | siliconflowfree | Completely free, no configuration needed |
| **Light Use** | openaliked / zhipu | Has free credits, cost-effective |
| **Long-term Use** | deepseek (recommended) | Good quality with cache mechanism |
| **High Quality** | deepseek / aliyunDashScope | Best translation results |

### By Budget

- **Zero Budget**: siliconflowfree (may have missing translations)
- **Low Budget**: openaliked (500k token daily) or zhipu (some models free)
- **Medium Budget**: deepseek (cost-effective with cache)
- **Quality Priority**: aliyunDashScope or deepseek

## pdf2zh Engine Configuration

### Custom Fonts

Font file path is a local path.

::: warning Remote Deployment Limitation
If using remote server deployment, this configuration cannot be used. You need to manually modify the `NOTO_FONT_PATH` field in `config.json`.
:::

## pdf2zh_next Engine Configuration

### Dual File Display Mode

- **Left&Right**: Side-by-side comparison mode
- **Top&Bottom**: Top-and-bottom comparison mode

### Extract Glossary

Enabling this will extract glossary from the document but consumes more tokens.

### OCR Workaround

- pdf2zh and pdf2zh_next don't provide document OCR functionality directly
- You need to use other tools to OCR scan files first
- This option is a compatibility solution for post-OCR files

::: tip Compatibility Mode
Compatibility mode generates larger files, don't enable unless necessary.
:::

## Extra Configuration Parameters

Extra configuration parameter names must match fields in the config file.

For example, in pdf2zh_next, openai's extra config:
- `openai_temperature`
- `openai_send_temperature`

These correspond to fields in the `config.toml` file.

::: info Documentation
For more information on extra configuration, please refer to [Extra Parameters](/en/guide/extra-params).
:::

## Command Line Arguments

Parameters available when starting `server.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--enable_venv` | `True` | Enable virtual environment management |
| `--env_tool` | `uv` | Virtual environment tool (uv/conda) |
| `--port` | `8890` | Service port number |
| `--check_update` | `True` | Auto check for updates |
| `--update_source` | `gitee` | Update source (github/gitee) |
| `--enable_mirror` | `True` | Enable domestic mirror |
| `--mirror_source` | USTC mirror | Mirror source address |
| `--enable_winexe` | `False` | Windows exe mode |
| `--winexe_path` | - | Windows exe file path |

### Usage Examples

```shell
# Change port
python server.py --port=9999

# Disable virtual environment management
python server.py --enable_venv=False

# Use conda virtual environment
python server.py --env_tool=conda

# Custom mirror source
python server.py --mirror_source="https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"
```

## Next Steps

- Read [Translation Options](/en/guide/translation-options) to learn about translation features
- Read [Package Updates](/en/guide/package-update) to learn how to update dependency packages
- Check [FAQ](/en/guide/faq/) if you encounter issues
