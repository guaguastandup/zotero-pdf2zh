/** Prevent DeepSeek Flash jobs from reaching an outdated Server. */
export function needsDeepSeekFlashPatch(settings: unknown): boolean {
    if (!settings || typeof settings !== "object") return false;
    const data = settings as { service?: unknown; model?: unknown };
    return (
        data.service === "deepseek" &&
        typeof data.model === "string" &&
        data.model.trim() === "deepseek-flash"
    );
}

export function supportsDeepSeekFlashPatch(payload: unknown): boolean {
    return (
        payload !== null &&
        typeof payload === "object" &&
        !Array.isArray(payload) &&
        "deepseekFlashThinkingPatch" in payload &&
        payload.deepseekFlashThinkingPatch === true
    );
}
