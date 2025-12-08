import { PDF2zhHelperFactory } from "./pdf2zhHelper";
import { ServerConfig } from "./pdf2zhTypes";

export class FileProcessor {
    private static instance: FileProcessor;
    private eventListeners: Array<(event: string, data: any) => void> = [];

    static getInstance(): FileProcessor {
        if (!FileProcessor.instance) {
            FileProcessor.instance = new FileProcessor();
        }
        return FileProcessor.instance;
    }
    addEventListener(listener: (event: string, data: any) => void) {
        this.eventListeners.push(listener);
    }

    private emit(event: string, data: any) {
        this.eventListeners.forEach((listener) => {
            try {
                listener(event, data);
            } catch (error) {
                ztoolkit.log(`事件监听器错误:`, error);
            }
        });
    }

    // 批量处理文件
    async processBatch(
        tasks: Array<{
            fileName: string;
            item: Zotero.Item;
            config: ServerConfig;
            endpoint: string;
        }>,
    ): Promise<void> {
        this.emit("batchStarted", { totalTasks: tasks.length }); // 触发批量开始事件
        let succeeded = 0;
        let failed = 0;
        let currentTaskIndex = 0;

        for (const task of tasks) {
            currentTaskIndex++;
            const currentFileName = task.fileName;

            // 创建进度回调
            const onProgress = (progress: number, message?: string) => {
                this.emit("taskProgress", {
                    taskIndex: currentTaskIndex,
                    totalTasks: tasks.length,
                    fileName: currentFileName,
                    progress,
                    message: message || `处理中: ${progress}%`,
                });
            };

            try {
                // 发送任务开始事件
                this.emit("taskStarted", {
                    taskIndex: currentTaskIndex,
                    totalTasks: tasks.length,
                    fileName: currentFileName,
                });

                await PDF2zhHelperFactory.processSingleFile({
                    ...task,
                    onProgress,
                });
                succeeded++;

                this.emit("taskCompleted", {
                    taskIndex: currentTaskIndex,
                    totalTasks: tasks.length,
                    fileName: currentFileName,
                    success: true,
                });
            } catch (error) {
                failed++;
                this.emit("taskCompleted", {
                    taskIndex: currentTaskIndex,
                    totalTasks: tasks.length,
                    fileName: currentFileName,
                    success: false,
                    error: error instanceof Error ? error.message : String(error),
                });
            }
        }
        this.emit("batchCompleted", {
            total: tasks.length,
            succeeded,
            failed,
        });
    }
}
