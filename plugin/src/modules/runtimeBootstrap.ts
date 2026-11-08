/** Isolated Windows setup. No shell, global installs, or unowned directory removal. */
export const DEFAULT_RUNTIME_ROOT = "D:\\ZoteroPlugin\\PDF2zh";
export const UV_VERSION = "0.13.7";
export const UV_ARTIFACTS = {
    x64: {
        url: `https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-pc-windows-msvc.zip`,
        sha256: "0cdc5b38fe5a8168ed6a25814f5ba43c21d313dd3187314fccb37b7cec46e021",
        executableSha256:
            "1791d7a9ed5b6df13ccf80f102e025c333010d96326b4ff0262aa3b578835c5a",
    },
    arm64: {
        url: `https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-aarch64-pc-windows-msvc.zip`,
        sha256: "505d9e65e7692bac3ddf98c66754aa26c5050c409c184af30a881a0a72cc85e3",
        executableSha256:
            "b1633856a68112cbfd9e81225066c986fecac4355bba4623eafd20d95f29b56f",
    },
};
const OWNER = "zotero-pdf2zh-runtime-v1";
export type RuntimeStage =
    | "checking"
    | "downloading-uv"
    | "python"
    | "venv"
    | "dependencies"
    | "ready"
    | "cancelled"
    | "failed";
