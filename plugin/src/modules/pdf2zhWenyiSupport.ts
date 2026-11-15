/** Check whether the Server reports Wenyi engine support. */
export function supportsWenyi(payload: unknown): boolean {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        return false;
    }
    const record = payload as Record<string, unknown>;
    const engines = record["engines"];
    return Array.isArray(engines) && engines.includes("wenyi");
}
