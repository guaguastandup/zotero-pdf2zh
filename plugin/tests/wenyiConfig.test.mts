import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import { tableModeFromPref } from "../src/modules/pdf2zhTableMode.ts";
import { inspect } from "node:util";
import vm from "node:vm";
import ts from "typescript";
import {
    translationConfig,
    wenyiModelOptions,
} from "../src/modules/wenyiConfig.ts";
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
        translateTableText: "true",
        skipReferences: "true",
        tableMode: "fixed",
        ignoreCache: "true",
    } as ServerConfig;
    const before = structuredClone(preferences);
    const actual = translationConfig(preferences);
    assert.equal(actual.service, "deepseek");
    assert.equal(actual.mono, "true");
    assert.equal(actual.dual, "false");
    assert.equal(actual.mono_cut, "false");
    assert.equal(actual.skipLastPages, "0");
    assert.equal(actual.ocr, "false");
    assert.equal(actual.autoOcr, "false");
    assert.equal(actual.onlyIncludeTranslatedPage, "false");
    assert.equal(actual.translateTableText, "false");
    assert.equal(actual.skipReferences, "false");
    assert.equal(actual.tableMode, "");
    assert.equal(actual.ignoreCache, "false");
    assert.equal(actual.targetLang, "zh-CN");
    assert.deepEqual(preferences, before);
});

