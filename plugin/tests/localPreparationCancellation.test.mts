import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
function fixture(failCancel = false, failBundle = false) {
    let rejectHealth: (error: Error) => void = () => {};
    let prepares = 0,
        stops = 0,
        bundleCancels = 0,
        runtimeCancels = 0;
    const runtime = {
        prepare: async () => {
            prepares++;
            return {};
        },
        cancel: async () => {
            runtimeCancels++;
            if (failCancel) throw new Error("cancel failed");
        },
    };
    const server = {
        start: async () => ({}),
        stop: async () => {
            stops++;
        },
    };
    const prefs: any = {
        new_serverip: "http://localhost:8890",
        localManagedRuntime: true,
        localServerScript: "D:\\ZoteroPlugin\\PDF2zh\\server.py",
        localPythonPath: "D:\\python.exe",
    };
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
    const require = (name: string) =>
        name.endsWith("/prefs")
            ? { getPref: (key: string) => prefs[key], setPref: () => {} }
            : name.endsWith("/localServer")
              ? {
                    localServer: server,
                    normalizeLocalServerUrl: () => ({
                        baseUrl: "http://localhost:8890",
                    }),
                }
              : name.endsWith("/bundledServer")
                ? {
                      cancelBundledServerInstallation: async () => {
                          bundleCancels++;
                          if (failBundle)
                              throw new Error("bundle cancellation failed");
                      },
                  }
                : name.endsWith("/runtimeBootstrap")
                  ? {
                        getRuntimeBootstrap: () => runtime,
                        cancelRuntimeBootstrapIfExists: () => runtime.cancel(),
                    }
                  : {};
    vm.runInNewContext(js, {
        exports,
        require,
        Zotero: {
            locale: "zh-CN",
            HTTP: {
                request: () =>
                    new Promise((_resolve, reject) => {
                        rejectHealth = reject;
                    }),
            },
        },
        console,
        setTimeout,
    });
    return {
        exports,
        resolveHealth: () => rejectHealth(new Error("unavailable")),
        get prepares() {
            return prepares;
        },
        get bundleCancels() {
            return bundleCancels;
        },
        get runtimeCancels() {
            return runtimeCancels;
        },
        get stops() {
            return stops;
        },
    };
}
test("cancellation during health probe prevents runtime preparation", async () => {
    const f = fixture();
    const start = f.exports.startConfiguredLocalServer();
    await f.exports.cancelLocalPreparation();
    f.resolveHealth();
    await start;
    assert.equal(f.prepares, 0);
});
test("server is stopped even if runtime cancellation fails", async () => {
    const f = fixture(true);
    await assert.rejects(f.exports.cancelLocalPreparation());
    assert.equal(f.stops, 1);
});

test("bundle cancellation failure still cancels runtime and stops server", async () => {
    const f = fixture(false, true);
    await assert.rejects(f.exports.cancelLocalPreparation());
    assert.equal(f.bundleCancels, 1);
    assert.equal(f.runtimeCancels, 1);
    assert.equal(f.stops, 1);
});
