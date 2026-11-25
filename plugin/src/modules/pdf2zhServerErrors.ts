export type ServerRequestPhase = "check" | "submit" | "poll" | "download";
type ServerErrorKind =
    | "missing-address"
    | "invalid-address"
    | "unreachable"
    | "timeout"
    | "unexpected-response"
    | "http";

export class ServerRequestError extends Error {
    readonly kind: ServerErrorKind;
    readonly serverUrl: string;
    readonly phase: ServerRequestPhase;
    readonly status?: number;

    constructor(
        kind: ServerErrorKind,
        serverUrl: string,
        phase: ServerRequestPhase,
        detail: string,
        status?: number,
    ) {
        super(detail);
        this.name = "ServerRequestError";
        this.kind = kind;
        this.serverUrl = serverUrl;
        this.phase = phase;
        this.status = status;
    }
}

export function errorMessage(error: unknown): string {
    // Zotero errors can cross window/sandbox boundaries: instanceof Error alone
    // does not reliably recognize DOMException or another window's Error.
    if (error && typeof error === "object" && "message" in error) {
        return String(error.message);
    }
    return String(error ?? "Unknown error");
}

export function normalizeServerAddress(value: string): string {
    const address = value.trim().replace(/\/+$/, "");
    if (!address) {
        throw new ServerRequestError("missing-address", "", "check", "");
    }
    try {
        const URLConstructor =
            typeof URL === "undefined" ? ztoolkit.getGlobal("URL") : URL;
        const parsed = new URLConstructor(address);
        if (
            !/^https?:\/\//i.test(address) ||
            !parsed.hostname ||
            parsed.search ||
            parsed.hash
        ) {
            throw new Error("Expected an HTTP(S) Server base address");
        }
        return address;
    } catch {
        throw new ServerRequestError("invalid-address", address, "check", "");
    }
}

export async function withServerTransport<T>(
    serverUrl: string,
    phase: ServerRequestPhase,
    request: () => Promise<T>,
): Promise<T> {
    try {
        return await request();
    } catch (error) {
        if (error instanceof ServerRequestError) throw error;
        const fields = (error || {}) as {
            code?: string;
            name?: string;
            response?: { status?: number };
        };
        const message = errorMessage(error);
        const status = fields.response?.status;
        if (status) {
            throw new ServerRequestError(
                "http",
                serverUrl,
                phase,
                `HTTP ${status}`,
                status,
            );
        }
        const timeout =
            fields.code === "ECONNABORTED" ||
            fields.code === "ETIMEDOUT" ||
            fields.name === "TimeoutError" ||
            /timed?\s*out|timeout/i.test(message);
        throw new ServerRequestError(
            timeout ? "timeout" : "unreachable",
            serverUrl,
            phase,
            message,
        );
    }
}

// A short GET probe is safe to repeat. Translation POSTs are never retried here.
// The transport is injected so this module works with Zotero's existing Axios
// adapter, without requiring AbortController in the plugin sandbox.
export async function probeServerHealth(
    value: string,
    get: (url: string) => Promise<{ status: number; data: unknown }>,
): Promise<{
    serverUrl: string;
    version: string;
    supportsGlossaryUpload?: true;
}> {
    const serverUrl = normalizeServerAddress(value);
    const response = await withServerTransport(serverUrl, "check", () =>
        get(`${serverUrl}/health`),
    );
    if (response.status < 200 || response.status >= 300) {
        throw new ServerRequestError(
            "http",
            serverUrl,
            "check",
            `HTTP ${response.status}`,
            response.status,
        );
    }
    const data = response.data as {
        status?: unknown;
        version?: unknown;
        supportsGlossaryUpload?: unknown;
    } | null;
    if (
        !data ||
        data.status !== "ok" ||
        typeof data.version !== "string" ||
        !data.version.trim()
    ) {
        throw new ServerRequestError(
            "unexpected-response",
            serverUrl,
            "check",
            "Unexpected health response",
        );
    }
    return {
        serverUrl,
        version: data.version,
        ...(data.supportsGlossaryUpload === true
            ? { supportsGlossaryUpload: true as const }
            : {}),
    };
}

type Translate = (key: string, args?: Record<string, unknown>) => string;

export function formatServerRequestError(
    error: unknown,
    text: Translate,
): string | null {
    if (!(error instanceof ServerRequestError)) return null;
    let kind: string = error.kind;
    if (kind === "http") {
        if (error.status === 401 || error.status === 403)
            kind = "access-denied";
        else if (error.status === 404) {
            kind =
                error.phase === "download"
                    ? "file-missing"
                    : "unexpected-response";
        } else if (error.status === 413) kind = "file-too-large";
    }
    const parts = [
        text(`server-error-${kind}-title`, { status: error.status ?? "" }),
        text(`server-error-${kind}-help`),
    ];
    parts.push(text(`server-error-phase-${error.phase}`));
    if (error.message) {
        const detail = error.message
            .replace(/https?:\/\/[^\s]+/gi, "[URL]")
            .replace(/\s+/g, " ")
            .slice(0, 300);
        parts.push(text("server-error-details", { detail }));
    }
    return parts.join("\n\n");
}
