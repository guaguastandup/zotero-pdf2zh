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
        for (const task of tasks) {
            try {
                await PDF2zhHelperFactory.processSingleFile(task);
                succeeded++;
            } catch (error) {
                failed++;
            }
        }
        this.emit("batchCompleted", {
            total: tasks.length,
            succeeded,
            failed,
        });
    }
}
