/**
 * 翻译附件标题格式化 (#310)。
 *
 * 纯函数实现, 不依赖 Zotero 运行时, 便于单测:
 * - shortTitle: 短标题-服务-类型 (历史默认, 输出与旧逻辑逐字一致)
 * - titlePrefix: 标题前N字符-年份-服务-类型 (#310 设想格式)
 * - fullTitle: 完整标题-服务-类型
 * - custom: 自定义模板, 占位符 {title} {titlePrefix} {shortTitle} {year} {service} {type}
 */

export type RenameStyle =
    | "shortTitle"
    | "titlePrefix"
    | "fullTitle"
    | "custom";

export const RENAME_STYLES: readonly RenameStyle[] = [
    "shortTitle",
    "titlePrefix",
    "fullTitle",
    "custom",
];

export const RENAME_TEMPLATE_PLACEHOLDERS = [
    "title",
    "titlePrefix",
    "shortTitle",
    "year",
    "service",
    "type",
] as const;

export interface TitleFormatInput {
    title: string;
    shortTitle: string;
    /** 条目日期字段的原始值, 如 "2023-05-01" / "2023年5月" / "May 2023" */
    date: string;
    service: string;
    type: string;
    style: string;
    prefixLength: number;
    template: string;
}

export function normalizeRenameStyle(value: unknown): RenameStyle {
    return RENAME_STYLES.includes(value as RenameStyle)
        ? (value as RenameStyle)
        : "shortTitle";
}

/** 从 Zotero 条目的日期字段提取四位年份, 兼容 ISO/中文/英文月份写法。 */
export function extractYear(date: string): string {
    const match = /(?:19|20)\d{2}/.exec(String(date || ""));
    return match ? match[0] : "";
}

function collapseWhitespace(text: string): string {
    return String(text || "").replace(/\s+/g, " ").trim();
}

/** 截取标题前缀; 超长时以省略号结尾, 让用户能看出被截断。 */
export function titlePrefixOf(title: string, length: number): string {
    const clean = collapseWhitespace(title);
    const limit = Math.max(1, Math.floor(Number(length) || 20));
    if (clean.length <= limit) return clean;
    return `${clean.slice(0, limit).trimEnd()}…`;
}

function joinParts(parts: (string | undefined)[]): string {
    return parts
        .filter((part): part is string => Boolean(part && part.trim()))
        .join("-");
}

function renderTemplate(
    template: string,
    values: Record<string, string>,
): string {
    let rendered = String(template || "");
    for (const key of RENAME_TEMPLATE_PLACEHOLDERS) {
        rendered = rendered.split(`{${key}}`).join(values[key] ?? "");
    }
    return collapseWhitespace(rendered);
}

export function buildAttachmentTitle(input: TitleFormatInput): string {
    const service = collapseWhitespace(input.service);
    const type = collapseWhitespace(input.type);
    const fallback = joinParts([service, type]);
    const title = collapseWhitespace(input.title);
    const shortTitle = collapseWhitespace(input.shortTitle);
    const year = extractYear(input.date);
    const prefix = titlePrefixOf(title, input.prefixLength);
    const values = {
        title,
        titlePrefix: prefix,
        shortTitle,
        year,
        service,
        type,
    };

    switch (normalizeRenameStyle(input.style)) {
        case "titlePrefix":
            // 无标题条目退回短标题/默认行为, 避免出现 "-年份-服务-类型" 开头。
            return title
                ? joinParts([prefix, year, service, type])
                : joinParts([shortTitle, year, service, type]) || fallback;
        case "fullTitle":
            return title
                ? joinParts([title, service, type])
                : joinParts([shortTitle, service, type]) || fallback;
        case "custom": {
            const rendered = renderTemplate(input.template, values);
            return rendered || fallback;
        }
        case "shortTitle":
        default:
            // 与历史行为逐字一致: 短标题-服务-类型, 无短标题则 服务-类型。
            return shortTitle
                ? joinParts([shortTitle, service, type])
                : fallback;
    }
}
