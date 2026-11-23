import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as serverErrors from "../src/modules/pdf2zhServerErrors.ts";

// Execute the actual helper with Zotero/UI and network boundaries replaced.
// This verifies that guidance is wired into translation, not only a formatter.
const source = ts.transpileModule(
    readFileSync(
        new URL("../src/modules/pdf2zhHelper.ts", import.meta.url),
        "utf8",
    ),
    {
        compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
        },
    },
).outputText;

function harness(
    get: (url: string) => Promise<unknown>,
    fetchImpl?: (options: RequestInit) => Promise<unknown>,
    glossary?: string,
) {
    const alerts: string[] = [];
    const calls = { batch: 0, files: 0, posts: 0, health: 0 };
    const translate = (
        key: string,
        options?: { args?: Record<string, unknown> },
    ) => `${key}${options?.args ? ` ${JSON.stringify(options.args)}` : ""}`;
    const dependencies: Record<string, unknown> = {
        "../utils/prefs": {
            getPref: (key: string) =>
                key === "glossaryFile" ? glossary : false,
        },
        "../utils/locale": { getString: translate },
        "../../package.json": { version: "test" },
        "./pdf2zhFileProcessor": {
            FileProcessor: {
                getInstance: () => ({
                    processBatch: async (
                        tasks: Parameters<typeof helper.processSingleFile>[0][],
                    ) => {
                        calls.batch++;
                        if (glossary) {
                            for (const task of tasks)
                                await helper.processSingleFile(task);
                        }
                        return {
                            total: tasks.length,
                            succeeded: tasks.length,
                            failed: 0,
                        };
                    },
                }),
            },
        },
        "./pdf2zhAttachmentUtils": {},
        "./pdf2zhGlossary": {
            readGlossaryFile: async () => "source,target\nattention,注意力\n",
        },
        "./pdf2zhTypes": { PDFType: {} },
        "./preferenceScript": { loadLLMApisFromPrefs: () => {} },
        "./pdf2zhServerErrors": serverErrors,
        axios: {
            default: {
                get: async (url: string) => {
                    if (url.endsWith("/health")) calls.health++;
                    return get(url);
                },
            },
        },
    };
    const context = {
        exports: {} as Record<string, any>,
        require: (name: string) => {
            assert.ok(name in dependencies, `Unmocked dependency: ${name}`);
            return dependencies[name];
        },
        Error,
        TypeError,
        setTimeout,
        fetch: async (_url: string, options: RequestInit) => {
            calls.posts++;
            return fetchImpl?.(options);
        },
        PathUtils: { filename: () => "paper.pdf" },
        Zotero: { Promise: { delay: async () => {} } },
        ztoolkit: {
            log: () => {},
            getGlobal: (key: string) =>
                key === "alert"
                    ? (message: string) => alerts.push(message)
                    : { getSelectedItems: () => [{}, {}, {}] },
        },
    };
    runInNewContext(source, context);
    const helper = context.exports.PDF2zhHelperFactory;
    helper.getServerConfig = () => ({
        serverUrl: "http://localhost:8890/",
        engine: "pdf2zh_next",
    });
    helper.validatePDFAttachment = async () => "/tmp/paper.pdf";
    helper.getFileType = () => "origin";
    helper.getOperationValidationError = () => null;
    helper.getActiveLLMApiConfig = () => null;
    helper.handleResponse = async () => {};
    helper.prepareFileData = async () => {
        calls.files++;
        return { fileName: "paper.pdf", base64: "test-pdf" };
    };
    return { helper, alerts, calls };
}

test("Server off: one popup for a batch, no PDF read or translation POST", async () => {
    const { helper, calls, alerts } = harness(async () => {
        throw new TypeError("NetworkError when attempting to fetch resource.");
    });
    await helper.processWorker("translate");
    assert.deepEqual(calls, { batch: 0, files: 0, posts: 0, health: 1 });
    assert.equal(alerts.length, 1);
    assert.match(alerts[0], /server-error-unreachable-help/);
    assert.match(alerts[0], /server-error-phase-check/);
});

