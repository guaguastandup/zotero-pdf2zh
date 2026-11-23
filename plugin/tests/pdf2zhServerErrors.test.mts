import assert from "node:assert/strict";
import test from "node:test";
import {
    ServerRequestError,
    formatServerRequestError,
    normalizeServerAddress,
    probeServerHealth,
    withServerTransport,
} from "../src/modules/pdf2zhServerErrors.ts";

const text = (key: string, args?: Record<string, unknown>) =>
    `${key}${args ? ` ${JSON.stringify(args)}` : ""}`;
const address = "http://localhost:8890";

test("missing and malformed addresses fail before any request", async () => {
    let calls = 0;
    for (const input of [
        "",
        "localhost:8890",
        "file:///tmp/test",
        "http:/localhost:8890",
        `${address}?token=x`,
    ]) {
        await assert.rejects(
            probeServerHealth(input, async () => {
                calls++;
                return { status: 200, data: {} };
            }),
            ServerRequestError,
        );
    }
    assert.equal(calls, 0);
});

test("address normalization supports HTTPS, IPv6 and proxy path prefixes", () => {
    assert.equal(normalizeServerAddress(` ${address}/// `), address);
    assert.equal(
        normalizeServerAddress("https://example.test/pdf2zh/"),
        "https://example.test/pdf2zh",
    );
    assert.equal(
        normalizeServerAddress("http://[::1]:8890"),
        "http://[::1]:8890",
    );
});

test("a successful health check uses the normalized address", async () => {
    const result = await probeServerHealth(`${address}/`, async (url) => {
        assert.equal(url, `${address}/health`);
        return { status: 200, data: { status: "ok", version: "4.1.7" } };
    });
    assert.deepEqual(result, { serverUrl: address, version: "4.1.7" });
});

test("address validation can use Zotero's window URL constructor", () => {
    const globals = globalThis as any;
    const originalURL = globals.URL;
    const originalToolkit = globals.ztoolkit;
    try {
        globals.URL = undefined;
        globals.ztoolkit = {
            getGlobal: (name: string) => {
                assert.equal(name, "URL");
                return originalURL;
            },
        };
        assert.equal(normalizeServerAddress(address), address);
    } finally {
        globals.URL = originalURL;
        if (originalToolkit === undefined) delete globals.ztoolkit;
        else globals.ztoolkit = originalToolkit;
    }
});

test("a stopped Server produces connection guidance before submission", async () => {
    await assert.rejects(
        probeServerHealth(address, async () => {
            throw {
                name: "TypeError",
                message: "NetworkError when attempting to fetch resource.",
            };
        }),
        (error: unknown) => {
            const message = formatServerRequestError(error, text)!;
            assert.match(message, /server-error-unreachable-title/);
            assert.match(message, /server-error-unreachable-help/);
            assert.match(message, /server-error-phase-check/);
            assert.match(message, /NetworkError/); // Detail remains available for support.
            return true;
        },
    );
});

test("Axios timeout and network errors are presented separately", async () => {
    for (const code of ["ECONNABORTED", "ETIMEDOUT", "ERR_NETWORK"]) {
        await assert.rejects(
            withServerTransport(address, "check", async () => {
                throw { code, message: "request failed" };
            }),
            (error: unknown) => {
                assert.ok(error instanceof ServerRequestError);
                assert.equal(
                    error.kind,
                    code === "ERR_NETWORK" ? "unreachable" : "timeout",
                );
                return true;
            },
        );
    }
});

test("HTML and unrelated JSON responses do not leak into the popup", async () => {
    for (const data of [
        "<html>Proxy login</html>",
        null,
        { status: "ok" },
        { version: "1.0" },
    ]) {
        await assert.rejects(
            probeServerHealth(address, async () => ({ status: 200, data })),
            (error: unknown) => {
                const message = formatServerRequestError(error, text)!;
                assert.match(message, /server-error-unexpected-response-title/);
                assert.doesNotMatch(message, /<html>/);
                return true;
            },
        );
    }
});

test("HTTP failures get guidance for their status rather than Server-offline text", () => {
    for (const [status, kind] of [
        [403, "access-denied"],
        [404, "unexpected-response"],
        [413, "file-too-large"],
        [503, "http"],
    ] as const) {
        const message = formatServerRequestError(
            new ServerRequestError(
                "http",
                address,
                "submit",
                `HTTP ${status}`,
                status,
            ),
            text,
        )!;
        assert.match(message, new RegExp(`server-error-${kind}-title`));
        assert.doesNotMatch(message, /server-error-unreachable/);
    }
});

test("transport failures after submission do not claim nothing was submitted", async () => {
    let calls = 0;
    await assert.rejects(
        withServerTransport(address, "submit", async () => {
            calls++;
            throw new TypeError("Failed to fetch");
        }),
        (error: unknown) => {
            const message = formatServerRequestError(error, text)!;
            assert.match(message, /server-error-phase-submit/);
            assert.doesNotMatch(message, /server-error-phase-check/);
            return true;
        },
    );
    assert.equal(
        calls,
        1,
        "translation submissions must not be automatically retried",
    );
});

test("download errors retain context through the transport boundary", async () => {
    const failure = new ServerRequestError(
        "http",
        address,
        "download",
        "HTTP 503",
        503,
    );
    await assert.rejects(
        withServerTransport(address, "download", async () => {
            throw failure;
        }),
        (error: unknown) => {
            assert.equal(error, failure);
            assert.match(
                formatServerRequestError(error, text)!,
                /server-error-phase-download/,
            );
            return true;
        },
    );
});

test("a missing result file is not described as a wrong Server address", () => {
    const message = formatServerRequestError(
        new ServerRequestError("http", address, "download", "HTTP 404", 404),
        text,
    )!;
    assert.match(message, /server-error-file-missing-help/);
    assert.doesNotMatch(message, /server-error-unexpected-response/);
});

test("provider and PDF errors are not mislabeled as a local connection problem", () => {
    for (const message of [
        "Invalid API key",
        "PDF cannot be parsed",
        "LLM provider NetworkError",
    ]) {
        assert.equal(formatServerRequestError(new Error(message), text), null);
    }
});

test("connection error popups omit the configured address and redact URLs from details", () => {
    const message = formatServerRequestError(
        new ServerRequestError(
            "unreachable",
            "http://alice:secret@example.test/?token=private",
            "check",
            "Failed to fetch http://alice:secret@example.test/?token=private",
        ),
        text,
    )!;
    assert.doesNotMatch(message, /alice|secret|private/);
    assert.doesNotMatch(message, /example\.test|server-error-address/);
});
