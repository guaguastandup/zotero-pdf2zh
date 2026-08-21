import { config } from "../../package.json";
import { setPref, getPref } from "../utils/prefs";
import {
    llmApiManager,
    LLMApiData,
    emptyLLMApi,
    formatExtraDataForDisplay,
} from "./llmApiManager";
import axios from "axios";

const PREF_UI_TEXT = {
    zh: {
        invalidFont: "文件类型无效，请选择 .ttf、.otf、.woff 或 .woff2 文件。",
        colService: "服务",
        colModel: "模型",
        colApiUrl: "API URL",
        colApiKey: "API Key",
        colActivate: "激活",
        colExtraData: "额外参数",
        serverAddressRequired: "请先设置 Server IP 地址",
        connectionTitle: "Server 连接检查",
        checking: "正在检查 Server 连接...",
        unknown: "未知",
        successLine: (version: string) => `✓ 连接成功！Server 版本: ${version}`,
        successAlert: (url: string, version: string) =>
            `✓ 连接成功！\n\nServer 地址: ${url}\nServer 版本: ${version}\n状态: 正常运行`,
        badStatus: (status: number) => `Server 返回错误状态: ${status}`,
        unknownError: "未知错误",
        timeout: "连接超时（10秒）",
        timeoutHelp:
            "可能原因:\n1. 网络连接不稳定\n2. 防火墙阻止了连接\n3. Server 响应时间过长\n\n建议:\n- 检查网络连接\n- 临时关闭防火墙测试\n- 确认 Server 已正常启动",
        responseError: (status: number) => `Server 返回错误: ${status}`,
        responseHelp:
            "可能原因:\n1. Server 版本过旧，不支持 /health 端点\n2. Server 配置错误\n\n建议:\n- 更新 Server 到最新版本\n- 检查 Server 日志查看错误详情",
        cannotConnect: "无法连接到 Server",
        cannotConnectHelp: (url: string) =>
            "可能原因:\n1. Server 未启动\n2. 插件里的地址/端口和终端不一致\n3. 该端口被其他程序占用\n\n建议:\n- 打开 Server 终端，看它打印的 http://127.0.0.1:端口\n- 把插件里的 Python Server IP 改成和终端完全一样\n- 当前检查的是: " +
            url,
        wrongService: "这个地址上不是 PDF2zh Server",
        wrongServiceHelp: (url: string) =>
            "当前检查的是 " +
            url +
            "\n这个端口有响应，但不是 PDF2zh（常见是被其他程序占用）。\n请看 Server 终端里实际打印的地址，把插件里的 Python Server IP 改成那个地址。",
        genericHelp: "请检查网络连接和 Server 状态",
        failureLine: (message: string) => `✗ 连接失败: ${message}`,
        failureAlert: (message: string, help: string) =>
            `✗ 连接失败\n\n错误信息: ${message}\n\n${help}`,
    },
    en: {
        invalidFont:
            "Invalid file type. Select a .ttf, .otf, .woff, or .woff2 file.",
        colService: "Service",
        colModel: "Model",
        colApiUrl: "API URL",
        colApiKey: "API Key",
        colActivate: "Active",
        colExtraData: "Extra Parameters",
        serverAddressRequired: "Set the Server IP address first.",
        connectionTitle: "Server Connection Check",
        checking: "Checking Server connection...",
        unknown: "Unknown",
        successLine: (version: string) =>
            `✓ Connected. Server version: ${version}`,
        successAlert: (url: string, version: string) =>
            `✓ Connected successfully.\n\nServer: ${url}\nVersion: ${version}\nStatus: Running`,
        badStatus: (status: number) => `Server returned status ${status}`,
        unknownError: "Unknown error",
        timeout: "Connection timed out (10 seconds)",
        timeoutHelp:
            "Possible causes:\n1. Unstable network\n2. A firewall is blocking the connection\n3. The Server is responding slowly\n\nTry:\n- Check your network\n- Temporarily test without the firewall\n- Confirm the Server is running",
        responseError: (status: number) => `Server returned error ${status}`,
        responseHelp:
            "Possible causes:\n1. The Server is too old to provide /health\n2. Server configuration error\n\nTry:\n- Update the Server\n- Check the Server terminal logs",
        cannotConnect: "Cannot connect to the Server",
        cannotConnectHelp: (url: string) =>
            "Possible causes:\n1. The Server is not running\n2. The plugin URL/port does not match the terminal\n3. Another program is using that port\n\nTry:\n- Check the http://127.0.0.1:PORT printed in the Server terminal\n- Set Python Server IP in the plugin to that exact address\n- Currently checking: " +
            url,
        wrongService: "This address is not a PDF2zh Server",
        wrongServiceHelp: (url: string) =>
            "Checked " +
            url +
            "\nSomething responded, but it is not PDF2zh (another program may be using this port).\nCopy the address printed in the Server terminal into Python Server IP.",
        genericHelp: "Check the network connection and Server status.",
        failureLine: (message: string) => `✗ Connection failed: ${message}`,
        failureAlert: (message: string, help: string) =>
            `✗ Connection failed\n\nError: ${message}\n\n${help}`,
    },
} as const;

