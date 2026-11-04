import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
import {
    initializeWenyiPreferences,
    WENYI_DEFAULTS,
} from "../src/modules/wenyiConfig.ts";

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
        "wenyi.reasoning_effort": "max",
    };
    const classes = new Map(
        [
            "pdf1x-config",
            "pdf2x-config",
            "wenyi-config",
            "legacy-llm-config",
            "legacy-pdf-config",
        ].map((name) => [name, [{ style: { display: "" } }]]),
    );
    const listeners = new Map<
        string,
        (event: { target: { value: string } }) => void
    >();
    const controls = new Map(
        [
            "mono",
            "dual",
            "mono-cut",
            "dual-cut",
            "crop-compare",
            "compare",
            "skipLastPages",
            ...Object.keys(WENYI_DEFAULTS).map((key) => `wenyi-${key}`),
        ].map((name) => [
            `#zotero-prefpane-pdf2zh-${name}`,
            {
                disabled: false,
                checked: false,
                value: "",
                addEventListener: (
                    event: string,
                    listener: (event: { target: { value: string } }) => void,
                ) => listeners.set(`${name}:${event}`, listener),
            },
        ]),
    );
    const document = {
        getElementById: () => null,
        createElement: () => ({ cloneNode: () => ({}) }),
        getElementsByClassName: (name: string) => classes.get(name) ?? [],
        querySelectorAll: (selector: string) =>
            classes.get(selector.slice(1)) ?? [],
        querySelector: (selector: string) => controls.get(selector) ?? null,
    };
    const context = vm.createContext({
        addon: { data: { prefs: { window: { document } } } },
        ztoolkit: { log() {} },
    });
    const source = fs.readFileSync(
        new URL("../src/modules/preferenceScript.ts", import.meta.url),
        "utf8",
    );
    const js = ts.transpileModule(source, {
        compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
        },
    }).outputText;
    const exports: any = {};
    const imports: Record<string, any> = {
        "../../package.json": { config: { addonRef: "pdf2zh" } },
        "../utils/prefs": {
            getPref: (key: string) => prefs[key],
            setPref: (key: string, value: unknown) => {
                prefs[key] = value;
            },
        },
        "./wenyiConfig": { initializeWenyiPreferences, WENYI_DEFAULTS },
    };
    vm.runInContext(
        `(function(require, exports) {${js}
        exports.changeEngine = handleEngineChange;
        exports.bindEvents = bindPrefEvents;})`,
        context,
    )((name: string) => imports[name] ?? {}, exports);
    exports.bindEvents();
    const control = (name: string) =>
        controls.get(`#zotero-prefpane-pdf2zh-${name}`)!;
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

test("the Wenyi engine option displays only the engine name", () => {
    const xhtml = fs.readFileSync(
        new URL("../addon/content/preferences.xhtml", import.meta.url),
        "utf8",
    );
    const option = xhtml.match(
        /<html:option\s+value="wenyi"\s*>([\s\S]*?)<\/html:option\s*>/,
    );
    assert.ok(option);
    assert.equal(option[1].trim(), "Wenyi");
});

test("engine switches show only the matching settings and preserve saved preferences", () => {
    const ui = setup();
    const before = { ...ui.prefs };
    ui.change("wenyi");
    assert.equal(ui.visible("wenyi-config"), true);
    for (const name of [
        "pdf1x-config",
        "pdf2x-config",
        "legacy-llm-config",
        "legacy-pdf-config",
    ]) {
        assert.equal(ui.visible(name), false);
    }
    assert.equal(ui.control("mono").checked, true);
    assert.equal(ui.control("mono").disabled, true);
    assert.equal(ui.control("dual").checked, false);
    ui.change("pdf2zh_next");
    assert.equal(ui.visible("pdf2x-config"), true);
    assert.equal(ui.visible("pdf1x-config"), false);
    assert.equal(ui.visible("wenyi-config"), false);
    assert.equal(ui.visible("legacy-llm-config"), true);
    assert.equal(ui.visible("legacy-pdf-config"), true);
    assert.equal(ui.control("mono").checked, false);
    assert.equal(ui.control("dual").checked, true);
    assert.equal(ui.control("dual").disabled, false);
    assert.equal(ui.control("skipLastPages").value, "3");
    ui.change("pdf2zh");
    assert.equal(ui.visible("pdf1x-config"), true);
    assert.equal(ui.visible("pdf2x-config"), false);
    assert.deepEqual(ui.prefs, before);
});

test("the entire default output-file section is hidden for Wenyi only", () => {
    const xhtml = fs.readFileSync(
        new URL("../addon/content/preferences.xhtml", import.meta.url),
        "utf8",
    );
    const section = xhtml.match(
        /<vbox\b([^>]*)>\s*<html:h3 data-l10n-id="pref-gen"[\s\S]*?<\/vbox>/,
    );
    assert.ok(section);
    assert.match(section[1], /\bclass="legacy-pdf-config"/);
    assert.match(section[0], /id="zotero-prefpane-__addonRef__-mono"/);
    assert.match(section[0], /id="zotero-prefpane-__addonRef__-mono-open"/);
    const ui = setup();
    const before = { ...ui.prefs };
    ui.change("wenyi");
    assert.equal(ui.visible("legacy-pdf-config"), false);
    for (const engine of ["pdf2zh", "pdf2zh_next"]) {
        ui.change(engine);
        assert.equal(ui.visible("legacy-pdf-config"), true);
    }
    assert.deepEqual(ui.prefs, before);
});