export interface RuntimeProgress {
    stage: RuntimeStage;
    message: string;
}
export interface RuntimeResult {
    root: string;
    pythonPath: string;
    uvPath: string;
    environment: Record<string, string>;
}
export interface RuntimeOptions {
    root?: string;
    serverDirectory: string;
    onProgress?: (progress: RuntimeProgress) => void;
}
export interface RuntimeProcess {
    wait(): Promise<{ exitCode: number; stdout?: string }>;
    kill(): Promise<unknown> | unknown;
}
export interface RuntimeDependencies {
    platform: string;
    architecture: "x64" | "arm64";
    join(...parts: string[]): string;
    exists(path: string): Promise<boolean>;
    assertSafePaths(
        paths: string[],
        signal: RuntimeCancellationSignal,
        recursiveRoots?: string[],
        pythonAliasRoot?: string,
    ): Promise<void>;
    read(path: string): Promise<string>;
    readBytes(path: string): Promise<Uint8Array>;
    write(path: string, value: string | Uint8Array): Promise<void>;
    mkdir(path: string, exclusive?: boolean): Promise<void>;
    download(
        url: string,
        signal: RuntimeCancellationSignal,
    ): Promise<Uint8Array>;
    sha256(bytes: Uint8Array): Promise<string>;
    extractUv(archive: string, executable: string): Promise<void>;
    uvCandidates(): string[];
    environment(): Record<string, string>;
    spawn(
        command: string,
        args: string[],
        environment: Record<string, string>,
        workdir: string,
    ): Promise<RuntimeProcess>;
}
/** Sandbox-safe cancellation, independent of DOM constructors. */
export interface RuntimeCancellationSignal {
    readonly aborted: boolean;
    addEventListener(
        type: "abort",
        listener: () => void,
        options?: { once?: boolean },
    ): void;
    removeEventListener(type: "abort", listener: () => void): void;
}
class RuntimeCancellationController {
    private listeners = new Set<() => void>();
    private cancelled = false;
    readonly signal: RuntimeCancellationSignal;
    constructor() {
        const isCancelled = () => this.cancelled;
        this.signal = {
            get aborted() {
                return isCancelled();
            },
            addEventListener: (_type, listener) => {
                this.listeners.add(listener);
            },
            removeEventListener: (_type, listener) => {
                this.listeners.delete(listener);
            },
        };
    }
    abort() {
        if (this.cancelled) return;
        this.cancelled = true;
        for (const listener of this.listeners) listener();
        this.listeners.clear();
    }
}
function absoluteWindowsPath(value: string) {
    if (
        !/^[a-z]:[\\/]/i.test(value) ||
        value.split(/[\\/]/).some((part) => part === ".." || part === ".") ||
        /[\r\n\0]/.test(value)
    )
        throw new Error(
            "环境目录必须是 Windows 本地磁盘的绝对路径，不能包含 . 或 ..。",
        );
    return value.length === 3 ? value : value.replace(/[\\/]+$/, "");
}
export class RuntimeBootstrapManager {
    private pending?: Promise<RuntimeResult>;
    private target?: string;
    private controller?: RuntimeCancellationController;
    private child?: RuntimeProcess;
    private listeners = new Set<(progress: RuntimeProgress) => void>();
    private progress?: RuntimeProgress;
    private dependencies: RuntimeDependencies;
    constructor(
        dependencies: RuntimeDependencies = createNativeRuntimeDependencies(),
    ) {
        this.dependencies = dependencies;
    }
    prepare(options: RuntimeOptions): Promise<RuntimeResult> {
        const root = absoluteWindowsPath(options.root || DEFAULT_RUNTIME_ROOT);
        const server = absoluteWindowsPath(options.serverDirectory);
        const target = `${root.toLowerCase()}|${server.toLowerCase()}`;
        if (this.pending && this.target !== target)
            return Promise.reject(
                new Error("另一项环境准备正在进行，请先取消或等待完成。"),
            );
        if (options.onProgress) {
            this.listeners.add(options.onProgress);
            if (this.pending && this.progress)
                options.onProgress(this.progress);
        }
        if (this.pending) return this.pending;
        this.target = target;
        this.controller = new RuntimeCancellationController();
        this.pending = this.prepareRuntime(
            root,
            server,
            this.controller.signal,
        ).finally(() => {
            this.pending = undefined;
            this.target = undefined;
            this.controller = undefined;
            this.listeners.clear();
        });
        return this.pending;
    }
    async cancel() {
        this.controller?.abort();
        const child = this.child;
        try {
            if (child) await child.kill();
        } finally {
            await this.pending?.catch(() => {});
        }
    }
    private emit(stage: RuntimeStage, message: string) {
        this.progress = { stage, message };
        for (const listener of this.listeners) {
            try {
                listener(this.progress);
            } catch {
                /* UI must not interrupt setup. */
            }
        }
    }
    private async prepareRuntime(
        root: string,
        server: string,
        signal: RuntimeCancellationSignal,
    ): Promise<RuntimeResult> {
        const io = this.dependencies;
        const check = () => {
            if (signal.aborted) throw new Error("环境准备已取消。");
        };
        const runtime = io.join(root, "runtime");
        const marker = io.join(runtime, ".pdf2zh-managed");
        const guardedPaths = [
            root,
            server,
            runtime,
            marker,
            io.join(runtime, "uv.exe"),
            io.join(runtime, `uv-${UV_VERSION}.zip`),
            io.join(runtime, "python"),
            io.join(runtime, "cache"),
            io.join(runtime, "server-venv"),
            io.join(runtime, "server-venv", "Scripts", "python.exe"),
            io.join(server, "requirements.txt"),
            io.join(server, "server.py"),
        ];
        const assertSafe = () => io.assertSafePaths(guardedPaths, signal);
        const run = async (
            command: string,
            args: string[],
            environment: Record<string, string>,
        ) => {
            check();
            if (
                /uv\.exe$/i.test(command) &&
                (args.includes("install") || args.includes("venv"))
            )
                await io.assertSafePaths(
                    guardedPaths,
                    signal,
                    [runtime],
                    io.join(runtime, "python"),
                );
            else await assertSafe();
            const child = await io.spawn(command, args, environment, server);
            this.child = child;
            try {
                if (signal.aborted) await child.kill();
                const result = await child.wait();
                check();
                if (result.exitCode !== 0)
                    throw new Error(
                        `环境准备失败（阶段：${this.progress?.stage || "checking"}，退出码 ${result.exitCode}），请检查网络、磁盘空间及目录写入权限。`,
                    );
                return result.stdout || "";
            } finally {
                if (this.child === child) this.child = undefined;
            }
        };
        try {
            this.emit("checking", "检查磁盘、已有工具和受管环境…");
            if (io.platform !== "win32")
                throw new Error("自动准备环境当前仅支持 Windows。");
            if (!(await io.exists(root.slice(0, 3))))
                throw new Error(
                    `${root.slice(0, 2)} 磁盘不存在，请选择可用磁盘。`,
                );
            const requirements = io.join(server, "requirements.txt");
            if (
                !(await io.exists(requirements)) ||
                !(await io.exists(io.join(server, "server.py")))
            )
                throw new Error(
                    "Server 目录不完整，需要 server.py 和 requirements.txt。",
                );
            check();
            await assertSafe();
            await io.mkdir(root);
            if (await io.exists(runtime)) {
                if (
                    !(await io.exists(marker)) ||
                    (await io.read(marker)).trim() !== OWNER
                )
                    throw new Error(
                        "runtime 目录已存在且不属于本插件；为保护已有环境，准备已停止。请选择空目录。",
                    );
            } else {
                await io.mkdir(runtime, true);
                await assertSafe();
                await io.write(marker, OWNER);
            }
            check();
            const environment = io.environment();
            for (const key of Object.keys(environment))
                if (
                    [
                        "PYTHONPATH",
                        "PYTHONHOME",
                        "PYTHONNOUSERSITE",
                        "VIRTUAL_ENV",
                        "UV_PYTHON",
                        "UV_PROJECT_ENVIRONMENT",
                    ].includes(key.toUpperCase())
                )
                    delete environment[key];
            Object.assign(environment, {
                // Explicit blanks also override polluted parent variables when
                // the Server launcher uses environmentAppend: true.
                PYTHONHOME: "",
                PYTHONPATH: "",
                VIRTUAL_ENV: "",
                PYTHONNOUSERSITE: "1",
                UV_PYTHON_INSTALL_DIR: io.join(runtime, "python"),
                UV_CACHE_DIR: io.join(runtime, "cache"),
                UV_PYTHON_PREFERENCE: "only-managed",
                UV_PYTHON_INSTALL_BIN: "0",
                UV_NO_PROGRESS: "1",
            });
            const artifact = UV_ARTIFACTS[io.architecture];
            const privateUv = io.join(runtime, "uv.exe");
            let uvPath = "";
            for (const candidate of io.uvCandidates()) {
                check();
                if (!(await io.exists(candidate))) continue;
                try {
                    await io.assertSafePaths([candidate], signal);
                    const bytes = await io.readBytes(candidate);
                    // A known official executable can be copied without executing the source.
                    if (
                        (await io.sha256(bytes)).toLowerCase() ===
                        artifact.executableSha256
                    ) {
                        check();
                        await assertSafe();
                        await io.write(privateUv, bytes);
                        uvPath = privateUv;
                        break;
                    }
                } catch (error) {
                    check(); /* An unusable tool is not modified. */
                }
            }
            if (!uvPath && (await io.exists(privateUv))) {
                if (
                    (
                        await io.sha256(await io.readBytes(privateUv))
                    ).toLowerCase() !== artifact.executableSha256
                )
                    throw new Error(
                        "受管 uv 校验失败，未执行该文件。请使用新的安装目录重试。",
                    );
                uvPath = privateUv;
            }
            if (!uvPath) {
                this.emit("downloading-uv", `下载并校验官方 uv ${UV_VERSION}…`);
                const bytes = await io.download(artifact.url, signal);
                check();
                if ((await io.sha256(bytes)).toLowerCase() !== artifact.sha256)
                    throw new Error(
                        "uv 下载文件校验失败，未执行该文件。请检查网络后重试。",
                    );
                check();
                const archive = io.join(runtime, `uv-${UV_VERSION}.zip`);
                uvPath = privateUv;
                // Only overwrite executables within this explicitly owned runtime.
                await assertSafe();
                await io.write(archive, bytes);
                await assertSafe();
                await io.extractUv(archive, uvPath);
                check();
                if (
                    (
                        await io.sha256(await io.readBytes(uvPath))
                    ).toLowerCase() !== artifact.executableSha256
                )
                    throw new Error("解压后的 uv 校验失败，未执行该文件。");
                const version = await run(uvPath, ["--version"], environment);
                if (
                    !version.startsWith(`uv ${UV_VERSION} `) &&
                    version.trim() !== `uv ${UV_VERSION}`
                )
                    throw new Error("下载的 uv 版本不符合预期。");
            }
            const uvDirectory = uvPath.slice(
                0,
                Math.max(uvPath.lastIndexOf("\\"), uvPath.lastIndexOf("/")),
            );
            const pathKey =
                Object.keys(environment).find(
                    (key) => key.toUpperCase() === "PATH",
                ) || "PATH";
            environment[pathKey] =
                `${uvDirectory};${environment[pathKey] || ""}`;
            const venv = io.join(runtime, "server-venv");
            const pythonPath = io.join(venv, "Scripts", "python.exe");
            const healthArgs = [
                "-I",
                "-c",
                "import sys; assert sys.version_info[:2] == (3,12); import flask,toml,pypdf,fitz,packaging",
            ];
            if (await io.exists(pythonPath)) {
                try {
                    await run(pythonPath, healthArgs, environment);
                    this.emit(
                        "ready",
                        "复用已有 Server 环境，无需下载或升级。",
                    );
                    return { root, pythonPath, uvPath, environment };
                } catch {
                    check();
                }
            }
            this.emit(
                "python",
                "准备隔离的 Python 3.12，首次下载可能需要数分钟…",
            );
            await run(
                uvPath,
                [
                    "--no-config",
                    "python",
                    "install",
                    "3.12",
                    "--no-bin",
                    "--no-registry",
                ],
                environment,
            );
            this.emit("venv", "检查并准备 Server 虚拟环境…");
            if (!(await io.exists(venv))) {
                await run(
                    uvPath,
                    ["--no-config", "venv", venv, "--python", "3.12"],
                    environment,
                );
            } else if (!(await io.exists(pythonPath))) {
                throw new Error(
                    "受管 Server 环境不完整；保留现有文件，请选择新的安装根目录后重试。",
                );
            }
            await run(
                pythonPath,
                [
                    "-I",
                    "-c",
                    "import sys; assert sys.version_info[:2] == (3,12), 'Python 3.12 required'",
                ],
                environment,
            );
            this.emit(
                "dependencies",
                "安装并校验 Server 依赖，首次安装可能需要数分钟…",
            );
            await run(
                uvPath,
                [
                    "--no-config",
                    "pip",
                    "install",
                    "--python",
                    pythonPath,
                    "-r",
                    requirements,
                ],
                environment,
            );
            await run(pythonPath, healthArgs, environment);
            check();
            this.emit("ready", "Server 环境准备完成。");
            return { root, pythonPath, uvPath, environment };
        } catch (error) {
            this.emit(
                signal.aborted ? "cancelled" : "failed",
                signal.aborted
                    ? "环境准备已取消。"
                    : error instanceof Error
                      ? error.message
                      : "环境准备失败，请检查网络及目录权限。",
            );
            throw error;
        }
    }
}

