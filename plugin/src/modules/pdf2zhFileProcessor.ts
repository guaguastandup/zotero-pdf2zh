import { PDF2zhHelperFactory } from "./pdf2zhHelper";
import { JobProgressUpdate, ServerConfig } from "./pdf2zhTypes";

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
        return () => {
            this.eventListeners = this.eventListeners.filter(
                (candidate) => candidate !== listener,
            );
        };
    }

    private emit(event: string, data: any) {
        [...this.eventListeners].forEach((listener) => {
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
        onProgress?: (update: JobProgressUpdate) => void,
    ): Promise<{ total: number; succeeded: number; failed: number }> {
        this.emit("batchStarted", { totalTasks: tasks.length });
        let succeeded = 0;
        let failed = 0;
        for (let index = 0; index < tasks.length; index++) {
            const task = tasks[index];
            const report = (
                update: Omit<JobProgressUpdate, "current" | "total">,
            ) => {
                onProgress?.({
                    ...update,
                    current: index + 1,
                    total: tasks.length,
                });
            };
            try {
                await PDF2zhHelperFactory.processSingleFile(task, report);
                succeeded++;
            } catch {
                failed++;
            }
        }
        this.emit("batchCompleted", {
            total: tasks.length,
            succeeded,
            failed,
        });
        return { total: tasks.length, succeeded, failed };
    }
}
