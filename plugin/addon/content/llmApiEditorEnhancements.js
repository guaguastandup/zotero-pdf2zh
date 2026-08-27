/* eslint-disable no-restricted-globals */
/* global Zotero, DEFAULT_SERVICES, addExtraFieldRow, bindInputSelectValue, currentData, document, fetch, findExtraFieldRow, mergedServices, navigator, removeExtraFieldRow, updateDeepSeekReasoningEffortState, updateModelOptions */

(() => {
    "use strict";

    const DEPRECATED_DEEPSEEK_MODELS = new Set([
        "deepseek-chat",
        "deepseek-reasoner",
    ]);
    const DEEPSEEK_THINKING_OPT_IN = "deepseek_thinking_explicit_opt_in";

    const TEXT = {
        zh: {
            fetchModels: "获取模型列表",
            fetching: "正在获取模型列表…",
            fetched: (count) => `已获取 ${count} 个模型；默认模型仍保留`,
            noModels: "接口返回成功，但没有识别到模型列表",
            baseUrlRequired: "请先填写 Base URL",
            apiKeyRequired: "该服务获取模型列表需要 API Key",
            failed: (message) => `获取失败：${message}`,
            legacyChat:
                "旧 deepseek-chat 已迁移为 deepseek-v4-flash（思考关闭）",
            legacyReasoner:
                "旧 deepseek-reasoner 已迁移为 deepseek-v4-flash（思考默认关闭；如需思考请手动开启）",
            unsupported:
                "当前服务可能没有兼容的模型列表接口；默认模型选项不会受影响",
            disabled: "关闭",
            enabled: "开启",
            high: "高",
            max: "最大",
        },
        en: {
            fetchModels: "Fetch Model List",
            fetching: "Fetching model list…",
            fetched: (count) =>
                `Fetched ${count} models; built-in defaults are still available`,
            noModels: "The request succeeded, but no model list was recognized",
            baseUrlRequired: "Enter a Base URL first",
            apiKeyRequired:
                "An API Key is required to fetch models for this service",
            failed: (message) => `Fetch failed: ${message}`,
            legacyChat:
                "Legacy deepseek-chat migrated to deepseek-v4-flash (thinking disabled)",
            legacyReasoner:
                "Legacy deepseek-reasoner migrated to deepseek-v4-flash (thinking disabled by default; enable it manually if needed)",
            unsupported:
                "This provider may not expose a compatible model-list endpoint; built-in defaults are unchanged",
            disabled: "Disabled",
            enabled: "Enabled",
            high: "High",
            max: "Max",
        },
    };

    function languageKey() {
        const lang = String(
            document.documentElement.lang || navigator.language || "en",
        ).toLowerCase();
        return lang.startsWith("zh") ? "zh" : "en";
    }

    function text(key, ...args) {
        const value = TEXT[languageKey()][key] ?? TEXT.en[key] ?? key;
        return typeof value === "function" ? value(...args) : value;
    }

    function normalizeBaseUrl(value) {
        return String(value || "")
            .trim()
            .replace(/\/+$/, "");
    }

    function modelRequestSpec(service, baseUrl, apiKey) {
        const serviceConfig = DEFAULT_SERVICES[service] || {};
        const defaultBase = serviceConfig.urls?.[0] || "";
        const base = normalizeBaseUrl(baseUrl || defaultBase);

        if (service === "deepseek") {
            if (!apiKey) throw new Error(text("apiKeyRequired"));
            return {
                url: "https://api.deepseek.com/models",
                headers: { Authorization: `Bearer ${apiKey}` },
            };
        }

        if (service === "openai") {
            if (!apiKey) throw new Error(text("apiKeyRequired"));
            return {
                url: `${base || "https://api.openai.com/v1"}/models`,
                headers: { Authorization: `Bearer ${apiKey}` },
            };
        }

        if (service === "gemini") {
            if (!apiKey) throw new Error(text("apiKeyRequired"));
            const geminiBase =
                base || "https://generativelanguage.googleapis.com/v1beta";
            return {
                url: `${geminiBase}/models?key=${encodeURIComponent(apiKey)}`,
                headers: {},
            };
        }

        if (service === "ollama") {
            const ollamaBase = base || "http://localhost:11434";
            return { url: `${ollamaBase}/api/tags`, headers: {} };
        }

        if (!base) throw new Error(text("baseUrlRequired"));
        return {
            url: base.endsWith("/models") ? base : `${base}/models`,
            headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : {},
        };
    }

    async function requestJson(url, headers) {
        if (Zotero?.HTTP?.request) {
            const xhr = await Zotero.HTTP.request("GET", url, {
                headers,
                responseType: "json",
                timeout: 20000,
            });
            if (xhr.status < 200 || xhr.status >= 300) {
                throw new Error(`HTTP ${xhr.status}`);
            }
            if (xhr.response && typeof xhr.response === "object") {
                return xhr.response;
            }
            const raw = xhr.responseText || xhr.response || "";
            return typeof raw === "string" ? JSON.parse(raw) : raw;
        }

        const response = await fetch(url, { method: "GET", headers });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    }

    function extractModelIds(payload) {
        let list = [];
        if (Array.isArray(payload)) list = payload;
        else if (Array.isArray(payload?.data)) list = payload.data;
        else if (Array.isArray(payload?.models)) list = payload.models;
        else if (Array.isArray(payload?.result?.data))
            list = payload.result.data;
        else if (Array.isArray(payload?.result)) list = payload.result;

        return [
            ...new Set(
                list
                    .map((item) => {
                        if (typeof item === "string") return item;
                        return (
                            item?.id ||
                            item?.name ||
                            item?.model ||
                            item?.model_name ||
                            ""
                        );
                    })
                    .map((value) => {
                        const normalized = String(value);
                        return normalized.startsWith("models/")
                            ? normalized.slice("models/".length)
                            : normalized;
                    })
                    .filter(Boolean),
            ),
        ];
    }

    function installModelFetchControls() {
        const footer = document.querySelector(".button-container");
        const link = document.getElementById("service-doc-link");
        if (!footer || !link || document.getElementById("fetch-models-btn"))
            return;

        const left = document.createElement("div");
        left.className = "model-list-actions";
        footer.insertBefore(left, link);
        left.appendChild(link);

        const button = document.createElement("button");
        button.type = "button";
        button.id = "fetch-models-btn";
        button.className = "btn btn-secondary btn-compact";
        button.textContent = text("fetchModels");
        left.insertBefore(button, link);

        const status = document.createElement("span");
        status.id = "fetch-models-status";
        status.className = "model-fetch-status";
        left.appendChild(status);

        const style = document.createElement("style");
        style.textContent = `
            .model-list-actions {
                display: flex;
                align-items: center;
                gap: 8px;
                min-width: 0;
            }
            .model-list-actions .btn-compact {
                margin-left: 0;
                padding: 6px 10px;
                font-size: 12px;
                white-space: nowrap;
            }
            .model-fetch-status {
                max-width: 260px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                color: #666;
                font-size: 12px;
            }
            .model-fetch-status.error {
                color: #c0392b;
            }
        `;
        document.head.appendChild(style);

        button.addEventListener("click", async () => {
            const service = document.getElementById("service").value.trim();
            const baseUrl = document.getElementById("apiUrl").value.trim();
            const apiKey = document.getElementById("apiKey").value.trim();

            button.disabled = true;
            status.classList.remove("error");
            status.textContent = text("fetching");
            try {
                const spec = modelRequestSpec(service, baseUrl, apiKey);
                const payload = await requestJson(spec.url, spec.headers);
                let models = extractModelIds(payload);
                if (service === "deepseek") {
                    models = models.filter(
                        (model) => !DEPRECATED_DEEPSEEK_MODELS.has(model),
                    );
                }
                if (!models.length) throw new Error(text("noModels"));

                if (!mergedServices[service]) {
                    mergedServices[service] = {
                        name: service,
                        models: [],
                        urls: baseUrl ? [baseUrl] : [],
                        apiKeys: [],
                    };
                }
                const defaults = DEFAULT_SERVICES[service]?.models || [];
                const existing = mergedServices[service].models || [];
                mergedServices[service].models = [
                    ...new Set([...defaults, ...existing, ...models.sort()]),
                ];
                updateModelOptions(service);
                status.textContent = text("fetched", models.length);
                status.title = "";
            } catch (error) {
                const message =
                    error?.message || String(error || "Unknown error");
                status.textContent = text("failed", message);
                status.title = text("unsupported");
                status.classList.add("error");
            } finally {
                button.disabled = false;
            }
        });
    }

    function setExtraSelectValue(key, value) {
        const row = findExtraFieldRow(key);
        const select = row?.querySelector(".extra-value");
        if (select) select.value = value;
    }

    function localizeDeepSeekSelectLabels() {
        const labels = {
            disabled: text("disabled"),
            enabled: text("enabled"),
            high: text("high"),
            max: text("max"),
        };
        for (const key of [
            "deepseek_thinking_mode",
            "deepseek_reasoning_effort",
        ]) {
            const select =
                findExtraFieldRow(key)?.querySelector(".extra-value");
            if (!select || select.tagName.toLowerCase() !== "select") continue;
            for (const option of select.options) {
                if (labels[option.value])
                    option.textContent = labels[option.value];
            }
        }
    }

    function setThinkingExplicitOptIn(enabled) {
        removeExtraFieldRow(DEEPSEEK_THINKING_OPT_IN);
        if (!enabled) return;
        addExtraFieldRow(DEEPSEEK_THINKING_OPT_IN, "true");
        const row = findExtraFieldRow(DEEPSEEK_THINKING_OPT_IN);
        if (row) row.style.display = "none";
    }

    function installDeepSeekThinkingConsent() {
        const modeSelect = findExtraFieldRow(
            "deepseek_thinking_mode",
        )?.querySelector(".extra-value");
        if (!modeSelect || modeSelect.tagName.toLowerCase() !== "select") return;

        // Existing saved `enabled` values are not sufficient consent: older
        // versions could create them automatically. Reconfirm once in 4.1.8.
        const existingMarker = findExtraFieldRow(DEEPSEEK_THINKING_OPT_IN);
        if (existingMarker) {
            existingMarker.style.display = "none";
        } else if (modeSelect.value === "enabled") {
            modeSelect.value = "disabled";
            updateDeepSeekReasoningEffortState();
        }
        if (modeSelect.value !== "enabled" && existingMarker) {
            setThinkingExplicitOptIn(false);
        }

        // Only a real user change to Enabled creates the consent marker.
        modeSelect.addEventListener("change", () => {
            setThinkingExplicitOptIn(modeSelect.value === "enabled");
        });
    }

    function migrateLegacyDeepSeekModel() {
        const service = document.getElementById("service").value;
        const modelInput = document.getElementById("model");
        if (
            service !== "deepseek" ||
            !DEPRECATED_DEEPSEEK_MODELS.has(modelInput.value)
        ) {
            return;
        }

        const legacyModel = modelInput.value;
        const explicitMode = Object.prototype.hasOwnProperty.call(
            currentData?.extraData || {},
            "deepseek_thinking_mode",
        );

        bindInputSelectValue("deepseek-v4-flash", "model");
        updateModelOptions("deepseek");

        // Never opt users into paid reasoning during migration. Preserve an
        // explicit new-plugin choice, otherwise migrate both legacy DeepSeek
        // models to thinking disabled and let the user enable it manually.
        if (!explicitMode) {
            setExtraSelectValue("deepseek_thinking_mode", "disabled");
            updateDeepSeekReasoningEffortState();
        }

        const status = document.getElementById("fetch-models-status");
        if (status) {
            status.textContent =
                legacyModel === "deepseek-reasoner"
                    ? text("legacyReasoner")
                    : text("legacyChat");
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        installModelFetchControls();
        migrateLegacyDeepSeekModel();
        localizeDeepSeekSelectLabels();
        installDeepSeekThinkingConsent();
    });
})();
