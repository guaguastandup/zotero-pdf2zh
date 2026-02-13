pref-title = Zotero PDF2zh
pref-help = { $name } Build { $version } { $time }

pref-config          = Zotero PDF2zh配置
pref-config-basic    = PDF2zh翻译配置
pref-serverip        = Python服务器IP地址
pref-engine          = 翻译引擎
pref-service         = 翻译服务
pref-threadNum       = 翻译线程数
pref-qps             = 最大QPS(每秒请求数)
pref-poolSize        = 池最大工作线程数(可选, 不需要可设置为0)
pref-rename          = 重命名条目为短标题(如'短标题-dual', 实际文件名不变)
pref-skipLastPages   = 最后几页跳过翻译

pref-sourceLang      = 源语言
pref-targetLang      = 目标语言

# pdf1x
pref-babeldoc        = 启用Babeldoc(Experimental)
pref-skipSubsetFonts = 跳过字体子集化(渲染失败时尝试, 生成文件大小更大)
pref-fontFile        = 上传字体文件

# pdf2x
pref-ocr             = 强制开启OCR版临时解决方案（不推荐）
pref-autoOcr         = 自动开启OCR版临时解决方案
pref-transFirst      = 双语(Dual)文件翻译页在前
pref-noWatermark     = 无水印模式
pref-fontFamily      = 选择字体
pref-dualMode        = 双语(Dual)文件显示模式
pref-saveGlossary    = 保存自动提取术语表
pref-disableGlossary = 禁用自动术语提取
pref-noDual          = 不生成双语(Dual)文件
pref-noMono          = 不生成单语(Mono)文件
pref-enhanceCompatibility         = 增强兼容性(自动执行跳过清理和禁用富文本翻译)
pref-skipClean                    = 跳过清理步骤(可能增强兼容性)
pref-disableRichTextTranslate     = 禁用富文本翻译(可能增强兼容性)
pref-translateTableText           = 翻译表格文本(Experimental)
pref-onlyIncludeTranslatedPage    = PDF仅包含选择翻译的页面

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