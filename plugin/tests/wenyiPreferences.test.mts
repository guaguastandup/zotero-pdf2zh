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

function setup(saved: Record<string, unknown> = {}) {
    const prefs: Record<string, unknown> = {
        engine: "wenyi",
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
        ...saved,
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
        (event: { target: { checked: boolean } }) => void
    >();
    const controls = new Map(
        Object.keys(WENYI_DEFAULTS).map((key) => [
            `wenyi-${key}`,
            {
                disabled: false,
                checked: false,
                addEventListener: (
                    event: string,
                    listener: (event: { target: { checked: boolean } }) => void,
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
    const check = (name: string, checked: boolean) => {
        const listener = listeners.get(`${name}:command`);
        assert.ok(listener, `${name} command listener`);
        assert.equal(control(name).disabled, false);
        control(name).checked = checked;
        listener({ target: control(name) });
    };
    return { change: exports.changeEngine, control, visible, prefs, check };
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
    assert.equal(ui.control("wenyi-translation_mode").checked, false);
    assert.equal(ui.control("wenyi-polish").checked, false);
    assert.equal(ui.control("wenyi-polish").disabled, false);
    ui.check("wenyi-translation_mode", true);
    assert.equal(ui.prefs["wenyi.translation_mode"], "best_of_three");
    assert.equal(ui.control("wenyi-translation_mode").checked, true);
    assert.equal(ui.control("wenyi-polish").checked, true);
    assert.equal(ui.control("wenyi-polish").disabled, true);
    assert.equal(ui.prefs["wenyi.polish"], "false");
    ui.change("pdf2zh_next");
    ui.change("wenyi");
    assert.equal(ui.control("wenyi-translation_mode").checked, true);
    const reopened = setup(ui.prefs);
    reopened.change("wenyi");
    assert.equal(reopened.control("wenyi-polish").checked, true);
    assert.equal(reopened.control("wenyi-polish").disabled, true);
    ui.check("wenyi-translation_mode", false);
    assert.equal(ui.prefs["wenyi.translation_mode"], "standard");
    assert.equal(ui.control("wenyi-polish").checked, false);
    assert.equal(ui.control("wenyi-polish").disabled, false);
});

for (const key of ["book_understanding", "polish", "review"]) {
    test(`${key} checkbox saves both states and restores them when reopened`, () => {
        const ui = setup();
        ui.change("wenyi");
        const before = { ...ui.prefs };
        for (const checked of [false, true]) {
            ui.check(`wenyi-${key}`, checked);
            assert.deepEqual(ui.prefs, {
                ...before,
                [`wenyi.${key}`]: String(checked),
            });
            const reopened = setup(ui.prefs);
            reopened.change("wenyi");
            assert.equal(reopened.control(`wenyi-${key}`).checked, checked);
        }
    });
}

test("Wenyi checkboxes are arranged in two rows of two in workflow order", () => {
    const section = xhtml.match(
        /<vbox class="wenyi-config"[^>]*>([\s\S]*?)<\/vbox>/,
    );
    assert.ok(section);
    const rows = Array.from(
        section[1].matchAll(
            /<hbox\b[^>]*>\s*(<hbox\b[\s\S]*?<\/hbox>\s*<hbox\b[\s\S]*?<\/hbox>)\s*<\/hbox>/g,
        ),
        ([, row]) =>
            Array.from(
                row.matchAll(
                    /<checkbox\s+id="zotero-prefpane-__addonRef__-wenyi-([^"]+)"/g,
                ),
                ([, key]) => key,
            ),
    );
    assert.deepEqual(rows, [
        ["book_understanding", "translation_mode"],
        ["polish", "review"],
    ]);
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
    assert.equal(ui.control("wenyi-review").checked, true);
    assert.equal(ui.control("wenyi-polish").checked, false);
    assert.equal(ui.control("wenyi-book_understanding").checked, true);
    assert.deepEqual(ui.prefs, before);
});

test("Wenyi controls use native checkboxes with localized labels and compatible defaults", () => {
    const registered = new Map<string, unknown>();
    vm.runInNewContext(
        fs.readFileSync(new URL("../addon/prefs.js", import.meta.url), "utf8"),
        { pref: (key: string, value: unknown) => registered.set(key, value) },
    );
    for (const [key, value] of Object.entries(WENYI_DEFAULTS)) {
        const checkbox = xhtml.match(
            new RegExp(
                `<checkbox\\s+id="zotero-prefpane-__addonRef__-wenyi-${key}"[^>]*/>`,
            ),
        );
        assert.ok(checkbox, key);
        // String-valued preferences must not use Zotero's boolean checkbox binding.
        assert.doesNotMatch(checkbox[0], /\bpreference=/);
        assert.match(
            xhtml,
            new RegExp(
                `<html:label\\s+for="zotero-prefpane-__addonRef__-wenyi-${key}"\\s+data-l10n-id="pref-wenyi-[^"]+"\\s*/>`,
            ),
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
