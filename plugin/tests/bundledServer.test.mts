import assert from "node:assert/strict";
import test from "node:test";
import { createHash } from "node:crypto";
import {
    installBundledServer,
    BundledServerInstallationController,
    decodeBundledServerFile,
    readBundledServerManifest,
} from "../src/modules/bundledServer.ts";
function fixture() {
    const files = new Map<string, Uint8Array>();
    const dirs = new Set<string>();
    const io = {
        assertSafePaths: async (_paths: string[]) => {},
        kind: async (p: string) =>
            files.has(p) ? "file" : dirs.has(p) ? "directory" : "missing",
        read: async (p: string) => files.get(p)!,
        mkdir: async (p: string) => {
            dirs.add(p);
        },
        write: async (p: string, d: Uint8Array) => {
            assert(!files.has(p));
            files.set(p, d);
        },
        decode: (d: string) => new Uint8Array(Buffer.from(d, "base64")),
        hash: async (d: Uint8Array) =>
            createHash("sha256").update(d).digest("hex"),
    };
    const d = Buffer.from("server code");
    const bundle = {
        version: "test",
        files: [
            {
                path: "server.py",
                base64: d.toString("base64"),
                sha256: createHash("sha256").update(d).digest("hex"),
            },
        ],
    };
    return { files, dirs, io, bundle };
}
const target = "D:\\ZoteroPlugin\\PDF2zh";
test("empty directory install is idempotent", async () => {
    const f = fixture();
    f.dirs.add(target);
    const r = await installBundledServer(f.bundle, f.io);
    assert.equal(r.scriptPath, target + "\\server.py");
    await installBundledServer(f.bundle, f.io);
    assert.equal(f.files.size, 1);
});
test("conflicting files are never overwritten", async () => {
    const f = fixture();
    f.files.set(target + "\\server.py", Buffer.from("user"));
    await assert.rejects(installBundledServer(f.bundle, f.io), /conflict/i);
    assert.equal(f.files.size, 1);
});
test("preserves existing user config", async () => {
    const f = fixture();
    f.files.set(target + "\\config\\config.json", Buffer.from("secret"));
    await installBundledServer(f.bundle, f.io);
    assert.equal(f.files.size, 2);
});
for (const p of [
    "../escape",
    "C:/escape",
    "utils/../../escape",
    "utils\\escape",
    "CON",
    "Server.py",
    "utils/a:stream",
    "utils/a.",
])
    test(`reject unsafe ${p}`, async () => {
        const f = fixture();
        f.bundle.files[0].path = p;
        await assert.rejects(installBundledServer(f.bundle, f.io));
        assert.equal(f.files.size, 0);
    });
test("hash mismatch rejects before mutation", async () => {
    const f = fixture();
    f.bundle.files[0].sha256 = "0".repeat(64);
    await assert.rejects(installBundledServer(f.bundle, f.io), /hash/i);
    assert.equal(f.dirs.size, 0);
});
test("parent file conflict rejects", async () => {
    const f = fixture();
    f.files.set("D:\\ZoteroPlugin", Buffer.from("occupied"));
    await assert.rejects(installBundledServer(f.bundle, f.io), /conflict/i);
    assert.equal(f.files.size, 1);
});

test("recovers after an interrupted install", async () => {
    const f = fixture();
    const d = Buffer.from("extra");
    f.bundle.files.push({
        path: "utils/config.py",
        base64: d.toString("base64"),
        sha256: createHash("sha256").update(d).digest("hex"),
    });
    const write = f.io.write;
    let calls = 0;
    f.io.write = async (p, d) => {
        if (++calls === 2) throw new Error("interrupted");
        await write(p, d);
    };
    await assert.rejects(installBundledServer(f.bundle, f.io), /interrupted/);
    f.io.write = write;
    await installBundledServer(f.bundle, f.io);
    assert.equal(f.files.size, 2);
});
test("rejects linked parent directories", async () => {
    const f = fixture();
    const kind = f.io.kind;
    f.io.kind = async (p) => (p === "D:\\ZoteroPlugin" ? "symlink" : kind(p));
    await assert.rejects(installBundledServer(f.bundle, f.io), /conflict/);
    assert.equal(f.files.size, 0);
});
test("directory occupying a payload file is a conflict", async () => {
    const f = fixture();
    f.dirs.add(target + "\\server.py");
    await assert.rejects(installBundledServer(f.bundle, f.io), /conflict/i);
    assert.equal(f.files.size, 0);
});
test("a late conflict does not leave earlier new files", async () => {
    const f = fixture();
    const d = Buffer.from("extra");
    f.bundle.files.push({
        path: "utils/config.py",
        base64: d.toString("base64"),
        sha256: createHash("sha256").update(d).digest("hex"),
    });
    f.files.set(target + "\\utils\\config.py", Buffer.from("custom"));
    await assert.rejects(installBundledServer(f.bundle, f.io), /conflict/i);
    assert.equal(f.files.size, 1);
    assert(!f.files.has(target + "\\server.py"));
});