function preferenceUiLanguage(): "zh" | "en" {
    const locale = String(Zotero.locale || "en-US").toLowerCase();
    return locale.startsWith("zh") ? "zh" : "en";
}

function prefText(key: keyof (typeof PREF_UI_TEXT)["en"], ...args: any[]) {
    const value: any = (PREF_UI_TEXT as any)[preferenceUiLanguage()][key];
    return typeof value === "function" ? value(...args) : value;
}

export async function registerPrefsScripts(_window: Window) {
    if (!addon.data.prefs) {
        addon.data.prefs = {
            window: _window,
            columns: [],
            rows: [],
        };
    } else {
        addon.data.prefs.window = _window;
    }
    if (!addon.data.llmApis) {
        addon.data.llmApis = {
            map: new Map<string, LLMApiData>(),
            cachedKeys: [],
        };
    }
    bindPrefEvents();
    initTableUI();
    initializeEngineConfig();
}

function bindPrefEvents() {
    const { window } = addon.data.prefs ?? {};
    if (!window) return;
    const doc = window.document;
    if (!doc) return;
    // 为SourceLangSelect和TargetLangSelect添加html:option
    const sourceLangSelect = doc.getElementById(
        `zotero-prefpane-${config.addonRef}-sourceLangSelect`,
    );
    const targetLangSelect = doc.getElementById(
        `zotero-prefpane-${config.addonRef}-targetLangSelect`,
    );
    for (const [langName, langCode] of Object.entries(lang_map)) {
        const option = doc.createElement("option");
        option.value = langCode;
        option.textContent = langName;
        sourceLangSelect?.appendChild(option.cloneNode(true));
        targetLangSelect?.appendChild(option.cloneNode(true));
    }
    // ********************* Engine *********************
    const groupbox = doc.querySelector("groupbox");
    if (groupbox) {
        groupbox.addEventListener("DOMContentLoaded", () => {
            setTimeout(() => {
                initializeEngineConfig();
            }, 200);
        });
    }
    doc
        .querySelector(`#zotero-prefpane-${config.addonRef}-engine`)
        ?.addEventListener("change", (e) => {
            const value = (e.target as HTMLInputElement).value;
            if (value) {
                setPref("engine", value);
                handleEngineChange(value);
            }
        });

    doc
        .querySelector(`#zotero-prefpane-${config.addonRef}-engineSelect`)
        ?.addEventListener("change", (e) => {
            const value = (e.target as HTMLSelectElement).value;
            if (value) {
                setPref("engine", value);
                handleEngineChange(value);
            }
        });

    // ********************* pdf1.x字体 *********************
    doc
        .querySelector(`#zotero-prefpane-${config.addonRef}-fontFile-clear`)
        ?.addEventListener("click", () => {
            setPref("fontFile", "");
        });
    doc
        .getElementById(`zotero-prefpane-${config.addonRef}-fontFile`)
        ?.addEventListener("change", function (event) {
            const file = (event.target as HTMLInputElement).files?.[0];
            ztoolkit.log("Selected font file:", getPref("fontFile"));
            if (file) {
                const validExtensions = [".ttf", ".otf", ".woff", ".woff2"];
                const extension = file.name
                    .slice(file.name.lastIndexOf("."))
                    .toLowerCase();
                if (!validExtensions.includes(extension)) {
                    alert(prefText("invalidFont"));
                    setPref("fontFile", "");

                    ztoolkit.log("Selected font file1:", file);
                } else {
                    setPref("fontFile", file.mozFullPath);
                    ztoolkit.log("Selected font file2:", getPref("fontFile"));
                }
            }
        });

    // ********************* Server连接检查 *********************
    // 新增：测试Server连接按钮事件
    doc
        .querySelector(`#zotero-prefpane-${config.addonRef}-checkConnection`)
        ?.addEventListener("click", async () => {
            await checkServerConnection();
        });

    // ********************* LLM API 表格 *********************
    // LLM API 表格
    doc
        .querySelector(
            `#zotero-prefpane-${config.addonRef}-llmapi-table-container`,
        )
        ?.addEventListener("showing", () => {
            ztoolkit.log("LLM API 表格容器显示事件触发");
            updateLLMApiTableUI();
        });

    // 绑定 LLM API 相关按钮事件
    const addButton = doc.getElementById(
        `zotero-prefpane-${config.addonRef}-llmapi-add`,
    );
    const removeButton = doc.getElementById(
        `zotero-prefpane-${config.addonRef}-llmapi-remove`,
    );
    const editButton = doc.getElementById(
        `zotero-prefpane-${config.addonRef}-llmapi-edit`,
    );
    const activateButton = doc.getElementById(
        `zotero-prefpane-${config.addonRef}-llmapi-activate`,
    );
    const toTopButton = doc.getElementById(
        `zotero-prefpane-${config.addonRef}-llmapi-totop`,
    );
    addButton?.addEventListener("command", async () => {
        await openLLMApiEditDialog();
    });
    removeButton?.addEventListener("command", () => {
        const selectedKeys = getLLMApiSelection();
        selectedKeys.forEach((key) => {
            if (key) {
                llmApiManager.deleteLLMApi(key);
                addon.data.llmApis?.map.delete(key);
            }
        });
        updateCachedLLMApiKeys();
        saveLLMApisToPrefs();
        updateLLMApiTableUI();
    });
    editButton?.addEventListener("command", async () => {
        const selectedKeys = getLLMApiSelection();
        if (selectedKeys.length === 1) {
            await openLLMApiEditDialog(selectedKeys[0]);
        }
    });
    activateButton?.addEventListener("command", () => {
        const selectedKeys = getLLMApiSelection();
        if (selectedKeys.length === 1) {
            const key = selectedKeys[0];
            const llmApi = addon.data.llmApis?.map.get(key);
            if (llmApi) {
                if (llmApi.activate) {
                    llmApiManager.deactivateLLMApi(key);
                } else {
                    llmApiManager.activateLLMApi(key);
                }
                // 更新addon.data中的数据
                addon.data.llmApis?.map.set(key, llmApiManager.getLLMApi(key)!);
                // 保存到偏好设置
                saveLLMApisToPrefs();
                // 更新表格显示
                updateLLMApiTableUI();
            }
        }
    });
    toTopButton?.addEventListener("command", () => {
        // 将这个条目移动到所有条目的最上面
        const selectedKeys = getLLMApiSelection();
        if (selectedKeys.length === 1) {
            const key = selectedKeys[0];
            const llmApi = addon.data.llmApis?.map.get(key);
            if (llmApi) {
                const llmApis = Array.from(
                    addon.data.llmApis?.map.values() || [],
                );
                const index = llmApis.findIndex((llmApi) => llmApi.key === key);
                if (index !== -1) {
                    llmApis.splice(index, 1);
                    llmApis.unshift(llmApi);
                    addon.data.llmApis?.map.clear();
                    llmApis.forEach((llmApi) => {
                        addon.data.llmApis?.map.set(llmApi.key, llmApi);
                    });
                    updateCachedLLMApiKeys();
                    saveLLMApisToPrefs();
                    updateLLMApiTableUI();
                }
            }
        }
    });
}

