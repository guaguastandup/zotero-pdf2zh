import assert from "node:assert/strict";
import test from "node:test";
import {
    classifyPDFFileName,
    taskFinishedWithoutFiles,
    validatePDFBytes,
} from "../src/modules/pdf2zhAttachmentUtils.ts";

const bytes = (value: string) => new TextEncoder().encode(value);

test("accepts a PDF with harmless leading and trailing bytes", () => {
    assert.doesNotThrow(() =>
        validatePDFBytes(
            bytes("prefix\n%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\ntrailer"),
            "valid.pdf",
        ),
    );
});

test("rejects an HTTP 200 HTML error page", () => {
    assert.throws(
        () => validatePDFBytes(bytes("<html>proxy error</html>"), "bad.pdf"),
        /不是完整 PDF/,
    );
});

test("rejects a truncated PDF without EOF", () => {
    assert.throws(
        () => validatePDFBytes(bytes("%PDF-1.7\n1 0 obj"), "cut.pdf"),
        /不是完整 PDF/,
    );
});

test("recognizes only matching successful tasks without files", () => {
    assert.equal(
        taskFinishedWithoutFiles(
            { taskId: "task-1", finished: true, status: "完成" },
            "task-1",
        ),
        true,
    );
    assert.equal(
        taskFinishedWithoutFiles(
            {
                taskId: "task-1",
                finished: true,
                status: "完成",
                fileList: ["done.pdf"],
            },
            "task-1",
        ),
        false,
    );
    assert.equal(
        taskFinishedWithoutFiles(
            { taskId: "task-1", finished: true, status: "失败" },
            "task-1",
        ),
        false,
    );
    assert.equal(
        taskFinishedWithoutFiles(
            { taskId: "another", finished: true, status: "完成" },
            "task-1",
        ),
        false,
    );
});

import { isPDFPath } from "../src/modules/pdf2zhAttachmentUtils.ts";
test("PDF extension matching accepts mixed case without accepting other files", () => {
    for (const path of ["Paper.pdf", "Paper.PDF", "Paper.PdF", "a.pdf.pdf"]) {
        assert.equal(isPDFPath(path), true);
    }
    for (const path of [null, undefined, "", "paper.pdf.txt", "paperpdf"]) {
        assert.equal(isPDFPath(path), false);
    }
});

test("classifyPDFFileName recognizes real product suffixes", () => {
    // legacy engine products
    assert.equal(classifyPDFFileName("Paper-mono.pdf"), "mono");
    assert.equal(classifyPDFFileName("Paper-dual.pdf"), "dual");
    assert.equal(classifyPDFFileName("Paper-mono-cut.pdf"), "mono-cut");
    assert.equal(classifyPDFFileName("Paper-dual-cut.pdf"), "dual-cut");
    assert.equal(classifyPDFFileName("Paper-compare.pdf"), "compare");
    assert.equal(classifyPDFFileName("Paper-cut.pdf"), "origin-cut");
    // pdf2zh_next products (dot-separated, locale watermark infix)
    assert.equal(
        classifyPDFFileName("a.pdf.no_watermark.zh-CN.dual.pdf"),
        "dual",
    );
    assert.equal(classifyPDFFileName("Paper.mono.pdf"), "mono");
    // dual-mode layout variants, mixed case
    assert.equal(classifyPDFFileName("Paper.LR_Dual.pdf"), "dual");
    assert.equal(classifyPDFFileName("Paper.TB_DUAL.pdf"), "dual");
});

test("classifyPDFFileName no longer misclassifies user papers (real report)", () => {
    // 用户论文文件名以 dual.pdf 结尾但没有分隔符: 不是我们的产物, 必须可翻译
    assert.equal(classifyPDFFileName("Quaternion dual.pdf"), "origin");
    assert.equal(classifyPDFFileName("visualdual.pdf"), "origin");
    assert.equal(classifyPDFFileName("Vision Dual.pdf"), "origin");
    assert.equal(classifyPDFFileName("dual.pdf"), "origin");
    // mono 同理
    assert.equal(classifyPDFFileName("Polymer mono.pdf"), "origin");
    assert.equal(classifyPDFFileName("compare.pdf"), "origin");
});
