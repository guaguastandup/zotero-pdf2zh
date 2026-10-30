import assert from "node:assert/strict";
import test from "node:test";
import ts from "typescript";
import fs from "node:fs";
import vm from "node:vm";

import {
    buildAttachmentTitle,
    extractYear,
    normalizeRenameStyle,
    titlePrefixOf,
} from "../src/modules/pdf2zhTitleFormat.ts";

// 直接 ESM 导入 + 兜底 vm 编译各跑一遍核心断言, 保证两种加载路径一致。
function loadViaVm() {
    const source = fs.readFileSync(
        new URL("../src/modules/pdf2zhTitleFormat.ts", import.meta.url),
        "utf8",
    );
    const js = ts.transpileModule(source, {
        compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
        },
    }).outputText;
    const exports = {};
    vm.runInContext(
        `(function(require, exports, module) {${js}\n})`,
        vm.createContext({}),
    )({}, exports, {});
    return exports as any;
}

function baseInput(overrides: Record<string, unknown> = {}) {
    return {
        title: "A Survey of Large Language Models",
        shortTitle: "LLM Survey",
        date: "2023-05-01",
        service: "siliconflowfree",
        type: "mono",
        style: "shortTitle",
        prefixLength: 20,
        template: "",
        ...overrides,
    };
}

test("shortTitle style keeps the historical output byte-for-byte", () => {
    assert.equal(
        buildAttachmentTitle(baseInput()),
        "LLM Survey-siliconflowfree-mono",
    );
    // 无短标题时退回 服务-类型 (旧行为)
    assert.equal(
        buildAttachmentTitle(baseInput({ shortTitle: "" })),
        "siliconflowfree-mono",
    );
});

test("titlePrefix style builds prefix-year-service-type (#310)", () => {
    const out = buildAttachmentTitle(
        baseInput({ style: "titlePrefix", prefixLength: 20 }),
    );
    assert.equal(out, "A Survey of Large La…-2023-siliconflowfree-mono");
    // 无年份时省略该段
    assert.equal(
        buildAttachmentTitle(
            baseInput({ style: "titlePrefix", date: "undated" }),
        ),
        "A Survey of Large La…-siliconflowfree-mono",
    );
    // 无标题条目退回短标题
    assert.equal(
        buildAttachmentTitle(baseInput({ style: "titlePrefix", title: "" })),
        "LLM Survey-2023-siliconflowfree-mono",
    );
    // 中文标题按字符截断
    assert.equal(
        buildAttachmentTitle(
            baseInput({
                style: "titlePrefix",
                title: "面向低资源场景的大模型高效推理方法综述",
                prefixLength: 10,
                date: "2024年3月",
            }),
        ),
        "面向低资源场景的大模…-2024-siliconflowfree-mono",
    );
});

test("fullTitle style uses the complete title", () => {
    assert.equal(
        buildAttachmentTitle(baseInput({ style: "fullTitle" })),
        "A Survey of Large Language Models-siliconflowfree-mono",
    );
});

test("custom template renders placeholders and falls back when empty", () => {
    assert.equal(
        buildAttachmentTitle(
            baseInput({ style: "custom", template: "{year} {type} [{service}]" }),
        ),
        "2023 mono [siliconflowfree]",
    );
    // 未知占位符原样保留; 已知占位符缺值时置空
    assert.equal(
        buildAttachmentTitle(
            baseInput({ style: "custom", template: "{nope}-{year}", date: "" }),
        ),
        "{nope}-",
    );
    // 模板渲染为空时退回 服务-类型
    assert.equal(
        buildAttachmentTitle(
            baseInput({ style: "custom", template: "{year}", date: "n/a" }),
        ),
        "siliconflowfree-mono",
    );
});

test("normalizeRenameStyle rejects unknown values to shortTitle", () => {
    assert.equal(normalizeRenameStyle("titlePrefix"), "titlePrefix");
    assert.equal(normalizeRenameStyle("bogus"), "shortTitle");
    assert.equal(normalizeRenameStyle(undefined), "shortTitle");
});

test("extractYear handles ISO, Chinese and English month formats", () => {
    assert.equal(extractYear("2023-05-01"), "2023");
    assert.equal(extractYear("2024年3月"), "2024");
    assert.equal(extractYear("May 2021"), "2021");
    assert.equal(extractYear("no year here"), "");
});

test("titlePrefixOf truncates with ellipsis and keeps short titles", () => {
    assert.equal(titlePrefixOf("short", 20), "short");
    assert.equal(titlePrefixOf("   a  b   ", 20), "a b");
    assert.equal(titlePrefixOf("abcdef", 3), "abc…");
    // 0 视为无效输入, 回退默认长度 20
    assert.equal(titlePrefixOf("abcdef", 0), "abcdef");
});

test("vm-compiled module matches ESM behavior", () => {
    const vmMod = loadViaVm();
    assert.equal(
        vmMod.buildAttachmentTitle(baseInput({ style: "titlePrefix" })),
        buildAttachmentTitle(baseInput({ style: "titlePrefix" })),
    );
    assert.equal(vmMod.extractYear("2023年5月"), "2023");
});