// 初始化 LLM API 表格
export async function initTableUI() {
    if (!addon.data.prefs?.window) return;
    loadLLMApisFromPrefs();
    const renderLock = Zotero.Promise.defer();
    addon.data.prefs.tableHelper = new ztoolkit.VirtualizedTable(
        addon.data.prefs.window!,
    )
        .setContainerId(
            `zotero-prefpane-${config.addonRef}-llmapi-table-container`,
        )
        .setProp({
            id: `zotero-prefpane-${config.addonRef}-llmapi-table`,
            columns: [
                {
                    dataKey: "service",
                    label: prefText("colService"),
                    width: 150,
                },
                { dataKey: "model", label: prefText("colModel"), width: 200 },
                { dataKey: "apiUrl", label: prefText("colApiUrl"), width: 140 },
                { dataKey: "apiKey", label: prefText("colApiKey"), width: 100 },
                {
                    dataKey: "activate",
                    label: prefText("colActivate"),
                    width: 80,
                },
                {
                    dataKey: "extraData",
                    label: prefText("colExtraData"),
                    width: 200,
                },
            ],
            showHeader: true,
            multiSelect: true,
            staticColumns: false,
            disableFontSizeScaling: true,
        })
        .setProp(
            "getRowCount",
            () => addon.data.llmApis?.cachedKeys.length || 0,
        )
        .setProp("getRowData", getRowData)
        .setProp("onSelectionChange", (selection) => {
            const selectedKeys = getLLMApiSelection();
            addon.data.llmApis.selectedKey = selectedKeys[0];
            addon.data.prefs?.window?.document
                .querySelectorAll(".llmapi-selection")
                ?.forEach((e) =>
                    setButtonDisabled(
                        e as XULButtonElement,
                        selectedKeys.length === 0,
                    ),
                );
            addon.data.prefs?.window?.document
                .querySelectorAll(".llmapi-selection-single")
                ?.forEach((e) =>
                    setButtonDisabled(
                        e as XULButtonElement,
                        selectedKeys.length !== 1,
                    ),
                );
        })
        .setProp("onKeyDown", (event: KeyboardEvent) => {
            if (
                event.key == "Delete" ||
                (Zotero.isMac && event.key == "Backspace")
            ) {
                const selectedKeys = getLLMApiSelection();
                selectedKeys.forEach((key) => {
                    if (key) {
                        llmApiManager.deleteLLMApi(key);
                        addon.data.llmApis?.map.delete(key);
                    }
                });
                updateCachedLLMApiKeys();
                saveLLMApisToPrefs();
                updateLLMApiTableUI();
                return false;
            }
            return true;
        })
        .render(-1, () => {
            renderLock.resolve();
        });
    await renderLock.promise;
    updateLLMApiTableUI();
    // 强制刷新表格显示所有行;
    setTimeout(() => {
        ztoolkit.log("Forcing table refresh...");
        const tableHelper = (addon.data.prefs as any).tableHelper;
        if (tableHelper && tableHelper.treeInstance) {
            // 强制重新计算行数
            const rowCount = addon.data.llmApis?.cachedKeys.length || 0;
            // 强制重新渲染
            tableHelper.treeInstance.invalidate();
            tableHelper.render(-1, () => {
                ztoolkit.log("Forced table refresh completed");
            });
        }
    }, 500);
}

