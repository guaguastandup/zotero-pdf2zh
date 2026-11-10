import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import * as titleFormat from "../src/modules/pdf2zhTitleFormat.ts";
import * as attachmentUtils from "../src/modules/pdf2zhAttachmentUtils.ts";

// Run the real unified import entry point without a Zotero installation or server.
function setup(style = "translatedTitle") {
    const imported: any[] = [];
    const requests: any[] = [];
    const notices: any[] = [];
    const pdfRequests: any[] = [];
    let reply: any = { status: "success", title: "注意力就是你所需要的一切" };
    const parents = new Map();
    const source = fs.readFileSync(
        new URL("../src/modules/pdf2zhHelper.ts", import.meta.url),
        "utf8",
    );
    const exports: any = {};
    const prefs: Record<string, unknown> = {
        renameStyle: style,
        renameTemplate: "{translatedTitle}-{type}",
        rename: true,
    };
    const context = vm.createContext({
        fetch: async (url: string, options: any) => {
            pdfRequests.push({ url, ...options });
            return {
                ok: true,
                status: 200,
                text: async () =>
                    JSON.stringify({
                        status: "success",
                        fileList: ["paper-mono.pdf"],
                    }),
            };
        },
        Zotero: {
            HTTP: {
                request: async (_method: string, url: string, options: any) => {
                    requests.push({ url, ...options });
                    if (reply instanceof Error) throw reply;
                    return { response: reply };
                },
            },
            Items: { get: (id: number) => parents.get(id) },
            File: { getValidFileName: (name: string) => name },
            Attachments: {
                importFromFile: async (options: any) => {
                    imported.push(options);
                    return { id: imported.length };
                },
            },
        },
        IOUtils: { remove: async () => {}, read: async () => new Uint8Array() },
        ztoolkit: {
            log() {},
            ProgressWindow: class {
                createLine(line: any) {
                    notices.push(line);
                    return this;
                }
                show() {}
            },
        },
    });
    const js = ts.transpileModule(source, {
        compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
        },
    }).outputText;
    vm.runInContext(`(function(require,exports){${js}\n})`, context)(
        (name: string) => {
            if (name === "./pdf2zhTitleFormat") return titleFormat;
            if (name === "./pdf2zhAttachmentUtils") return attachmentUtils;
            if (name === "../utils/locale")
                return { getString: (key: string) => key };
            if (name === "../utils/prefs")
                return { getPref: (key: string) => prefs[key] };
            return {};
        },
        exports,
    );
    const item = (
        id: number,
        fields: Record<string, string>,
        parentItemID?: number,
        attachment = false,
    ) => ({
        id,
        libraryID: 1,
        parentItemID,
        isAttachment: () => attachment,
        getCollections: () => [9],
        getField: (key: string) => fields[key] || "",
    });
    const attachKeys = new Set<string>();
    const add = (sourceItem: any, type = "mono", rename = true) =>
        exports.PDF2zhHelperFactory.addAttachment({
            item: sourceItem,
            type,
            service: "openailiked",
            attachKeys,
            filePath: `/tmp/paper-${type}.pdf`,
            fileName: `paper-${type}.pdf`,
            options: { rename, openAfterProcess: false },
        });
    const helper = exports.PDF2zhHelperFactory;
    helper.downloadTranslatedFile = async () => new Uint8Array();
    helper.writeTempPdf = async () => "/tmp/input.pdf";
    const config = {
        serverUrl: "http://localhost:8890/",
        engine: "pdf2zh_next",
        next_service: "siliconflowfree",
        sourceLang: "en",
        targetLang: "zh-CN",
    };
    const handle = (item: any, overrides = {}) =>
        helper.handleResponse(
            {
                status: "success",
                fileList: ["paper-mono.pdf", "paper-dual.pdf"],
            },
            item,
            { ...config, ...overrides },
        );
    return {
        imported,
        parents,
        item,
        add,
        helper,
        handle,
        requests,
        notices,
        pdfRequests,
        prefs,
        reply: (value: any) => {
            reply = value;
        },
    };
}

