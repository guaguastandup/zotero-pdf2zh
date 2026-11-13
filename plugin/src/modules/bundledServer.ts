export interface ServerBundle {
    version: string;
    files: { path: string; base64: string; sha256: string }[];
}
export interface BundleIO {
    /** Reject reparse points in each path and every existing ancestor. */
    assertSafePaths(paths: string[]): Promise<void>;
    kind(path: string): Promise<string>;
    read(path: string): Promise<Uint8Array>;
    mkdir(path: string): Promise<void>;
    /** Must fail if a file already exists. */
    write(path: string, data: Uint8Array): Promise<void>;
    decode(data: string): Uint8Array;
    hash(data: Uint8Array): Promise<string>;
}
export const bundledServerDirectory = "D:\\ZoteroPlugin\\PDF2zh";
function safePath(path: string) {
    if (
        !/^[a-z0-9_-]+(?:\.[a-z0-9_-]+)*(?:\/[a-z0-9_-]+(?:\.[a-z0-9_-]+)*)*$/.test(
            path,
        )
    )
        throw new Error(`Unsafe bundled Server path: ${path}`);
    for (const part of path.split("/")) {
        if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part))
            throw new Error(`Unsafe bundled Server path: ${path}`);
    }
}
export async function installBundledServer(
    bundle: ServerBundle,
    io: BundleIO,
    checkCancelled: () => void = () => {},
) {
    const checked = async <T>(operation: () => Promise<T>): Promise<T> => {
        checkCancelled();
        const result = await operation();
        checkCancelled();
        return result;
    };
    checkCancelled();
    if (
        !bundle ||
        typeof bundle.version !== "string" ||
        !Array.isArray(bundle.files) ||
        !bundle.files.length
    )
        throw new Error("Invalid bundled Server manifest.");
    const prepared: { path: string; bytes: Uint8Array; sha256: string }[] = [];
    const names = new Set<string>();
    const dirs = new Set(["D:\\ZoteroPlugin", bundledServerDirectory]);
    for (const file of bundle.files) {
        safePath(file.path);
        if (names.has(file.path) || !/^[a-f0-9]{64}$/.test(file.sha256))
            throw new Error(
                "Invalid bundled Server manifest hash or duplicate path.",
            );
        names.add(file.path);
        checkCancelled();
        const bytes = io.decode(file.base64);
        if ((await checked(() => io.hash(bytes))) !== file.sha256)
            throw new Error(`Bundled Server hash mismatch: ${file.path}`);
        const parts = file.path.split("/");
        for (let i = 1; i < parts.length; i++)
            dirs.add(
                bundledServerDirectory + "\\" + parts.slice(0, i).join("\\"),
            );
        prepared.push({
            path: bundledServerDirectory + "\\" + parts.join("\\"),
            bytes,
            sha256: file.sha256,
        });
    }
    if (!names.has("server.py"))
        throw new Error("Bundled Server lacks server.py.");
    if (typeof io.assertSafePaths !== "function")
        throw new Error("Windows path safety capability is unavailable.");
    await checked(() =>
        io.assertSafePaths([...dirs, ...prepared.map((file) => file.path)]),
    );
    // Preflight every collision before writing. Existing user data is never replaced.
    for (const dir of dirs) {
        const kind = await checked(() => io.kind(dir));
        if (kind !== "missing" && kind !== "directory")
            throw new Error(`Server installation conflict: ${dir}`);
    }
    for (const file of prepared) {
        const kind = await checked(() => io.kind(file.path));
        if (kind === "missing") continue;
        if (kind !== "file")
            throw new Error(`Server installation conflict: ${file.path}`);
        const existing = await checked(() => io.read(file.path));
        if ((await checked(() => io.hash(existing))) !== file.sha256)
            throw new Error(`Server installation conflict: ${file.path}`);
    }
    for (const dir of dirs) {
        await checked(() => io.assertSafePaths([dir]));
        await checked(() => io.mkdir(dir));
    }
    for (const file of prepared) {
        await checked(() => io.assertSafePaths([file.path]));
        if ((await checked(() => io.kind(file.path))) === "missing")
            await checked(() => io.write(file.path, file.bytes));
    }
    return {
        installDirectory: bundledServerDirectory,
        scriptPath: bundledServerDirectory + "\\server.py",
    };
}
/** Use a real DOM window: the privileged plugin sandbox need not expose atob. */
export function decodeBundledServerFile(
    data: string,
    window: { atob(data: string): string } = Zotero.getMainWindow(),
): Uint8Array {
    const text = window.atob(data);
    return Uint8Array.from(text, (char) => char.charCodeAt(0));
}
const nativeIO: BundleIO = {
    async assertSafePaths(paths) {
        const runtime = await import("./runtimeBootstrap");
        await runtime.assertWindowsSafePaths(paths);
    },
    async kind(path) {
        try {
            const stat = await IOUtils.stat(path);
            return stat.type === "regular" ? "file" : stat.type || "other";
        } catch (error) {
            if ((error as any).name === "NotFoundError") return "missing";
            throw error;
        }
    },
    read: (path) => IOUtils.read(path),
    mkdir: (path) => IOUtils.makeDirectory(path, { ignoreExisting: true }),
    write: async (path, data) => {
        await IOUtils.write(path, data, { mode: "create" });
    },
    decode(data) {
        return decodeBundledServerFile(data);
    },
    async hash(data) {
        const hash = (Components.classes as any)[
            "@mozilla.org/security/hash;1"
        ].createInstance(Components.interfaces.nsICryptoHash);
        hash.init(hash.SHA256);
        hash.update(data, data.length);
        return Array.from(hash.finish(false) as string, (char) =>
            char.charCodeAt(0).toString(16).padStart(2, "0"),
        ).join("");
    },
};
/** Read jar resources via nsIChannel; HTTP URI parsing rejects addon IDs containing @. */
export async function readBundledServerManifest(
    resourceRoot: string,
): Promise<ServerBundle> {
    const text = await Zotero.File.getResourceAsync(
        resourceRoot + "content/bundled-server.json",
    );
    return JSON.parse(text);
}
type InstallationResult = Awaited<ReturnType<typeof installBundledServer>>;
/** One shared install task; cancellation joins it before allowing safe retry. */
export class BundledServerInstallationController {
    private current?: {
        cancelled: boolean;
        pending: Promise<InstallationResult>;
    };
    start(
        perform: (checkCancelled: () => void) => Promise<InstallationResult>,
    ) {
        if (this.current) return this.current.pending;
        const task = {
            cancelled: false,
            pending: undefined as unknown as Promise<InstallationResult>,
        };
        const checkCancelled = () => {
            if (task.cancelled)
                throw new Error("Bundled Server installation cancelled.");
        };
        task.pending = Promise.resolve()
            .then(() => {
                checkCancelled();
                return perform(checkCancelled);
            })
            .finally(() => {
                if (this.current === task) this.current = undefined;
            });
        this.current = task;
        return task.pending;
    }
    async cancel(): Promise<void> {
        const task = this.current;
        if (!task) return;
        task.cancelled = true;
        await task.pending.catch(() => {});
    }
}
const installationController = new BundledServerInstallationController();
export function cancelBundledServerInstallation(): Promise<void> {
    return installationController.cancel();
}
export async function ensureBundledServerInstalled(
    resourceRoot: string = rootURI,
) {
    if (!Zotero.isWin)
        throw new Error("Bundled Server installation requires Windows.");
    return installationController.start(async (checkCancelled) => {
        checkCancelled();
        const bundle = await readBundledServerManifest(resourceRoot);
        checkCancelled();
        return installBundledServer(bundle, nativeIO, checkCancelled);
    });
}
