import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";
const ui = readFileSync(
    new URL("../addon/content/preferences.xhtml", import.meta.url),
    "utf8",
);
const code = readFileSync(
    new URL("../src/modules/preferenceScript.ts", import.meta.url),
    "utf8",
);
test("first-run controls offer preparation, cancellation and progress", () => {
    assert.match(ui, /localServerPrepare/);
    assert.match(ui, /localServerCancel/);
    assert.match(ui, /localServerStatus/);
    assert.match(code, /ensureBundledServerInstalled/);
    assert.match(code, /getRuntimeBootstrap/);
});
import vm from "node:vm";
import ts from "typescript";
function prepareFixture(saved: boolean) {
    const prefs: any = {
        new_serverip: "http://localhost:8890",
        localPythonPath: saved ? "D:\\manual\\python.exe" : "",
        localServerScript: "",
        localManagedRuntime: false,
    };
    const elements = new Map<string, any>();
    for (const name of [
        "localServerStart",
        "localServerStop",
        "localServerPrepare",
        "localServerCancel",
        "localServerStatus",
        "localPythonPath",
        "localServerScript",
        "new_serverip",
    ]) {
        elements.set(name, {
            value: "",
            dataset: {},
            addEventListener(type: string, cb: any) {
                this[type] = cb;
            },
        });
    }
    let installs = 0;
    const source = code + "\nexports.bindForTest = bindLocalServerControls;";
    const js = ts.transpileModule(source, {
        compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
        },
    }).outputText;
    const exports: any = {};
    const require = (name: string) =>
        name.endsWith("package.json")
            ? { config: { addonRef: "pdf2zh" } }
            : name.endsWith("/prefs")
              ? {
                    getPref: (key: string) => prefs[key],
                    setPref: (key: string, value: any) => {
                        prefs[key] = value;
                    },
                }
              : name.endsWith("/localServer")
                ? {
                      localServer: {
                          getState: () => "stopped",
                          start: async () => ({ owned: true }),
                      },
                      normalizeLocalServerUrl: () => ({
                          baseUrl: "http://localhost:8890",
                      }),
                  }
                : name.endsWith("/bundledServer")
                  ? {
                        ensureBundledServerInstalled: async () => {
                            installs++;
                            return {
                                scriptPath: "D:\\managed\\server.py",
                                installDirectory: "D:\\managed",
                            };
                        },
                    }
                  : name.endsWith("/runtimeBootstrap")
                    ? {
                          getRuntimeBootstrap: () => ({
                              prepare: async () => ({
                                  pythonPath: "D:\\managed\\python.exe",
                                  environment: {},
                              }),
                          }),
                      }
                    : name.endsWith("/localServerDiscovery")
                      ? { discoverLocalServer: async () => ({}) }
                      : {};
    vm.runInNewContext(js, {
        exports,
        require,
        Zotero: {
            locale: "zh-CN",
            isWin: true,
            HTTP: {
                request: async () => {
                    throw new Error("offline");
                },
            },
        },
        console,
        setTimeout,
        setInterval: () => 1,
        clearInterval() {},
    });
    const win: any = {
        document: {
            getElementById: (id: string) =>
                elements.get(id.replace("zotero-prefpane-pdf2zh-", "")) || null,
        },
        addEventListener() {},
        setInterval: () => 1,
        clearInterval() {},
    };
    exports.bindForTest(win);
    elements.get("localPythonPath").value = "D:\\suggested\\python.exe";
    elements.get("localServerScript").value = "D:\\suggested\\server.py";
    return {
        prefs,
        click: () => elements.get("localServerPrepare").click(),
        get installs() {
            return installs;
        },
    };
}
test("unsaved discovery suggestions do not block automatic preparation", async () => {
    const f = prepareFixture(false);
    await f.click();
    assert.equal(f.installs, 1);
    assert.equal(f.prefs.localPythonPath, "D:\\managed\\python.exe");
});
test("saved manual paths are protected from automatic preparation", async () => {
    const f = prepareFixture(true);
    await f.click();
    assert.equal(f.installs, 0);
    assert.equal(f.prefs.localPythonPath, "D:\\manual\\python.exe");
});