test("custom glossary is included in translation requests only on a supporting Server", async () => {
    const bodies: Record<string, unknown>[] = [];
    const connected = harness(
        async () => ({
            status: 200,
            data: {
                status: "ok",
                version: "4.1.8",
                supportsGlossaryUpload: true,
            },
        }),
        async (options) => {
            bodies.push(JSON.parse(String(options.body)));
            return {
                ok: true,
                status: 200,
                text: async () => '{"status":"success"}',
            };
        },
        "/local/private/terms.csv",
    );
    await connected.helper.processWorker("translate");
    assert.equal(bodies.length, 3);
    assert.equal(connected.calls.health, 1);
    for (const body of bodies) {
        assert.equal(body.glossaryCsv, "source,target\nattention,注意力\n");
        assert.doesNotMatch(JSON.stringify(body), /\/local\/private/);
    }
    bodies.length = 0;
    await connected.helper.processWorker("crop");
    assert.equal(bodies.length, 3);
    assert.ok(bodies.every((body) => !("glossaryCsv" in body)));

    const old = harness(
        async () => ({ status: 200, data: { status: "ok", version: "4.1.7" } }),
        undefined,
        "/local/private/terms.csv",
    );
    await old.helper.processWorker("translate");
    assert.equal(old.calls.posts, 0);
    assert.match(old.alerts[0], /glossary-error-server/);
});

test("an unrelated service cannot receive the selected PDFs", async () => {
    const { helper, calls, alerts } = harness(async () => ({
        status: 200,
        data: "<html>Login</html>",
    }));
    await helper.processWorker("translate");
    assert.equal(calls.batch, 0);
    assert.equal(calls.posts, 0);
    assert.match(alerts[0], /server-error-unexpected-response/);
});

test("a healthy Server is checked only once before starting the batch", async () => {
    const { helper, calls, alerts } = harness(async () => ({
        status: 200,
        data: { status: "ok", version: "4.1.7" },
    }));
    await helper.processWorker("translate");
    assert.equal(calls.health, 1);
    assert.equal(calls.batch, 1);
    assert.equal(alerts.length, 0);
});

test("disconnect during submission shows uncertain-submission guidance, without resubmitting", async () => {
    const { helper, calls, alerts } = harness(
        async () => ({}),
        async () => {
            throw new TypeError("Failed to fetch");
        },
    );
    await assert.rejects(
        helper.processSingleFile({
            fileName: "paper.pdf",
            item: {},
            config: helper.getServerConfig(),
            endpoint: "translate",
        }),
    );
    assert.equal(calls.posts, 1);
    assert.equal(alerts.length, 1);
    assert.match(alerts[0], /server-error-phase-submit/);
    assert.match(alerts[0], /server-error-unreachable-help/);
});

test("a real Server's provider error retains its original explanation", async () => {
    const { helper, alerts } = harness(
        async () => ({}),
        async () => ({
            ok: false,
            status: 500,
            text: async () =>
                JSON.stringify({
                    status: "error",
                    message: "Invalid API key for translation provider",
                }),
        }),
    );
    await assert.rejects(
        helper.processSingleFile({
            fileName: "paper.pdf",
            item: {},
            config: helper.getServerConfig(),
            endpoint: "translate",
        }),
        /Invalid API key/,
    );
    assert.match(alerts[0], /Invalid API key/);
    assert.doesNotMatch(alerts[0], /server-error-unreachable/);
});

test("repeated polling failures stop waiting and preserve the submitted-task context", async () => {
    let checks = 0;
    const { helper, calls } = harness(async () => {
        checks++;
        throw { code: "ETIMEDOUT", message: "timeout" };
    });
    await assert.rejects(
        helper.waitForAcceptedTask(helper.getServerConfig(), "task-1"),
        (error: unknown) => {
            assert.ok(error instanceof serverErrors.ServerRequestError);
            assert.equal(error.phase, "poll");
            return true;
        },
    );
    assert.equal(checks, 3);
    assert.equal(calls.posts, 0);
});

test("one interrupted poll recovers without losing or resubmitting the task", async () => {
    let checks = 0;
    const { helper, calls } = harness(async () => {
        if (++checks === 1) throw new TypeError("Failed to fetch");
        return {
            status: 200,
            data: {
                tasks: [
                    {
                        taskId: "task-1",
                        finished: true,
                        status: "success",
                        fileList: ["done.pdf"],
                    },
                ],
            },
        };
    });
    const result = await helper.waitForAcceptedTask(
        helper.getServerConfig(),
        "task-1",
    );
    assert.equal(result.status, "success");
    assert.equal(checks, 2);
    assert.equal(calls.posts, 0);
});

test("older Servers can still provide completed tasks through history", async () => {
    const { helper } = harness(async (url) =>
        url.endsWith("/tasks")
            ? { status: 404, data: {} }
            : {
                  status: 200,
                  data: {
                      history: [
                          {
                              taskId: "task-1",
                              finished: true,
                              status: "success",
                              fileList: ["done.pdf"],
                          },
                      ],
                  },
              },
    );
    const result = await helper.waitForAcceptedTask(
        helper.getServerConfig(),
        "task-1",
    );
    assert.equal(result.status, "success");
});
