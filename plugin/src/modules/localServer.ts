/** Launches only a user-configured local Python server; never claims an existing service. */
export interface LocalServerOptions {
    serverUrl: string;
    pythonPath: string;
    scriptPath: string;
    timeoutMs?: number;
}
interface ProcessHandle {
    kill(): Promise<unknown> | unknown;
    wait(): Promise<unknown>;
}
interface LaunchSpec {
    command: string;
    arguments: string[];
    workdir: string;
}
export interface LocalServerDependencies {
    probe(url: string): Promise<boolean | "other">;
    spawn(spec: LaunchSpec): Promise<ProcessHandle>;
    now(): number;
    sleep(ms: number): Promise<void>;
}
export function normalizeLocalServerUrl(value: string) {
    const url = new URL(value.trim());
    if (
        url.protocol !== "http:" ||
        !["localhost", "127.0.0.1"].includes(url.hostname) ||
        url.username ||
        url.password ||
        url.search ||
        url.hash ||
        url.pathname !== "/"
    ) {
        throw new Error(
            "Automatic startup requires a plain HTTP Server address using localhost or 127.0.0.1; IPv6 startup is not supported.",
        );
    }
    return {
        baseUrl: url.origin,
        host: url.hostname.replace(/^\[|\]$/g, ""),
        port: Number(url.port || 80),
    };
}
function parentDirectory(path: string) {
    const index = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
    if (
        index < 0 ||
        (!path.startsWith("/") &&
            !/^[a-z]:[\\/]/i.test(path) &&
            !path.startsWith("\\\\"))
    ) {
        throw new Error("Select absolute Python and server.py paths.");
    }
    return path.slice(0, index) || "/";
}
const nativeDependencies: LocalServerDependencies = {
    async probe(url) {
        try {
            const response = await Zotero.HTTP.request("GET", `${url}/health`, {
                timeout: 1500,
                responseType: "json",
                successCodes: false,
            });
            if (response.status !== 200) return "other";
            const data = response.response as {
                status?: unknown;
                version?: unknown;
            } | null;
            return data?.status === "ok" && typeof data?.version === "string"
                ? true
                : "other";
        } catch (error) {
            // A reached but invalid JSON service is not an unused port.
            if (error instanceof SyntaxError) return "other";
            return false;
        }
    },
    async spawn(spec) {
        const runtime = (globalThis as any).ChromeUtils;
        let subprocess: any;
        try {
            subprocess = runtime.importESModule(
                "resource://gre/modules/Subprocess.sys.mjs",
            ).Subprocess;
        } catch {
            subprocess = runtime.import(
                "resource://gre/modules/Subprocess.jsm",
            ).Subprocess;
        }
        // Discard output instead of logging server configuration, API keys, or URLs.
        const process = await subprocess.call({ ...spec, stderr: "stdout" });
        void (async () => {
            try {
                while (await process.stdout.readString()) {
                    /* drain */
                }
            } catch {
                /* Process closure ends draining. */
            }
        })();
        return process;
    },
    now: () => Date.now(),
    sleep: (ms) => Zotero.Promise.delay(ms),
};
export class LocalServerManager {
    private dependencies: LocalServerDependencies;
    private process?: ProcessHandle;
    private processBaseUrl?: string;
    private pending?: Promise<{
        status: "started" | "already-running";
        owned: boolean;
    }>;
    private state: "stopped" | "starting" | "running" = "stopped";
    private generation = 0;
    constructor(dependencies: LocalServerDependencies = nativeDependencies) {
        this.dependencies = dependencies;
    }
    getState() {
        return this.state;
    }
    start(options: LocalServerOptions) {
        if (this.pending) return this.pending;
        this.pending = this.launch(options).finally(() => {
            this.pending = undefined;
        });
        return this.pending;
    }
    private async launch(
        options: LocalServerOptions,
    ): Promise<{ status: "started" | "already-running"; owned: boolean }> {
        const target = normalizeLocalServerUrl(options.serverUrl);
        const timeout = options.timeoutMs ?? 120000;
        if (!Number.isFinite(timeout) || timeout <= 0)
            throw new Error("Invalid startup timeout.");
        const generation = ++this.generation;
        const checkCancelled = () => {
            if (generation !== this.generation)
                throw new Error("Server startup cancelled.");
        };
        let launched: ProcessHandle | undefined;
        this.state = "starting";
        try {
            if (this.process && this.processBaseUrl !== target.baseUrl)
                throw new Error(
                    "Stop the managed Server before changing its address.",
                );
            const health = await this.dependencies.probe(target.baseUrl);
            checkCancelled();
            if (health === true) {
                this.state = "running";
                return { status: "already-running", owned: !!this.process };
            }
            if (health === "other")
                throw new Error(
                    "The Server port is occupied by another service.",
                );
            if (this.process)
                throw new Error(
                    "The managed Server is already running but not healthy.",
                );
            parentDirectory(options.pythonPath);
            const workdir = parentDirectory(options.scriptPath);
            if (!/server\.py$/i.test(options.scriptPath))
                throw new Error("Select the Server server.py file.");
            const child = await this.dependencies.spawn({
                command: options.pythonPath,
                arguments: [
                    options.scriptPath,
                    "--host",
                    target.host,
                    "--port",
                    String(target.port),
                    "--non-interactive",
                    "--check_update",
                    "false",
                ],
                workdir,
            });
            launched = child;
            this.process = child;
            this.processBaseUrl = target.baseUrl;
            checkCancelled();
            let exited = false;
            void child.wait().then(
                () => {
                    exited = true;
                    if (this.process === child) {
                        this.process = undefined;
                        this.processBaseUrl = undefined;
                        this.state = "stopped";
                    }
                },
                () => {
                    exited = true;
                },
            );
            const deadline = this.dependencies.now() + timeout;
            while (this.dependencies.now() < deadline) {
                checkCancelled();
                if (exited)
                    throw new Error(
                        "Server exited before becoming ready. Check the Python environment and Server version.",
                    );
                if ((await this.dependencies.probe(target.baseUrl)) === true) {
                    checkCancelled();
                    if (exited)
                        throw new Error("Server exited before becoming ready.");
                    this.state = "running";
                    return { status: "started", owned: true };
                }
                await this.dependencies.sleep(
                    Math.min(
                        500,
                        Math.max(1, deadline - this.dependencies.now()),
                    ),
                );
            }
            throw new Error(
                "Server startup timed out. Check the Python environment and Server configuration.",
            );
        } catch (error) {
            if (launched && this.process === launched) {
                this.process = undefined;
                this.processBaseUrl = undefined;
                await launched.kill();
            }
            this.state = this.process ? "running" : "stopped";
            throw error;
        }
    }
    async stop() {
        this.generation++;
        const child = this.process;
        this.process = undefined;
        this.processBaseUrl = undefined;
        this.state = "stopped";
        if (child) await child.kill();
        if (this.pending) await this.pending.catch(() => {});
    }
}
export const localServer = new LocalServerManager();