// 更新 LLM API 缓存键列表
function updateCachedLLMApiKeys() {
    if (!addon.data.llmApis) return;
    addon.data.llmApis.cachedKeys = Array.from(addon.data.llmApis.map.keys());
}

// 打开 LLM API 编辑对话框
async function openLLMApiEditDialog(key?: string) {
    const llmApi = key ? addon.data.llmApis?.map.get(key) : emptyLLMApi;
    if (!llmApi) {
        return false;
    }

    const dialogData = {
        service: llmApi.service || "openai",
        model: llmApi.model || "",
        apiKey: llmApi.apiKey || "",
        apiUrl: llmApi.apiUrl || "",
        activate: llmApi.activate || false,
        extraData: llmApi.extraData || {},
    };

    // 创建窗口参数
    const windowArgs: {
        _initPromise: any;
        data: {
            service: string;
            model: string;
            apiKey: string;
            apiUrl: string;
            activate: boolean;
            extraData: any;
        };
        isEdit: boolean;
        result?: {
            success: boolean;
            data: {
                service: string;
                model: string;
                apiKey: string;
                apiUrl: string;
                activate: boolean;
            };
            isEdit: boolean;
            originalKey?: string;
        };
    } = {
        _initPromise: Zotero.Promise.defer(),
        data: dialogData,
        isEdit: !!key,
    };

    // 打开XHTML对话框
    const dialogWindow = Zotero.getMainWindow().openDialog(
        `chrome://${config.addonRef}/content/llmApiEditor.xhtml`,
        `${config.addonRef}-llmApiEditor`,
        `chrome,centerscreen,resizable,status,dialog=no`,
        windowArgs,
    );
    if (!dialogWindow) {
        return false;
    }
    // 等待对话框初始化完成
    await windowArgs._initPromise.promise;
    // 等待对话框关闭
    const result = await new Promise<any>((resolve) => {
        const checkClosed = () => {
            if (dialogWindow.closed) {
                resolve(windowArgs.result);
            } else {
                setTimeout(checkClosed, 100);
            }
        };
        checkClosed();
    });

    if (!result || !result.success) {
        return false;
    }

    const userData = result.data;
    try {
        // 如果是编辑现有配置，使用现有key；否则创建新的key
        const newLLMApi: LLMApiData = {
            key: key || Zotero.Utilities.generateObjectKey(),
            service: userData.service || userData.serviceselect || "",
            model: userData.model || userData.modelselect || "",
            apiKey: userData.apiKey,
            apiUrl: userData.apiUrl,
            activate: userData.activate,
            extraData: userData.extraData || {},
        };
        // 添加到addon.data.llmApis
        if (addon.data.llmApis) {
            addon.data.llmApis.map.set(newLLMApi.key, newLLMApi);
            updateCachedLLMApiKeys();
        }
        // 更新llmApiManager
        llmApiManager.updateLLMApi(newLLMApi);
        // 保存到偏好设置
        saveLLMApisToPrefs();
        // 更新表格
        updateLLMApiTableUI();
        return true;
    } catch (error) {
        return false;
    }
}

