import assert from "node:assert/strict";
import test from "node:test";
import {
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
