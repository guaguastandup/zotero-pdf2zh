import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import { tableModeFromPref } from "../src/modules/pdf2zhTableMode.ts";
import { classifyPDFFileName } from "../src/modules/pdf2zhAttachmentUtils.ts";
import {
    translationConfig,
    wenyiModelOptions,
} from "../src/modules/wenyiConfig.ts";

const SAMPLE_CSV = "source,target,tgt_lng\nattention,注意力,zh_CN\n";

/**
 * 在 VM 里加载 pdf2zhHelper 并用受控 prefs + fetch 捕获发出的请求体。
 * 术语表的关键契约: 传"内容"而非路径(远端 server 读不到本机路径)。
 */
function loadHelper(
    preferences: Record<string, unknown>,
    files: Record<string, string>,
) {
    let body: any;
    const context = vm.createContext({
        addon: { data: { llmApis: { map: new Map(), cachedKeys: [] } } },
        ztoolkit: {
            log: () => {},
            getGlobal: (name: string) =>
                name === "alert" ? () => {} : undefined,
        },
        Zotero: {
            File: {
                getContentsAsync: async (path: string) => {
                    if (!(path in files)) {
                        throw new Error("file not found");
                    }
                    return files[path];
                },
            },
        },
        fetch: async (_url: string, request: any) => {
            if (!request.body) {
                return {
                    ok: true,
                    json: async () => ({ status: "ok" }),
                };
            }
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
    const imports: Record<string, any> = {
        "../../package.json": { version: "test" },
        "../utils/prefs": {
            getPref: (key: string) => preferences[key],
        },
        "./pdf2zhTableMode": { tableModeFromPref },
        "./pdf2zhAttachmentUtils": { classifyPDFFileName },
        "../utils/locale": { getString: (key: string) => key },
        "./wenyiConfig": { translationConfig, wenyiModelOptions },
        "./pdf2zhDeepSeekFlash": {
            needsDeepSeekFlashPatch: () => false,
            supportsDeepSeekFlashPatch: () => true,
        },
        "./llmApiManager": { llmApiManager: { updateLLMApi() {} } },
    };
    for (const name of [
        "pdf2zhTypes",
        "preferenceScript",
        "pdf2zhWenyiSupport",
        "pdf2zhHelper",
    ]) {
        const source = fs.readFileSync(`src/modules/${name}.ts`, "utf8");
        const js = ts.transpileModule(source, {
            compilerOptions: {
                module: ts.ModuleKind.CommonJS,
                target: ts.ScriptTarget.ES2022,
            },
        }).outputText;
        const exports = {};
        vm.runInContext(`(function(require, exports) {${js}\n})`, context)(
            (required: string) => imports[required] ?? {},
            exports,
        );
        imports[`./${name}`] = exports;
    }
    const helper = imports["./pdf2zhHelper"].PDF2zhHelperFactory;
    return {
        helper,
        send: () =>
            helper.sendRequest(
                { fileName: "paper.pdf", base64: "offline-fixture" },
                helper.getServerConfig(),
                "translate",
            ),
        getBody: () => body,
    };
}

const BASE_PREFS = {
    engine: "pdf2zh_next",
    new_serverip: "http://127.0.0.1:8890",
    service: "google",
    next_service: "openai",
    targetLang: "zh-CN",
    sourceLang: "en",
};

test("enabled glossary ships file content (not a path) with the request", async () => {
    const { send, getBody } = loadHelper(
        {
            ...BASE_PREFS,
            customGlossaryEnabled: "true",
            customGlossaryPath: "/Users/someone/terms.csv",
        },
        { "/Users/someone/terms.csv": SAMPLE_CSV },
    );
    const result = await send();
    assert.equal(result.status, "success");
    assert.deepEqual(getBody().customGlossary, {
        fileName: "terms.csv",
        content: SAMPLE_CSV,
    });
});

test("disabled glossary keeps the request body unchanged", async () => {
    const { send, getBody } = loadHelper(
        {
            ...BASE_PREFS,
            customGlossaryEnabled: "false",
            customGlossaryPath: "/Users/someone/terms.csv",
        },
        { "/Users/someone/terms.csv": SAMPLE_CSV },
    );
    await send();
    assert.equal(getBody().customGlossary, undefined);
});

test("enabled without a path fails loudly instead of silently skipping", async () => {
    const { send } = loadHelper(
        {
            ...BASE_PREFS,
            customGlossaryEnabled: "true",
            customGlossaryPath: "",
        },
        {},
    );
    await assert.rejects(send(), /operation-error-glossary-empty/);
});

test("unreadable glossary file fails loudly", async () => {
    const { send } = loadHelper(
        {
            ...BASE_PREFS,
            customGlossaryEnabled: "true",
            customGlossaryPath: "/Users/someone/gone.csv",
        },
        {},
    );
    await assert.rejects(send(), /operation-error-glossary-read/);
});

test("glossary is not attached for non-pdf2zh_next engines", async () => {
    const { send, getBody } = loadHelper(
        {
            ...BASE_PREFS,
            engine: "pdf2zh",
            customGlossaryEnabled: "true",
            customGlossaryPath: "/Users/someone/terms.csv",
        },
        { "/Users/someone/terms.csv": SAMPLE_CSV },
    );
    await send();
    assert.equal(getBody().customGlossary, undefined);
});