// 保存 LLM APIs 到偏好设置
function saveLLMApisToPrefs() {
    if (!addon.data.llmApis) return;
    const llmApisArray = Array.from(addon.data.llmApis.map.values());
    const llmApisJson = JSON.stringify(llmApisArray);
    setPref("llmApis", llmApisJson as string);
}

function migrateLegacyDeepSeekConfig(llmApi: LLMApiData): boolean {
    if (llmApi.service !== "deepseek") return false;
    if (
        llmApi.model !== "deepseek-chat" &&
        llmApi.model !== "deepseek-reasoner"
    ) {
        return false;
    }

    const legacyModel = llmApi.model;
    llmApi.model = "deepseek-v4-flash";
    llmApi.extraData = llmApi.extraData || {};

    // Preserve an explicitly saved thinking choice. Otherwise map the retired
    // aliases to their V4 Flash semantics.
    if (!("deepseek_thinking_mode" in llmApi.extraData)) {
        if (legacyModel === "deepseek-reasoner") {
            llmApi.extraData.deepseek_thinking_mode = "enabled";
            llmApi.extraData.deepseek_reasoning_effort = "high";
        } else {
            llmApi.extraData.deepseek_thinking_mode = "disabled";
            delete llmApi.extraData.deepseek_reasoning_effort;
        }
    }
    return true;
}

