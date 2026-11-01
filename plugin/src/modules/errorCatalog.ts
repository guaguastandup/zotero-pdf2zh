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
    PDF_PASSWORD_REQUIRED: "这份 PDF 有密码保护，暂时无法翻译。",
    SCANNED_PDF_DETECTED:
        "检测到扫描版 PDF：页面是图片，没有可提取的文字层，无法翻译。",
    PDF_CID_CHARS_TOO_MANY:
        "这份 PDF 的内嵌字体异常（CID 字符过多），解析失败。",
    DISK_SPACE_INSUFFICIENT: "磁盘空间不足，无法保存翻译文件。",
    FILE_PERMISSION_DENIED: "无法读取文件或写入输出目录。",
    VENV_PATH_INVALID: "翻译虚拟环境路径失效（常见于移动 server 文件夹后）。",
    CONDA_ENV_NOT_FOUND: "无法定位 Conda 虚拟环境，翻译引擎未能启动。",
    ENV_RUST_BUILD_REQUIRED: "安装 pdf2zh_next 依赖时需要 Rust 编译器。",
    MSVC_REDIST_REQUIRED: "缺少 Microsoft Visual C++ 运行库。",
    LLM_API_KEY_INVALID: "当前 API Key 无效或未通过服务商校验。",
    UPSTREAM_BALANCE_INSUFFICIENT: "翻译服务账户余额不足或额度已用完。",
    UPSTREAM_RATE_LIMIT: "上游翻译服务限流或配额尽。",
    UPSTREAM_SSL_TIMEOUT: "连接翻译 API 时 SSL 握手超时。",
    UPSTREAM_SSL_ERROR: "与翻译 API 的 HTTPS 连接异常中断。",
    UPSTREAM_CONNECTION_REFUSED: "无法连接翻译 API（连接被拒绝）。",
    UPSTREAM_NETWORK_ERROR: "无法连接上游翻译服务（网络或 DNS 问题）。",
    UPSTREAM_HTML_RESPONSE: "翻译 API 返回了 HTML 页面而不是 JSON。",
    TRANSLATION_CANCELLED: "翻译进程被取消或超时终止。",
    ENGINE_STDIO_BROKEN: "翻译引擎子进程过早退出，翻译未完成。",
    BABELDOC_INTERNAL_ERROR: "BabelDOC 处理 PDF 时发生内部错误。",
};

const USER_MESSAGES_EN: Record<string, string> = {
    PDF_PASSWORD_REQUIRED: "This PDF is password protected.",
    SCANNED_PDF_DETECTED:
        "Scanned PDF detected: pages are images with no text layer.",
    PDF_CID_CHARS_TOO_MANY:
        "This PDF has broken embedded fonts (too many CID chars).",
    DISK_SPACE_INSUFFICIENT: "Not enough disk space for output files.",
    FILE_PERMISSION_DENIED: "Cannot read the file or write the output folder.",
    VENV_PATH_INVALID:
        "Translation venv path is invalid (server folder moved?).",
    CONDA_ENV_NOT_FOUND: "Conda environment not found.",
    ENV_RUST_BUILD_REQUIRED: "Rust compiler required for pdf2zh_next deps.",
    MSVC_REDIST_REQUIRED: "Microsoft Visual C++ Redistributable is missing.",
    LLM_API_KEY_INVALID: "API key invalid or rejected by the provider.",
    UPSTREAM_BALANCE_INSUFFICIENT: "Provider balance or quota exhausted.",
    UPSTREAM_RATE_LIMIT: "Upstream rate limit reached.",
    UPSTREAM_SSL_TIMEOUT: "SSL handshake timed out connecting to the API.",
    UPSTREAM_SSL_ERROR: "HTTPS connection to the API failed.",
    UPSTREAM_CONNECTION_REFUSED: "Connection refused by the translation API.",
    UPSTREAM_NETWORK_ERROR: "Cannot reach the translation API.",
    UPSTREAM_HTML_RESPONSE: "API returned HTML instead of JSON.",
    TRANSLATION_CANCELLED: "Translation cancelled or timed out.",
    ENGINE_STDIO_BROKEN: "Engine exited early; translation incomplete.",
    BABELDOC_INTERNAL_ERROR: "Internal BabelDOC error.",
};

