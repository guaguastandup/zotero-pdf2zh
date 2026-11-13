import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
const source = readFileSync(
    new URL("../src/modules/preferenceScript.ts", import.meta.url),
    "utf8",
);
const js = ts.transpileModule(source, {
    compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
    },
}).outputText;
function fixture(input: string | undefined, saved = "", launchFails = false) {
    const opened: string[] = [];
    const alerts: string[] = [];
    const exports: any = {};
    vm.runInNewContext(js, {
        exports,
        URL,
        require: (name: string) =>
            name.endsWith("package.json")
                ? { config: { addonRef: "pdf2zh" } }
                : name.endsWith("/prefs")
                  ? { getPref: () => saved }
                  : {},
        Zotero: {
            locale: "en-US",
            launchURL: (url: string) => {
                if (launchFails) throw new Error("secret");
                opened.push(url);
            },
        },
    });
    const window = {
        document: {
            getElementById: () =>
                input === undefined ? null : { value: input },
        },
        alert: (message: string) => alerts.push(message),
    };
    return { opened, alerts, open: () => exports.openServerDashboard(window) };
}
test("opens default dashboard without requiring a running server", async () => {
    const f = fixture("");
    await f.open();
    assert.deepEqual(f.opened, ["http://localhost:8890/"]);
    assert.deepEqual(f.alerts, []);
});
test("uses current edited remote base URL and strips query secrets", async () => {
    const f = fixture(
        " https://remote.example/pdf2zh/?token=secret#secret ",
        "http://old.example",
    );
    await f.open();
    assert.deepEqual(f.opened, ["https://remote.example/pdf2zh/"]);
});
test("uses saved URL if the input is unavailable", async () => {
    const f = fixture(undefined, "http://remote.example:8890");
    await f.open();
    assert.deepEqual(f.opened, ["http://remote.example:8890/"]);
});
for (const input of [
    "javascript:alert(1)",
    "file:///secret",
    "ftp://host",
    "http://user:secret@host",
    "not a URL",
]) {
    test(`rejects unsafe dashboard address ${input.split(":")[0]}`, async () => {
        const f = fixture(input);
        await f.open();
        assert.deepEqual(f.opened, []);
        assert.equal(f.alerts.length, 1);
        assert.doesNotMatch(f.alerts[0], /secret/);
    });
}
test("browser launch failure gives a generic accurate message", async () => {
    const f = fixture("http://localhost:8890", "", true);
    await f.open();
    assert.deepEqual(f.opened, []);
    assert.equal(f.alerts.length, 1);
    assert.match(f.alerts[0], /Could not open the browser/);
    assert.doesNotMatch(f.alerts[0], /secret|success/i);
});
test("preferences expose and bind the dashboard shortcut next to connection check", () => {
    const ui = readFileSync(
        new URL("../addon/content/preferences.xhtml", import.meta.url),
        "utf8",
    );
    assert.match(ui, /checkConnection[\s\S]*?openDashboard[\s\S]*?<\/hbox>/);
    assert.match(
        source,
        /openDashboard`\)[\s\S]*?addEventListener\("click", \(\) => openServerDashboard\(window\)\)/,
    );
});
