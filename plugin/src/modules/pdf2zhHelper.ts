import { getPref } from "../utils/prefs";
import { getString } from "../utils/locale";
import { FileProcessor } from "./pdf2zhFileProcessor";
import { ServerConfig, PDFType, PDFOperationOptions } from "./pdf2zhTypes";
import { loadLLMApisFromPrefs } from "./preferenceScript";

export class PDF2zhHelperFactory {
    // 翻译请求本身不要重试，避免同一篇 PDF 被重复翻译。
    private static readonly MAX_RETRIES = 1;
    private static readonly RETRY_DELAY = 2000; // 2秒
    // 下载/补拉附件可以多试几次：文件往往已经在 translated 目录里了。
    private static readonly DOWNLOAD_MAX_RETRIES = 3;
    // 同一轮处理里已经挂上的附件（parent + service + type），避免本地导入失败后又 HTTP 再挂一次。
    private static currentAttachKeys = new Set<string>();

    // **** 由hooks.ts调用, main entries *****
    static async processWorker(
        endpoint: string, // 仅包含请求类型
    ) {
        const pane = ztoolkit.getGlobal("ZoteroPane");
        const selectedItems = pane.getSelectedItems();
        if (selectedItems.length == 0) {
            ztoolkit.getGlobal("alert")(
                getString("operation-error-no-selection"),
            );
            return;
        }
        const tasks: Array<{
            fileName: string;
            item: Zotero.Item;
            config: ServerConfig;
            endpoint: string;
        }> = [];
        for (const item of selectedItems) {
            try {
                const filepath = await this.validatePDFAttachment(item);
                const fileName = PathUtils.filename(filepath);
                const inputType = this.getFileType(fileName);
                const operationError = this.getOperationValidationError(
                    endpoint,
                    inputType,
                );
                if (operationError) {
                    throw new Error(operationError);
                }
                const config = this.getServerConfig();
                tasks.push({
                    fileName,
                    item,
                    config,
                    endpoint,
                });
            } catch (error) {
                const message =
                    error instanceof Error
                        ? error.message
                        : getString("operation-error-unknown");
                ztoolkit.getGlobal("alert")(
                    getString("operation-error-prefix", {
                        args: { message },
                    }),
                );
            }
        }
        if (tasks.length === 0) {
            return;
        }

        const progressWindow = new ztoolkit.ProgressWindow(
            getString("operation-progress-title"),
        ).createLine({
            text: getString("operation-progress-processing"),
            type: "default",
            progress: 0,
        });
        progressWindow.show();

        const fileProcessor = FileProcessor.getInstance();
        const removeListener = fileProcessor.addEventListener((event, data) => {
            switch (event) {
                case "batchStarted":
                    progressWindow.changeLine({
                        text: getString("operation-batch-started", {
                            args: { count: data.totalTasks },
                        }),
                        type: "default",
                        progress: 0,
                    });
                    break;
                case "batchCompleted":
                    progressWindow.changeLine({
                        text: getString("operation-batch-completed", {
                            args: {
                                succeeded: data.succeeded,
                                failed: data.failed,
                            },
                        }),
                        type: data.failed > 0 ? "error" : "success",
                        progress: 100,
                    });
                    break;
            }
        });
        try {
            await fileProcessor.processBatch(tasks);
        } finally {
            removeListener();
        }
    }

    static getOperationValidationError(
        endpoint: string,
        inputType: string,
    ): string | null {
        const allowed: Record<string, string[]> = {
            translate: [PDFType.ORIGIN],
            crop: [PDFType.ORIGIN, PDFType.MONO, PDFType.DUAL],
            compare: [PDFType.ORIGIN, PDFType.DUAL],
            "crop-compare": [PDFType.ORIGIN, PDFType.DUAL, PDFType.DUAL_CUT],
        };

        if (endpoint === "crop-compare" && inputType === PDFType.CROP_COMPARE) {
            return getString("operation-error-crop-compare-terminal");
        }
        if (endpoint === "compare" && inputType === PDFType.COMPARE) {
            return getString("operation-error-compare-terminal");
        }
        const accepted = allowed[endpoint];
        if (!accepted || accepted.includes(inputType)) {
            return null;
        }
        const key =
            endpoint === "translate"
                ? "operation-error-translate"
                : endpoint === "crop"
                  ? "operation-error-crop"
                  : endpoint === "compare"
                    ? "operation-error-compare"
                    : "operation-error-crop-compare";
        return getString(key);
    }

