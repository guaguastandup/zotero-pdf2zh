# Configuration

::: tip Coming Soon
English documentation is under construction. Please switch to Chinese for complete documentation.
:::

## Plugin Settings

Open "Tools → PDF2zh Preferences" in Zotero to configure the plugin.

## Basic Configuration

### Python Server IP

Set the Python server address.

- **Default**: `http://127.0.0.1:8890`
- **Description**: Modify this if you changed the port or use remote deployment

### Translation Engine

Select the translation engine.

- **pdf2zh**: Based on PDFMathTranslate
- **pdf2zh_next**: Next-generation engine with more features

## QPS and Pool Size

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