// 从偏好设置加载 LLM APIs
export function loadLLMApisFromPrefs() {
    const llmApisJson = getPref("llmApis");
    if (!llmApisJson || typeof llmApisJson !== "string") {
        ztoolkit.log("No valid data found in prefs");
        return;
    }
    try {
        const llmApisArray = JSON.parse(llmApisJson);
        if (Array.isArray(llmApisArray)) {
            let migratedLegacyDeepSeek = false;
            // 清空现有数据
            addon.data.llmApis?.map.clear();
            // 加载数据到addon.data.llmApis和llmApiManager
            llmApisArray.forEach((llmApi: LLMApiData) => {
                if (llmApi.key && llmApi.service) {
                    if (migrateLegacyDeepSeekConfig(llmApi)) {
                        migratedLegacyDeepSeek = true;
                    }
                    // 为旧数据设置默认值
                    if (llmApi.activate === undefined) {
                        llmApi.activate = false;
                    }
                    if (!llmApi.extraData) {
                        llmApi.extraData = {};
                    }
                    let key = llmApi.key;
                    if (!key) {
                        key = Zotero.Utilities.generateObjectKey();
                        llmApi.key = key;
                    }
                    addon.data.llmApis?.map.set(llmApi.key, llmApi);
                    llmApiManager.updateLLMApi(llmApi);
                }
            });
            updateCachedLLMApiKeys();
            if (migratedLegacyDeepSeek) {
                saveLLMApisToPrefs();
                ztoolkit.log(
                    "Migrated retired DeepSeek aliases to DeepSeek V4 Flash",
                );
            }
        } else {
            ztoolkit.log("Parsed data is not an array");
        }
    } catch (error) {
        ztoolkit.log("Error loading LLM APIs from prefs:", error);
    }
    ztoolkit.log("LLM APIs loaded from prefs:", addon.data.llmApis);
}

function updateLLMApiTableUI() {
    setTimeout(() => addon.data.prefs?.tableHelper?.treeInstance.invalidate());
}

function setButtonDisabled(button: XUL.Button, disabled: boolean) {
    if (button) {
        button.disabled = disabled;
    }
}

function getRowData(index: number) {
    const keys = addon.data.llmApis?.cachedKeys || [];
    let llmApi = emptyLLMApi;
    if (keys && keys.length > index) {
        const key = keys[index];
        llmApi = addon.data.llmApis?.map.get(key) || emptyLLMApi;
    }
    return {
        key: llmApi.key || "",
        service: llmApi.service || "",
        model: llmApi.model || "",
        apiUrl: llmApi.apiUrl || "",
        apiKey: llmApi.apiKey || "",
        extraData: formatExtraDataForDisplay(llmApi.extraData),
        activate: llmApi.activate ? "✅" : "",
    };
}

// 获取 LLM API 选择
function getLLMApiSelection() {
    const indices =
        addon.data.prefs?.tableHelper?.treeInstance?.selection.selected;
    if (!indices) {
        return [];
    }
    const keys = addon.data.llmApis?.cachedKeys || [];
    return Array.from(indices).map((i) => keys[i]) || [];
}

// ------------ pdf2zh 1.x & pdf2zh 2.x switch ------------
// 初始化引擎配置显示
function initializeEngineConfig() {
    const { window } = addon.data.prefs ?? {};
    if (!window) {
        ztoolkit.log("Window object not found");
        return;
    }
    // 延迟执行，确保DOM完全加载
    setTimeout(() => {
        const engineSelect = window.document.querySelector(
            `#zotero-prefpane-${config.addonRef}-engineSelect`,
        ) as HTMLSelectElement | null;
        if (engineSelect) {
            const currentEngine = engineSelect.value;
            handleEngineChange(currentEngine);
        }
    }, 100);
}

