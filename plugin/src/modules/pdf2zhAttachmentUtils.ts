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