    // 处理单个文件
    static async processSingleFile(params: {
        fileName: string; // 文件名
        item: Zotero.Item; // item
        config: ServerConfig; // serverConfig
        endpoint: string; // 请求类型
    }) {
        const { fileName, item, config, endpoint } = params; // config
        ztoolkit.log(
            `Processing Single File: ${fileName}, ServerConfig: ${config}`,
        );
        this.currentAttachKeys.clear();
        try {
            const fileData = await this.prepareFileData(item);
            const response = await this.sendRequest(fileData, config, endpoint);
            await this.handleResponse(response, item, config);
        } catch (error) {
            ztoolkit.log(`处理单个文件失败: ${fileName}, 错误: ${error}`);
            const message =
                error instanceof Error
                    ? error.message
                    : getString("operation-error-unknown");
            ztoolkit.getGlobal("alert")(
                getString("operation-error-single-file", {
                    args: { fileName, message },
                }),
            );
            // FileProcessor owns batch success/failure accounting. Propagate the
            // error after showing the per-file message so a failed task is not
            // counted as success.
            throw error;
        }
    }

    // 准备文件数据
    static async prepareFileData(
        item: Zotero.Item,
    ): Promise<{ fileName: string; base64: string }> {
        const filepath = await this.validatePDFAttachment(item);
        const fileName = PathUtils.filename(filepath);
        const base64 = await this.readPDFAsBase64(filepath);
        return { fileName, base64 }; // 返回PDF数据用于传输, 返回fileName
    }

