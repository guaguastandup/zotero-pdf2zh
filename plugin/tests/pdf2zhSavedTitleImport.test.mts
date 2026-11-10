import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import * as titleFormat from "../src/modules/pdf2zhTitleFormat.ts";

// Run the real unified import entry point without a Zotero installation or server.
function setup(style = "translatedTitle") {
    const imported: any[] = [];
    const parents = new Map();
    const source = fs.readFileSync(
        new URL("../src/modules/pdf2zhHelper.ts", import.meta.url),
        "utf8",
    );
    const exports: any = {};
    const prefs: Record<string, unknown> = {
        renameStyle: style,
        renameTemplate: "{translatedTitle}-{type}",
    };
    const context = vm.createContext({
        Zotero: {
            Items: { get: (id: number) => parents.get(id) },
            File: { getValidFileName: (name: string) => name },
            Attachments: {
                importFromFile: async (options: any) => {
                    imported.push(options);
                    return { id: imported.length };
                },
            },
        },
        ztoolkit: { log() {} },
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
    return { imported, parents, item, add };
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
