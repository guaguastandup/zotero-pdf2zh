import assert from "node:assert/strict";
import test from "node:test";
import { supportsWenyi } from "../src/modules/pdf2zhWenyiSupport.ts";

test("server health payload with wenyi engine is accepted", () => {
    assert.equal(
        supportsWenyi({
            status: "ok",
            version: "9.9.9",
            engines: ["pdf2zh", "pdf2zh_next", "wenyi"],
        }),
        true,
    );
});

test("payloads without a wenyi engine entry are rejected", () => {
    // 旧版 Server 的 /health 没有 engines 字段, 必须拒绝而不是静默回退。
    assert.equal(supportsWenyi({ status: "ok", version: "1.0.0" }), false);
    assert.equal(
        supportsWenyi({
            status: "ok",
            engines: ["pdf2zh", "pdf2zh_next"],
        }),
        false,
    );
});

test("malformed payloads never crash the capability check", () => {
    for (const value of [
        undefined,
        null,
        "",
        "wenyi",
        42,
        [],
        ["wenyi"],
        { engines: "wenyi" },
        { engines: null },
    ]) {
        assert.equal(supportsWenyi(value), false);
    }
});
