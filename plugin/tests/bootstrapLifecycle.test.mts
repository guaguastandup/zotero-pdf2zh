import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = fs.readFileSync(
    new URL("../addon/bootstrap.js", import.meta.url),
    "utf8",
);
function harness(start: () => Promise<void>, initialize = Promise.resolve()) {
    const events: string[] = [];
    const context: any = {
        APP_SHUTDOWN: 2,
        Zotero: {
            initializationPromise: initialize,
            logError: () => events.push("error"),
            __addonInstance__: {
                hooks: {
                    onStartup: start,
                    onShutdown: () => events.push("shutdown"),
                    onMainWindowLoad: () => events.push("window"),
                    onMainWindowUnload: () => events.push("unload"),
                },
            },
        },
        Components: {
            classes: {
                "@mozilla.org/addons/addon-manager-startup;1": {
                    getService: () => ({
                        registerChrome: () => {
                            events.push("register");
                            return { destruct: () => events.push("destruct") };
                        },
                    }),
                },
            },
            interfaces: {},
        },
        Cc: {
            "@mozilla.org/intl/stringbundle;1": {
                getService: () => ({ flushBundles() {} }),
            },
        },
        ComponentsUnused: {},
        Services: {
            appinfo: { platformVersion: "115.0" },
            io: { newURI: (url: string) => url },
            scriptloader: { loadSubScript: () => events.push("script") },
        },
    };
    vm.createContext(context);
    vm.runInContext(source, context);
    return { context, events };
}
const data = { id: "pdf2zh", rootURI: "file:///test/" };

test("bootstrap waits for startup before delivering a window callback", async () => {
    let ready!: () => void;
    const wait = new Promise<void>((resolve) => {
        ready = resolve;
    });
    const { context, events } = harness(() => wait);
    const startup = context.startup(data, 3);
    const window = context.onMainWindowLoad({ window: {} });
    await new Promise((resolve) => setImmediate(resolve));
    assert.deepEqual(events, ["register", "script"]);
    ready();
    await Promise.all([startup, window]);
    assert.deepEqual(events, ["register", "script", "window"]);
});

test("modern hosts use ESM in the plugin scope without changing the host shim", async () => {
    const { context } = harness(async () => {});
    const calls: string[] = [];
    context.Services.appinfo.platformVersion = "140.0";
    const hostImport = () => {
        throw new Error("removed JSM import");
    };
    context.ChromeUtils = {
        import: hostImport,
        importESModule(path: string) {
            assert.equal(this, context.ChromeUtils);
            calls.push(path);
            return { loaded: true };
        },
    };
    context.Services.scriptloader.loadSubScript = (
        _url: string,
        scope: any,
    ) => {
        assert.equal(scope.ChromeUtils.import, undefined);
        assert.deepEqual(scope.ChromeUtils.importESModule("Console.sys.mjs"), {
            loaded: true,
        });
    };
    await context.startup(data, 3);
    assert.equal(context.ChromeUtils.import, hostImport);
    assert.deepEqual(calls, ["Console.sys.mjs"]);
});

test("Gecko 115 hosts retain their original module import behavior", async () => {
    const { context } = harness(async () => {});
    context.Services.scriptloader.loadSubScript = (
        _url: string,
        scope: any,
    ) => {
        assert.equal(Object.hasOwn(scope, "ChromeUtils"), false);
    };
    await context.startup(data, 3);
});

test("a failed asynchronous startup is reported and releases chrome registration", async () => {
    const { context, events } = harness(async () => {
        throw new Error("startup failed");
    });
    await assert.rejects(context.startup(data, 3), /startup failed/);
    assert.deepEqual(events, [
        "register",
        "script",
        "error",
        "shutdown",
        "destruct",
    ]);
});

test("disable while Zotero is initializing prevents a delayed registration", async () => {
    let ready!: () => void;
    const wait = new Promise<void>((resolve) => {
        ready = resolve;
    });
    const { context, events } = harness(async () => {
        events.push("started");
    }, wait);
    const startup = context.startup(data, 3);
    context.shutdown(data, 4);
    ready();
    await startup;
    assert.deepEqual(events, ["shutdown"]);
});
