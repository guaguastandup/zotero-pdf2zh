import assert from "node:assert/strict";
import test from "node:test";
import { posix } from "node:path";
import { discoverLocalServer } from "../src/modules/localServerDiscovery.ts";

function fixture(roots: string[], python = "") {
    const files = new Set(
        roots.flatMap((root) => [
            root + "/server.py",
            root + "/requirements.txt",
            root + "/utils/config.py",
        ]),
    );
    if (python) files.add(python);
    const readPaths: string[] = [];
    return {
        readPaths,
        io: {
            join: posix.join,
            isFile: async (path: string) => files.has(path),
            read: async (path: string) => {
                readPaths.push(path);
                return "PDF2zh --non-interactive";
            },
        },
    };
}
test("suggests a unique known installation with an existing adjacent Python", async () => {
    const root = "/home/test/Downloads/zotero-pdf2zh/server";
    const python = root + "/.venv/bin/python";
    const { io } = fixture([root], python);
    assert.deepEqual(await discoverLocalServer("/home/test", io), {
        scriptPath: root + "/server.py",
        pythonPath: python,
    });
});
test("does not choose between multiple installations", async () => {
    const { io } = fixture([
        "/home/test/server",
        "/home/test/Documents/server",
    ]);
    assert.deepEqual(await discoverLocalServer("/home/test", io), {});
});
test("keeps an explicitly supplied script as the only search target", async () => {
    const { io, readPaths } = fixture(["/custom/server", "/home/test/server"]);
    assert.deepEqual(
        await discoverLocalServer("/home/test", io, "/custom/server/server.py"),
        { scriptPath: "/custom/server/server.py" },
    );
    assert.deepEqual(readPaths, ["/custom/server/server.py"]);
});
test("missing and old installations retain manual setup without throwing", async () => {
    const { io } = fixture(["/home/test/server"]);
    io.read = async () => "PDF2zh older server";
    assert.deepEqual(await discoverLocalServer("/home/test", io), {});
    io.isFile = async () => {
        throw new Error("denied");
    };
    assert.deepEqual(await discoverLocalServer("/home/test", io), {});
});

for (const environment of ["zotero-pdf2zh-next-venv", "zotero-pdf2zh-venv"]) {
    test(`does not suggest translation environment ${environment}`, async () => {
        const root = "/home/test/server";
        const { io } = fixture(
            [root],
            `${root}/${environment}/Scripts/python.exe`,
        );
        assert.deepEqual(await discoverLocalServer("/home/test", io), {
            scriptPath: root + "/server.py",
        });
    });
}
test("suggests a dedicated Server venv on Windows", async () => {
    const root = "/home/test/server";
    const python = root + "/venv/Scripts/python.exe";
    const { io } = fixture([root], python);
    assert.deepEqual(await discoverLocalServer("/home/test", io), {
        scriptPath: root + "/server.py",
        pythonPath: python,
    });
});
