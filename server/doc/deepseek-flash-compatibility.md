# DeepSeek Flash thinking compatibility (experimental)

## Why

pdf2zh-next 2.9.0 recognizes only the model-name prefix deepseek-v4- when
DeepSeekSettings.transform() writes the thinking control into OpenAI extra_body.
The current official model deepseek-flash defaults to thinking enabled if this
field is absent. Ignoring it can increase charges.

## Supported behavior

- The actual deepseek-flash model ID is kept (no alias rewrite).
- Disabled explicitly sends extra_body = {"thinking": {"type": "disabled"}}.
- Enabled passes the selected high/max reasoning effort.
- The hook wraps only DeepSeekSettings.transform() and restores it afterwards.
- The Python engine must be pdf2zh-next 2.9.0 (uv, conda, or system Python).
- On Windows, the standalone EXE cannot load this patch; it rejects
  deepseek-flash requests instead of silently incurring reasoning charges.
- Old Servers and unknown Python engine versions fail closed before API calls.
- The legacy deepseek-v4-pro and deepseek-v4-flash pathways stay unchanged.

## Verification

The tests validate actual Pydantic settings conversion and final extra_body
without an API call, including macOS/Windows/Linux CI. End-to-end provider
confirmation is still required before distribution.

With a small PDF and a deliberately low API quota, verify the provider
request log has thinking.type=disabled and zero reasoning tokens; also verify
the previous DeepSeek V4 model still functions.

Official API: https://api-docs.deepseek.com/guides/thinking_mode/
Upstream issue: https://github.com/PDFMathTranslate-next/PDFMathTranslate-next/issues/360