test("parent and child imports share saved names for mono/dual and keep dedup/storage semantics", async () => {
    const s = setup();
    const parent = s.item(1, {
        title: "Source title",
        extra: "titleTranslation: 中文标题",
    });
    s.parents.set(1, parent);
    await s.add(parent);
    const child = s.item(2, { title: "Original PDF" }, 1, true);
    await s.add(child, "dual");
    await s.add(child, "mono");
    assert.equal(s.imported.length, 2);
    assert.deepEqual(
        s.imported.map((x) => x.title),
        ["中文标题-mono", "中文标题-dual"],
    );
    assert.deepEqual(
        s.imported.map((x) => x.fileBaseName),
        ["paper-mono", "paper-dual"],
    );
    for (const entry of s.imported) {
        assert.equal(entry.parentItemID, 1);
        assert.equal(entry.collections, undefined);
    }
});

test("standalone PDF with unavailable Extra imports using source title and collection", async () => {
    const s = setup();
    const standalone = s.item(3, { title: "Standalone PDF" }, undefined, true);
    standalone.getField = (key) => {
        if (key === "extra") throw new Error("Invalid field");
        return key === "title" ? "Standalone PDF" : "";
    };
    await s.add(standalone);
    assert.equal(s.imported[0].title, "Standalone PDF-mono");
    assert.equal(s.imported[0].parentItemID, undefined);
    assert.equal(s.imported[0].collections[0], 9);
});

test("rename disabled and historical preference retain existing behavior", async () => {
    for (const style of ["translatedTitle", "shortTitle"]) {
        const s = setup(style);
        const item = s.item(1, {
            title: "Original",
            shortTitle: "Short",
            extra: "titleTranslation: 中文标题",
        });
        await s.add(item, "mono", false);
        assert.equal(s.imported[0].title, "paper-mono.pdf");
        await s.add(item, "dual");
        assert.equal(
            s.imported[1].title,
            style === "shortTitle" ? "Short-openailiked-dual" : "中文标题-dual",
        );
    }
});

test("missing saved title is translated once before importing mono and dual", async () => {
    const s = setup();
    const parent = s.item(1, { title: "Attention Is All You Need" });
    s.parents.set(1, parent);
    const child = s.item(2, { title: "Original PDF" }, 1, true);
    await s.handle(child, {
        llm_api: { service: "siliconflowfree", extraData: {} },
    });
    assert.equal(s.requests.length, 1);
    assert.equal(
        JSON.parse(s.requests[0].body).title,
        "Attention Is All You Need",
    );
    assert.equal(s.requests[0].url, "http://localhost:8890/translateTitle");
    assert.equal(s.requests[0].timeout, 95000);
    assert.equal(s.requests[0].logBodyLength, 0);
    assert.equal(s.requests[0].errorDelayMax, 0);
    assert.deepEqual(
        s.imported.map((x) => x.title),
        ["注意力就是你所需要的一切-mono", "注意力就是你所需要的一切-dual"],
    );
    assert.equal(s.notices.length, 0);
});

test("title request starts alongside PDF translation and keeps the same API profile", async () => {
    const s = setup();
    const profile = {
        service: "openailiked",
        model: "selected-model",
        apiKey: "test-key",
        extraData: {},
    };
    s.helper.getActiveLLMApiConfig = () => profile;
    s.helper.prepareFileData = async () => ({
        fileName: "paper.pdf",
        base64: "fixture",
    });
    s.helper.sendRequest = async (_file: any, config: any) => {
        assert.equal(s.requests.length, 1);
        assert.equal(config.llm_api.model, "selected-model");
        s.helper.getActiveLLMApiConfig = () => ({
            ...profile,
            model: "different-model",
        });
        return {
            status: "success",
            fileList: ["paper-mono.pdf", "paper-dual.pdf"],
        };
    };
    await s.helper.processSingleFile({
        item: s.item(1, { title: "Attention Is All You Need" }),
        fileName: "paper.pdf",
        endpoint: "translate",
        config: {
            serverUrl: "http://localhost:8890",
            engine: "pdf2zh_next",
            next_service: "openailiked",
            targetLang: "zh-CN",
        },
    });
    assert.equal(s.requests.length, 1);
    assert.equal(
        JSON.parse(s.requests[0].body).llm_api.model,
        "selected-model",
    );
    assert.equal(s.imported.length, 2);
});

