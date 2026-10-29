export type TableMode = "preserve" | "fixed" | "adaptive";

/** Apply prettier table processing only when both table options are enabled. */
export function tableModeFromPref(
    value: unknown,
    translateTableText: unknown,
): TableMode | "" {
    return translateTableText === true && value === true ? "fixed" : "";
}

export function requireTableModeSupport(mode: TableMode, payload: unknown) {
    const modes =
        payload && typeof payload === "object" && "tableModes" in payload
            ? payload.tableModes
            : undefined;
    if (!Array.isArray(modes) || !modes.includes(mode)) {
        throw new Error(
            `Server does not support table mode '${mode}'. Update Server or turn off Prettier tables.`,
        );
    }
}