// 引擎切换处理函数
function handleEngineChange(engine: string) {
    ztoolkit.log("引擎切换处理函数", engine);
    const { window } = addon.data.prefs ?? {};
    if (!window) {
        ztoolkit.log("窗口对象不存在");
        return;
    }
    // 获取所有class为pdf2x-config的元素
    const pdf2xConfigs = window.document.getElementsByClassName("pdf2x-config");
    for (const configElement of pdf2xConfigs as any as HTMLElement[]) {
        configElement.style.display =
            engine === "pdf2zh_next" ? "block" : "none";
    }
    const pdf1xConfigs = window.document.getElementsByClassName("pdf1x-config");
    for (const configElement of pdf1xConfigs as any as HTMLElement[]) {
        configElement.style.display =
            engine === "pdf2zh_next" ? "none" : "block";
    }
}

const lang_map = {
    English: "en",
    "Simplified Chinese": "zh-CN",
    "Traditional Chinese - Hong Kong": "zh-HK",
    "Traditional Chinese - Taiwan": "zh-TW",
    Japanese: "ja",
    Korean: "ko",
    Polish: "pl",
    Russian: "ru",
    Spanish: "es",
    Portuguese: "pt",
    "Brazilian Portuguese": "pt-BR",
    French: "fr",
    Malay: "ms",
    Indonesian: "id",
    Turkmen: "tk",
    "Filipino (Tagalog)": "tl",
    Vietnamese: "vi",
    "Kazakh (Latin)": "kk",
    German: "de",
    Dutch: "nl",
    Irish: "ga",
    Italian: "it",
    Greek: "el",
    Swedish: "sv",
    Danish: "da",
    Norwegian: "no",
    Icelandic: "is",
    Finnish: "fi",
    Ukrainian: "uk",
    Czech: "cs",
    Romanian: "ro",
    Hungarian: "hu",
    Slovak: "sk",
    Croatian: "hr",
    Estonian: "et",
    Latvian: "lv",
    Lithuanian: "lt",
    Belarusian: "be",
    Macedonian: "mk",
    Albanian: "sq",
    "Serbian (Cyrillic)": "sr",
    Slovenian: "sl",
    Catalan: "ca",
    Bulgarian: "bg",
    Maltese: "mt",
    Swahili: "sw",
    Amharic: "am",
    Oromo: "om",
    Tigrinya: "ti",
    "Haitian Creole": "ht",
    Latin: "la",
    Lao: "lo",
    Malayalam: "ml",
    Gujarati: "gu",
    Thai: "th",
    Burmese: "my",
    Tamil: "ta",
    Telugu: "te",
    Oriya: "or",
    Armenian: "hy",
    "Mongolian (Cyrillic)": "mn",
    Georgian: "ka",
    Khmer: "km",
    Bosnian: "bs",
    Luxembourgish: "lb",
    Romansh: "rm",
    Turkish: "tr",
    Sinhala: "si",
    Uzbek: "uz",
    Kyrgyz: "ky",
    Tajik: "tg",
    Abkhazian: "ab",
    Afar: "aa",
    Afrikaans: "af",
    Akan: "ak",
    Aragonese: "an",
    Avaric: "av",
    Ewe: "ee",
    Aymara: "ay",
    Ojibwa: "oj",
    Occitan: "oc",
    Ossetian: "os",
    Pali: "pi",
    Bashkir: "ba",
    Basque: "eu",
    Breton: "br",
    Chamorro: "ch",
    Chechen: "ce",
    Chuvash: "cv",
    Tswana: "tn",
    "Ndebele, South": "nr",
    Ndonga: "ng",
    Faroese: "fo",
    Fijian: "fj",
    "Frisian, Western": "fy",
    Ganda: "lg",
    Kongo: "kg",
    Kalaallisut: "kl",
    "Church Slavic": "cu",
    Guarani: "gn",
    Interlingua: "ia",
    Herero: "hz",
    Kikuyu: "ki",
    Rundi: "rn",
    Kinyarwanda: "rw",
    Galician: "gl",
    Kanuri: "kr",
    Cornish: "kw",
    Komi: "kv",
    Xhosa: "xh",
    Corsican: "co",
    Cree: "cr",
    Quechua: "qu",
    "Kurdish (Latin)": "ku",
    Kuanyama: "kj",
    Limburgan: "li",
    Lingala: "ln",
    Manx: "gv",
    Malagasy: "mg",
    Marshallese: "mh",
    Maori: "mi",
    Navajo: "nv",
    Nauru: "na",
    Nyanja: "ny",
    "Norwegian Nynorsk": "nn",
    Sardinian: "sc",
    "Northern Sami": "se",
    Samoan: "sm",
    Sango: "sg",
    Shona: "sn",
    Esperanto: "eo",
    "Scottish Gaelic": "gd",
    Somali: "so",
    "Southern Sotho": "st",
    Tatar: "tt",
    Tahitian: "ty",
    Tongan: "to",
    Twi: "tw",
    Walloon: "wa",
    Welsh: "cy",
    Venda: "ve",
    Volapük: "vo",
    Interlingue: "ie",
    "Hiri Motu": "ho",
    Igbo: "ig",
    Ido: "io",
    Inuktitut: "iu",
    Inupiaq: "ik",
    "Sichuan Yi": "ii",
    Yoruba: "yo",
    Zhuang: "za",
    Tsonga: "ts",
    Zulu: "zu",
};

