## server.py v3.0.17
# guaguastandup
# zotero-pdf2zh
apiKey = "apiKey"
apiUrl = "apiUrl"
model = "model"
extraData = "extraData"

pdf2zh_config_map = {
    "deepl": {
        apiKey: "DEEPL_AUTH_KEY"
    },
    "deeplx": {
        apiUrl: "DEEPLX_ENDPOINT"
    },
    "ollama": {
        apiUrl: "OLLAMA_HOST",
        model: "OLLAMA_MODEL"
    },
    "xinference": {
        apiUrl: "XINFERENCE_HOST",
        model: "XINFERENCE_MODEL"
    },
    "openai": {
        apiKey: "OPENAI_API_KEY",
        model: "OPENAI_MODEL",
        apiUrl: "OPENAI_BASE_URL"
    },
    "azure-openai": {
        apiKey: "AZURE_OPENAI_API_KEY",
        model: "AZURE_OPENAI_MODEL",
        apiUrl: "AZURE_OPENAI_BASE_URL"
    },
    "zhipu": {
        apiKey: "ZHIPU_API_KEY",
        model: "ZHIPU_MODEL"
    },
    "ModelScope": {
        apiKey: "MODELSCOPE_API_KEY",
        model: "MODELSCOPE_MODEL"
    },
    "silicon": {
        apiKey: "SILICON_API_KEY",
        model: "SILICON_MODEL"
    },
    "gemini": {
        apiKey: "GEMINI_API_KEY",
        model: "GEMINI_MODEL"
    },
    "azure": {
        apiKey: "AZURE_API_KEY",
        apiUrl: "AZURE_ENDPOINT"
    },
    "tencent": {
        apiKey: "TENCENTCLOUD_SECRET_KEY",
        model: "TENCENTCLOUD_SECRET_ID",
    },
    "dify": {
        apiKey: "DIFY_API_KEY",
        apiUrl: "DIFY_API_URL"
    },
    "anythingllm": {
        apiKey: "AnythingLLM_APIKEY",
        apiUrl: "AnythingLLM_URL"
    },
    "grok": {
        apiKey: "GROK_API_KEY",  # Note: Table says GORK, assuming typo for GROK
        model: "GROK_MODEL"
    },
    "groq": {
        apiKey: "GROQ_API_KEY",
        model: "GROQ_MODEL"
    },
    "deepseek": {
        apiKey: "DEEPSEEK_API_KEY",
        model: "DEEPSEEK_MODEL"
    },
    "openailiked": {
        apiKey: "OPENAILIKED_API_KEY",
        model: "OPENAILIKED_MODEL",
        apiUrl: "OPENAILIKED_BASE_URL"
    },
    "qwen-mt": {
        apiKey: "ALI_API_KEY",
        model: "ALI_MODEL",
        extraData: [
            "ALI_DOMAINS"
        ]
    }

}

pdf2zh_next_config_map = {
    "deepl": {
        apiKey: "deepl_auth_key"
    },
    "openai": {
        apiKey: "openai_api_key",
        model: "openai_model",
        apiUrl: "openai_base_url",
        extraData: [
            'openai_temperature',
            'openai_reasoning_effort',
            'openai_send_temperature',
            'openai_send_reasoning_effort'
        ]
    },
    "aliyundashscope": {
        apiKey: "aliyun_dashscope_api_key",
        model: "aliyun_dashscope_model",
        apiUrl: "aliyun_dashscope_base_url",
        extraData: [
            "aliyun_dashscope_timeout",
            "aliyun_dashscope_temperature",
            "aliyun_dashscope_send_temperature",
            "aliyun_dashscope_enable_json_mode"
        ]
    },
    "xinference": {
        apiUrl: "xinference_host",
        model: "xinference_model"
    },
    "ollama": {
        apiUrl: "ollama_host",
        model: "ollama_model",
        extraData: [
            "num_predict"
        ]
    },
    "azureopenai": {
        apiKey: "azure_openai_api_key",
        model: "azure_openai_model",
        apiUrl: "azure_openai_base_url",
        extraData: [
            "azure_openai_api_version"
        ]
    },
    "modelscope": {
        apiKey: "modelscope_api_key",
        model: "modelscope_model",
        extraData: [
            "modelscope_enable_json_mode"
        ]
    },
    "zhipu": {
        apiKey: "zhipu_api_key",
        model: "zhipu_model",
        extraData:[
            "zhipu_enable_json_mode"
        ]
    },
    "siliconflow": {
        apiKey: "siliconflow_api_key",
        model: "siliconflow_model",
        apiUrl: "siliconflow_base_url",
        extraData: [
            "siliconflow_enable_thinking",
            "siliconflow_send_enable_thinking_param"
        ]
    },
    "tencentmechinetranslation": {
        apiKey: "tencentcloud_secret_key",
        model: "tencentcloud_secret_id"
    },
    "gemini": {
        apiKey: "gemini_api_key",
        model: "gemini_model",
        extraData: [
            "gemini_enable_json_mode"
        ]
    },
    "azure": {
        apiKey: "azure_api_key",
        apiUrl: "azure_endpoint"
    },
    "anythingllm": {
        apiKey: "anythingllm_apikey",
        apiUrl: "anythingllm_url"
    },
    "dify": {
        apiKey: "dify_apikey",
        apiUrl: "dify_url"
    },
    "grok": {
        apiKey: "grok_api_key",
        model: "grok_model",
        extraData: [
            "grok_enable_json_mode"
        ]
    },
    "groq": {
        apiKey: "groq_api_key",
        model: "groq_model",
        extraData: [
            "groq_enable_json_mode"
        ]
    },
    "deepseek": {
        apiKey: "deepseek_api_key",
        model: "deepseek_model"
    },
    "qwenmt": {
        apiKey: "qwenmt_api_key",
        model: "qwenmt_model",
        apiUrl: "qwenmt_base_url",
        extraData: [
            "ali_domains"
        ]
    },
    "openaicompatible": {
        apiKey: "openai_compatible_api_key",
        model: "openai_compatible_model",
        apiUrl: "openai_compatible_base_url",
        extraData: [
            "openai_compatible_temperature",
            "openai_compatible_reasoning_effort",
            "openai_compatible_send_temperature",
            "openai_compatible_send_reasoning_effort",
            "openai_compatible_enable_json_mode"
        ]
    },
    "claudecode": {
        apiUrl: "claude_code_path",
        model: "claude_code_model"
    }
}