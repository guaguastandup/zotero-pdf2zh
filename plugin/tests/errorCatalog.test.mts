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
        assert.equal(r.errorCode, "SCANNED_PDF_DETECTED");
        assert.ok(r.userMessage.includes("扫描版"));
        assert.ok(r.hint.includes("OCR"));
    }
});

test("CID chars error classifies (#363-style real log)", () => {
    const r = classifyErrorFromText(
        "Babeldoc translation error: The document contains too many CID chars.",
    );
    assert.equal(r.errorCode, "PDF_CID_CHARS_TOO_MANY");
});

test("provider errors classify", () => {
    assert.equal(
        classifyErrorFromText("Error code 401 - Incorrect API key provided")
            .errorCode,
        "LLM_API_KEY_INVALID",
    );
    assert.equal(
        classifyErrorFromText("Balance is insufficient for the request")
            .errorCode,
        "UPSTREAM_BALANCE_INSUFFICIENT",
    );
});

test("already-friendly server message passes through unchanged", () => {
    const friendly = "检测到扫描版 PDF：页面是图片，没有可提取的文字层，无法翻译。";
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
    assert.ok(out.includes("扫描版"));
    assert.ok(out.includes("OCR"));
});

test("unknown errors keep original text", () => {
    assert.equal(
        presentableError("some brand new failure"),
        "some brand new failure",
    );
});
