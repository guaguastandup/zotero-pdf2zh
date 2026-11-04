import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
import {
    wenyiPipelineOptions,
    WENYI_DEFAULTS,
} from "../src/modules/wenyiConfig.ts";

const xhtml = fs.readFileSync(
    new URL("../addon/content/preferences.xhtml", import.meta.url),
    "utf8",
);
const js = ts.transpileModule(
    fs.readFileSync(
        new URL("../src/modules/preferenceScript.ts", import.meta.url),
        "utf8",
    ),
    {
        compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
        },
    },
).outputText;

function setup() {
    const prefs: Record<string, unknown> = {
        mono: false,
        dual: true,
        "mono-cut": true,
        skipLastPages: 3,
        ...Object.fromEntries(
            Object.entries(WENYI_DEFAULTS).map(([key, value]) => [
                `wenyi.${key}`,
                value,
            ]),
        ),
    };
    const classes = new Map(
        [
            "pdf1x-config",
            "pdf2x-config",
            "wenyi-config",
            "legacy-pdf-config",
        ].map((name) => [name, [{ style: { display: "" } }]]),
    );
    const listeners = new Map<
        string,
        (event: { target: { value: string } }) => void
    >();
    const controls = new Map(
        Object.keys(WENYI_DEFAULTS).map((key) => [
            `wenyi-${key}`,
            {
                disabled: false,
                value: "",
                addEventListener: (
                    event: string,
                    listener: (event: { target: { value: string } }) => void,
                ) => listeners.set(`wenyi-${key}:${event}`, listener),
            },
        ]),
    );
    const document = {
        getElementById: () => null,
        createElement: () => ({}),
        querySelectorAll: (selector: string) =>
            classes.get(selector.slice(1)) ?? [],
        querySelector: (selector: string) =>
            controls.get(selector.replace(/^#zotero-prefpane-pdf2zh-/, "")) ??
            null,
    };
    const context = vm.createContext({
        addon: { data: { prefs: { window: { document } } } },
        ztoolkit: { log() {} },
    });
    const exports: any = {};
    const imports: Record<string, any> = {
        "../../package.json": { config: { addonRef: "pdf2zh" } },
        "../utils/prefs": {
            getPref: (key: string) => prefs[key],
            setPref: (key: string, value: unknown) => {
                prefs[key] = value;
            },
        },
        "./wenyiConfig": { wenyiPipelineOptions },
    };
    vm.runInContext(
        `(function(require, exports) {${js}
        exports.changeEngine = handleEngineChange;
        exports.bindEvents = bindPrefEvents;})`,
        context,
    )((name: string) => imports[name] ?? {}, exports);
    exports.bindEvents();
    const control = (name: string) => controls.get(name)!;
    const visible = (name: string) =>
        classes.get(name)![0].style.display !== "none";
    const select = (name: string, value: string) => {
        const listener = listeners.get(`${name}:change`);
        assert.ok(listener, `${name} change listener`);
        control(name).value = value;
        listener({ target: control(name) });
    };
    return { change: exports.changeEngine, control, visible, prefs, select };
}

test("engine switches show only the matching settings and preserve saved preferences", () => {
    const section = xhtml.match(
        /<vbox\b[^>]*class="legacy-pdf-config"[^>]*>[\s\S]*?<\/vbox>/,
    );
    assert.ok(section);
    assert.match(section[0], /data-l10n-id="pref-gen"/);
    assert.match(section[0], /id="zotero-prefpane-__addonRef__-mono"/);
    assert.match(section[0], /id="zotero-prefpane-__addonRef__-mono-open"/);
    const ui = setup();
    const before = { ...ui.prefs };
    for (const [engine, selected] of [
        ["wenyi", "wenyi-config"],
        ["pdf2zh_next", "pdf2x-config"],
        ["pdf2zh", "pdf1x-config"],
    ]) {
        ui.change(engine);
        for (const name of ["wenyi-config", "pdf1x-config", "pdf2x-config"]) {
            assert.equal(
                ui.visible(name),
                name === selected,
                `${engine}: ${name}`,
            );
        }
        assert.equal(ui.visible("legacy-pdf-config"), engine !== "wenyi");
        assert.deepEqual(ui.prefs, before);
    }
});

test("three-draft precision defaults off and restores the saved polish choice when disabled", () => {
    const ui = setup();
    ui.prefs.engine = "wenyi";
    ui.prefs["wenyi.translation_mode"] = "";
    ui.prefs["wenyi.polish"] = "false";
    ui.change("wenyi");
    assert.equal(ui.control("wenyi-translation_mode").value, "standard");
    assert.equal(ui.control("wenyi-polish").value, "false");
    assert.equal(ui.control("wenyi-polish").disabled, false);
    ui.select("wenyi-translation_mode", "best_of_three");
    assert.equal(ui.prefs["wenyi.translation_mode"], "best_of_three");
    assert.equal(ui.control("wenyi-translation_mode").value, "best_of_three");
    assert.equal(ui.control("wenyi-polish").value, "true");
    assert.equal(ui.control("wenyi-polish").disabled, true);
    assert.equal(ui.prefs["wenyi.polish"], "false");
    ui.change("pdf2zh_next");
    ui.change("wenyi");
    assert.equal(ui.control("wenyi-translation_mode").value, "best_of_three");
    ui.select("wenyi-translation_mode", "standard");
    assert.equal(ui.prefs["wenyi.translation_mode"], "standard");
    assert.equal(ui.control("wenyi-polish").value, "false");
    assert.equal(ui.control("wenyi-polish").disabled, false);
});

test("model controls stay in the shared LLM API editor", () => {
    assert.doesNotMatch(xhtml, /wenyi-thinking|wenyi-reasoning_effort/);
    const editor = fs.readFileSync(
        new URL("../addon/content/llmApiEditor.xhtml", import.meta.url),
        "utf8",
    );
    assert.match(editor, /deepseek_thinking_mode/);
    assert.match(editor, /deepseek_reasoning_effort/);
});

test("empty preferences display defaults without rewriting saved values", () => {
    const ui = setup();
    ui.prefs["wenyi.review"] = "";
    ui.prefs["wenyi.polish"] = "false";
    ui.prefs["wenyi.book_understanding"] = "";
    const before = { ...ui.prefs };
    ui.change("wenyi");
    assert.equal(ui.control("wenyi-review").value, "true");
    assert.equal(ui.control("wenyi-polish").value, "false");
    assert.equal(ui.control("wenyi-book_understanding").value, "true");
    assert.deepEqual(ui.prefs, before);
});

test("Wenyi controls bind supported choices and defaults with localized labels", () => {
    const registered = new Map<string, unknown>();
    vm.runInNewContext(
        fs.readFileSync(new URL("../addon/prefs.js", import.meta.url), "utf8"),
        { pref: (key: string, value: unknown) => registered.set(key, value) },
    );
    for (const [key, value] of Object.entries(WENYI_DEFAULTS)) {
        const select = xhtml.match(
            new RegExp(
                `<html:select\\s+id="zotero-prefpane-__addonRef__-wenyi-${key}"[\\s\\S]*?</html:select>`,
            ),
        );
        assert.ok(select, key);
        assert.ok(
            select[0].includes(
                `preference="extensions.zotero.__addonRef__.wenyi.${key}"`,
            ),
            key,
        );
        const values = Array.from(
            select[0].matchAll(/<html:option\s+value="([^"]*)"/g),
            (match) => match[1],
        );
        assert.deepEqual(
            values.sort(),
            key === "translation_mode"
                ? ["best_of_three", "standard"]
                : ["false", "true"],
            key,
        );
        assert.equal(
            registered.get(`__prefsPrefix__.wenyi.${key}`),
            value,
            key,
        );
    }
    for (const key of ["thinking", "reasoning_effort", "max_concurrency"]) {
        assert.equal(registered.has(`__prefsPrefix__.wenyi.${key}`), false);
    }
    const ids = Array.from(
        xhtml.matchAll(/data-l10n-id="(pref-wenyi-[^"]+)"/g),
    );
    for (const language of ["en-US", "zh-CN"]) {
        const messages = fs.readFileSync(
            new URL(
                `../addon/locale/${language}/preferences.ftl`,
                import.meta.url,
            ),
            "utf8",
        );
        for (const [, id] of ids) {
            assert.match(messages, new RegExp(`^${id}\\s*=`, "m"));
        }
    }
});