test("decodes binary using the injected Zotero window capability", () => {
    const window = {
        marker: "window",
        atob(data: string) {
            assert.equal(this.marker, "window");
            assert.equal(data, "AP+A");
            return "\x00\xff\x80";
        },
    };
    assert.deepEqual(
        [...decodeBundledServerFile("AP+A", window)],
        [0, 255, 128],
    );
});
test("default decoder obtains atob from the Zotero main window", () => {
    const runtime = globalThis as any;
    const previous = runtime.Zotero;
    let called = false;
    runtime.Zotero = {
        getMainWindow: () => ({
            atob: () => {
                called = true;
                return "A";
            },
        }),
    };
    try {
        assert.deepEqual([...decodeBundledServerFile("QQ==")], [65]);
        assert(called);
    } finally {
        if (previous === undefined) delete runtime.Zotero;
        else runtime.Zotero = previous;
    }
});
test("reads an XPI jar containing @ through the native resource channel", async () => {
    const { createRequire } = await import("node:module");
    const AdmZip = createRequire(import.meta.url)("adm-zip");
    const archive = new AdmZip();
    const fixtureBundle = fixture().bundle;
    fixtureBundle.files.push({ ...fixtureBundle.files[0], path: "bo.mp3" });
    archive.addFile(
        "content/bundled-server.json",
        Buffer.from(JSON.stringify(fixtureBundle)),
    );
    const xpi = new AdmZip(archive.toBuffer());
    const runtime = globalThis as any;
    const previous = runtime.Zotero;
    runtime.Zotero = {
        File: {
            getContentsFromURLAsync: async () => {
                throw new Error(
                    "HTTP URI.username must never be consulted for jar resources",
                );
            },
            getResourceAsync: async (url: string) => {
                assert.equal(
                    url,
                    "jar:file:///test/pdf2zh@guaguastandup.com.xpi!/content/bundled-server.json",
                );
                return xpi.readAsText("content/bundled-server.json");
            },
        },
    };
    try {
        const bundle = await readBundledServerManifest(
            "jar:file:///test/pdf2zh@guaguastandup.com.xpi!/",
        );
        assert(bundle.files.some((f) => f.path === "server.py"));
        assert(bundle.files.some((f) => f.path === "bo.mp3"));
    } finally {
        if (previous === undefined) delete runtime.Zotero;
        else runtime.Zotero = previous;
    }
});
test("refuses installation when Windows path safety capability is absent", async () => {
    const f = fixture();
    await assert.rejects(
        installBundledServer(f.bundle, {
            ...f.io,
            assertSafePaths: undefined,
        } as any),
        /safety|capability/i,
    );
    assert.equal(f.files.size, 0);
});
test("junction guard rejects before any filesystem mutation", async () => {
    const f = fixture();
    const io = {
        assertSafePaths: async (_paths: string[]) => {},
        ...f.io,
        assertSafePaths: async (_paths: string[]) => {
            throw new Error("ReparsePoint junction rejected");
        },
    };
    await assert.rejects(installBundledServer(f.bundle, io), /ReparsePoint/);
    assert.equal(f.dirs.size, 0);
    assert.equal(f.files.size, 0);
});
test("rechecks paths immediately before writes after creating directories", async () => {
    const f = fixture();
    const mkdir = f.io.mkdir;
    let swapped = false;
    f.io.mkdir = async (path) => {
        await mkdir(path);
        if (path === target) swapped = true;
    };
    f.io.assertSafePaths = async (paths) => {
        if (swapped && paths.includes(target + "\\server.py"))
            throw new Error("ReparsePoint changed before write");
    };
    await assert.rejects(
        installBundledServer(f.bundle, f.io),
        /ReparsePoint changed/,
    );
    assert.equal(f.files.size, 0);
});
test("full path guard covers nested payloads before mutations", async () => {
    const f = fixture();
    const d = Buffer.from("nested");
    f.bundle.files.push({
        path: "utils/config.py",
        base64: d.toString("base64"),
        sha256: createHash("sha256").update(d).digest("hex"),
    });
    let first = true;
    f.io.assertSafePaths = async (paths) => {
        if (first) {
            first = false;
            assert(paths.includes("D:\\ZoteroPlugin"));
            assert(paths.includes(target));
            assert(paths.includes(target + "\\utils"));
            assert(paths.includes(target + "\\utils\\config.py"));
            assert.equal(f.dirs.size, 0);
        }
    };
    await installBundledServer(f.bundle, f.io);
    assert(!first);
});

test("cancellation waits for active IO, stops further writes and permits retry", async () => {
    const f = fixture();
    const d = Buffer.from("second");
    f.bundle.files.push({
        path: "utils/config.py",
        base64: d.toString("base64"),
        sha256: createHash("sha256").update(d).digest("hex"),
    });
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
        release = resolve;
    });
    let entered!: () => void;
    const writing = new Promise<void>((resolve) => {
        entered = resolve;
    });
    const original = f.io.write;
    let writes = 0;
    f.io.write = async (path, data) => {
        await original(path, data);
        writes++;
        if (writes === 1) {
            entered();
            await gate;
        }
    };
    const controller = new BundledServerInstallationController();
    const run = (check: () => void) =>
        installBundledServer(f.bundle, f.io, check);
    const pending = controller.start(run);
    assert.equal(controller.start(run), pending);
    const rejected = assert.rejects(pending, /cancelled/i);
    await writing;
    let finished = false;
    const cancelled = controller.cancel().then(() => {
        finished = true;
    });
    await Promise.resolve();
    assert(!finished);
    release();
    await cancelled;
    await rejected;
    assert.equal(writes, 1);
    assert.equal(f.files.size, 1);
    await controller.start(run);
    assert.equal(f.files.size, 2);
    assert.equal(writes, 2);
});
test("cancellation during a path guard prevents directory creation", async () => {
    const f = fixture();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
        release = resolve;
    });
    let entered!: () => void;
    const checking = new Promise<void>((resolve) => {
        entered = resolve;
    });
    f.io.assertSafePaths = async () => {
        entered();
        await gate;
    };
    const controller = new BundledServerInstallationController();
    const pending = controller.start((check) =>
        installBundledServer(f.bundle, f.io, check),
    );
    const rejected = assert.rejects(pending, /cancelled/i);
    await checking;
    const cancelled = controller.cancel();
    release();
    await cancelled;
    await rejected;
    assert.equal(f.dirs.size, 0);
    assert.equal(f.files.size, 0);
});
