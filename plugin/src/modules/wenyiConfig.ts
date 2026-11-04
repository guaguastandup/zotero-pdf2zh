import type { ServerConfig, WenyiOptions } from "./pdf2zhTypes";

type ReadPreference = (key: string) => unknown;

export const WENYI_DEFAULTS = {
    book_understanding: "true",
    translation_mode: "standard",
    polish: "true",
    review: "true",
    thinking: "false",
    reasoning_effort: "high",
} as const;

/** Replace retired empty choices without overwriting explicit user selections. */
export function initializeWenyiPreferences(
    read: ReadPreference,
    write: (key: string, value: string) => void,
): void {
    for (const [key, value] of Object.entries(WENYI_DEFAULTS)) {
        const name = `wenyi.${key}`;
        const current = read(name);
        if (current === undefined || current === "") write(name, value);
    }
}

function preference(read: ReadPreference, key: keyof typeof WENYI_DEFAULTS) {
    const value = read(`wenyi.${key}`);
    return value === undefined || value === "" ? WENYI_DEFAULTS[key] : value;
}

function booleanValue(value: unknown): boolean {
    if (value === true || value === "true") return true;
    if (value === false || value === "false") return false;
    throw new Error("Wenyi toggle must be enabled or disabled");
}

/** Send explicit plugin choices; never inherit CLI thinking or PDF2zh extraData. */
function readOptions(read: ReadPreference): WenyiOptions {
    const pipeline: NonNullable<WenyiOptions["pipeline"]> = {};
    for (const key of ["book_understanding", "polish", "review"] as const) {
        pipeline[key] = booleanValue(preference(read, key));
    }
    const mode = preference(read, "translation_mode");
    if (mode !== "standard" && mode !== "best_of_three") {
        throw new Error(
            "Wenyi translation_mode must be standard or best_of_three",
        );
    }
    pipeline.translation_mode = mode;
    if (mode === "best_of_three") pipeline.polish = true;
    const effort = preference(read, "reasoning_effort");
    if (effort !== "high" && effort !== "max") {
        throw new Error("Wenyi reasoning_effort must be high or max");
    }
    return {
        pipeline,
        model: {
            thinking: booleanValue(preference(read, "thinking")),
            reasoning_effort: effort,
        },
    };
}

/** Wenyi v1 uses the Server's DeepSeek preset and exports complete mono PDFs. */
export function translationConfig(
    config: ServerConfig,
    read: ReadPreference = () => undefined,
): ServerConfig {
    if (config.engine !== "wenyi") return config;
    return {
        ...config,
        wenyi: readOptions(read),
        service: "deepseek",
        next_service: "deepseek",
        skipLastPages: "0",
        mono: "true",
        dual: "false",
        mono_cut: "false",
        dual_cut: "false",
        crop_compare: "false",
        compare: "false",
        noMono: "false",
        noDual: "true",
        ocr: "false",
        autoOcr: "false",
        translateTableText: "false",
        tableMode: "",
        ignoreCache: "false",
        onlyIncludeTranslatedPage: "false",
    };
}