test("legacy engines keep their configuration without reading Wenyi preferences", () => {
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

test("Wenyi sends typed workflow options, preserving false and ignoring retired preferences", () => {
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
        prompt_genre: "academic",
        pipeline: {
            book_understanding: false,
            translation_mode: "standard",
            polish: false,
            review: true,
        },
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

test("new and legacy empty preferences default to academic with workflow stages enabled", () => {
    for (const value of [undefined, ""]) {
        const actual = translationConfig(
            { engine: "wenyi" } as ServerConfig,
            () => value,
        );
        assert.deepEqual(actual.wenyi, {
            prompt_genre: "academic",
            pipeline: {
                book_understanding: true,
                translation_mode: "standard",
                polish: true,
                review: true,
            },
        });
    }
});

test("Wenyi sends the selected CLI prompt genre without changing stored preferences", () => {
    for (const genre of ["academic", "literary"]) {
        const prefs = { "wenyi.prompt_genre": genre };
        const actual = translationConfig(
            { engine: "wenyi" } as ServerConfig,
            (key) => prefs[key as keyof typeof prefs],
        );
        assert.equal(actual.wenyi!.prompt_genre, genre);
        assert.deepEqual(prefs, { "wenyi.prompt_genre": genre });
    }
    for (const genre of ["neutral", "Academic", "../academic", true, null]) {
        assert.throws(
            () =>
                translationConfig({ engine: "wenyi" } as ServerConfig, (key) =>
                    key === "wenyi.prompt_genre" ? genre : undefined,
                ),
            /prompt_genre/,
        );
    }
});

test("invalid Wenyi workflow settings are not silently coerced", () => {
    for (const [key, value] of [
        ["wenyi.polish", "sometimes"],
        ["wenyi.translation_mode", "true"],
        ["wenyi.translation_mode", "best_of_five"],
    ]) {
        assert.throws(() =>
            translationConfig({ engine: "wenyi" } as ServerConfig, (name) =>
                name === key ? value : "",
            ),
        );
    }
});

test("Wenyi maps only the shared DeepSeek thinking controls without mutation", () => {
    for (const mode of ["disabled", "enabled"]) {
        for (const effort of ["high", "max"]) {
            const extra = {
                deepseek_thinking_mode: mode,
                deepseek_reasoning_effort: effort,
                api_key: "ignored-key",
                base_url: "http://untrusted.invalid",
                deepseek_enable_json_mode: true,
                thinking: mode !== "enabled",
            };
            const before = structuredClone(extra);
            assert.deepEqual(wenyiModelOptions(extra), {
                thinking: mode === "enabled",
                reasoning_effort: effort,
            });
            assert.deepEqual(extra, before);
        }
    }
});

test("empty shared thinking controls explicitly disable thinking", () => {
    for (const extra of [
        undefined,
        null,
        {},
        { deepseek_thinking_mode: "", deepseek_reasoning_effort: "" },
    ]) {
        assert.deepEqual(wenyiModelOptions(extra), {
            thinking: false,
            reasoning_effort: "high",
        });
    }
});

test("invalid shared thinking controls fail instead of silently changing model behavior", () => {
    for (const extra of [
        "invalid",
        [],
        { deepseek_thinking_mode: true },
        { deepseek_thinking_mode: "true" },
        { deepseek_thinking_mode: "auto" },
        { deepseek_reasoning_effort: "ultra" },
    ]) {
        assert.throws(() => wenyiModelOptions(extra));
    }
});

test("Wenyi sends only the active DeepSeek key and never logs it", async () => {
    let body: any;
    let fetchCount = 0;
    const logs: string[] = [];
    const context = vm.createContext({
        addon: { data: { llmApis: { map: new Map(), cachedKeys: [] } } },
        ztoolkit: {
            log: (...args: unknown[]) =>
                logs.push(inspect(args, { depth: null })),
        },
        fetch: async (_url: string, request: any) => {
            fetchCount++;
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
    const preferences: Record<string, string> = {
        engine: "wenyi",
        new_serverip: "http://127.0.0.1:8890",
        "wenyi.translation_mode": "best_of_three",
        "wenyi.polish": "false",
        "wenyi.thinking": "false",
        "wenyi.max_concurrency": "6",
        "wenyi.prompt_genre": "literary",
    };
    const imports: Record<string, any> = {
        "../../package.json": { version: "test" },
        "../utils/prefs": {
            getPref: (key: string) =>
                key === "skipReferences" ? true : preferences[key],
        },
        "./pdf2zhTableMode": { tableModeFromPref },
        "../utils/locale": { getString: (key: string) => key },
        "./wenyiConfig": { translationConfig, wenyiModelOptions },
        "./llmApiManager": { llmApiManager: { updateLLMApi() {} } },
    };
    for (const name of ["preferenceScript", "pdf2zhHelper"]) {
        const source = fs.readFileSync(
            new URL(`../src/modules/${name}.ts`, import.meta.url),
            "utf8",
        );
        const js = ts.transpileModule(source, {
            compilerOptions: {
                module: ts.ModuleKind.CommonJS,
                target: ts.ScriptTarget.ES2022,
            },
        }).outputText;
        const exports = {};
        vm.runInContext(`(function(require, exports) {${js}\n})`, context)(
            (name: string) => imports[name] ?? {},
            exports,
        );
        imports[`./${name}`] = exports;
    }
    const helper = imports["./pdf2zhHelper"].PDF2zhHelperFactory;
    preferences.llmApis = JSON.stringify([
        {
            key: "active-deepseek",
            activate: true,
            service: "deepseek",
            apiKey: " fake-plugin-key ",
            model: "ignored-model",
            apiUrl: "http://untrusted.invalid",
            extraData: {
                api_key: "ignored-key",
                deepseek_thinking_mode: "enabled",
                deepseek_reasoning_effort: "max",
                deepseek_enable_json_mode: true,
            },
        },
    ]);
    const config = helper.getServerConfig();
    const send = () =>
        helper.sendRequest(
            { fileName: "paper.pdf", base64: "offline-fixture" },
            config,
            "translate",
        );
    const result = await send();
    assert.equal(result.status, "success");
    assert.equal(body.engine, "wenyi");
    assert.equal(body.asyncJob, true);
    assert.equal(body.mono, "true");
    assert.equal(Object.hasOwn(body, "skipReferences"), false);
    assert.deepEqual(body.wenyi, {
        prompt_genre: "literary",
        pipeline: {
            book_understanding: true,
            translation_mode: "best_of_three",
            polish: true,
            review: true,
        },
        model: { thinking: true, reasoning_effort: "max" },
    });
    assert.deepEqual(body.llm_api, {
        service: "deepseek",
        apiKey: "fake-plugin-key",
    });
    assert.doesNotMatch(logs.join("\n"), /fake-plugin-key|ignored-key/);
    const active = JSON.parse(preferences.llmApis);
    active[0].extraData.deepseek_thinking_mode = "disabled";
    preferences.llmApis = JSON.stringify(active);
    await send();
    assert.deepEqual(body.wenyi.model, {
        thinking: false,
        reasoning_effort: "max",
    });
    assert.equal(Object.hasOwn(config.wenyi, "model"), false);
    for (const extraData of [
        { deepseek_thinking_mode: "auto" },
        { deepseek_reasoning_effort: "ultra" },
    ]) {
        preferences.llmApis = JSON.stringify([{ ...active[0], extraData }]);
        await assert.rejects(
            send(),
            /DeepSeek (thinking mode|reasoning effort)/,
        );
    }
    for (const invalid of [
        null,
        {},
        { service: "deepseek", apiKey: "" },
        { service: "deepseek", apiKey: "  " },
        { service: "openai", apiKey: "wrong-provider" },
        {
            service: "deepseek",
            apiKey: "inactive-plugin-key",
            activate: false,
        },
    ]) {
        preferences.llmApis = JSON.stringify(
            invalid ? [{ key: "test-config", activate: true, ...invalid }] : [],
        );
        await assert.rejects(send(), /operation-error-wenyi-key-required/);
    }
    for (const invalid of [
        "",
        '{"apiKey":"malformed-plugin-key"',
        JSON.stringify([
            {
                key: "partial-config",
                activate: true,
                service: "deepseek",
                apiKey: "partial-plugin-key",
            },
            null,
        ]),
    ]) {
        preferences.llmApis = JSON.stringify([
            {
                key: "previous-config",
                activate: true,
                service: "deepseek",
                apiKey: "previous-plugin-key",
            },
        ]);
        assert.equal(
            helper.getActiveLLMApiConfig("deepseek").apiKey,
            "previous-plugin-key",
        );
        preferences.llmApis = invalid;
        await assert.rejects(send(), /operation-error-wenyi-key-required/);
    }
    assert.doesNotMatch(
        logs.join("\n"),
        /fake-plugin-key|inactive-plugin-key|malformed-plugin-key|previous-plugin-key|partial-plugin-key|ignored-key/,
    );
    assert.equal(fetchCount, 2);
});
