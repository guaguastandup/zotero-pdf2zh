export function isPDFPath(path: string | null | undefined): boolean {
    return typeof path === "string" && /\.pdf$/i.test(path);
}

const PRODUCT_SUFFIXES: [suffix: string, type: string][] = [
    // Order matters: longer markers first (mono-cut also ends with -cut).
    ["-mono-cut.pdf", "mono-cut"],
    [".mono-cut.pdf", "mono-cut"],
    ["-dual-cut.pdf", "dual-cut"],
    [".dual-cut.pdf", "dual-cut"],
    ["-crop-compare.pdf", "crop-compare"],
    [".crop-compare.pdf", "crop-compare"],
    ["-compare.pdf", "compare"],
    [".compare.pdf", "compare"],
    ["-cut.pdf", "origin-cut"],
    [".cut.pdf", "origin-cut"],
    ["-mono.pdf", "mono"],
    [".mono.pdf", "mono"],
    ["-dual.pdf", "dual"],
    [".dual.pdf", "dual"],
    [".lr_dual.pdf", "dual"],
    [".tb_dual.pdf", "dual"],
];

/**
 * Classify a PDF as one of our translated products by its filename.
 * Only names ENDING in a product marker ("-mono.pdf" for the legacy
 * engine, ".zh-CN.dual.pdf" style for pdf2zh_next) count; a paper
 * whose title merely ends in "dual.pdf" is the user's own file and
 * must stay translatable.
 */
export function classifyPDFFileName(fileName: string): string {
    const name = String(fileName || "").toLowerCase();
    for (const [suffix, type] of PRODUCT_SUFFIXES) {
        if (name.endsWith(suffix)) {
            return type;
        }
    }
    return "origin";
}

function containsBytes(
    bytes: Uint8Array,
    needle: readonly number[],
    start: number,
    end: number,
): boolean {
    const first = Math.max(0, start);
    const last = Math.min(bytes.length, end) - needle.length;
    for (let i = first; i <= last; i++) {
        let matched = true;
        for (let j = 0; j < needle.length; j++) {
            if (bytes[i + j] !== needle[j]) {
                matched = false;
                break;
            }
        }
        if (matched) {
            return true;
        }
    }
    return false;
}

export function validatePDFBytes(bytes: Uint8Array, fileName: string): void {
    // Be lenient about harmless leading/trailing bytes, but reject common
    // HTTP 200 error pages and truncated downloads before Zotero imports them.
    const hasHeader = containsBytes(
        bytes,
        [0x25, 0x50, 0x44, 0x46, 0x2d], // %PDF-
        0,
        Math.min(bytes.length, 1024),
    );
    const hasEOF = containsBytes(
        bytes,
        [0x25, 0x25, 0x45, 0x4f, 0x46], // %%EOF
        Math.max(0, bytes.length - 65_536),
        bytes.length,
    );
    if (!hasHeader || !hasEOF) {
        throw new Error(`下载内容不是完整 PDF: ${fileName}`);
    }
}

function stringList(value: unknown): string[] {
    return Array.isArray(value)
        ? value.filter(
              (item): item is string =>
                  typeof item === "string" && item.length > 0,
          )
        : [];
}

function taskIdFromPayload(task: Record<string, unknown>): string {
    const raw = task.taskId ?? task.task_id ?? "";
    return typeof raw === "string" || typeof raw === "number"
        ? String(raw).trim()
        : "";
}

export function taskFinishedWithoutFiles(
    task: Record<string, unknown> | undefined,
    taskId: string,
): boolean {
    if (!task || taskIdFromPayload(task) !== taskId) {
        return false;
    }
    const nested =
        task.result && typeof task.result === "object"
            ? (task.result as Record<string, unknown>)
            : null;
    const status = String(task.status || nested?.status || "");
    const completed =
        task.finished === true ||
        status === "完成" ||
        status === "success" ||
        nested?.status === "success";
    const failed =
        status === "失败" || status === "failed" || nested?.status === "error";
    const files = stringList(nested?.fileList ?? task.fileList);
    const paths = stringList(nested?.filePaths ?? task.filePaths);
    return completed && !failed && files.length === 0 && paths.length === 0;
}
