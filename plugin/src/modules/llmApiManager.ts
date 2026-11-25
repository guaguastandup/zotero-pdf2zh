export interface LLMServiceConfig {
    name: string;
    models?: string[];
    urls?: string[];
    extraData?: any[];
}

export interface LLMApiData {
    key: string;
    service: string;
    apiType?: "openai-compatible";
    apiKey: string;
    apiUrl: string;
    model: string;
    activate: boolean;
    extraData?: Record<string, any>;
}

export const emptyLLMApi: LLMApiData = {
    key: "",
    service: "",
    apiKey: "",
    apiUrl: "",
    model: "",
    activate: false,
    extraData: {},
};

class LLMApiManager {
    private data: Map<string, LLMApiData>;
    constructor() {
        this.data = new Map<string, LLMApiData>();
    }
    public updateLLMApi(llmApi: LLMApiData): string {
        let key = llmApi.key;
        if (!key) {
            key = Zotero.Utilities.generateObjectKey();
            llmApi.key = key;
        }
        // 如果新条目要激活，需要先停用相同service的其他条目
        if (llmApi.activate) {
            this.deactivateSameServiceModel(llmApi.service, key);
        }
        this.data.set(key, llmApi);
        return key;
    }
    // 停用相同service的其他条目
    private deactivateSameServiceModel(
        service: string,
        excludeKey: string,
    ): void {
        this.data.forEach((llmApi, key) => {
            if (
                key !== excludeKey &&
                llmApi.service === service &&
                llmApi.activate
            ) {
                llmApi.activate = false;
                this.data.set(key, llmApi);
            }
        });
    }

    // 激活指定条目，同时停用相同service的其他条目
    public activateLLMApi(key: string): boolean {
        const llmApi = this.data.get(key);
        if (!llmApi) return false;

        this.deactivateSameServiceModel(llmApi.service, key);
        llmApi.activate = true;
        this.data.set(key, llmApi);
        return true;
    }

    // 停用指定条目
    public deactivateLLMApi(key: string): boolean {
        const llmApi = this.data.get(key);
        if (!llmApi) return false;

        llmApi.activate = false;
        this.data.set(key, llmApi);
        return true;
    }

    public getLLMApi(key: string): LLMApiData | undefined {
        return this.data.get(key);
    }

    public getAllLLMApis(): LLMApiData[] {
        return Array.from(this.data.values());
    }

    public deleteLLMApi(key: string): boolean {
        return this.data.delete(key);
    }

    public getActiveLLMApiByService(service: string): LLMApiData | undefined {
        for (const llmApi of this.data.values()) {
            if (llmApi.service === service && llmApi.activate) {
                return llmApi;
            }
        }
        return undefined;
    }
}

// 向外暴露的方法
export const llmApiManager = new LLMApiManager();
// 获取所有 LLM API 配置，供其他模块使用
export function getAllLLMApiConfigs(): LLMApiData[] {
    return llmApiManager.getAllLLMApis();
}
// 根据服务获取激活的 API 配置
export function getActiveLLMApiByService(
    service: string,
): LLMApiData | undefined {
    return llmApiManager.getActiveLLMApiByService(service);
}

// 辅助函数：从表单数据创建 LLM API 数据
export function createLLMApiFromFormData(formData: any): LLMApiData {
    return {
        key: formData.key || "",
        service: formData.service || formData.serviceselect || "",
        apiType: formData.apiType,
        apiKey: formData.apiKey || "",
        apiUrl: formData.apiUrl || "",
        model: formData.model || formData.modelselect || "",
        activate: formData.activate !== undefined ? formData.activate : false,
        extraData: formData.extraData || {},
    };
}

// 格式化 extraData 为显示字符串
export function formatExtraDataForDisplay(
    extraData?: Record<string, any>,
): string {
    if (
        !extraData ||
        typeof extraData !== "object" ||
        Object.keys(extraData).length === 0
    ) {
        return "";
    }
    const pairs: string[] = [];
    for (const [key, value] of Object.entries(extraData)) {
        if (key && key.trim()) {
            // 截断长值以保持表格整洁
            const displayValue =
                String(value || "").length > 10
                    ? String(value || "").substring(0, 10) + "..."
                    : String(value || "");
            pairs.push(`${key}=${displayValue}`);
        }
    }
    // 限制总长度，避免表格列过宽
    const result = pairs.join(", ");
    return result.length > 50 ? result.substring(0, 47) + "..." : result;
}
