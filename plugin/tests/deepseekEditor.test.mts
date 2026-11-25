import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";

// Run the actual editor startup handler with a minimal DOM. No Zotero or
// network access is required to reproduce saved-setting migration bugs.
function openEditor(model: string, saved: Record<string, string> = {}) {
    const controls = new Map(
        Object.entries({
            deepseek_thinking_mode: "disabled",
            deepseek_reasoning_effort: "high",
            ...saved,
        }).map(([key, value]) => [
            key,
            { value, tagName: "SELECT", options: [], disabled: false },
        ]),
    );
    const elements = {
        service: { value: "deepseek" },
        model: { value: model },
        "fetch-models-status": { textContent: "" },
    };
    const handlers = new Map<string, () => void>();
    runInNewContext(
        readFileSync(
            new URL(
                "../addon/content/llmApiEditorEnhancements.js",
                import.meta.url,
            ),
            "utf8",
        ),
        {
            document: {
                documentElement: { lang: "en" },
                querySelector: () => null,
                getElementById: (id: keyof typeof elements) => elements[id],
                addEventListener: (event: string, callback: () => void) =>
                    handlers.set(event, callback),
            },
            currentData: { extraData: saved },
            findExtraFieldRow: (key: string) =>
                controls.has(key)
                    ? { querySelector: () => controls.get(key), style: {} }
                    : undefined,
            removeExtraFieldRow: (key: string) => controls.delete(key),
            addExtraFieldRow: (key: string, value: string) =>
                controls.set(key, {
                    value,
                    tagName: "INPUT",
                    options: [],
                    disabled: false,
                }),
            bindInputSelectValue: (value: string) => {
                elements.model.value = value;
            },
            updateModelOptions: () => {},
            updateDeepSeekReasoningEffortState: () => {
                controls.get("deepseek_reasoning_effort")!.disabled =
                    controls.get("deepseek_thinking_mode")!.value !== "enabled";
            },
        },
    );
    handlers.get("DOMContentLoaded")!();
    return { controls, elements };
}

test("opening an enabled configuration preserves the user's saved choice", () => {
    const { controls } = openEditor("deepseek-v4-flash", {
        deepseek_thinking_mode: "enabled",
        deepseek_reasoning_effort: "max",
    });
    assert.equal(controls.get("deepseek_thinking_mode")?.value, "enabled");
    assert.equal(controls.get("deepseek_reasoning_effort")?.value, "max");
});

test("obsolete opt-in metadata is removed without changing the mode", () => {
    for (const mode of ["enabled", "disabled"]) {
        const { controls } = openEditor("deepseek-v4-flash", {
            deepseek_thinking_mode: mode,
            deepseek_thinking_explicit_opt_in: "true",
        });
        assert.equal(controls.get("deepseek_thinking_mode")?.value, mode);
        assert.equal(controls.has("deepseek_thinking_explicit_opt_in"), false);
    }
});

test("a new V4 configuration defaults to thinking disabled", () => {
    const { controls } = openEditor("deepseek-v4-flash");
    assert.equal(controls.get("deepseek_thinking_mode")?.value, "disabled");
});

test("retired aliases migrate to V4 with thinking disabled by default", () => {
    for (const [model, expected] of [
        ["deepseek-chat", "disabled"],
        ["deepseek-reasoner", "disabled"],
    ]) {
        const { controls, elements } = openEditor(model);
        assert.equal(elements.model.value, "deepseek-v4-flash");
        assert.equal(controls.get("deepseek_thinking_mode")?.value, expected);
        assert.equal(
            controls.get("deepseek_reasoning_effort")?.disabled,
            expected !== "enabled",
        );
    }
});

test("an explicit saved mode takes priority over legacy model defaults", () => {
    for (const [model, mode] of [
        ["deepseek-reasoner", "disabled"],
        ["deepseek-chat", "enabled"],
    ]) {
        const { controls, elements } = openEditor(model, {
            deepseek_thinking_mode: mode,
        });
        assert.equal(elements.model.value, "deepseek-v4-flash");
        assert.equal(controls.get("deepseek_thinking_mode")?.value, mode);
    }
});
