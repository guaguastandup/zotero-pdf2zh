export type TableMode = "preserve" | "fixed" | "adaptive";

/** Apply prettier table processing only when both table options are enabled. */
export function tableModeFromPref(
    value: unknown,
    translateTableText: unknown,
): TableMode | "" {
    return translateTableText === true && value === true ? "fixed" : "";
}

/** Missing capabilities mean an old Server; malformed responses remain errors. */
export function supportsTableMode(mode: TableMode, payload: unknown): boolean {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("Invalid Server capability response.");
    }
    if (!("tableModes" in payload)) return false;
    const modes = payload.tableModes;
    if (
        !Array.isArray(modes) ||
        modes.some((value) => typeof value !== "string")
    ) {
        throw new Error("Invalid Server tableModes capability.");
    }
    return modes.includes(mode);
}
