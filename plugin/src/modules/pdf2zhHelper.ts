import { getPref } from "../utils/prefs";
import { getString } from "../utils/locale";
import { version as pluginVersion } from "../../package.json";
import { FileProcessor } from "./pdf2zhFileProcessor";
import {
    taskFinishedWithoutFiles,
    validatePDFBytes,
} from "./pdf2zhAttachmentUtils";
import {
    ServerConfig,
    PDFType,
    PDFOperationOptions,
    JobProgressUpdate,
} from "./pdf2zhTypes";
import { loadLLMApisFromPrefs } from "./preferenceScript";

export class PDF2zhHelperFactory {
    // 翻译请求本身不要重试，避免同一篇 PDF 被重复翻译。
    private static readonly MAX_RETRIES = 1;
    private static readonly RETRY_DELAY = 2000; // 2秒
    // 下载/补拉附件可以多试几次：文件往往已经在 translated 目录里了。
    private static readonly DOWNLOAD_MAX_RETRIES = 3;
    // Server may report completion before its file metadata is visible to the
    // polling endpoint. Allow a short grace period, never the full job timeout.
    private static readonly COMPLETED_FILE_GRACE_MS = 20_000;

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

        const progress = JobProgressPopup.open(
            tasks.map((task) => task.fileName),
        );
        const fileProcessor = FileProcessor.getInstance();
        try {
            const result = await fileProcessor.processBatch(tasks, (update) => {
                progress.updateFile(update);
            });
            progress.complete(result.succeeded, result.failed);
        } catch (error) {
            progress.complete(0, tasks.length);
            throw error;
        }
    }

    static operationActionLabel(endpoint: string): string {
        if (endpoint === "crop") {
            return getString("operation-action-crop");
        }
        if (endpoint === "compare") {
            return getString("operation-action-compare");
        }
        if (endpoint === "crop-compare") {
            return getString("operation-action-crop-compare");
        }
        return getString("operation-action-translate");
    }

    static formatJobProgressText(update: JobProgressUpdate): string {
        const action = this.operationActionLabel(update.endpoint);
        let text = "";
        switch (update.phase) {
            case "submitting":
                text = getString("operation-progress-submitting", {
                    args: { fileName: update.fileName },
                });
                break;
            case "accepted":
                text = getString("operation-progress-accepted", {
                    args: { fileName: update.fileName, action },
                });
                break;
            case "running": {
                const parts: string[] = [];
                if (
                    typeof update.percent === "number" &&
                    Number.isFinite(update.percent) &&
                    update.percent > 0
                ) {
                    parts.push(`${Math.round(update.percent)}%`);
                }
                if (update.detail) {
                    parts.push(update.detail);
                }
                text = getString("operation-progress-running", {
                    args: {
                        fileName: update.fileName,
                        action,
                        suffix: parts.length ? ` · ${parts.join(" · ")}` : "",
                    },
                });
                break;
            }
            case "importing":
                text = getString("operation-progress-importing", {
                    args: { fileName: update.fileName },
                });
                break;
            case "file-done":
                text = getString("operation-progress-file-done", {
                    args: { fileName: update.fileName },
                });
                break;
            case "file-failed":
                text = getString("operation-progress-file-failed", {
                    args: {
                        fileName: update.fileName,
                        message: this.shortProgressError(
                            update.error ||
                                getString("operation-error-unknown"),
                        ),
                    },
                });
                break;
        }
        return text;
    }

    static shortProgressError(message: string): string {
        const compact = message.replace(/\s+/g, " ").trim();
        if (compact.length <= 80) {
            return compact;
        }
        return `${compact.slice(0, 77)}...`;
    }

    static jobProgressPercent(update: JobProgressUpdate): number {
        const fileFraction = (() => {
            if (update.phase === "submitting") {
                return 0.05;
            }
            if (update.phase === "accepted") {
                return 0.12;
            }
            if (update.phase === "running") {
                const raw =
                    typeof update.percent === "number" &&
                    Number.isFinite(update.percent)
                        ? Math.min(Math.max(update.percent, 0), 100)
                        : 0;
                return 0.12 + (raw / 100) * 0.73;
            }
            if (update.phase === "importing") {
                return 0.9;
            }
            return 1;
        })();
        return Math.round(
            ((update.current - 1 + fileFraction) / update.total) * 100,
        );
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
    static async processSingleFile(
        params: {
            fileName: string; // 文件名
            item: Zotero.Item; // item
            config: ServerConfig; // serverConfig
            endpoint: string; // 请求类型
        },
        onProgress?: (
            update: Omit<JobProgressUpdate, "current" | "total">,
        ) => void,
    ) {
        const { fileName, item, config, endpoint } = params; // config
        ztoolkit.log(
            `Processing Single File: ${fileName}, ServerConfig: ${config}`,
        );
        try {
            onProgress?.({ phase: "submitting", fileName, endpoint });
            const fileData = await this.prepareFileData(item);
            const response = await this.sendRequest(
                fileData,
                config,
                endpoint,
                onProgress,
            );
            onProgress?.({ phase: "importing", fileName, endpoint });
            await this.handleResponse(response, item, config);
            onProgress?.({ phase: "file-done", fileName, endpoint });
        } catch (error) {
            ztoolkit.log(`处理单个文件失败: ${fileName}, 错误: ${error}`);
            const message =
                error instanceof Error
                    ? error.message
                    : getString("operation-error-unknown");
            onProgress?.({
                phase: "file-failed",
                fileName,
                endpoint,
                error: message,
            });
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
        onProgress?: (
            update: Omit<JobProgressUpdate, "current" | "total">,
        ) => void,
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
                // 新协议：Server 立刻返回 accepted + taskId，插件再轮询。
                // 没带这个标记的旧插件（含 DCC 4.0.3）会走 Server 同步返回 fileList。
                asyncJob: true,
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
                headers: {
                    "Content-Type": "application/json",
                    "X-PDF2zh-Protocol": "accepted",
                    "X-PDF2zh-Plugin-Version": pluginVersion,
                },
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
            if (
                !response.ok ||
                result.status === "error" ||
                result.status === "failed"
            ) {
                ztoolkit.log(`response`, response, result);
                throw new Error(result.message || "服务器返回错误");
            }
            const taskId = this.taskIdFromPayload(result);
            if (
                result.status === "accepted" ||
                (taskId && result.status !== "success")
            ) {
                if (!taskId) {
                    throw new Error("服务器已接收任务，但没有返回 taskId");
                }
                onProgress?.({
                    phase: "accepted",
                    fileName: fileData.fileName,
                    endpoint,
                });
                return this.waitForAcceptedTask(config, taskId, (running) => {
                    onProgress?.({
                        phase: "running",
                        fileName: fileData.fileName,
                        endpoint,
                        percent: running.percent,
                        detail: running.message,
                    });
                });
            }
            return result;
        });
    }

    static parseServerPayload(text: string): {
        status?: string;
        message?: string;
        taskId?: string;
        task_id?: string;
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
            task_id?: string;
            [key: string]: unknown;
        };
    }

    static taskIdFromPayload(payload: {
        taskId?: unknown;
        task_id?: unknown;
    }): string {
        const raw = payload.taskId ?? payload.task_id ?? "";
        return typeof raw === "string" || typeof raw === "number"
            ? String(raw).trim()
            : "";
    }

    static stringList(value: unknown): string[] {
        if (!Array.isArray(value)) {
            return [];
        }
        return value.filter(
            (item): item is string =>
                typeof item === "string" && item.length > 0,
        );
    }

    static completedTaskPayload(
        task: Record<string, unknown> | undefined,
        taskId: string,
    ): { status: string; message?: string; [key: string]: unknown } | null {
        if (!task || Array.isArray(task.tasks) || Array.isArray(task.history)) {
            return null;
        }
        const id = this.taskIdFromPayload(task);
        if (!id || id !== taskId) {
            return null;
        }
        const nested =
            task.result && typeof task.result === "object"
                ? (task.result as Record<string, unknown>)
                : null;
        const status = String(task.status || nested?.status || "");
        const failed =
            status === "失败" ||
            status === "failed" ||
            nested?.status === "error" ||
            (task.finished === true &&
                status !== "完成" &&
                status !== "success");
        if (failed) {
            return {
                status: "error",
                message: String(
                    nested?.message || task.error || task.message || "翻译失败",
                ),
            };
        }
        const files = this.stringList(nested?.fileList ?? task.fileList);
        const paths = this.stringList(nested?.filePaths ?? task.filePaths);
        const succeeded =
            (task.finished === true ||
                status === "完成" ||
                status === "success" ||
                nested?.status === "success") &&
            (files.length > 0 || paths.length > 0);
        if (!succeeded) {
            return null;
        }
        if (nested && nested.status === "success" && files.length > 0) {
            return nested as { status: string; message?: string };
        }
        return {
            status: "success",
            fileList: files,
            filePaths: paths,
            outputDir: String(nested?.outputDir || task.outputDir || ""),
        };
    }

    static taskFinishedWithoutFiles(
        task: Record<string, unknown> | undefined,
        taskId: string,
    ): boolean {
        return taskFinishedWithoutFiles(task, taskId);
    }

    static async fetchTaskRecord(
        config: ServerConfig,
        taskId: string,
    ): Promise<Record<string, unknown> | undefined> {
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
                (task) => this.taskIdFromPayload(task) === taskId,
            );
            if (matched) {
                return matched;
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
            return history.find(
                (task) => this.taskIdFromPayload(task) === taskId,
            );
        } catch (error) {
            ztoolkit.log("读取翻译任务状态失败:", error);
            return undefined;
        }
    }

    static async fetchCompletedTask(
        config: ServerConfig,
        taskId: string,
    ): Promise<{
        status: string;
        message?: string;
        [key: string]: unknown;
    } | null> {
        const task = await this.fetchTaskRecord(config, taskId);
        return this.completedTaskPayload(task, taskId);
    }

    static async waitForAcceptedTask(
        config: ServerConfig,
        taskId: string,
        onRunning?: (info: { percent: number; message: string }) => void,
    ): Promise<{ status: string; message?: string; [key: string]: unknown }> {
        // Zotero 插件沙箱没有 AbortController / ReadableStream / EventSource，
        // 不能去拉无限的 /events。POST 已经成功开工，这里只等这个 taskId 结束。
        const deadline = Date.now() + 3 * 60 * 60 * 1000;
        let completedWithoutFilesSince: number | null = null;
        while (Date.now() < deadline) {
            const task = await this.fetchTaskRecord(config, taskId);
            const payload = this.completedTaskPayload(task, taskId);
            if (payload) {
                if (payload.status === "error") {
                    throw new Error(payload.message || "翻译失败");
                }
                const files = this.stringList(payload.fileList);
                ztoolkit.log(
                    `任务 ${taskId} 已完成，准备导入 ${files.length} 个文件`,
                );
                return payload;
            }
            if (this.taskFinishedWithoutFiles(task, taskId)) {
                completedWithoutFilesSince ??= Date.now();
                if (
                    Date.now() - completedWithoutFilesSince >=
                    this.COMPLETED_FILE_GRACE_MS
                ) {
                    throw new Error(
                        getString("operation-error-completed-no-files"),
                    );
                }
                ztoolkit.log(
                    `任务 ${taskId} 标记完成但还没有文件，等待 Server 落盘`,
                );
            } else {
                completedWithoutFilesSince = null;
            }
            if (task && task.finished !== true) {
                const raw = Number(task.progress);
                onRunning?.({
                    percent: Number.isFinite(raw) ? raw : 0,
                    message: String(task.message || task.status || ""),
                });
            }
            await Zotero.Promise.delay(1000);
        }
        throw new Error("等待翻译结果超时");
    }

    static async handleResponse(
        response: any,
        item: Zotero.Item,
        config: ServerConfig,
    ) {
        ztoolkit.log("response", response);
        if (response.status === "accepted") {
            throw new Error("任务仍在处理中，尚未完成");
        }
        if (response.status !== "success") {
            ztoolkit.log(`服务器返回错误: ${response.message}`);
            throw new Error(String(response.message || "服务器返回错误"));
        }
        if (!Array.isArray(response.fileList)) {
            ztoolkit.log(`服务器返回的 fileList 不是数组`);
            throw new Error(getString("operation-error-no-files"));
        }
        const fileList = response.fileList as string[];
        const outputDir =
            typeof response.outputDir === "string" ? response.outputDir : "";
        const filePaths = Array.isArray(response.filePaths)
            ? (response.filePaths as string[])
            : [];
        const errors: Error[] = [];
        let attached = 0;
        const attachKeys = new Set<string>();
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
                    attachKeys,
                });
                attached++;
            } catch (error) {
                ztoolkit.log(`处理文件 ${fileName} 时出错:`, error);
                errors.push(
                    error instanceof Error ? error : new Error(String(error)),
                );
            }
        }
        if (errors.length > 0) {
            throw new Error(
                getString("operation-error-partial-attachments", {
                    args: {
                        attached,
                        total: fileList.length,
                        message: errors
                            .map((error) => error.message)
                            .join("; "),
                    },
                }),
            );
        }
        if (attached > 0) {
            return;
        }
        throw new Error(getString("operation-error-no-files"));
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
        const bytes = new Uint8Array(buffer);
        validatePDFBytes(bytes, fileName);
        return bytes;
    }

    static storageLeafName(fileName: string): string {
        const leaf = String(fileName || "")
            .replace(/^.*[/\\]/, "")
            .trim();
        return leaf || "translated.pdf";
    }

    static storageFileBaseName(fileName: string): string {
        const leaf = this.storageLeafName(fileName);
        return leaf.replace(/\.pdf$/i, "") || leaf;
    }

    static safeStorageLeafName(fileName: string): string {
        const leaf = this.storageLeafName(fileName);
        // Preserve the translated filename structure and semantic suffixes;
        // only cross-platform-invalid characters are normalized by Zotero.
        return Zotero.File.getValidFileName(leaf) || "translated.pdf";
    }

    static async writeTempPdf(bytes: Uint8Array): Promise<string> {
        // Keep the temp leaf ASCII-only. PathUtils.join/filename reject some
        // Docker paths and unicode names (e.g. "Shi 等 - test.pdf") with
        // NS_ERROR_FILE_UNRECOGNIZED_PATH on Windows. importFromFile later
        // copies this file into storage/ using fileBaseName, so the temp
        // name is only a transfer vehicle.
        const tempName = `pdf2zh-${Date.now()}-${Math.random()
            .toString(36)
            .slice(2, 10)}.pdf`;
        const tempPath = PathUtils.join(PathUtils.tempDir, tempName);
        await IOUtils.write(tempPath, bytes);
        return tempPath;
    }

    static localPathCandidates(
        fileName: string,
        localPath?: string,
        outputDir?: string,
    ): string[] {
        const candidates = [localPath || ""];
        if (outputDir) {
            try {
                candidates.push(PathUtils.join(outputDir, fileName));
            } catch (error) {
                ztoolkit.log(
                    `拼接本地输出路径失败: ${outputDir} / ${fileName}`,
                    error,
                );
            }
        }
        return candidates.filter(
            (path, index, all) => path && all.indexOf(path) === index,
        );
    }

    static async attachFromLocalPath(params: {
        localPath: string;
        fileName: string;
        item: Zotero.Item;
        config: ServerConfig;
        options: PDFOperationOptions;
        type: string;
        attachKeys: Set<string>;
    }): Promise<boolean> {
        const { localPath, fileName, item, config, options, type, attachKeys } =
            params;
        if (!localPath) {
            return false;
        }
        const exists = await this.safeExists(localPath);
        if (!exists) {
            return false;
        }
        const service =
            config.engine == "pdf2zh" ? config.service : config.next_service;
        const bytes = await IOUtils.read(localPath);
        const tempPath = await this.writeTempPdf(bytes);
        try {
            const attached = await this.addAttachment({
                item,
                filePath: tempPath,
                fileName,
                options,
                type,
                service,
                attachKeys,
            });
            if (attached) {
                ztoolkit.log(`已从本地路径添加附件: ${localPath}`);
            }
            return attached;
        } finally {
            try {
                await IOUtils.remove(tempPath);
            } catch (error) {
                ztoolkit.log(`清理临时文件失败: ${tempPath}`, error);
            }
        }
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
        attachKeys: Set<string>;
    }) {
        const { fileName, config, item, options, type } = params;
        const service =
            config.engine == "pdf2zh" ? config.service : config.next_service;
        let httpError: unknown;
        try {
            await this.retryOperation(
                async () => {
                    const bytes = await this.downloadTranslatedFile(
                        fileName,
                        config,
                    );
                    const tempPath = await this.writeTempPdf(bytes);
                    try {
                        const attached = await this.addAttachment({
                            item,
                            filePath: tempPath,
                            fileName,
                            options,
                            type,
                            service,
                            attachKeys: params.attachKeys,
                        });
                        if (!attached) {
                            throw new Error(`未能添加附件: ${fileName}`);
                        }
                        ztoolkit.log(`已通过 HTTP 添加文件: ${fileName}`);
                    } finally {
                        try {
                            await IOUtils.remove(tempPath);
                        } catch (error) {
                            ztoolkit.log(
                                `清理临时文件失败: ${tempPath}`,
                                error,
                            );
                        }
                    }
                },
                params.retries ?? this.DOWNLOAD_MAX_RETRIES,
                this.RETRY_DELAY,
            );
            return;
        } catch (error) {
            httpError = error;
            ztoolkit.log(`HTTP 下载附件失败 ${fileName}，尝试本机路径:`, error);
        }

        for (const localPath of this.localPathCandidates(
            fileName,
            params.localPath,
            params.outputDir,
        )) {
            try {
                const attached = await this.attachFromLocalPath({
                    localPath,
                    fileName,
                    item,
                    config,
                    options,
                    type,
                    attachKeys: params.attachKeys,
                });
                if (attached) {
                    return;
                }
            } catch (error) {
                ztoolkit.log(`本地路径导入失败 ${localPath}:`, error);
            }
        }

        throw httpError instanceof Error
            ? httpError
            : new Error(`无法导入文件: ${fileName}`);
    }

    static async addAttachment(params: {
        item: Zotero.Item;
        filePath: string; // 文件路径(已经保存到Zotero临时文件夹)
        fileName: string;
        options: PDFOperationOptions; // PDF(rename, open)
        type: string; // PDF处理类型(用于短标题)
        service: string; // 服务(用于短标题)
        attachKeys: Set<string>;
    }): Promise<boolean> {
        const { item, filePath, fileName, options, type, service, attachKeys } =
            params;
        const parentItemID = this.getParentItemID(item); // 如果本身就是parent条目, 那么会返回id.item
        let targetItem = item;
        if (item.isAttachment() && parentItemID) {
            targetItem = Zotero.Items.get(parentItemID);
        }
        // Server filenames may be valid on Linux/Docker but invalid on the
        // Zotero host (notably Windows). Sanitize using Zotero's own rules
        // before using the name in storage or as the attachment title.
        const leafName = this.safeStorageLeafName(fileName);
        let newTitle = service + "-" + type;
        const shortTitle = targetItem.getField("shortTitle");
        if (shortTitle && shortTitle.length > 0) {
            newTitle = shortTitle + "-" + service + "-" + type;
        }
        const attachKey = `${parentItemID ?? "none"}::${service}::${type}::${leafName}`;
        if (attachKeys.has(attachKey)) {
            ztoolkit.log(`跳过本轮重复附件: ${newTitle}`);
            return true;
        }
        // parentItemID and collections cannot both be provided.
        // fileBaseName is the storage leaf without extension; title is only
        // the Zotero item display name. The storage name keeps translated/'s
        // naming format after cross-platform-invalid characters are normalized.
        const attachment = await Zotero.Attachments.importFromFile({
            file: filePath,
            parentItemID: parentItemID == undefined ? undefined : parentItemID,
            libraryID: item.libraryID,
            collections:
                parentItemID == undefined
                    ? this.getCollections(item)
                    : undefined,
            fileBaseName: this.storageFileBaseName(leafName),
            title: options.rename ? newTitle : leafName,
        });
        if (!attachment?.id) {
            ztoolkit.log(`importFromFile 未返回附件: ${newTitle}`);
            return false;
        }
        attachKeys.add(attachKey);
        if (options.openAfterProcess) {
            try {
                Zotero.Reader.open(attachment.id);
            } catch (error) {
                ztoolkit.log(
                    `附件已添加，但打开阅读器失败: ${newTitle}`,
                    error,
                );
            }
        }
        return true;
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

class JobProgressPopup {
    private static shared: {
        window: any;
        lineCount: number;
        batches: number;
        closeToken: number;
    } | null = null;

    private window: any;
    private summaryIdx: number;
    private fileIdx: number[];
    private total: number;
    private done = 0;
    private finishedFiles = new Set<number>();
    private enabled: boolean;

    static shouldShow(): boolean {
        const raw = getPref("showProgress");
        if (raw === undefined || raw === null || raw === "") {
            return true;
        }
        return PDF2zhHelperFactory.isTrue(raw);
    }

    static open(fileNames: string[]): JobProgressPopup {
        return new JobProgressPopup(fileNames);
    }

    private constructor(fileNames: string[]) {
        this.enabled = JobProgressPopup.shouldShow();
        this.total = fileNames.length;
        this.fileIdx = [];
        this.summaryIdx = 0;
        if (!this.enabled) {
            this.window = null;
            return;
        }
        const firstOpen = !JobProgressPopup.shared?.window;
        const shared = JobProgressPopup.ensureWindow();
        this.window = shared.window;
        shared.batches += 1;
        shared.closeToken += 1;
        this.summaryIdx = shared.lineCount;
        this.createLine({
            text: getString("operation-batch-started", {
                args: { count: this.total },
            }),
            type: "default",
            progress: 0,
        });
        this.fileIdx = fileNames.map((fileName) => {
            const idx = shared.lineCount;
            this.createLine({
                text: getString("operation-progress-waiting", {
                    args: { fileName },
                }),
                type: "default",
                progress: 0,
            });
            return idx;
        });
        if (firstOpen) {
            try {
                this.window.show();
            } catch (error) {
                ztoolkit.log("显示进度窗口失败:", error);
            }
        }
    }

    private static ensureWindow() {
        if (!JobProgressPopup.shared?.window) {
            const window = new ztoolkit.ProgressWindow(
                getString("operation-progress-title"),
                {
                    closeOnClick: false,
                    closeTime: -1,
                    closeOtherProgressWindows: false,
                },
            );
            JobProgressPopup.shared = {
                window,
                lineCount: 0,
                batches: 0,
                closeToken: 0,
            };
        }
        return JobProgressPopup.shared;
    }

    private createLine(line: { text: string; type: string; progress: number }) {
        if (!this.window || !JobProgressPopup.shared) {
            return;
        }
        this.window.createLine(line);
        JobProgressPopup.shared.lineCount += 1;
    }

    private changeLine(
        idx: number,
        line: { text: string; type: string; progress: number },
    ) {
        if (!this.window) {
            return;
        }
        try {
            this.window.changeLine({ idx, ...line });
            this.window.show();
        } catch (error) {
            ztoolkit.log("更新进度窗口失败:", error);
        }
    }

    updateFile(update: JobProgressUpdate) {
        if (!this.enabled) {
            return;
        }
        const idx = this.fileIdx[update.current - 1];
        if (idx === undefined) {
            return;
        }
        const fileProgress = PDF2zhHelperFactory.jobProgressPercent({
            ...update,
            current: 1,
            total: 1,
        });
        this.changeLine(idx, {
            text: PDF2zhHelperFactory.formatJobProgressText(update),
            type:
                update.phase === "file-failed"
                    ? "error"
                    : update.phase === "file-done"
                      ? "success"
                      : "default",
            progress: fileProgress,
        });
        if (update.phase === "file-done" || update.phase === "file-failed") {
            if (!this.finishedFiles.has(update.current)) {
                this.finishedFiles.add(update.current);
                this.done = Math.min(this.total, this.done + 1);
            }
        }
        const overall = Math.min(
            99,
            Math.round(
                ((this.done +
                    (this.finishedFiles.has(update.current)
                        ? 0
                        : fileProgress / 100)) /
                    this.total) *
                    100,
            ),
        );
        const percentText =
            update.phase === "running" &&
            typeof update.percent === "number" &&
            update.percent > 0
                ? ` · ${Math.round(update.percent)}%`
                : "";
        this.changeLine(this.summaryIdx, {
            text:
                getString("operation-progress-summary", {
                    args: { done: this.done, total: this.total },
                }) + percentText,
            type: "default",
            progress: overall,
        });
    }

    complete(succeeded: number, failed: number) {
        if (!this.enabled) {
            return;
        }
        this.changeLine(this.summaryIdx, {
            text: getString("operation-batch-completed", {
                args: {
                    succeeded,
                    failed,
                    kind:
                        failed > 0 && succeeded === 0
                            ? "failed"
                            : failed > 0
                              ? "mixed"
                              : "success",
                },
            }),
            type:
                failed > 0 && succeeded === 0
                    ? "error"
                    : failed > 0
                      ? "default"
                      : "success",
            progress: 100,
        });
        const shared = JobProgressPopup.shared;
        if (!shared) {
            return;
        }
        shared.batches = Math.max(0, shared.batches - 1);
        if (shared.batches > 0) {
            return;
        }
        const token = ++shared.closeToken;
        Zotero.Promise.delay(8000).then(() => {
            if (
                !JobProgressPopup.shared ||
                JobProgressPopup.shared.closeToken !== token ||
                JobProgressPopup.shared.batches > 0
            ) {
                return;
            }
            try {
                JobProgressPopup.shared.window?.close();
            } catch (error) {
                ztoolkit.log("关闭进度窗口失败:", error);
            }
            JobProgressPopup.shared = null;
        });
    }
}
