/**
 * 用户错误提示目录（与 server/utils/error_catalog.py 规则对齐的插件端兜底）。
 *
 * 优先使用 Server 响应里的 userMessage/hint；Server 未分类（如旧版本）时，
 * 在插件侧对原始错误文本做一次本地分类，避免把引擎的技术报错直接甩给用户。
 */

export type ClassifiedError = {
    errorCode: string;
    userMessage: string;
    hint: string;
};

function isEnglishUi(): boolean {
    const locale = String(
        (Zotero as typeof Zotero & { locale?: string }).locale || "",
    ).toLowerCase();
    return locale.startsWith("en");
}

const USER_MESSAGES_ZH: Record<string, string> = {
    SCANNED_PDF_DETECTED:
        "检测到扫描版 PDF：页面是图片，没有可提取的文字层，无法翻译。",
    PDF_CID_CHARS_TOO_MANY:
        "这份 PDF 的内嵌字体异常（CID 字符过多），解析失败。",
};

const USER_MESSAGES_EN: Record<string, string> = {
    SCANNED_PDF_DETECTED:
        "Scanned PDF detected: pages are images with no text layer.",
    PDF_CID_CHARS_TOO_MANY:
        "This PDF has broken embedded fonts (too many CID chars).",
};

const HINTS_ZH: Record<string, string> = {
    SCANNED_PDF_DETECTED:
        "请换一份带文字层的 PDF（出版社原版通常可以），或先用 OCR 工具转成文字版再翻译。",
    PDF_CID_CHARS_TOO_MANY:
        "常见于老旧或扫描转换的 PDF，请换该文献的其他 PDF 版本，或先 OCR。",
};

type Rule = { code: string; test: (l: string) => boolean };

// 与 server 端 ERROR_RULES 对齐。起步原则: 只收录经真实报错验证过的
// 案例, 宁缺勿滥; 新规则先拿到真实错误文本再添加。
const RULES: Rule[] = [
    {
        code: "SCANNED_PDF_DETECTED",
        test: (l) =>
            /(contains no graphs|no extractable text|scanned pdf|no text layer|without text layer)/.test(
                l,
            ),
    },
    {
        code: "PDF_CID_CHARS_TOO_MANY",
        test: (l) => /too many cid chars/.test(l),
    },
];

export function classifyErrorFromText(message: string): ClassifiedError {
    const text = String(message || "").trim();
    const lower = text.toLowerCase();
    const en = isEnglishUi();
    if (!text) {
        return {
            errorCode: "UNKNOWN_ERROR",
            userMessage: en ? "Operation failed." : "操作失败。",
            hint: en ? "Check the server log." : "请查看 server 终端日志。",
        };
    }
    // 已是本目录产出的中文消息（Server 新版已分类）时原样透传。
    for (const rule of RULES) {
        if (rule.test(lower)) {
            return {
                errorCode: rule.code,
                userMessage:
                    (en ? USER_MESSAGES_EN : USER_MESSAGES_ZH)[rule.code] ||
                    text,
                hint: HINTS_ZH[rule.code] || "",
            };
        }
    }
    return {
        errorCode: "UNKNOWN_ERROR",
        userMessage: text,
        hint: en
            ? "Check the server log for details."
            : "详情请查看 server 终端日志。",
    };
}

/** 组装最终展示文本：优先 Server 的 userMessage/hint，其次本地分类。 */
export function presentableError(message: string, payload?: unknown): string {
    const data =
        payload && typeof payload === "object"
            ? (payload as Record<string, unknown>)
            : null;
    const serverUser = String(data?.userMessage || "");
    const serverHint = String(data?.hint || "");
    if (serverUser) {
        return serverHint ? `${serverUser}\n${serverHint}` : serverUser;
    }
    const classified = classifyErrorFromText(message);
    if (classified.errorCode !== "UNKNOWN_ERROR") {
        const friendly = classified.hint
            ? `${classified.userMessage}\n${classified.hint}`
            : classified.userMessage;
        // 解读只是附加层: 原始错误保留, 便于用户反馈与作者排查。
        const rawTail = message.split(/\n/).slice(-3).join("\n").trim();
        return rawTail && rawTail !== friendly
            ? `${friendly}\n\n[原始错误] ${rawTail}`
            : friendly;
    }
    return message;
}
