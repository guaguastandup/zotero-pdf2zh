import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import { translationConfig } from "../src/modules/wenyiConfig.ts";
import type { ServerConfig } from "../src/modules/pdf2zhTypes.ts";

test("Wenyi produces mono output without changing the user's other-engine preferences", () => {
    const preferences = {
        engine: "wenyi",
        service: "google",
        next_service: "openai",
        targetLang: "zh-CN",
        dual: "true",
        mono: "false",
        mono_cut: "true",
        skipLastPages: "3",
        ocr: "true",
        autoOcr: "true",
        onlyIncludeTranslatedPage: "true",
    } as ServerConfig;
    const actual = translationConfig(preferences);
    assert.equal(actual.service, "deepseek");
    assert.equal(actual.mono, "true");
    assert.equal(actual.dual, "false");
    assert.equal(actual.mono_cut, "false");
    assert.equal(actual.skipLastPages, "0");
    assert.equal(actual.ocr, "false");
    assert.equal(actual.autoOcr, "false");
    assert.equal(actual.onlyIncludeTranslatedPage, "false");
    assert.equal(actual.targetLang, "zh-CN");
    assert.equal(preferences.dual, "true");
    assert.equal(preferences.skipLastPages, "3");
});

test("other translation engines retain their exact configuration", () => {
    for (const engine of ["pdf2zh", "pdf2zh_next"]) {
        const settings = { engine } as ServerConfig;
        assert.equal(translationConfig(settings), settings);
    }
});

test("Wenyi settings use native typed options and preserve explicit false", () => {
    const prefs: Record<string, string> = {
        "wenyi.book_understanding": "false",
        "wenyi.polish": "false",
        "wenyi.review": "true",
        "wenyi.thinking": "false",
        "wenyi.reasoning_effort": "max",
        "wenyi.max_concurrency": "6",
    };
    const actual = translationConfig(
        { engine: "wenyi" } as ServerConfig,
        (key) => prefs[key],
    );
    assert.deepEqual(actual.wenyi, {
        pipeline: {
            book_understanding: false,
            translation_mode: "standard",
            polish: false,
            review: true,
        },
        model: { thinking: false, reasoning_effort: "max" },
    });
});

test("three-draft precision requires polishing without replacing the saved choice", () => {
    const prefs: Record<string, string> = {
        "wenyi.translation_mode": "best_of_three",
        "wenyi.polish": "false",
    };
    const read = (key: string) => prefs[key];
    assert.deepEqual(
        translationConfig({ engine: "wenyi" } as ServerConfig, read).wenyi!
            .pipeline,
        {
            book_understanding: true,
            translation_mode: "best_of_three",
            polish: true,
            review: true,
        },
    );
    assert.equal(prefs["wenyi.polish"], "false");
    prefs["wenyi.translation_mode"] = "standard";
    const standard = translationConfig(
        { engine: "wenyi" } as ServerConfig,
        read,
    ).wenyi!.pipeline!;
    assert.equal(standard.translation_mode, "standard");
    assert.equal(standard.polish, false);
});

test("retired concurrency preferences are never read or forwarded", () => {
    const actual = translationConfig(
        { engine: "wenyi" } as ServerConfig,
        (key) => {
            if (key === "wenyi.max_concurrency") {
                throw new Error(
                    "Retired concurrency preference must not be read",
                );
            }
            return "";
        },
    );
    assert.equal(Object.hasOwn(actual.wenyi!, "provider"), false);
});

test("new and legacy empty preferences explicitly disable thinking and enable workflow stages", () => {
    for (const value of [undefined, ""]) {
        const actual = translationConfig(
            { engine: "wenyi" } as ServerConfig,
            () => value,
        );
        assert.deepEqual(actual.wenyi, {
            pipeline: {
                book_understanding: true,
                translation_mode: "standard",
                polish: true,
                review: true,
            },
            model: { thinking: false, reasoning_effort: "high" },
        });
    }
});

test("legacy engines never read Wenyi settings", () => {
    for (const engine of ["pdf2zh", "pdf2zh_next"]) {
        const settings = { engine } as ServerConfig;
        assert.equal(
            translationConfig(settings, () => {
                throw new Error("Legacy engines must not read Wenyi settings");
            }),
            settings,
        );
    }
});

test("invalid Wenyi settings are not silently coerced or ignored", () => {
    for (const [key, value] of [
        ["wenyi.polish", "sometimes"],
        ["wenyi.translation_mode", "true"],
        ["wenyi.translation_mode", "best_of_five"],
        ["wenyi.reasoning_effort", "ultra"],
    ]) {
        assert.throws(() =>
            translationConfig({ engine: "wenyi" } as ServerConfig, (name) =>
                name === key ? value : "",
            ),
        );
    }
});

test("the actual Wenyi request never loads or sends plugin LLM credentials", async () => {
    const source = fs.readFileSync(
        new URL("../src/modules/pdf2zhHelper.ts", import.meta.url),
        "utf8",
    );
    const js = ts.transpileModule(source, {
        compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
        },
    }).outputText;
    let body: any;
    const context = vm.createContext({
        ztoolkit: { log() {} },
        fetch: async (_url: string, request: any) => {
            body = JSON.parse(request.body);
            return {
                ok: true,
                text: async () =>
                    JSON.stringify({
                        status: "success",
                        fileList: ["mono.pdf"],
                    }),
            };
        },
    });
    const exports: any = {};
    const preferences: Record<string, string> = {
        engine: "wenyi",
        new_serverip: "http://127.0.0.1:8890",
        "wenyi.translation_mode": "best_of_three",
        "wenyi.polish": "false",
        "wenyi.thinking": "false",
        "wenyi.max_concurrency": "6",
    };
    const imports: Record<string, any> = {
        "../../package.json": { version: "test" },
        "../utils/prefs": { getPref: (key: string) => preferences[key] },
        "./wenyiConfig": { translationConfig },
    };
    vm.runInContext(`(function(require, exports) {${js}\n})`, context)(
        (name: string) => imports[name] ?? {},
        exports,
    );
    const helper = exports.PDF2zhHelperFactory;
    helper.getActiveLLMApiConfig = () => {
        throw new Error("Wenyi must not read plugin LLM configuration");
    };
    const config = helper.getServerConfig();
    const result = await helper.sendRequest(
        { fileName: "paper.pdf", base64: "offline-fixture" },
        config,
        "translate",
    );
    assert.equal(result.status, "success");
    assert.equal(body.engine, "wenyi");
    assert.equal(body.asyncJob, true);
    assert.equal(body.mono, "true");
    assert.deepEqual(body.wenyi, {
        pipeline: {
            book_understanding: true,
            translation_mode: "best_of_three",
            polish: true,
            review: true,
        },
        model: { thinking: false, reasoning_effort: "high" },
    });
    assert.equal(Object.hasOwn(body, "llm_api"), false);
});
