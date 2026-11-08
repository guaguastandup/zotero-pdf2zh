import assert from "node:assert/strict";
import test from "node:test";
import { win32 } from "node:path";
import {
    mkdtempSync,
    mkdirSync,
    symlinkSync,
    rmSync,
    unlinkSync,
    rmdirSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { spawn } from "node:child_process";
import {
    RuntimeBootstrapManager,
    cancelRuntimeBootstrapIfExists,
    createNativeRuntimeDependencies,
    assertWindowsSafePaths,
    UV_ARTIFACTS,
    UV_VERSION,
    type RuntimeDependencies,
} from "../src/modules/runtimeBootstrap.ts";

const root = "D:\\ZoteroPlugin\\PDF2zh";
const runtime = win32.join(root, "runtime");
const python = win32.join(runtime, "server-venv", "Scripts", "python.exe");
function fixture() {
    const links = new Set<string>();
    const files = new Map<string, string>([
        ["D:\\", ""],
        [win32.join(root, "server.py"), ""],
        [win32.join(root, "requirements.txt"), "flask"],
    ]);
    const commands: {
        command: string;
        args: string[];
        environment: Record<string, string>;
    }[] = [];
    let downloads = 0,
        extracts = 0,
        killed = 0;
    let digest = UV_ARTIFACTS.x64.sha256;
    let candidates: string[] = [];
    let healthExitCode = 0;
    let waitHook:
        | (() => Promise<{ exitCode: number; stdout?: string }>)
        | undefined;
    const io: RuntimeDependencies = {
        platform: "win32",
        architecture: "x64",
        join: win32.join,
        exists: async (path) => files.has(path),
        assertSafePaths: async (paths, _signal, recursiveRoots = []) => {
            for (const link of links) {
                if (
                    paths.some(
                        (path) => path === link || path.startsWith(link + "\\"),
                    ) ||
                    recursiveRoots.some((path) => link.startsWith(path + "\\"))
                )
                    throw new Error("安装路径包含符号链接或 junction");
            }
        },
        read: async (path) => files.get(path) || "",
        readBytes: async () => new Uint8Array([2]),
        write: async (path, value) => {
            files.set(path, typeof value === "string" ? value : "binary");
        },
        mkdir: async (path, exclusive) => {
            if (exclusive && files.has(path)) throw new Error("exists");
            files.set(path, "directory");
        },
        download: async () => {
            downloads++;
            return new Uint8Array([1]);
        },
        sha256: async (bytes) =>
            bytes[0] === 2 ? UV_ARTIFACTS.x64.executableSha256 : digest,
        extractUv: async (_archive, executable) => {
            extracts++;
            files.set(executable, "exe");
        },
        uvCandidates: () => candidates,
        environment: () => ({
            Path: "C:\\Windows",
            PYTHONHOME: "bad",
            PYTHONPATH: "bad",
            VIRTUAL_ENV: "unrelated",
        }),
        spawn: async (command, args, environment) => {
            commands.push({ command, args, environment });
            if (args.includes("venv")) {
                files.set(win32.join(runtime, "server-venv"), "directory");
                files.set(python, "python");
            }
            return {
                kill: async () => {
                    killed++;
                },
                wait: async () =>
                    waitHook
                        ? waitHook()
                        : {
                              exitCode: command === python ? healthExitCode : 0,
                              stdout: args.includes("--version")
                                  ? `uv ${UV_VERSION} (test)`
                                  : "",
                          },
            };
        },
    };
    const manager = new RuntimeBootstrapManager(io);
    return {
        io,
        manager,
        commands,
        files,
        links,
        counts: () => ({ downloads, extracts, killed }),
        setDigest: (value: string) => {
            digest = value;
        },
        setCandidates: (value: string[]) => {
            candidates = value;
        },
        setHealthExitCode: (value: number) => {
            healthExitCode = value;
        },
        setWaitHook: (value: typeof waitHook) => {
            waitHook = value;
        },
    };
}
test("fresh setup verifies official archive before extraction, isolates Python and forwards uv PATH", async () => {
    const f = fixture();
    const stages: string[] = [];
    const result = await f.manager.prepare({
        serverDirectory: root,
        onProgress: (p) => stages.push(p.stage),
    });
    assert.equal(result.pythonPath, python);
    assert.equal(f.counts().downloads, 1);
    assert.equal(result.environment.PYTHONHOME, "");
    assert.equal(result.environment.PYTHONPATH, "");
    assert.equal(result.environment.VIRTUAL_ENV, "");
    assert.equal(
        result.environment.UV_PYTHON_INSTALL_DIR,
        win32.join(runtime, "python"),
    );
    assert.ok(result.environment.Path.startsWith(runtime + ";"));
    assert.equal(result.environment.UV_PYTHON_PREFERENCE, "only-managed");
    for (const command of f.commands) {
        if (command.environment.UV_PYTHON_PREFERENCE)
            assert.ok(
                !command.args.includes("--managed-python"),
                "uv preference must not be specified twice",
            );
    }
    assert.equal(result.environment.PATH, undefined);
    const install = f.commands.find(
        (c) => c.args.includes("install") && c.args.includes("3.12"),
    );
    assert.ok(install?.args.includes("--no-bin"));
    assert.ok(install?.args.includes("--no-registry"));
    assert.deepEqual(stages, [
        "checking",
        "downloading-uv",
        "python",
        "venv",
        "dependencies",
        "ready",
    ]);
});
test("checksum mismatch never extracts or executes downloaded code", async () => {
    const f = fixture();
    f.setDigest("bad");
    await assert.rejects(
        f.manager.prepare({ serverDirectory: root }),
        /校验失败/,
    );
    assert.equal(f.counts().extracts, 0);
    assert.equal(f.commands.length, 0);
});
test("nonzero exit reports its stage without raw command output or credentials", async () => {
    const f = fixture();
    const original = f.io.spawn;
    f.io.spawn = async (...args) => {
        const child = await original(...args);
        return args[1].includes("venv")
            ? {
                  ...child,
                  wait: async () => ({
                      exitCode: 23,
                      stdout: "API_TOKEN=secret-value command --key private",
                  }),
              }
            : child;
    };
    await assert.rejects(
        f.manager.prepare({ serverDirectory: root }),
        (error: Error) => {
            assert.match(error.message, /阶段：venv/);
            assert.match(error.message, /23/);
            assert.doesNotMatch(
                error.message,
                /API_TOKEN|secret-value|--key|private/,
            );
            return true;
        },
    );
});
test("orchestration works when the Zotero sandbox has no DOM AbortController", async () => {
    const original = globalThis.AbortController;
    try {
        (globalThis as any).AbortController = undefined;
        const f = fixture();
        const result = await f.manager.prepare({ serverDirectory: root });
        assert.equal(result.pythonPath, python);
    } finally {
        globalThis.AbortController = original;
    }
});
test("never modifies an unowned runtime or a missing drive", async () => {
    const f = fixture();
    f.files.set(runtime, "directory");
    await assert.rejects(
        f.manager.prepare({ serverDirectory: root }),
        /不属于本插件/,
    );
    assert.equal(f.commands.length, 0);
    assert.equal(f.counts().downloads, 0);
    f.files.delete("D:\\");
    await assert.rejects(
        f.manager.prepare({ serverDirectory: root }),
        /磁盘不存在/,
    );
});
test("healthy existing managed runtime is reused offline without installation", async () => {
    const f = fixture();
    await f.manager.prepare({ serverDirectory: root });
    const previous = f.commands.length;
    await f.manager.prepare({ serverDirectory: root });
    assert.equal(f.counts().downloads, 1);
    assert.equal(f.commands.length, previous + 1);
    assert.equal(f.commands.at(-1)?.command, python);
});
test("an existing usable uv is reused without downloading or altering it", async () => {
    const f = fixture();
    const uv = "C:\\Users\\test\\.local\\bin\\uv.exe";
    f.setCandidates([uv]);
    f.files.set(uv, "existing");
    const result = await f.manager.prepare({ serverDirectory: root });
    assert.equal(result.uvPath, win32.join(runtime, "uv.exe"));
    assert.equal(f.counts().downloads, 0);
    assert.equal(f.files.get(uv), "existing");
});
test("same target calls deduplicate and notify each observer", async () => {
    const f = fixture();
    const seen: string[] = [];
    const first = f.manager.prepare({ serverDirectory: root });
    const second = f.manager.prepare({
        serverDirectory: root,
        onProgress: (p) => seen.push(p.stage),
    });
    assert.equal(first, second);
    await assert.rejects(
        f.manager.prepare({ root: "D:\\other", serverDirectory: root }),
        /正在进行/,
    );
    await first;
    assert.equal(f.counts().downloads, 1);
    assert.ok(seen.includes("ready"));
});
test("download cancellation stops before extraction and can be retried", async () => {
    const f = fixture();
    let entered!: () => void;
    const ready = new Promise<void>((r) => {
        entered = r;
    });
    const download = f.io.download;
    f.io.download = async (_url, signal) => {
        entered();
        return new Promise((_resolve, reject) =>
            signal.addEventListener(
                "abort",
                () => reject(new Error("cancelled")),
                { once: true },
            ),
        );
    };
    const pending = f.manager.prepare({ serverDirectory: root });
    await ready;
    await f.manager.cancel();
    await assert.rejects(pending);
    assert.equal(f.counts().extracts, 0);
    f.io.download = download;
    await f.manager.prepare({ serverDirectory: root });
});
test("cancellation kills only the child owned by this operation and waits for it", async () => {
    const f = fixture();
    let entered!: () => void, finish!: () => void;
    const ready = new Promise<void>((r) => {
        entered = r;
    });
    f.setWaitHook(
        () =>
            new Promise((resolve) => {
                entered();
                finish = () => resolve({ exitCode: 1 });
            }),
    );
    const original = f.io.spawn;
    f.io.spawn = async (...args) => {
        const process = await original(...args);
        return {
            ...process,
            kill: async () => {
                await process.kill();
                finish();
            },
        };
    };
    const pending = f.manager.prepare({ serverDirectory: root });
    await ready;
    await f.manager.cancel();
    await assert.rejects(pending, /取消/);
    assert.equal(f.counts().killed, 1);
});
test("incomplete existing venv is preserved with explicit recovery guidance", async () => {
    const f = fixture();
    f.files.set(runtime, "directory");
    f.files.set(
        win32.join(runtime, ".pdf2zh-managed"),
        "zotero-pdf2zh-runtime-v1",
    );
    f.files.set(win32.join(runtime, "server-venv"), "user-files");
    await assert.rejects(
        f.manager.prepare({ serverDirectory: root }),
        /不完整/,
    );
    assert.equal(f.files.get(win32.join(runtime, "server-venv")), "user-files");
});
test("all preexisting runtime targets and parent junctions are rejected before mutation", async () => {
    for (const path of [
        "D:\\ZoteroPlugin",
        root,
        runtime,
        win32.join(runtime, ".pdf2zh-managed"),
        win32.join(runtime, "uv.exe"),
        win32.join(runtime, `uv-${UV_VERSION}.zip`),
        win32.join(runtime, "server-venv"),
        win32.join(runtime, "server-venv", "Scripts"),
        win32.join(runtime, "python"),
        win32.join(runtime, "cache"),
    ]) {
        const f = fixture();
        f.links.add(path);
        const before = [...f.files];
        await assert.rejects(
            f.manager.prepare({ serverDirectory: root }),
            /junction/,
        );
        assert.deepEqual([...f.files], before, path);
        assert.equal(f.commands.length, 0, path);
    }
});
test("deep runtime junction is rejected before uv modifies the tree", async () => {
    const f = fixture();
    f.files.set(runtime, "directory");
    f.files.set(
        win32.join(runtime, ".pdf2zh-managed"),
        "zotero-pdf2zh-runtime-v1",
    );
    f.files.set(win32.join(runtime, "uv.exe"), "exe");
    f.links.add(win32.join(runtime, "cache", "outside"));
    await assert.rejects(
        f.manager.prepare({ serverDirectory: root }),
        /junction/,
    );
    assert.equal(f.commands.length, 0);
});
test("a junction introduced during download is rejected before archive writes", async () => {
    const f = fixture();
    f.io.download = async () => {
        f.links.add(win32.join(runtime, `uv-${UV_VERSION}.zip`));
        return new Uint8Array([1]);
    };
    await assert.rejects(
        f.manager.prepare({ serverDirectory: root }),
        /junction/,
    );
    assert.equal(
        f.files.has(win32.join(runtime, `uv-${UV_VERSION}.zip`)),
        false,
    );
    assert.equal(f.counts().extracts, 0);
});
test("shutdown cancellation has zero native initialization when no singleton exists", async () => {
    const original = (globalThis as any).Zotero;
    try {
        Object.defineProperty(globalThis, "Zotero", {
            configurable: true,
            get() {
                throw new Error("native initialization forbidden");
            },
        });
        await cancelRuntimeBootstrapIfExists();
    } finally {
        Object.defineProperty(globalThis, "Zotero", {
            configurable: true,
            writable: true,
            value: original,
        });
    }
});
test("native download resolves the current live main window on every call", async () => {
    const globals = globalThis as any;
    const previous = {
        Zotero: globals.Zotero,
        runtimeHost: globals.runtimeHost,
        ChromeUtils: globals.ChromeUtils,
    };
    const calls: string[] = [];
    const first = {
        closed: true,
        AbortController,
        fetch: async () => {
            throw new Error("stale window");
        },
    };
    const second = {
        closed: false,
        AbortController,
        fetch: async () => {
            calls.push("new window");
            return {
                ok: true,
                arrayBuffer: async () => new Uint8Array([1]).buffer,
            };
        },
    };
    let current: any = first;
    try {
        globals.Zotero = { isWin: true, getMainWindow: () => current };
        globals.runtimeHost = {
            Services: { appinfo: { XPCOMABI: "x86_64" } },
            Components: {},
        };
        globals.ChromeUtils = {
            importESModule: () => ({ setTimeout, clearTimeout }),
        };
        const native = createNativeRuntimeDependencies();
        current = second;
        const signal = {
            aborted: false,
            addEventListener() {},
            removeEventListener() {},
        };
        await native.download("https://example.invalid", signal);
        assert.deepEqual(calls, ["new window"]);
    } finally {
        Object.assign(globals, previous);
    }
});
test(
    "real Windows junction policy permits only the exact internal uv Python alias",
    { skip: process.platform !== "win32" },
    async () => {
        const globals = globalThis as any;
        const previous = {
            Zotero: globals.Zotero,
            runtimeHost: globals.runtimeHost,
            ChromeUtils: globals.ChromeUtils,
            PathUtils: globals.PathUtils,
        };
        const temporary = mkdtempSync(
            win32.join(tmpdir(), "pdf2zh-junction-test-"),
        );
        const outside = win32.join(temporary, "outside");
        const junction = win32.join(temporary, "runtime");
        mkdirSync(outside);
        symlinkSync(outside, junction, "junction");
        try {
            globals.Zotero = { isWin: true };
            globals.runtimeHost = {
                Services: {
                    env: { get: (name: string) => process.env[name] || "" },
                    appinfo: { XPCOMABI: "x86_64" },
                },
                Components: {},
            };
            globals.PathUtils = win32;
            globals.ChromeUtils = {
                importESModule: (module: string) =>
                    module.includes("Timer")
                        ? { setTimeout, clearTimeout }
                        : {
                              Subprocess: {
                                  call: async (spec: any) => {
                                      const child = spawn(
                                          spec.command,
                                          spec.arguments,
                                          {
                                              env: spec.environment,
                                              cwd: spec.workdir,
                                              windowsHide: true,
                                          },
                                      );
                                      const finished = new Promise<{
                                          exitCode: number;
                                      }>((resolve) =>
                                          child.on("close", (code) =>
                                              resolve({ exitCode: code ?? -1 }),
                                          ),
                                      );
                                      child.stderr.resume();
                                      child.stdout.resume();
                                      return {
                                          stdout: {
                                              readString: async () => "",
                                          },
                                          wait: () => finished,
                                          kill: () => child.kill(),
                                      };
                                  },
                              },
                          },
            };
            await assertWindowsSafePaths([outside]);
            await assert.rejects(
                assertWindowsSafePaths([junction]),
                /junction/,
            );
            await assert.rejects(
                assertWindowsSafePaths([
                    win32.join(junction, "not-created", "uv.exe"),
                ]),
                /junction/,
            );
            const pythonRoot = win32.join(temporary, "python");
            const version = "cpython-3.12.13-windows-x86_64-none";
            const target = win32.join(pythonRoot, version);
            const alias = win32.join(
                pythonRoot,
                "cpython-3.12-windows-x86_64-none",
            );
            const prefixOutside = win32.join(
                temporary,
                "python-outside",
                version,
            );
            mkdirSync(target, { recursive: true });
            mkdirSync(prefixOutside, { recursive: true });
            const signal = {
                aborted: false,
                addEventListener() {},
                removeEventListener() {},
            };
            const native = createNativeRuntimeDependencies();
            const inspect = () =>
                native.assertSafePaths(
                    [pythonRoot],
                    signal,
                    [pythonRoot],
                    pythonRoot,
                );
            symlinkSync(target, alias, "junction");
            await inspect();
            // The public bundle checker never receives the alias allowance.
            await assert.rejects(assertWindowsSafePaths([alias]), /junction/);
            unlinkSync(alias);
            symlinkSync(prefixOutside, alias, "junction");
            await assert.rejects(inspect(), /junction/);
            unlinkSync(alias);
            const wrongTarget = win32.join(pythonRoot, "unrelated-python");
            mkdirSync(wrongTarget);
            symlinkSync(wrongTarget, alias, "junction");
            await assert.rejects(inspect(), /junction/);
            unlinkSync(alias);
            const wrongArchitecture = win32.join(
                pythonRoot,
                "cpython-3.12-windows-aarch64-none",
            );
            symlinkSync(target, wrongArchitecture, "junction");
            await assert.rejects(inspect(), /junction/);
            unlinkSync(wrongArchitecture);
            // A matching leaf name cannot hide an alias chain to external content.
            rmdirSync(target);
            symlinkSync(prefixOutside, target, "junction");
            symlinkSync(target, alias, "junction");
            await assert.rejects(inspect(), /junction/);
        } finally {
            Object.assign(globals, previous);
            rmSync(temporary, { recursive: true, force: true });
        }
    },
);
