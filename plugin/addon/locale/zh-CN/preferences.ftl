pref-title = Zotero PDF2zh
pref-help = { $name } Build { $version } { $time }

pref-config          = Zotero PDF2zh配置
pref-config-basic    = PDF2zh翻译配置
pref-serverip        = Python服务器IP地址
pref-engine          = 翻译引擎
pref-service         = 翻译服务
pref-threadNum       = 翻译线程数
pref-qps             = 最大QPS(每秒请求数)
pref-poolSize        = 最大并发Worker数(0=跟随QPS)
pref-rename          = 翻译后重命名附件标题
pref-rename-style    = 标题格式
pref-rename-style-short =
    .label = 短标题-服务-类型 (如"短标题-siliconflowfree-mono")
pref-rename-style-prefix =
    .label = 标题前缀-年份-服务-类型 (如"A Survey of LLM…-2024-...-mono")
pref-rename-style-full =
    .label = 完整标题-服务-类型
pref-rename-style-custom =
    .label = 自定义模板
pref-rename-prefix-length = 前缀字符数
pref-rename-template = 标题模板
pref-showProgress    = 在 Zotero 右下角显示翻译进度
pref-skipLastPages   = 最后几页跳过翻译

pref-sourceLang      = 源语言
pref-targetLang      = 目标语言

# pdf1x
pref-babeldoc        = 启用Babeldoc(Experimental)
pref-skipSubsetFonts = 跳过字体子集化(渲染失败时尝试, 生成文件大小更大)
pref-fontFile        = 上传字体文件
pref-clear =
    .label = 清除

# pdf2x
pref-ocr             = 强制开启OCR版临时解决方案（不推荐）
pref-autoOcr         = 自动开启OCR版临时解决方案
pref-transFirst      = 双语(Dual)译文在前（左右模式时译文在左）
pref-noWatermark     = 无水印模式
pref-fontFamily      = 选择字体
pref-dualMode        = 双语(Dual)文件显示模式
pref-pdf1x-config-title = pdf2zh 1.x 配置
pref-pdf2x-config-title = pdf2zh 2.x 配置
pref-dualMode-lr     = 左右对照
pref-dualMode-tb     = 原文/译文交替页
pref-saveGlossary    = 保存自动提取术语表
pref-disableGlossary = 禁用自动术语提取
pref-noDual          = 不生成双语(Dual)文件
pref-noMono          = 不生成单语(Mono)文件
pref-enhanceCompatibility         = 增强兼容性(会启用跳过清理、禁用富文本翻译，并可能使译文在前)
pref-skipClean                    = 跳过清理步骤(可能增强兼容性)
pref-disableRichTextTranslate     = 禁用富文本翻译(可能增强兼容性)
pref-translateTableText           = 翻译表格文本(Experimental)
pref-skipReferences = 跳过参考文献列表翻译（实验性；不影响正文引用）
pref-prettierTables = 更美观的表格
pref-onlyIncludeTranslatedPage    = 仅保留实际翻译的页面(仅设置跳过/选择页面时生效)

pref-gen           = 默认生成文件
pref-open          = 生成后自动打开
pref-mono          = 生成mono文件 (仅包含翻译语言)
pref-dual          = 生成dual文件 (双语对照)
pref-mono-cut      = 生成单栏mono文件 (适配手机阅读)
pref-dual-cut      = 生成单栏dual文件 (适配手机阅读)
pref-crop-compare  = 生成双语对照文件 (竖向切割后左右拼接）
pref-compare       = 生成双语对照文件 (直接左右拼接)

pref-llmapi-services  = 翻译服务配置
pref-llmapi-add       = 新增
pref-llmapi-remove    = 删除
pref-llmapi-edit      = 编辑
pref-llmapi-activate  = 激活
pref-llmapi-totop     = 置顶
pref-check-connection = 检查连接
pref-ignoreCache      = 跳过翻译缓存(重新请求翻译服务, 会产生额外费用, 默认关闭)

pref-local-server = 本地服务启动
pref-local-server-help = 手动模式：选择已安装环境的 Python 和支持 --non-interactive 的 server.py。退出 Zotero 时仅停止插件启动的进程；失败时查看后端 server/logs/server.log。
pref-local-python = Python 可执行文件路径
pref-local-script = server.py 路径
pref-local-python-browse =
    .aria-label = 浏览 Python 可执行文件
pref-local-script-browse =
    .aria-label = 浏览 server.py
pref-local-auto = Zotero 启动时自动启动本地服务（默认关闭）
pref-local-start = 启动本地服务
pref-local-stop = 停止插件启动的服务

pref-local-discovery-help = 打开此页时会在主目录、下载、桌面和文档的常见目录查找已安装新版后端及其虚拟环境；只填入空白字段作为候选，核对后点击启动才保存。自定义安装位置可手动浏览。

pref-local-prepare = 自动准备并启动
pref-local-cancel = 取消准备
pref-local-prepare-help = Windows 首次准备需要联网下载运行环境和依赖；首次使用翻译引擎时仍可能按需下载。已有服务将优先复用。
