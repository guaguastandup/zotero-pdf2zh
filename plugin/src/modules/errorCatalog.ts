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
    PDF_UNREADABLE_TEXT:
        "这份 PDF 读不出可翻译的文字（扫描件没有文字层，或内嵌字体编码异常）。",
    BITSTRING_INCOMPATIBLE:
        "翻译引擎无法导入 BitStream，通常是 bitstring 依赖版本不兼容。",
    API_RATE_LIMIT: "翻译服务返回请求频率限制（HTTP 429）。",
    API_AUTH_FAILED: "翻译服务拒绝了身份认证（API Key 或访问权限可能有问题）。",
};

const USER_MESSAGES_EN: Record<string, string> = {
    PDF_UNREADABLE_TEXT:
        "This PDF has no extractable text (scanned pages or broken fonts).",
    BITSTRING_INCOMPATIBLE: "The translation engine cannot import BitStream from bitstring.",
    API_RATE_LIMIT: "The translation provider rejected too many requests (HTTP 429).",
    API_AUTH_FAILED: "The translation provider rejected API authentication.",
};

const HINTS_ZH: Record<string, string> = {
    PDF_UNREADABLE_TEXT:
        "请换一份带文字层的 PDF（出版社原版通常可以），或先用 OCR 工具转成文字版再翻译。",
    BITSTRING_INCOMPATIBLE:
        "请在 Server 目录执行 python manage_packages.py doctor，检查 bitstring 版本是否为 >=4.3.0,<5。",
    API_RATE_LIMIT: "请核对 API 额度，降低 QPS 或并发后重试。",
    API_AUTH_FAILED: "请核对服务商、API Key 和模型权限；不要分享完整密钥。",
};

type Rule = { code: string; test: (l: string) => boolean };

// 与 server 端 ERROR_RULES 对齐。起步原则: 只收录经真实报错验证过的
// 案例, 宁缺勿滥; 新规则先拿到真实错误文本再添加。
const RULES: Rule[] = [
    {
        code: "BITSTRING_INCOMPATIBLE",
        test: (l) =>
            (l.includes("cannot import name 'bitstream'") && l.includes("bitstring")) ||
            l.includes("no module named 'bitstring'"),
    },
    {
        code: "API_RATE_LIMIT",
        test: (l) =>
            /\b(?:http|status(?:\s+code)?|error\s+code)\s*[:=]?\s*429\b/.test(l) ||
            l.includes("429 too many requests") ||
            l.includes("rate_limit_exceeded"),
    },
    {
        code: "API_AUTH_FAILED",
        test: (l) =>
            l.includes("invalid_api_key") ||
            l.includes("incorrect api key provided") ||
            l.includes("401 unauthorized"),
    },
    {
        code: "PDF_UNREADABLE_TEXT",
        test: (l) =>
            /(too many cid chars|contains no graphs|no extractable text|scanned pdf|no text layer|without text layer)/.test(
                l,
            ),
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
