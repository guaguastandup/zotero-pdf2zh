import { getPref } from "../utils/prefs";
import axios from "axios";
import { FileProcessor } from "./pdf2zhFileProcessor";
import { ServerConfig, PDFType, PDFOperationOptions } from "./pdf2zhTypes";
import { loadLLMApisFromPrefs } from "./preferenceScript";

export class PDF2zhHelperFactory {
    // 添加重试配置(其实不需要重试)
    private static readonly MAX_RETRIES = 1;
    private static readonly RETRY_DELAY = 2000; // 2秒

    // **** 由hooks.ts调用, main entries *****
    static async processWorker(
        endpoint: string, // 仅包含请求类型
    ) {
        const pane = ztoolkit.getGlobal("ZoteroPane");
        const selectedItems = pane.getSelectedItems();
        if (selectedItems.length == 0) {
            ztoolkit.getGlobal("alert")("请先选择一个条目或附件。");
            return;
        }
        // 新增了显示处理进度窗口
        const progressWindow = new ztoolkit.ProgressWindow(
            "PDF处理",
        ).createLine({
            text: "正在处理PDF文件...",
            type: "default",
            progress: 0,
        });
        progressWindow.show();

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
                const config = this.getServerConfig();
                tasks.push({
                    fileName,
                    item,
                    config,
                    endpoint,
                });
            } catch (error) {
                const message =
                    error instanceof Error ? error.message : "未知错误";
                ztoolkit.getGlobal("alert")(`错误: ${message}`);
            }
        }
        const fileProcessor = FileProcessor.getInstance();
        fileProcessor.addEventListener((event, data) => {
            switch (event) {
                case "batchStarted":
                    progressWindow.changeLine({
                        text: `开始处理 ${data.totalTasks} 个文件...`,
                        type: "default",
                        progress: 0,
                    });
                    break;
                case "batchCompleted":
                    progressWindow.changeLine({
                        text: `处理完成！成功: ${data.succeeded}, 失败: ${data.failed}`,
                        type: data.failed > 0 ? "error" : "success",
                        progress: 100,
                    });
                    break;
            }
        });
        // 处理任务
        await fileProcessor.processBatch(tasks);
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
        try {
            const fileData = await this.prepareFileData(item);
            const response = await this.sendRequest(fileData, config, endpoint);
            await this.handleResponse(response, item, config);
        } catch (error) {
            ztoolkit.log(`处理单个文件失败: ${fileName}, 错误: ${error}`);
            ztoolkit.getGlobal("alert")(
                `处理单个文件失败: ${fileName}\n错误信息: ${error}`,
            );
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
                ztoolkit.log("llmApiConfig", llmApiConfig);
            }

            // 第一步：发送翻译请求，获取任务ID
            const response = await fetch(`${config.serverUrl}/${endpoint}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
            });

            if (!response.ok) {
                ztoolkit.log(`response`, response);
                const result = (await response.json()) as unknown as {
                    status: string;
                    message?: string;
                };
                if (result.status === "error") {
                    throw new Error(result.message || "服务器返回错误");
                }
            }

            const initialResult = (await response.json()) as unknown as {
                status: string;
                task_id?: string;
                message?: string;
            };

            if (initialResult.status === "error") {
                throw new Error(initialResult.message || "服务器返回错误");
            }

            // 如果返回了task_id，说明是异步任务，需要轮询状态
            if (initialResult.task_id) {
                ztoolkit.log(`任务已创建，任务ID: ${initialResult.task_id}`);
                return await this.pollTaskStatus(config.serverUrl, initialResult.task_id);
            }

            // 否则是同步返回的结果（向后兼容旧的端点）
            return initialResult;
        });
    }

    // 轮询任务状态
    static async pollTaskStatus(serverUrl: string, taskId: string, maxAttempts: number = 600) {
        const pollInterval = 2000; // 每2秒轮询一次

        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            await new Promise(resolve => setTimeout(resolve, pollInterval));

            try {
                const statusResponse = await fetch(`${serverUrl}/task/${taskId}`, {
                    method: "GET",
                    headers: { "Content-Type": "application/json" },
                });

                if (!statusResponse.ok) {
                    throw new Error(`查询任务状态失败: ${statusResponse.statusText}`);
                }

                const taskStatus = (await statusResponse.json()) as {
                    status: string;
                    result?: any;
                    error?: string;
                    progress?: number;
                };

                ztoolkit.log(`任务状态: ${taskStatus.status}, 进度: ${taskStatus.progress}%`);

                // 任务完成
                if (taskStatus.status === "completed") {
                    ztoolkit.log(`任务完成:`, taskStatus.result);
                    return {
                        status: "success",
                        ...taskStatus.result
                    };
                }

                // 任务失败
                if (taskStatus.status === "failed") {
                    throw new Error(taskStatus.error || "任务处理失败");
                }

                // 继续轮询 (pending 或 processing 状态)
            } catch (error) {
                ztoolkit.log(`轮询任务状态时出错:`, error);
                throw error;
            }
        }

        throw new Error("任务超时，请稍后重试");
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
        const fileList = response.fileList;
        for (const file of fileList) {
            // const fileName = file.fileName; // 'translated/pdf1x/xxx-dual.pdf'
            // const fileType = file.type;
            const fileType = this.getFileType(file);
            const options = this.getPDFOptions(fileType);
            // 指定file的类型为string
            const fileName = file;
            try {
                await this.fetchAndAttachPDF({
                    fileName,
                    config,
                    item,
                    options,
                    type: fileType,
                });
            } catch (error) {
                ztoolkit.log(`处理文件 ${fileName} 时出错:`, error);
                throw error;
            }
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
    // 检查文件是否已存在
    static async checkFileExists(
        fileName: string,
        config: ServerConfig,
    ): Promise<boolean> {
        try {
            const response = await axios.head(
                `${config.serverUrl}/translatedFile/${fileName}`,
                { timeout: 5000 },
            );
            return response.status === 200;
        } catch (error) {
            return false;
        }
    }

    static async fetchAndAttachPDF(params: {
        // 从服务器获取文件附件
        fileName: string; // TODO: 文件名由Server端提供
        config: ServerConfig;
        item: Zotero.Item;
        options: PDFOperationOptions;
        type: string;
    }) {
        const { fileName, config, item, options, type } = params;
        return this.retryOperation(async () => {
            // 检查文件是否存在
            const fileExists = await this.checkFileExists(fileName, config);
            if (!fileExists) {
                throw new Error(`文件 ${fileName} 在服务器上不存在`);
            }
            const response = await axios.get(
                `${config.serverUrl}/translatedFile/${fileName}`,
                {
                    responseType: "arraybuffer",
                    timeout: 360000, // 6分钟
                },
            );

            const tempPath = PathUtils.join(PathUtils.tempDir, fileName);
            await IOUtils.write(tempPath, new Uint8Array(response.data));
            let service;
            if (config.engine == "pdf2zh") {
                service = config.service;
            } else {
                service = config.next_service;
            }
            await this.addAttachment({
                item,
                filePath: tempPath,
                options: options,
                type: type,
                service: service,
            });
            // 清理临时文件
            await IOUtils.remove(tempPath);
            ztoolkit.log(`成功添加文件: ${fileName}`);
        });
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
        if (options.openAfterProcess && attachment?.id) {
            Zotero.Reader.open(attachment.id);
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
