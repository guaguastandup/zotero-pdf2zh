import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

// Execute the production hooks/menu factory with a small DOM/toolkit double.
// The double models toolkit 5.1.0-beta.10: string targets use the active
// document, and unregisterAll removes every node owned by that instance.
function setup() {
    const windows: any[] = [];
    const errors: any[] = [];
    const commands: string[] = [];
    let active: any;
    function window() {
        const nodes = new Map();
        const doc: any = {
            querySelector: (selector: string) => nodes.get(selector) ?? null,
        };
        const popup = { ownerDocument: doc, nodes };
        nodes.set("#zotero-itemmenu", popup);
        const win = { document: doc, nodes, popup };
        windows.push(win);
        active = win;
        return win;
    }
    function createZToolkit() {
        const owned: any[] = [];
        return {
            Menu: {
                register(target: any, options: any) {
                    const popup =
                        typeof target === "string"
                            ? active.document.querySelector("#zotero-itemmenu")
                            : target;
                    if (!popup) return false;
                    const key = `#${options.id}`;
                    const node = {
                        options,
                        remove() {
                            if (popup.nodes.get(key) === node)
                                popup.nodes.delete(key);
                        },
                    };
                    owned.push(node);
                    popup.nodes.set(key, node);
                },
            },
            unregisterAll() {
                owned.forEach((node) => node.remove());
            },
        };
    }
    const addon: any = {
        data: {
            alive: true,
            config: { addonRef: "pdf2zh" },
            ztoolkit: createZToolkit(),
        },
        hooks: { onDialogEvents: (command: string) => commands.push(command) },
    };
    const context: any = vm.createContext({
        addon,
        rootURI: "test/",
        Zotero: {
            getMainWindows: () => windows,
            Promise: { delay: async () => {} },
            PreferencePanes: { register() {} },
            logError: (error: any) => errors.push(error),
        },
    });
    Object.defineProperty(context, "ztoolkit", {
        get: () => addon.data.ztoolkit,
    });
    function load(path: string, imports: any) {
        const source = fs.readFileSync(new URL(path, import.meta.url), "utf8");
        const js = ts.transpileModule(source, {
            compilerOptions: {
                module: ts.ModuleKind.CommonJS,
                target: ts.ScriptTarget.ES2022,
            },
        }).outputText;
        const exports = {};
        const run = vm.runInContext(
            `(function(require, exports) {${js}\n})`,
            context,
        );
        run((name: string) => imports[name] ?? {}, exports);
        return exports as any;
    }
    const locale = { getString: (key: string) => key, initLocale() {} };
    const factory = load("../src/modules/pdf2zh.ts", {
        "../utils/locale": locale,
    });
    const hooks = load("../src/hooks.ts", {
        "./modules/pdf2zh": factory,
        "./utils/locale": locale,
        "./utils/ztoolkit": { createZToolkit },
        "./modules/preferenceScript": { initTableUI() {} },
    }).default;
    const menu = (win: any) => win.nodes.get("#zotero-itemmenu-pdf2zh");
    return { window, hooks, addon, menu, errors, commands };
}

test("startup registers each window even when another window is active", async () => {
    const s = setup();
    const a = s.window();
    const b = s.window();
    await s.hooks.onStartup();
    assert.ok(s.menu(a));
    assert.ok(s.menu(b));
});
test("closing an older window leaves the newer window menu usable", async () => {
    const s = setup();
    const a = s.window();
    await s.hooks.onMainWindowLoad(a);
    const b = s.window();
    await s.hooks.onMainWindowLoad(b);
    await s.hooks.onMainWindowUnload(a);
    assert.ok(s.menu(b));
    assert.equal(s.menu(a), undefined);
    for (const item of s.menu(b).options.children) item.commandListener();
    assert.deepEqual(s.commands, [
        "translatePDF",
        "cropPDF",
        "comparePDF",
        "crop-comparePDF",
    ]);
});
test("shutdown removes menus from every window, then reload registers them", async () => {
    const s = setup();
    const a = s.window();
    await s.hooks.onMainWindowLoad(a);
    const b = s.window();
    await s.hooks.onMainWindowLoad(b);
    s.hooks.onShutdown();
    assert.equal(s.menu(a), undefined);
    assert.equal(s.menu(b), undefined);
    s.addon.data.alive = true;
    await s.hooks.onStartup();
    assert.ok(s.menu(a));
    assert.ok(s.menu(b));
});
test("repeated load does not replace or duplicate a menu", async () => {
    const s = setup();
    const a = s.window();
    await s.hooks.onMainWindowLoad(a);
    const original = s.menu(a);
    await s.hooks.onMainWindowLoad(a);
    assert.equal(s.menu(a), original);
});
test("missing popup is diagnosed and a later load can retry", async () => {
    const s = setup();
    const a = s.window();
    a.nodes.delete("#zotero-itemmenu");
    await s.hooks.onMainWindowLoad(a);
    assert.equal(s.menu(a), undefined);
    assert.equal(s.errors.length, 1);
    a.nodes.set("#zotero-itemmenu", a.popup);
    await s.hooks.onMainWindowLoad(a);
    assert.ok(s.menu(a));
});