test("disabling thinking disables effort without deleting its saved value", () => {
    const ui = setup();
    ui.change("wenyi");
    assert.equal(ui.control("wenyi-reasoning_effort").disabled, true);
    ui.prefs["wenyi.thinking"] = "true";
    ui.change("wenyi");
    assert.equal(ui.control("wenyi-reasoning_effort").disabled, false);
    assert.equal(ui.prefs["wenyi.reasoning_effort"], "max");
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

test("retired empty choices migrate to visible values without replacing explicit selections", () => {
    const ui = setup();
    delete ui.prefs["wenyi.thinking"];
    ui.prefs["wenyi.review"] = "";
    ui.prefs["wenyi.polish"] = "false";
    ui.prefs["wenyi.book_understanding"] = "";
    ui.prefs["wenyi.reasoning_effort"] = "";
    ui.change("wenyi");
    assert.equal(ui.prefs["wenyi.thinking"], "false");
    assert.equal(ui.control("wenyi-thinking").value, "false");
    assert.equal(ui.control("wenyi-reasoning_effort").disabled, true);
    assert.equal(ui.control("wenyi-reasoning_effort").value, "high");
    assert.equal(ui.control("wenyi-review").value, "true");
    assert.equal(ui.control("wenyi-polish").value, "false");
    assert.equal(ui.control("wenyi-book_understanding").value, "true");
    ui.prefs["wenyi.thinking"] = "true";
    ui.change("wenyi");
    assert.equal(ui.control("wenyi-thinking").value, "true");
    assert.equal(ui.control("wenyi-reasoning_effort").disabled, false);
});

test("Wenyi selects have concrete choices and no default option", () => {
    const xhtml = fs.readFileSync(
        new URL("../addon/content/preferences.xhtml", import.meta.url),
        "utf8",
    );
    for (const key of [
        "book_understanding",
        "translation_mode",
        "polish",
        "review",
        "thinking",
        "reasoning_effort",
    ]) {
        const select = xhtml.match(
            new RegExp(
                `<html:select\\s+id="zotero-prefpane-__addonRef__-wenyi-${key}"[\\s\\S]*?</html:select>`,
            ),
        );
        assert.ok(select, key);
        const values = Array.from(
            select[0].matchAll(/<html:option\s+value="([^"]*)"/g),
            (match) => match[1],
        );
        assert.deepEqual(
            values,
            key === "reasoning_effort"
                ? ["high", "max"]
                : key === "translation_mode"
                  ? ["best_of_three", "standard"]
                  : ["true", "false"],
        );
    }
});

test("Wenyi settings omit explanatory paragraphs and the redundant Review field name", () => {
    const xhtml = fs.readFileSync(
        new URL("../addon/content/preferences.xhtml", import.meta.url),
        "utf8",
    );
    assert.doesNotMatch(
        xhtml,
        /data-l10n-id="pref-wenyi-(help|defaults-help|model-help)"/,
    );
    for (const [language, label] of [
        ["en-US", "Whole-document Review"],
        ["zh-CN", "全书审校"],
    ]) {
        const messages = fs.readFileSync(
            new URL(
                `../addon/locale/${language}/preferences.ftl`,
                import.meta.url,
            ),
            "utf8",
        );
        assert.match(
            messages,
            new RegExp(`^pref-wenyi-review\\s*=\\s*${label}$`, "m"),
        );
    }
});

test("Chinese Wenyi settings use only Chinese labels and localized effort choices", () => {
    const messages = fs.readFileSync(
        new URL("../addon/locale/zh-CN/preferences.ftl", import.meta.url),
        "utf8",
    );
    assert.match(messages, /^pref-wenyi-translation-mode\s*=\s*三译合润$/m);
    const labels = Array.from(
        messages.matchAll(
            /^(?:pref-wenyi-[\w-]+|[ \t]+\.placeholder)[ \t]*=[ \t]*(.*)$/gm,
        ),
        (match) => match[1],
    );
    assert.ok(labels.length > 0);
    for (const label of labels) assert.doesNotMatch(label, /[A-Za-z]/);
    const xhtml = fs.readFileSync(
        new URL("../addon/content/preferences.xhtml", import.meta.url),
        "utf8",
    );
    for (const key of ["high", "max"]) {
        assert.match(
            xhtml,
            new RegExp(
                `<html:option\\s+value="${key}"\\s+data-l10n-id="pref-wenyi-effort-${key}"\\s*/>`,
            ),
        );
    }
});

test("all native Wenyi controls are preference-bound and localized in both languages", () => {
    const xhtml = fs.readFileSync(
        new URL("../addon/content/preferences.xhtml", import.meta.url),
        "utf8",
    );
    const defaults = fs.readFileSync(
        new URL("../addon/prefs.js", import.meta.url),
        "utf8",
    );
    const registered = new Map<string, unknown>();
    vm.runInNewContext(defaults, {
        pref: (key: string, value: unknown) => registered.set(key, value),
    });
    assert.doesNotMatch(
        xhtml,
        /wenyi-max_concurrency|pref-wenyi-max-concurrency/,
    );
    assert.equal(
        registered.has("__prefsPrefix__.wenyi.max_concurrency"),
        false,
    );
    for (const key of [
        "book_understanding",
        "translation_mode",
        "polish",
        "review",
        "thinking",
        "reasoning_effort",
    ]) {
        assert.ok(
            xhtml.includes(`id="zotero-prefpane-__addonRef__-wenyi-${key}"`),
        );
        assert.ok(
            xhtml.includes(
                `preference="extensions.zotero.__addonRef__.wenyi.${key}"`,
            ),
        );
        assert.equal(
            registered.get(`__prefsPrefix__.wenyi.${key}`),
            WENYI_DEFAULTS[key as keyof typeof WENYI_DEFAULTS],
        );
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