const HINTS_ZH: Record<string, string> = {
    PDF_PASSWORD_REQUIRED: "请先用 PDF 阅读器解锁并另存副本，再对副本翻译。",
    SCANNED_PDF_DETECTED:
        "请换一份带文字层的 PDF（出版社原版通常可以），或先用 OCR 工具转成文字版再翻译。",
    PDF_CID_CHARS_TOO_MANY:
        "常见于老旧或扫描转换的 PDF，请换该文献的其他 PDF 版本，或先 OCR。",
    DISK_SPACE_INSUFFICIENT: "请释放磁盘空间后重试。",
    FILE_PERMISSION_DENIED:
        "确认 PDF 可打开、server 目录可写（Windows 可管理员运行）。",
    VENV_PATH_INVALID:
        "uv 用户勿移动 server 文件夹；或删除 *-venv 后重跑 update_packages.py。",
    CONDA_ENV_NOT_FOUND:
        "conda env list 检查，或重跑 python update_packages.py 重建。",
    ENV_RUST_BUILD_REQUIRED: "安装 rustup 后重试。",
    MSVC_REDIST_REQUIRED: "https://aka.ms/vs/17/release/vc_redist.x64.exe",
    LLM_API_KEY_INVALID: "在「LLM API 配置管理」中核对 Key。",
    UPSTREAM_BALANCE_INSUFFICIENT: "充值或更换 API Key。",
    UPSTREAM_RATE_LIMIT: "降低 QPS/并发（bing/google 建议 ≤2）后重试。",
    UPSTREAM_SSL_TIMEOUT: "检查网络或代理。",
    UPSTREAM_SSL_ERROR: "检查代理/防火墙，或更换网络。",
    UPSTREAM_CONNECTION_REFUSED: "核对 API 地址、代理与防火墙。",
    UPSTREAM_NETWORK_ERROR: "检查网络、代理与 API 地址。",
    UPSTREAM_HTML_RESPONSE: "通常是 API 地址写错或被网关拦截。",
    TRANSLATION_CANCELLED: "缩小页码范围、降低并发后重试。",
    ENGINE_STDIO_BROKEN:
        "看终端日志先修前面的报错；仅 Broken pipe 时重启 server 重试。",
    BABELDOC_INTERNAL_ERROR: "换引擎、降并发，或换其他 PDF。",
};

type Rule = { code: string; test: (l: string) => boolean };

// 与 server 端 ERROR_RULES 对齐的关键词（服务端已分类时不会走到这里）。
const RULES: Rule[] = [
    {
        code: "PDF_PASSWORD_REQUIRED",
        test: (l) =>
            /(file has not been decrypted|password required|document is encrypted|incorrect password)/.test(
                l,
            ),
    },
    {
        code: "SCANNED_PDF_DETECTED",
        test: (l) =>
            /(contains no graphs|no extractable text|scanned pdf|no text layer|without text layer)/.test(
                l,
            ),
    },
    { code: "PDF_CID_CHARS_TOO_MANY", test: (l) => /cid chars/.test(l) },
    {
        code: "DISK_SPACE_INSUFFICIENT",
        test: (l) => /(no space left|disk full|winerror 112|errno 28)/.test(l),
    },
    {
        code: "VENV_PATH_INVALID",
        test: (l) => /failed to canonicalize script path/.test(l),
    },
    { code: "ENV_RUST_BUILD_REQUIRED", test: (l) => /rust compiler/.test(l) },
    {
        code: "MSVC_REDIST_REQUIRED",
        test: (l) => /(visual c\+\+ redistributable|dll load failed)/.test(l),
    },
    {
        code: "LLM_API_KEY_INVALID",
        test: (l) =>
            /(api key not valid|api_key_invalid|incorrect api key)/.test(l),
    },
    {
        code: "UPSTREAM_BALANCE_INSUFFICIENT",
        test: (l) =>
            /(balance is insufficient|余额不足|account balance)/.test(l),
    },
    {
        code: "UPSTREAM_RATE_LIMIT",
        test: (l) => /(rate limit|resource_exhausted)/.test(l),
    },
    {
        code: "UPSTREAM_SSL_TIMEOUT",
        test: (l) => /handshake/.test(l) && /timed out/.test(l),
    },
    {
        code: "UPSTREAM_SSL_ERROR",
        test: (l) => /(unexpected_eof_while_reading|ssl error)/.test(l),
    },
    {
        code: "UPSTREAM_CONNECTION_REFUSED",
        test: (l) => /(connection refused|积极拒绝|10061)/.test(l),
    },
    {
        code: "UPSTREAM_NETWORK_ERROR",
        test: (l) =>
            /(apiconnectionerror|connection error|connecterror)/.test(l),
    },
    {
        code: "UPSTREAM_HTML_RESPONSE",
        test: (l) => l.includes("</html>") && l.includes("translation"),
    },
    {
        code: "TRANSLATION_CANCELLED",
        test: (l) => /(translation cancel|did not finish in time)/.test(l),
    },
    {
        code: "ENGINE_STDIO_BROKEN",
        test: (l) => /(brokenpipeerror|broken pipe|errno 32)/.test(l),
    },
    {
        code: "BABELDOC_INTERNAL_ERROR",
        test: (l) =>
            /(cannot unpack non-iterable nonetype|babeldoc translation error)/.test(
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