// ********************* Server连接检查 *********************
// 新增：测试Server连接功能的实现
// 使用axios请求/health端点来验证服务器是否正常运行
// 包含详细的错误处理和故障排除提示
async function checkServerConnection() {
    const serverUrl = getPref("new_serverip")?.toString() || "";
    if (!serverUrl) {
        ztoolkit.getGlobal("alert")(prefText("serverAddressRequired"));
        return;
    }

    const progressWindow = new ztoolkit.ProgressWindow(
        prefText("connectionTitle"),
        { closeOnClick: false, closeTime: -1 },
    ).createLine({
        text: prefText("checking"),
        type: "default",
        progress: 50,
    });
    progressWindow.show();

    try {
        const response = await axios.get(`${serverUrl}/health`, {
            timeout: 10000,
            headers: { "Content-Type": "application/json" },
        });
        if (response.status !== 200 || !response.data) {
            throw new Error(prefText("badStatus", response.status));
        }

        const data = response.data;
        if (
            !data ||
            typeof data !== "object" ||
            (data.status !== "ok" && !data.version)
        ) {
            throw new Error(prefText("wrongService"));
        }
        const version = data.version || prefText("unknown");
        ztoolkit.log("Server connection succeeded:", data);
        progressWindow.changeLine({
            text: prefText("successLine", version),
            type: "success",
            progress: 100,
        });
        setTimeout(() => {
            progressWindow.close();
            ztoolkit.getGlobal("alert")(
                prefText("successAlert", serverUrl, version),
            );
        }, 1000);
    } catch (error) {
        ztoolkit.log("Server connection failed:", error);
        let errorMsg = prefText("unknownError");
        let troubleshooting = prefText("genericHelp");

        if (axios.isAxiosError(error)) {
            if (
                error.code === "ECONNABORTED" ||
                error.message.includes("timeout")
            ) {
                errorMsg = prefText("timeout");
                troubleshooting = prefText("timeoutHelp");
            } else if (error.response) {
                if (
                    error.response.status === 401 ||
                    error.response.status === 403 ||
                    error.response.status === 404
                ) {
                    errorMsg = prefText("wrongService");
                    troubleshooting = prefText("wrongServiceHelp", serverUrl);
                } else {
                    errorMsg = prefText("responseError", error.response.status);
                    troubleshooting = prefText("responseHelp");
                }
            } else if (error.request) {
                errorMsg = prefText("cannotConnect");
                troubleshooting = prefText("cannotConnectHelp", serverUrl);
            } else {
                errorMsg = error.message;
            }
        } else if (error instanceof Error) {
            errorMsg = error.message;
            if (errorMsg === prefText("wrongService")) {
                troubleshooting = prefText("wrongServiceHelp", serverUrl);
            }
        }

        progressWindow.changeLine({
            text: prefText("failureLine", errorMsg),
            type: "error",
            progress: 100,
        });
        setTimeout(() => {
            progressWindow.close();
            ztoolkit.getGlobal("alert")(
                prefText("failureAlert", errorMsg, troubleshooting),
            );
        }, 1500);
    }
}
