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

// Execute the XHTML's real save handler: this catches reassignment of a const
// after accepting the compatibility prompt (#399), not just migration logic.
function saveEditor(model: string, supported: boolean, accept = true) {
    const source = readFileSync(
        new URL("../addon/content/llmApiEditor.xhtml", import.meta.url),
        "utf8",
    );
    const handler = source.slice(
        source.indexOf("function saveLLMApi()"),
        source.indexOf("window.saveLLMApi = saveLLMApi;"),
    );
    const elements = {
        service: { value: "deepseek" },
        model: { value: model },
        apiKey: { value: "test-key" },
        apiUrl: { value: "https://api.deepseek.com" },
        activate: { checked: true },
        "extra-fields-container": { getElementsByClassName: () => [] },
    };
    const state = {
        confirmations: 0,
        alerts: [] as string[],
        history: [] as string[][],
        closed: false,
        result: undefined as
            | {
                  success: boolean;
                  data: { model: string; extraData: Record<string, string> };
              }
            | undefined,
    };
    runInNewContext(handler + "\nsaveLLMApi();", {
        document: {
            getElementById: (id: keyof typeof elements) => elements[id],
        },
        window: { arguments: [state], close: () => (state.closed = true) },
        DEPRECATED_DEEPSEEK_MODELS: new Set([
            "deepseek-chat",
            "deepseek-reasoner",
        ]),
        DEFAULT_SERVICES: { deepseek: {} },
        serverSupportsFlashHook: () => supported,
        confirm: () => {
            state.confirmations++;
            return accept;
        },
        alert: (message: string) => state.alerts.push(message),
        t: (key: string) => key,
        saveUserHistory: (...values: string[]) => state.history.push(values),
        isEditMode: false,
        currentData: {},
    });
    return { state, elements };
}

test("accepting the old/unknown server correction saves V4 and closes the editor", () => {
    const { state, elements } = saveEditor("deepseek-flash", false);
    assert.equal(state.confirmations, 1);
    assert.equal(state.result?.success, true);
    assert.equal(state.result?.data.model, "deepseek-v4-flash");
    assert.equal(
        state.result?.data.extraData.deepseek_thinking_mode,
        "disabled",
    );
    assert.equal(elements.model.value, "deepseek-v4-flash");
    assert.equal(state.history[0][1], "deepseek-v4-flash");
    assert.equal(state.closed, true);
});

test("declining correction leaves the editor open without saving or mutating the model", () => {
    const { state, elements } = saveEditor("deepseek-flash", false, false);
    assert.equal(state.result, undefined);
    assert.equal(state.closed, false);
    assert.equal(state.history.length, 0);
    assert.equal(elements.model.value, "deepseek-flash");
});

test("a supported server saves flash without a correction prompt", () => {
    const { state } = saveEditor("deepseek-flash", true);
    assert.equal(state.confirmations, 0);
    assert.equal(state.result?.data.model, "deepseek-flash");
    assert.equal(state.closed, true);
});

test("V4 saves on an older server while unknown DeepSeek spellings stay editable", () => {
    const valid = saveEditor("deepseek-v4-flash", false).state;
    assert.equal(valid.confirmations, 0);
    assert.equal(valid.result?.success, true);
    const invalid = saveEditor("deepseek-flahs", true).state;
    assert.equal(invalid.result, undefined);
    assert.equal(invalid.closed, false);
    assert.deepEqual(invalid.alerts, ["deepseekNonFlashSpellingAlert"]);
});