function subprocessModule() {
    const runtime = (globalThis as any).ChromeUtils;
    try {
        return runtime.importESModule(
            "resource://gre/modules/Subprocess.sys.mjs",
        ).Subprocess;
    } catch {
        return runtime.import("resource://gre/modules/Subprocess.jsm")
            .Subprocess;
    }
}
function backgroundTimers() {
    const runtime = (globalThis as any).ChromeUtils;
    try {
        return runtime.importESModule("resource://gre/modules/Timer.sys.mjs");
    } catch {
        return runtime.import("resource://gre/modules/Timer.jsm");
    }
}
function encodedPowerShell(source: string) {
    const alphabet =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    const bytes: number[] = [];
    for (let index = 0; index < source.length; index++)
        bytes.push(
            source.charCodeAt(index) & 255,
            source.charCodeAt(index) >>> 8,
        );
    let result = "";
    for (let index = 0; index < bytes.length; index += 3) {
        const value =
            (bytes[index] << 16) |
            ((bytes[index + 1] || 0) << 8) |
            (bytes[index + 2] || 0);
        result +=
            alphabet[(value >>> 18) & 63] +
            alphabet[(value >>> 12) & 63] +
            (index + 1 < bytes.length ? alphabet[(value >>> 6) & 63] : "=") +
            (index + 2 < bytes.length ? alphabet[value & 63] : "=");
    }
    return result;
}
async function checkWindowsPaths(
    paths: string[],
    recursiveRoots: string[],
    signal: RuntimeCancellationSignal,
    pythonAliasRoot?: string,
) {
    if (!Zotero.isWin) throw new Error("路径安全检查当前仅支持 Windows。");
    const globals = globalThis as any;
    const services =
        (globals.runtimeHost || globals).Services ||
        (Zotero.getMainWindow() as any)?.Services;
    if (!services) throw new Error("后台路径安全检查不可用，已停止安装。");
    const literal = (path: string) =>
        "'" + absoluteWindowsPath(path).replace(/'/g, "''") + "'";
    const aliasArchitecture = /aarch64|arm64/i.test(
        services.appinfo?.XPCOMABI || "",
    )
        ? "aarch64"
        : "x86_64";
    // Only uv's exact minor-version alias is permitted. This option is never
    // passed by the public bundle checker. Targets must be ordinary direct
    // siblings in the same managed Python directory, with safe ancestors.
    const source = `$ErrorActionPreference='Stop'
$aliasRoot=${pythonAliasRoot ? literal(pythonAliasRoot) : "''"}
function AllowedAlias($item) {
    if(!$aliasRoot -or $item.Name -ne 'cpython-3.12-windows-${aliasArchitecture}-none' -or $item.LinkType -notin @('Junction','SymbolicLink')) { return $false }
    $expectedRoot=[IO.Path]::GetFullPath($aliasRoot).TrimEnd('\\')
    if(![String]::Equals([IO.Path]::GetFullPath($item.Parent.FullName).TrimEnd('\\'),$expectedRoot,[StringComparison]::OrdinalIgnoreCase)) { return $false }
    $targets=@($item.Target)
    if($targets.Count -ne 1 -or !$targets[0]) { return $false }
    $target=[string]$targets[0]
    foreach($prefix in @('\\??\\','\\\\?\\')) { if($target.StartsWith($prefix)) { $target=$target.Substring($prefix.Length) } }
    if(![IO.Path]::IsPathRooted($target)) { return $false }
    $target=[IO.Path]::GetFullPath($target).TrimEnd('\\')
    if(![String]::Equals([IO.Path]::GetDirectoryName($target),$expectedRoot,[StringComparison]::OrdinalIgnoreCase)) { return $false }
    if([IO.Path]::GetFileName($target) -notmatch '^cpython-3\\.12\\.\\d+-windows-${aliasArchitecture}-none$') { return $false }
    $current=$target
    while($current) {
        $entry=Get-Item -LiteralPath $current -Force -ErrorAction Stop
        if(($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { return $false }
        if($current -eq $target -and !$entry.PSIsContainer) { return $false }
        $current=Split-Path -Path $current -Parent
    }
    return $true
}
function Inspect([string]$p) {
    while($p) {
        try { $item=Get-Item -LiteralPath $p -Force -ErrorAction Stop; if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -and !(AllowedAlias $item)) { exit 42 } }
        catch [System.Management.Automation.ItemNotFoundException] {}
        $p=Split-Path -Path $p -Parent
    }
}
try {
    foreach($p in @(${paths.map(literal).join(",")})) { Inspect $p }
    foreach($p in @(${recursiveRoots.map(literal).join(",")})) {
        if(Test-Path -LiteralPath $p) {
            Get-ChildItem -LiteralPath $p -Force -Recurse -ErrorAction Stop | ForEach-Object {
                if(($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -and !(AllowedAlias $_)) { exit 42 }
            }
        }
    }
    exit 0
} catch { exit 43 }`;
    const systemRoot = services.env.get("SystemRoot");
    const child = await subprocessModule().call({
        command: PathUtils.join(
            systemRoot,
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe",
        ),
        arguments: [
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encodedPowerShell(source),
        ],
        environment: { SystemRoot: systemRoot },
        environmentAppend: false,
        workdir: systemRoot,
        stderr: "stdout",
    });
    const drain = (async () => {
        try {
            while (await child.stdout.readString()) {
                /* no user paths or diagnostics logged */
            }
        } catch {
            /* process ended */
        }
    })();
    const timers = backgroundTimers();
    const abort = () => {
        try {
            void Promise.resolve(child.kill()).catch(() => {});
        } catch {
            /* The child can exit just before cancellation. */
        }
    };
    signal.addEventListener("abort", abort);
    const timer = timers.setTimeout(abort, 30000);
    try {
        if (signal.aborted) abort();
        const result = await child.wait();
        await drain;
        if (signal.aborted) throw new Error("环境准备已取消。");
        if (result.exitCode === 42)
            throw new Error(
                "安装路径包含符号链接或 junction，已停止以保护目录外文件。请选择普通本地目录。",
            );
        if (result.exitCode !== 0)
            throw new Error(
                "无法验证安装路径安全性（权限不足或检查超时），已停止安装。",
            );
    } finally {
        timers.clearTimeout(timer);
        signal.removeEventListener("abort", abort);
    }
}
/** Fail closed: Windows nsIFile.isSymlink() does not detect junctions. */
export async function assertWindowsSafePaths(
    paths: string[],
    recursiveRoots: string[] = [],
) {
    if (!paths.length && !recursiveRoots.length) return;
    await checkWindowsPaths(
        paths,
        recursiveRoots,
        new RuntimeCancellationController().signal,
    );
}
export function createNativeRuntimeDependencies(): RuntimeDependencies {
    const globals = globalThis as any;
    const host = globals.runtimeHost || globals;
    const services = host.Services || (Zotero.getMainWindow() as any)?.Services;
    const components =
        host.Components || (Zotero.getMainWindow() as any)?.Components;
    if (!services || !components)
        throw new Error(
            "Zotero 主窗口或后台运行环境尚未就绪，请打开主窗口后重试。",
        );
    const environment = () => {
        const result: Record<string, string> = {};
        // Restrict forwarding to process configuration; do not copy API credentials.
        for (const key of [
            "PATH",
            "SystemRoot",
            "WINDIR",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "SSL_CERT_FILE",
            "REQUESTS_CA_BUNDLE",
        ])
            if (services.env.exists(key)) result[key] = services.env.get(key);
        return result;
    };
    return {
        platform: Zotero.isWin ? "win32" : "other",
        architecture: /aarch64|arm64/i.test(services.appinfo.XPCOMABI)
            ? "arm64"
            : "x64",
        join: (...parts) => PathUtils.join(...parts),
        exists: (path) => IOUtils.exists(path),
        assertSafePaths: (
            paths,
            signal,
            recursiveRoots = [],
            pythonAliasRoot,
        ) => checkWindowsPaths(paths, recursiveRoots, signal, pythonAliasRoot),
        read: (path) => IOUtils.readUTF8(path),
        readBytes: (path) => IOUtils.read(path),
        write: async (path, value) => {
            if (typeof value === "string") await IOUtils.writeUTF8(path, value);
            else await IOUtils.write(path, value);
        },
        mkdir: async (path, exclusive = false) => {
            await IOUtils.makeDirectory(path, {
                createAncestors: !exclusive,
                ignoreExisting: !exclusive,
            });
        },
        environment,
        uvCandidates: () => {
            const home = services.env.get("USERPROFILE");
            return home
                ? [
                      PathUtils.join(home, ".local", "bin", "uv.exe"),
                      PathUtils.join(home, ".cargo", "bin", "uv.exe"),
                  ]
                : [];
        },
        async download(url, signal) {
            // Resolve on each download: a manager can outlive its original window.
            const window = Zotero.getMainWindow() as any;
            if (
                !window ||
                window.closed ||
                !window.AbortController ||
                !window.fetch
            )
                throw new Error(
                    "Zotero 主窗口不可用，请打开主窗口后重试下载。",
                );
            const controller = new window.AbortController();
            const timers = backgroundTimers();
            const abort = () => controller.abort();
            signal.addEventListener("abort", abort);
            const timer = timers.setTimeout(abort, 180000);
            try {
                if (signal.aborted) controller.abort();
                const response = await window.fetch(url, {
                    signal: controller.signal,
                    credentials: "omit",
                });
                if (!response.ok)
                    throw new Error(
                        `官方 uv 下载失败（HTTP ${response.status}）。`,
                    );
                const bytes = new Uint8Array(await response.arrayBuffer());
                if (bytes.length > 100 * 1024 * 1024)
                    throw new Error("uv 下载大小超出预期。");
                return bytes;
            } finally {
                timers.clearTimeout(timer);
                signal.removeEventListener("abort", abort);
            }
        },
        async sha256(bytes) {
            const hash = components.classes[
                "@mozilla.org/security/hash;1"
            ].createInstance(components.interfaces.nsICryptoHash);
            hash.init(hash.SHA256);
            hash.update(bytes, bytes.length);
            return Array.from(hash.finish(false) as string)
                .map((char) => char.charCodeAt(0).toString(16).padStart(2, "0"))
                .join("");
        },
        async extractUv(archive, executable) {
            const file = (path: string) => {
                const value = components.classes[
                    "@mozilla.org/file/local;1"
                ].createInstance(components.interfaces.nsIFile);
                value.initWithPath(path);
                return value;
            };
            const zip = components.classes[
                "@mozilla.org/libjar/zip-reader;1"
            ].createInstance(components.interfaces.nsIZipReader);
            zip.open(file(archive));
            try {
                zip.extract("uv.exe", file(executable));
            } finally {
                zip.close();
            }
        },
        async spawn(command, args, env, workdir) {
            const Subprocess = subprocessModule();
            const child = await Subprocess.call({
                command,
                arguments: args,
                environment: env,
                environmentAppend: false,
                workdir,
                stderr: "stdout",
            });
            const output = (async () => {
                let text = "";
                try {
                    let part;
                    while ((part = await child.stdout.readString())) {
                        text = (text + part).slice(-4096);
                    }
                } catch {
                    /* Process ended. */
                }
                return text;
            })();
            return {
                kill: () => child.kill(),
                wait: async () => ({
                    ...(await child.wait()),
                    stdout: await output,
                }),
            };
        },
    };
}
// Lazy native initialization keeps the orchestration usable in offline tests.
let instance: RuntimeBootstrapManager | undefined;
export function getRuntimeBootstrap() {
    return (instance ||= new RuntimeBootstrapManager());
}
export async function cancelRuntimeBootstrapIfExists() {
    await instance?.cancel();
}
export const runtimeBootstrap = {
    prepare: (options: RuntimeOptions) =>
        getRuntimeBootstrap().prepare(options),
    cancel: cancelRuntimeBootstrapIfExists,
};
