declare const _globalThis: {
    [key: string]: any;
    Zotero: _ZoteroTypes.Zotero; // Zotero对象
    ztoolkit: ZToolkit; // 工具链
    addon: typeof addon;
};

// Present in Zotero's File API but not yet declared by the pinned
// zotero-types package.
declare namespace _ZoteroTypes {
    interface File {
        getValidFileName(fileName: string): string;
    }
}

declare type ZToolkit = ReturnType<
    typeof import("../src/utils/ztoolkit").createZToolkit
>;

declare const ztoolkit: ZToolkit;

declare const rootURI: string;

declare const addon: import("../src/addon").default;

declare const __env__: "production" | "development";
