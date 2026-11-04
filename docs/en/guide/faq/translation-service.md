# Translation Service

::: tip Coming Soon
English documentation is under construction. Please switch to Chinese for complete documentation.
:::

## Can I use without API configuration?

Yes! Use **siliconflowfree** service with pdf2zh_next engine for free translation (may have some omissions).

## Recommended Services

- **siliconflowfree** - Free, no configuration required
- **deepseek** - High quality, with caching mechanism (recommended)
- **openaliked** - Volcano Engine, 50w token daily quota

## Can I use my own service name?

Yes. When adding an entry under **LLM API Configuration**, type any name (for example `my-gateway`) instead of picking a built-in service.

- Custom names are called through the **OpenAI-compatible** protocol: provide the Base URL, API key and model.
- After saving, the name appears in the **Translation Service** dropdown and can be selected like a built-in service.
- Multiple custom names can stay active at the same time; switching providers only requires changing the Translation Service selection.
- Both engines work: pdf2zh 1.x runs the entry through `openailiked`, pdf2zh_next through `openaicompatible`.

::: tip
Do not reuse a built-in service name (such as `openai`, `deepseek` or `openailiked`); it will follow that service's rules.
:::