    static async sendRequest(
        fileData: { fileName: string; base64: string },
        config: ServerConfig,
        endpoint: string,
    ) {
        return this.retryOperation(async () => {
            // 获取激活的 LLM API 配置
            let llmApiConfig;
            if (config.engine == "pdf2zh") {
                llmApiConfig = this.getActiveLLMApiConfig(config.service);
            } else {
                llmApiConfig = this.getActiveLLMApiConfig(config.next_service);
            }

            const requestBody: any = {
                fileName: fileData.fileName,
                fileContent: fileData.base64,
                ...config, // 发送config数据
            };
            ztoolkit.log("server config: ", config);
            // 如果有激活的 LLM API 配置，添加到请求中
            if (llmApiConfig) {
                requestBody.llm_api = llmApiConfig;
                ztoolkit.log("llmApiConfig", {
                    service: llmApiConfig.service,
                    model: llmApiConfig.model,
                    apiUrl: llmApiConfig.apiUrl,
                    apiKey: llmApiConfig.apiKey ? "********" : "",
                    extraDataKeys: Object.keys(llmApiConfig.extraData || {}),
                });
            }
            const response = await fetch(`${config.serverUrl}/${endpoint}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
                cache: "no-store",
            });
            const text = await response.text();
            let result: {
                status?: string;
                message?: string;
                taskId?: string;
                [key: string]: unknown;
            };
            try {
                result = this.parseServerPayload(text);
            } catch (error) {
                ztoolkit.log(`response`, response, text);
                throw new Error(
                    text ||
                        (error instanceof Error
                            ? error.message
                            : `服务器返回错误 HTTP ${response.status}`),
                );
            }
            if (!response.ok || result.status === "error") {
                ztoolkit.log(`response`, response, result);
                throw new Error(result.message || "服务器返回错误");
            }
            if (
                result.status === "accepted" &&
                typeof result.taskId === "string" &&
                result.taskId
            ) {
                return this.waitForAcceptedTask(config, result.taskId);
            }
            return result;
        });
    }

    static parseServerPayload(text: string): {
        status?: string;
        message?: string;
        taskId?: string;
        [key: string]: unknown;
    } {
        const trimmed = (text || "").trim();
        if (!trimmed) {
            throw new Error("服务器返回为空");
        }
        return JSON.parse(trimmed) as {
            status?: string;
            message?: string;
            taskId?: string;
            [key: string]: unknown;
        };
    }

    static completedTaskPayload(
        task: Record<string, unknown> | undefined,
        taskId: string,
    ): { status: string; message?: string; [key: string]: unknown } | null {
        if (!task) {
            return null;
        }
        const id = String(task.taskId || "");
        if (id !== taskId) {
            return null;
        }
        const nested =
            task.result && typeof task.result === "object"
                ? (task.result as Record<string, unknown>)
                : null;
        const finished =
            task.active === false ||
            task.status === "完成" ||
            task.status === "失败" ||
            task.status === "success" ||
            task.status === "failed" ||
            nested?.status === "success" ||
            nested?.status === "error";
        if (!finished) {
            return null;
        }
        if (
            task.status === "失败" ||
            task.status === "failed" ||
            nested?.status === "error"
        ) {
            return {
                status: "error",
                message: String(
                    nested?.message || task.error || task.message || "翻译失败",
                ),
            };
        }
        if (nested && nested.status === "success") {
            return nested as { status: string; message?: string };
        }
        return {
            status: "success",
            fileList: task.fileList || [],
            filePaths: task.filePaths || [],
            outputDir: task.outputDir || "",
        };
    }

    static async fetchCompletedTask(
        config: ServerConfig,
        taskId: string,
    ): Promise<{
        status: string;
        message?: string;
        [key: string]: unknown;
    } | null> {
        const base = this.normalizeServerUrl(config.serverUrl);
        try {
            const tasksRes = await fetch(`${base}/api/tasks`, {
                cache: "no-store",
            });
            const tasksData = tasksRes.ok
                ? ((await tasksRes.json()) as {
                      tasks?: Array<Record<string, unknown>>;
                  })
                : { tasks: [] };
            const tasks = Array.isArray(tasksData.tasks) ? tasksData.tasks : [];
            const matched = tasks.find(
                (task) => String(task.taskId || "") === taskId,
            );
            const fromTasks = this.completedTaskPayload(matched, taskId);
            if (fromTasks) {
                return fromTasks;
            }
            if (matched) {
                return null;
            }
            const historyRes = await fetch(`${base}/api/history`, {
                cache: "no-store",
            });
            const historyData = historyRes.ok
                ? ((await historyRes.json()) as {
                      history?: Array<Record<string, unknown>>;
                  })
                : { history: [] };
            const history = Array.isArray(historyData.history)
                ? historyData.history
                : [];
            for (const task of history) {
                const payload = this.completedTaskPayload(task, taskId);
                if (payload) {
                    return payload;
                }
            }
        } catch (error) {
            ztoolkit.log("读取翻译任务状态失败:", error);
        }
        return null;
    }

    static async waitForAcceptedTask(
        config: ServerConfig,
        taskId: string,
    ): Promise<{ status: string; message?: string; [key: string]: unknown }> {
        // Zotero 插件沙箱没有 AbortController / ReadableStream / EventSource，
        // 不能去拉无限的 /events。POST 已经成功开工，这里只等这个 taskId 结束。
        const deadline = Date.now() + 3 * 60 * 60 * 1000;
        while (Date.now() < deadline) {
            const payload = await this.fetchCompletedTask(config, taskId);
            if (payload) {
                if (payload.status === "error") {
                    throw new Error(payload.message || "翻译失败");
                }
                return payload;
            }
            await new Promise<void>((resolve) => setTimeout(resolve, 3000));
        }
        throw new Error("等待翻译结果超时");
    }

    static async handleResponse(
        response: any,
        item: Zotero.Item,
        config: ServerConfig,
    ) {
        ztoolkit.log("response", response);
        if (response.status !== "success") {
            ztoolkit.log(`服务器返回错误: ${response.message}`);
            return;
        }
        if (!Array.isArray(response.fileList)) {
            ztoolkit.log(`服务器返回的 fileList 不是数组`);
            return;
        }
        const fileList = response.fileList as string[];
        const outputDir =
            typeof response.outputDir === "string" ? response.outputDir : "";
        const filePaths = Array.isArray(response.filePaths)
            ? (response.filePaths as string[])
            : [];
        const errors: Error[] = [];
        let attached = 0;
        for (let i = 0; i < fileList.length; i++) {
            const fileName = fileList[i];
            const fileType = this.getFileType(fileName);
            const options = this.getPDFOptions(fileType);
            try {
                await this.fetchAndAttachPDF({
                    fileName,
                    config,
                    item,
                    options,
                    type: fileType,
                    localPath:
                        typeof filePaths[i] === "string" ? filePaths[i] : "",
                    outputDir,
                });
                attached++;
            } catch (error) {
                ztoolkit.log(`处理文件 ${fileName} 时出错:`, error);
                errors.push(
                    error instanceof Error ? error : new Error(String(error)),
                );
            }
        }
        if (attached > 0) {
            return;
        }
        if (errors.length > 0) {
            throw errors[0];
        }
    }
    // ************* PDF Utils *************
    static async blobToBase64(blob: Blob): Promise<string> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result as string);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }
    static async safeExists(path: string) {
        try {
            return await IOUtils.exists(path);
        } catch (error) {
            ztoolkit.log(`检查路径 ${path} 时出错:`, error);
            return false;
        }
    }

    static async getAttachmentItem(
        item: Zotero.Item,
    ): Promise<Zotero.Item | false> {
        let attachItem;
        if (item.isAttachment()) {
            attachItem = item;
        } else if (item.isRegularItem()) {
            const bestItem = await item.getBestAttachment(); // 最早添加的附件Item
            attachItem = bestItem;
        }
        if (!attachItem) return false;
        return attachItem;
    }

    static async validatePDFAttachment(item: Zotero.Item): Promise<string> {
        const attachItem = await this.getAttachmentItem(item); // 获取item对应的attchItem
        if (!attachItem) return "No valid attachment found";
        const filepath = attachItem.getFilePath().toString();
        if (!filepath?.endsWith(".pdf"))
            throw new Error("Please select a PDF attachment");
        const exists = await this.safeExists(filepath);
        if (!exists) throw new Error("PDF file not found");
        return filepath;
    }

    static async readPDFAsBase64(filepath: string): Promise<string> {
        const contentRaw = await IOUtils.read(filepath);
        const blob = new Blob([contentRaw], { type: "application/pdf" });
        return this.blobToBase64(blob);
    }

    static getPDFOptions(type: string): PDFOperationOptions {
        return {
            rename: this.isTrue(getPref("rename")),
            openAfterProcess: this.isTrue(getPref(`${type}-open`)),
        };
    }
    // *************** PDF文件类型管理 ***************
    // 这段逻辑应该放到server里面, 不需要在插件中
    static getFileType(fileName: string): string {
        if (fileName.indexOf("mono.pdf") != -1) {
            return PDFType.MONO;
        } else if (fileName.indexOf("dual.pdf") != -1) {
            return PDFType.DUAL;
        } else if (fileName.indexOf("mono-cut.pdf") != -1) {
            return PDFType.MONO_CUT;
        } else if (fileName.indexOf("dual-cut.pdf") != -1) {
            return PDFType.DUAL_CUT;
        } else if (fileName.indexOf("crop-compare.pdf") != -1) {
            return PDFType.CROP_COMPARE;
        } else if (fileName.indexOf("compare.pdf") != -1) {
            return PDFType.COMPARE;
        } else if (fileName.indexOf("cut.pdf") != -1) {
            return PDFType.ORIGIN_CUT;
        } else {
            return PDFType.ORIGIN;
        }
    }

    // ************* 从 Server.py 获取PDF文件 *************
    static normalizeServerUrl(serverUrl: string): string {
        return (serverUrl || "").trim().replace(/\/+$/, "");
    }

    static translatedFileUrl(serverUrl: string, fileName: string): string {
        return `${this.normalizeServerUrl(serverUrl)}/translatedFile/${encodeURIComponent(fileName)}`;
    }

    static async downloadTranslatedFile(
        fileName: string,
        config: ServerConfig,
    ): Promise<Uint8Array> {
        const url = this.translatedFileUrl(config.serverUrl, fileName);
        const response = await fetch(url, { method: "GET" });
        if (!response.ok) {
            throw new Error(`下载失败 HTTP ${response.status}: ${fileName}`);
        }
        const buffer = await response.arrayBuffer();
        if (!buffer || buffer.byteLength === 0) {
            throw new Error(`下载文件为空: ${fileName}`);
        }
        return new Uint8Array(buffer);
    }

    static async attachFromLocalPath(params: {
        localPath: string;
        fileName: string;
        item: Zotero.Item;
        config: ServerConfig;
        options: PDFOperationOptions;
        type: string;
    }): Promise<boolean> {
        const { localPath, fileName, item, config, options, type } = params;
        if (!localPath) {
            return false;
        }
        const exists = await this.safeExists(localPath);
        if (!exists) {
            return false;
        }
        const service =
            config.engine == "pdf2zh" ? config.service : config.next_service;
        await this.addAttachment({
            item,
            filePath: localPath,
            options,
            type,
            service,
        });
        ztoolkit.log(`已从本地路径添加附件: ${localPath}`);
        return true;
    }

    static async fetchAndAttachPDF(params: {
        fileName: string;
        config: ServerConfig;
        item: Zotero.Item;
        options: PDFOperationOptions;
        type: string;
        localPath?: string;
        outputDir?: string;
        retries?: number;
    }) {
        const { fileName, config, item, options, type } = params;
        const localCandidates = [
            params.localPath || "",
            params.outputDir ? PathUtils.join(params.outputDir, fileName) : "",
        ].filter((path, index, all) => path && all.indexOf(path) === index);

        for (const localPath of localCandidates) {
            try {
                const attached = await this.attachFromLocalPath({
                    localPath,
                    fileName,
                    item,
                    config,
                    options,
                    type,
                });
                if (attached) {
                    return;
                }
            } catch (error) {
                ztoolkit.log(`本地路径导入失败 ${localPath}:`, error);
            }
        }

        return this.retryOperation(
            async () => {
                const bytes = await this.downloadTranslatedFile(
                    fileName,
                    config,
                );
                const tempPath = PathUtils.join(PathUtils.tempDir, fileName);
                await IOUtils.write(tempPath, bytes);
                try {
                    const service =
                        config.engine == "pdf2zh"
                            ? config.service
                            : config.next_service;
                    await this.addAttachment({
                        item,
                        filePath: tempPath,
                        options,
                        type,
                        service,
                    });
                    ztoolkit.log(`成功添加文件: ${fileName}`);
                } finally {
                    try {
                        await IOUtils.remove(tempPath);
                    } catch (error) {
                        ztoolkit.log(`清理临时文件失败: ${tempPath}`, error);
                    }
                }
            },
            params.retries ?? this.DOWNLOAD_MAX_RETRIES,
            this.RETRY_DELAY,
        );
    }

    static async addAttachment(params: {
        item: Zotero.Item;
        filePath: string; // 文件路径(已经保存到Zotero临时文件夹)
        options: PDFOperationOptions; // PDF(rename, open)
        type: string; // PDF处理类型(用于短标题)
        service: string; // 服务(用于短标题)
    }) {
        const { item, filePath, options, type, service } = params;
        const parentItemID = this.getParentItemID(item); // 如果本身就是parent条目, 那么会返回id.item
        let targetItem = item;
        if (item.isAttachment() && parentItemID) {
            targetItem = Zotero.Items.get(parentItemID);
        }
        let newTitle = service + "-" + type;
        const shortTitle = targetItem.getField("shortTitle");
        if (shortTitle && shortTitle.length > 0) {
            newTitle = shortTitle + "-" + service + "-" + type;
        }
        const attachKey = `${parentItemID ?? "none"}::${service}::${type}`;
        if (this.currentAttachKeys.has(attachKey)) {
            ztoolkit.log(`跳过本轮重复附件: ${newTitle}`);
            return;
        }
        // parentItemID and collections cannot both be provided
        const attachment = await Zotero.Attachments.importFromFile({
            file: filePath,
            parentItemID: parentItemID == undefined ? undefined : parentItemID,
            libraryID: item.libraryID,
            collections:
                parentItemID == undefined
                    ? this.getCollections(item)
                    : undefined,
            title: options.rename ? newTitle : PathUtils.filename(filePath),
        });
        this.currentAttachKeys.add(attachKey);
        if (options.openAfterProcess && attachment?.id) {
            try {
                Zotero.Reader.open(attachment.id);
            } catch (error) {
                ztoolkit.log(
                    `附件已添加，但打开阅读器失败: ${newTitle}`,
                    error,
                );
            }
        }
    }

    // ************* Config *************
    static getServerConfig(): ServerConfig {
        return {
            serverUrl: getPref("new_serverip")?.toString() || "",

            service: getPref("service")?.toString() || "",
            next_service: getPref("next_service")?.toString() || "",
            engine: getPref("engine")?.toString() || "",

            sourceLang: getPref("sourceLang")?.toString() || "",
            targetLang: getPref("targetLang")?.toString() || "",

            skipLastPages: getPref("skipLastPages")?.toString() || "",
            threadNum: getPref("threadNum")?.toString() || "",
            qps: getPref("qps")?.toString() || "10",
            poolSize: getPref("poolSize")?.toString() || "0",

            // generate
            mono: getPref("mono")?.toString() || "",
            dual: getPref("dual")?.toString() || "",
            mono_cut: getPref("mono-cut")?.toString() || "",
            dual_cut: getPref("dual-cut")?.toString() || "",
            crop_compare: getPref("crop-compare")?.toString() || "",
            compare: getPref("compare")?.toString() || "",

            // pdf1x专用配置
            babeldoc: getPref("babeldoc")?.toString() || "",
            skipSubsetFonts: getPref("skipSubsetFonts")?.toString() || "",
            fontFile: getPref("fontFile")?.toString() || "",

            // pdf2x专用配置
            // TODO: 如果noDual和noMono同时被选择, 我们默认不选择noDual
            fontFamily: getPref("fontFamily")?.toString() || "",
            dualMode: getPref("dualMode")?.toString() || "",
            transFirst: getPref("transFirst")?.toString() || "",
            ocr: getPref("ocr")?.toString() || "",
            autoOcr: getPref("autoOcr")?.toString() || "",
            noWatermark: getPref("noWatermark")?.toString() || "",
            saveGlossary: getPref("saveGlossary")?.toString() || "",
            disableGlossary: getPref("disableGlossary")?.toString() || "",
            noDual: getPref("noDual")?.toString() || "",
            noMono: getPref("noMono")?.toString() || "",
            skipClean: getPref("skipClean")?.toString() || "",
            disableRichTextTranslate:
                getPref("disableRichTextTranslate")?.toString() || "",
            enhanceCompatibility:
                getPref("enhanceCompatibility")?.toString() || "",
            translateTableText: getPref("translateTableText")?.toString() || "",
            onlyIncludeTranslatedPage:
                getPref("onlyIncludeTranslatedPage")?.toString() || "",
        };
    }

    static getActiveLLMApiConfig(service: string): any {
        // 获取当前激活的 LLM API 配置
        loadLLMApisFromPrefs();
        if (!addon.data.llmApis?.map) {
            return null;
        }
        // 查找激活的配置
        for (const [key, llmApi] of addon.data.llmApis.map) {
            if (llmApi.activate && llmApi.service == service) {
                return {
                    service: llmApi.service,
                    model: llmApi.model,
                    apiKey: llmApi.apiKey,
                    apiUrl: llmApi.apiUrl,
                    extraData: llmApi.extraData || {},
                };
            }
        }
        return null;
    }

    // **************** Utils ****************
    static isTrue(value: string | number | boolean | undefined): boolean {
        if (value == undefined) return false;
        return (
            value == true ||
            value == "true" ||
            value == "1" ||
            value == "True" ||
            value == "TRUE" ||
            value == 1
        );
    }

    // 重试机制
    static async retryOperation<T>(
        operation: () => Promise<T>,
        maxRetries: number = this.MAX_RETRIES,
        delay: number = this.RETRY_DELAY,
    ): Promise<T> {
        let lastError: Error;
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                return await operation();
            } catch (error) {
                lastError =
                    error instanceof Error ? error : new Error(String(error));
                if (attempt === maxRetries) {
                    throw lastError;
                }
                ztoolkit.log(
                    `操作失败，第 ${attempt} 次重试 (共 ${maxRetries} 次): ${lastError.message}`,
                );
                await new Promise((resolve) =>
                    setTimeout(resolve, delay * attempt),
                );
            }
        }
        throw lastError!;
    }

    // 获取item的 partent itemID
    static getParentItemID(item: Zotero.Item): number | undefined {
        let ID;
        if (item.isAttachment()) {
            const parentItemID = item.parentItemID;
            ID =
                parentItemID != null && parentItemID !== false
                    ? parentItemID
                    : undefined;
        } else {
            ID = item.id;
        }
        return ID;
    }

    // 获取item对应的分类(collections)
    static getCollections(item: Zotero.Item): number[] | undefined {
        const collections = item.getCollections();
        return collections.length > 0 ? [collections[0]] : undefined;
    }
}
