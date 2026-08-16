pref-title = Zotero PDF2zh
pref-help = { $name } Build { $version } { $time }

pref-config          = Zoterp PDF2zh Configuration
pref-config-basic    = PDF2zh Translation Config
pref-serverip        = Python Server IP Address
pref-engine          = Translation Engine
pref-service         = Translation Service
pref-threadNum       = Translation Threads Num
pref-qps             = Max QPS (Requests Per Second)
pref-poolSize        = Thread Pool Size(Optional)
pref-rename          = Rename attachment title (e.g. 'ShortTitle | dual', actual file name remains unchanged)
pref-renamePrefix    = Title Prefix
pref-renameSuffix    = Title Suffix
pref-renameAdvanced  = Enable advanced rename template
pref-renameTemplate  = Rename template (available: {baseTitle} {shortTitle} {parentTitle} {type} {service} {targetLang} {prefix} {suffix})
pref-renameHelp      = ?
    .title = Click to view full example
pref-renameHelpContent = Example values:
    shortTitle = DVDAS
    parentTitle = Deep Video Discovery
    baseTitle = shortTitle first, otherwise truncated parentTitle
    type = dual
    service = openai
    targetLang = zh-CN
    prefix = [Translated]
    suffix = [Bilingual]

    Default template:
    {prefix}{baseTitle}{suffix} | {type}
    Result:
    [Translated]DVDAS[Bilingual] | dual

    Advanced template:
    {parentTitle} | {service} | {targetLang} | {type}
    Result:
    Deep Video Discovery | openai | zh-CN | dual
pref-skipLastPages   = Skip Last Pages Translation

pref-sourceLang      = Source Language
pref-targetLang      = Target Language

# pdf1x
pref-babeldoc        = Enable Babeldoc (Experimental)
pref-skipSubsetFonts  = Skip Font Subsetting (Try when rendering fails, results in larger file size)
pref-fontFile        = Upload Font File

# pdf2x
pref-ocr             = OCR workaround (experimental, will auto enable Skip scanned detection in backend)
pref-autoOcr         = Auto enable OCR workaround (enable automatic OCR workaround for heavily scanned documents)
pref-transFirst      = Dual File Translation Pages First
pref-noWatermark     = No Watermark
pref-fontFamily      = Choose Font
pref-dualMode        = Dual Mode
pref-saveGlossary    = Save automatically extracted glossary
pref-disableGlossary = Disable auto extract glossary
pref-noDual          = Do not generate dual file
pref-noMono          = Do not generate mono file
pref-skipClean       = Skip clean(maybe improve compatibility)
pref-disableRichTextTranslate = Disable rich text translation(maybe improve compatibility)
pref-enhanceCompatibility = Enhance compatibility(auto-enables skip_clean and disable_rich_text)
pref-translateTableText = Translate table text(experimental)
pref-onlyIncludeTranslatedPage = Only Include Translated Pages

pref-gen = Default Generated File
pref-open = Automatically Open After Generation
pref-mono = Generate Mono File (Contains Only Target Language)
pref-dual = Generate Dual File (Bilingual Comparison)
pref-mono-cut = Generate Single Column Mono File (Optimized for Mobile Reading)
pref-dual-cut = Generate Single Column Dual File (Optimized for Mobile Reading)
pref-crop-compare = Generate Bilingual Comparison File (Vertical Split and Left-Right Concatenation)
pref-compare= Generate Bilingual Comparison File (Direct Left-Right Concatenation)

pref-skim-config = Skim Reader / MinerU Config
pref-mineru-token = MinerU Token
pref-mineru-baseUrl = MinerU API URL
pref-mineru-modelVersion = MinerU Model Version
pref-mineru-language = Parse Language
pref-mineru-timeout = Timeout Seconds
pref-skim-translate = Generate full translation PDF with skim PDF

pref-llmapi-services        = Translation Service Configuration
pref-llmapi-add       = Add
pref-llmapi-remove    = Remove
pref-llmapi-edit      = Edit
pref-llmapi-activate  = Activate
pref-llmapi-test      = Test
pref-llmapi-totop     = Pin
pref-check-connection = Check Connection
