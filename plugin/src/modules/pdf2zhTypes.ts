export enum PDFType {
    MONO = "mono",
    DUAL = "dual",
    MONO_CUT = "mono-cut",
    DUAL_CUT = "dual-cut",
    CROP_COMPARE = "crop-compare",
    COMPARE = "compare",
    ORIGIN_CUT = "origin-cut",
    ORIGIN = "origin",
    UNKNOWN = "unknown",
}

export interface ServerConfig {
    serverUrl: string;
    threadNum: string;
    qps: string;
    poolSize: string;
    engine: string;
    service: string;
    next_service: string;

    skipLastPages: string;
    sourceLang: string;
    targetLang: string;
    // generate
    mono: string;
    mono_cut: string;
    dual: string;
    dual_cut: string;
    crop_compare: string;
    compare: string;

    // pdf1x专用配置
    babeldoc: string;
    skipSubsetFonts: string;
    fontFile: string;

    // pdf2x专用配置
    ocr: string;
    autoOcr: string;
    transFirst: string;
    noWatermark: string;
    fontFamily: string;
    dualMode: string;
    saveGlossary: string;
    disableGlossary: string;
    noDual: string;
    noMono: string;
    skipClean: string;
    disableRichTextTranslate: string;
    enhanceCompatibility: string;
    translateTableText: string;
    onlyIncludeTranslatedPage: string;
}

export interface PDFOperationOptions {
    rename: boolean;
    openAfterProcess: boolean;
}