test("Chinese original and saved Chinese titles avoid network requests", async () => {
    for (const fields of [
        { title: "中文原题" },
        { title: "English title", extra: "titleTranslation: 中文译名" },
    ]) {
        const s = setup();
        await s.handle(s.item(1, fields));
        assert.equal(s.requests.length, 0);
        assert.match(s.imported[0].title, /^中文/);
    }
});

test("old Server, timeout and invalid translation still import PDFs with one visible warning", async () => {
    for (const response of [
        new Error("404"),
        new Error("Timeout"),
        null,
        { status: "success", title: "Untranslated title" },
    ]) {
        const s = setup();
        s.reply(response);
        await s.handle(s.item(1, { title: "English title" }));
        assert.equal(s.requests.length, 1);
        assert.equal(s.imported.length, 2);
        assert.equal(s.imported[0].title, "English title-mono");
        assert.equal(s.notices.length, 1);
    }
});

test("other target languages do not reuse untagged Chinese Extra", async () => {
    const s = setup();
    s.reply({ status: "success", title: "Titre traduit" });
    await s.handle(
        s.item(1, {
            title: "English title",
            extra: "titleTranslation: 中文译名",
        }),
        { targetLang: "fr" },
    );
    assert.equal(JSON.parse(s.requests[0].body).targetLang, "fr");
    assert.equal(s.imported[0].title, "Titre traduit-mono");
});

test("historical modes and disabled renaming never request title translation", async () => {
    for (const style of ["shortTitle", "fullTitle", "titlePrefix"]) {
        const s = setup(style);
        await s.handle(s.item(1, { title: "English title" }));
        assert.equal(s.requests.length, 0);
    }
    const s = setup();
    s.prefs.rename = false;
    await s.handle(s.item(1, { title: "English title" }));
    assert.equal(s.requests.length, 0);
    assert.equal(s.imported[0].title, "paper-mono.pdf");
});

test("PDF requests retain the legacy API payload shape with or without a selected profile", async () => {
    for (const api of [
        null,
        { service: "openailiked", apiKey: "test-key", extraData: {} },
    ]) {
        const s = setup();
        await s.helper.sendRequest(
            { fileName: "paper.pdf", base64: "fixture" },
            {
                serverUrl: "http://localhost:8890",
                engine: "pdf2zh_next",
                next_service: "openailiked",
                llm_api: api,
            },
            "translate",
        );
        const body = JSON.parse(s.pdfRequests[0].body);
        assert.equal(body.fileContent, "fixture");
        assert.equal(body.asyncJob, true);
        if (api) assert.deepEqual(body.llm_api, api);
        else assert.equal(Object.hasOwn(body, "llm_api"), false);
    }
});

test("custom translatedTitle template uses generated titles on local import fallback", async () => {
    const s = setup("custom");
    s.helper.downloadTranslatedFile = async () => {
        throw new Error("offline file download");
    };
    s.helper.retryOperation = async (operation: any) => operation();
    s.helper.safeExists = async () => true;
    s.helper.localPathCandidates = () => ["/translated/paper.pdf"];
    await s.handle(s.item(1, { title: "Attention Is All You Need" }));
    assert.equal(s.requests.length, 1);
    assert.equal(s.imported[1].title, "注意力就是你所需要的一切-dual");
});
