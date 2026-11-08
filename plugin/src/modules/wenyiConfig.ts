import type { ServerConfig, WenyiOptions } from "./pdf2zhTypes";

type ReadPreference = (key: string) => unknown;

export const WENYI_DEFAULTS = {
    prompt_genre: "academic",
    book_understanding: "true",
    translation_mode: "standard",
    polish: "true",
    review: "true",
    annotation_alignment: "false",
    mono: "true",
    bilingual: "false",
    bilingual_order: "target_first",
} as const;

function preference(read: ReadPreference, key: keyof typeof WENYI_DEFAULTS) {
    const value = read(`wenyi.${key}`);
    return value === undefined || value === "" ? WENYI_DEFAULTS[key] : value;
}

function booleanValue(value: unknown): boolean {
    if (value === true || value === "true") return true;
    if (value === false || value === "false") return false;
    throw new Error("Wenyi toggle must be enabled or disabled");
}

/** Select a CLI prompt genre separately from YAML pipeline settings. */
export function wenyiPromptGenre(
    read: ReadPreference,
): NonNullable<WenyiOptions["prompt_genre"]> {
    const genre = preference(read, "prompt_genre");
    if (genre !== "academic" && genre !== "literary") {
        throw new Error("Wenyi prompt_genre must be academic or literary");
    }
    return genre;
}

/** Resolve workflow choices without overwriting the user's stored preferences. */
export function wenyiPipelineOptions(
    read: ReadPreference,
): NonNullable<WenyiOptions["pipeline"]> {
    const pipeline: NonNullable<WenyiOptions["pipeline"]> = {};
    for (const key of [
        "book_understanding",
        "polish",
        "review",
        "annotation_alignment",
    ] as const) {
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
    return pipeline;
}

/** Keep edition choices separate from PDF2zh's generation preferences. */
export function wenyiExportOptions(read: ReadPreference) {
    const order = preference(read, "bilingual_order");
    if (order !== "target_first" && order !== "source_first") {
        throw new Error(
            "Wenyi bilingual_order must be target_first or source_first",
        );
    }
    return {
        mono: booleanValue(preference(read, "mono")),
        bilingual: booleanValue(preference(read, "bilingual")),
        bilingual_order: order,
    } as const;
}

/** Map only the shared DeepSeek thinking controls, never arbitrary extraData. */
export function wenyiModelOptions(
    extraData: unknown,
): NonNullable<WenyiOptions["model"]> {
    const extra = extraData ?? {};
    if (typeof extra !== "object" || Array.isArray(extra)) {
        throw new Error("DeepSeek extra parameters must be an object");
    }
    const fields = extra as Record<string, unknown>;
    const mode = fields.deepseek_thinking_mode;
    if (
        mode != null &&
        mode !== "" &&
        mode !== "disabled" &&
        mode !== "enabled"
    ) {
        throw new Error("DeepSeek thinking mode must be disabled or enabled");
    }
    const effort = fields.deepseek_reasoning_effort;
    if (
        effort != null &&
        effort !== "" &&
        effort !== "high" &&
        effort !== "max"
    ) {
        throw new Error("DeepSeek reasoning effort must be high or max");
    }
    return {
        thinking: mode === "enabled",
        reasoning_effort: effort === "max" ? "max" : "high",
    };
}

/** Wenyi uses the Server's DeepSeek preset and exports complete PDFs. */
export function translationConfig(
    config: ServerConfig,
    read: ReadPreference = () => undefined,
): ServerConfig {
    if (config.engine !== "wenyi") return config;
    const output = wenyiExportOptions(read);
    if (!output.mono && !output.bilingual) {
        throw new Error("Select at least one Wenyi PDF output");
    }
    return {
        ...config,
        wenyi: {
            prompt_genre: wenyiPromptGenre(read),
            pipeline: wenyiPipelineOptions(read),
            output: { bilingual_order: output.bilingual_order },
        },
        service: "deepseek",
        next_service: "deepseek",
        skipLastPages: "0",
        mono: String(output.mono),
        dual: String(output.bilingual),
        mono_cut: "false",
        dual_cut: "false",
        crop_compare: "false",
        compare: "false",
        noMono: String(!output.mono),
        noDual: String(!output.bilingual),
        ocr: "false",
        autoOcr: "false",
        translateTableText: "false",
        skipReferences: "false",
        tableMode: "",
        ignoreCache: "false",
        onlyIncludeTranslatedPage: "false",
    };
}
