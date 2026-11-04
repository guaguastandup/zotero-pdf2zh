import assert from "node:assert/strict";
import test from "node:test";

// classifyErrorFromText 读取全局 Zotero.locale；测试环境注入 zh-CN。
(globalThis as Record<string, unknown>).Zotero = { locale: "zh-CN" };

const { classifyErrorFromText, presentableError } = await import(
    "../src/modules/errorCatalog.ts"
);

test("scanned PDF errors classify with actionable hint", () => {
    for (const text of [
        "ERROR:babeldoc:This document contains no graphs",
        "scanned pdf detected",
    ]) {
        const r = classifyErrorFromText(text);
        assert.equal(r.errorCode, "PDF_UNREADABLE_TEXT");
        assert.ok(r.userMessage.includes("读不出"));
        assert.ok(r.hint.includes("OCR"));
    }
});

test("CID chars error classifies (#363-style real log)", () => {
    const r = classifyErrorFromText(
        "Babeldoc translation error: The document contains too many CID chars.",
    );
    assert.equal(r.errorCode, "PDF_UNREADABLE_TEXT");
});

test("known API authentication and unknown balances are distinct", () => {
    // 只有明确的服务端鉴权错误才给出针对性的解读。
    assert.equal(
        classifyErrorFromText("Error code 401 - Incorrect API key provided")
            .errorCode,
        "API_AUTH_FAILED",
    );
    assert.equal(
        classifyErrorFromText("Balance is insufficient for the request")
            .errorCode,
        "UNKNOWN_ERROR",
    );
});

test("already-friendly server message passes through unchanged", () => {
    const friendly =
        "检测到扫描版 PDF：页面是图片，没有可提取的文字层，无法翻译。";
    // Server 新版已分类的中文消息本身不含英文关键词, 不应被二次加工。
    const r = classifyErrorFromText(friendly);
    assert.equal(r.userMessage, friendly);
});

test("presentableError prefers server userMessage/hint", () => {
    const out = presentableError("raw engine error", {
        userMessage: "扫描版 PDF。",
        hint: "请先 OCR。",
    });
    assert.equal(out, "扫描版 PDF。\n请先 OCR。");
});

test("presentableError falls back to local classification", () => {
    const out = presentableError("The document contains no graphs");
    assert.ok(out.includes("读不出"));
    assert.ok(out.includes("OCR"));
});

test("unknown errors keep original text", () => {
    assert.equal(
        presentableError("some brand new failure"),
        "some brand new failure",
    );
});

test("known BitStream and provider errors get specific codes", () => {
    const bitstring =
        "ImportError: cannot import name 'BitStream' from 'bitstring'";
    const limited = "Error: status code 429 - Too Many Requests";
    const unauthorized = "AuthenticationError: invalid_api_key";
    const unknown = "Unrelated failed operation";

    function codeOf(value: string) {
        return classifyErrorFromText(value).errorCode;
    }

    assert.equal(codeOf(bitstring), "BITSTRING_INCOMPATIBLE");
    assert.equal(codeOf(limited), "API_RATE_LIMIT");
    assert.equal(codeOf(unauthorized), "API_AUTH_FAILED");
    assert.equal(codeOf(unknown), "UNKNOWN_ERROR");
});
