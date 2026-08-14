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
| **Dual Layout Modes** | Basic dual layout only | Side-by-side / alternating original and translated pages |
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

Current `pdf2zh_next` treats these as separate controls:

- **QPS** limits the request rate sent to the translation service.
- **Pool Size** limits the number of concurrent translation workers.
- **Pool Size = 0 (recommended default)** leaves the worker count unset so `pdf2zh_next` follows QPS for the worker count.

The old `pool size = qps * 10` guidance no longer matches current `pdf2zh_next` behavior. Multiplying workers by ten can unnecessarily increase local pressure and make provider rate limits easier to hit.

::: tip Not sure how to set it?
Usually, set **QPS** according to your provider's current limits and leave **Pool Size at 0**. Set Pool Size manually only when your provider has a separate concurrency limit or when you intentionally want to cap local workers.
:::

If a provider only publishes RPM, a rough conversion is:

```text
qps = rpm / 60
```

Account, model, and plan limits change over time, so prefer the provider's current official documentation over fixed historical values in this project documentation.

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
| **siliconflowfree** | Free translation service exposed through pdf2zh_next | pdf2zh_next only; no API key required; free service availability and rate limits may vary |
| **bing/google** | Machine translation services | If rate limited, lower QPS |

### Credits, Pricing, and Rate Limits

Provider credits, model availability, and rate limits change frequently. Check the provider's current page before relying on old fixed concurrency or quota values.

### High-Quality Services

| Service Name | Description | Recommended Settings |
|--------------|-------------|---------------------|
| **aliyunDashScope** | Good translation quality | Select a currently available model in the LLM API configuration |
| **deepseek** | Good translation quality with DeepSeek V4 support | Choose `deepseek-v4-pro` / `deepseek-v4-flash`; for PDF translation, keeping thinking disabled is the cost-conscious default |

See [Extra Parameters](/en/guide/extra-params) for DeepSeek V4 thinking controls.

### OpenAI Compatible Services

**openailiked** can be used with LLM services that expose an OpenAI-compatible API.

You need to provide:
- **URL**: API address from your LLM service provider
- **API Key**: Your API key
- **Model**: Model name

::: tip Example
For Volcano Engine, use the base URL `https://ark.cn-beijing.volces.com/api/v3`.

**Common OpenAI Compatible Service URLs:**

| Service | URL |
|---------|-----|
| Volcano Engine | `https://ark.cn-beijing.volces.com/api/v3` |
| SiliconFlow | `https://api.siliconflow.cn/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Zhipu AI | `https://open.bigmodel.cn/api/paas/v4` |

::: warning Warning
Don't include `/completions` or `/chat/completions` suffixes in the URL. Enter the base API address only.
:::

## Translation Service Selection Recommendations

Pricing, free quotas, and rate-limit policies change over time. Choose a service based on current availability, translation quality for your target language, price, and the actual QPS/concurrency limits on your account.

## pdf2zh Engine Configuration

### Custom Fonts

Font file path is a local path.

::: warning Remote Deployment Limitation
If using remote server deployment, this configuration cannot be used. You need to manually modify the `NOTO_FONT_PATH` field in `config.json`.
:::

## pdf2zh_next Engine Configuration

### Dual Layout and Ordering

- **Side by Side / LR**: original and translated content are shown side-by-side on the same page.
- **Alternating Pages / TB**: original and translated pages alternate. Older UI/docs called this “Top & Bottom”; that label does not describe the current upstream behavior.
- **Translation First**: disabled by default. With the upstream default ordering, LR mode normally means **original on the left and translation on the right**. Enabling it reverses the order, putting the translation on the left.

::: warning Compatibility mode and ordering
“Enhance compatibility” is not only a rendering toggle. For some problematic PDFs, the upstream compatibility path may require translated pages first. Therefore the final output may still be translation-first even when the standalone “Translation First” checkbox is off while compatibility mode is enabled.
:::

### Keep Only Actually Translated Pages

This option is meaningful only when a page range is selected. In this project, a common way to create a page range is “Skip Last Pages”. For example, if you skip the last two pages, enabling this option removes pages outside the translated range from the output PDF.

### Extract Glossary

Enabling this will extract a glossary from the document but consumes more tokens.

### OCR Workaround

- pdf2zh/pdf2zh_next do not provide a complete OCR pipeline by themselves
- You can OCR scanned documents with another tool first
- The OCR-related options here mainly improve compatibility with those PDFs

::: tip Compatibility Mode
Compatibility mode may change several processing behaviors. Leave it off unless you encounter rendering errors, broken text layers, or similar compatibility problems.
:::

## Extra Configuration Parameters

Extra configuration parameter names must match fields in the config file.

For example, in pdf2zh_next, OpenAI extra parameters include:
- `openai_temperature`
- `openai_send_temperature`

These correspond to fields in `config.toml`.

::: info Documentation
For more information, see [Extra Parameters](/en/guide/extra-params).
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
