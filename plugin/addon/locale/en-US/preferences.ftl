pref-title = Zotero PDF2zh
pref-help = { $name } Build { $version } { $time }

pref-config          = Zotero PDF2zh Configuration
pref-config-basic    = PDF2zh Translation Config
pref-serverip        = Python Server IP Address
pref-engine          = Translation Engine
pref-engine-wenyi-note = Wenyi is an optional experimental engine, currently using DeepSeek. Extra workflow stages are off by default; enable only as needed. Long documents may use many tokens and take considerable time.
pref-wenyi-pipeline-title = Wenyi Workflow Configuration
pref-wenyi-service = Translation service (currently DeepSeek only)
pref-wenyi-prompt-genre = Translation style
pref-wenyi-prompt-genre-academic = Academic
pref-wenyi-prompt-genre-literary = Literary
pref-wenyi-book-understanding = Whole-document prescan
pref-wenyi-translation-mode = Three-draft precision
pref-wenyi-polish = Polish translation
pref-wenyi-review = Whole-document Review
pref-wenyi-annotation-alignment = Align annotation/link anchors
pref-wenyi-bilingual-order = Bilingual order (left to right)
pref-wenyi-target-first = Translation first
pref-wenyi-source-first = Original first
pref-service         = Translation Service
pref-threadNum       = Translation Threads Num
pref-qps             = Max QPS (Requests Per Second)
pref-poolSize        = Max Concurrent Workers (0 = follow QPS)
pref-rename          = Rename Item to Short Title (e.g. 'ShortTitle-dual', actual file name remains unchanged)
pref-rename-style    = Title format
pref-rename-style-short =
    .label = Short title - service - type
pref-rename-style-prefix =
    .label = Title prefix - year - service - type
pref-rename-style-full =
    .label = Full title - service - type
pref-rename-style-custom =
    .label = Custom template
pref-rename-prefix-length = Prefix words
pref-rename-template = Title template
pref-showProgress    = Show translation progress in the Zotero popup
pref-skipLastPages   = Skip Last Pages Translation

pref-sourceLang      = Source Language
pref-targetLang      = Target Language

# pdf1x
pref-babeldoc        = Enable Babeldoc (Experimental)
pref-skipSubsetFonts = Skip Font Subsetting (Try when rendering fails, results in larger file size)
pref-fontFile        = Upload Font File
pref-clear =
    .label = Clear

# pdf2x
pref-ocr             = OCR workaround (experimental, will auto enable Skip scanned detection in backend)
pref-autoOcr         = Auto enable OCR workaround (enable automatic OCR workaround for heavily scanned documents)
pref-transFirst      = Put translation first in Dual output (left side in side-by-side mode)
pref-noWatermark     = No Watermark
pref-fontFamily      = Choose Font
pref-dualMode        = Dual Mode
pref-pdf1x-config-title = pdf2zh 1.x Configuration
pref-pdf2x-config-title = pdf2zh 2.x Configuration
pref-dualMode-lr     = Side by Side
pref-dualMode-tb     = Alternating Pages
pref-saveGlossary    = Save automatically extracted glossary
pref-disableGlossary = Disable auto extract glossary

pref-glossary-file-choose = Choose Glossary CSV…
pref-glossary-file-clear = Remove
pref-glossary-file-help = Applies to future pdf2zh_next translations. Use UTF-8 CSV with source,target headers and an optional tgt_lng column. Keep the original file available so the plugin can send it to the Server when translating.
pref-noDual          = Do not generate dual file
pref-noMono          = Do not generate mono file
pref-skipClean       = Skip clean(maybe improve compatibility)
pref-disableRichTextTranslate = Disable rich text translation(maybe improve compatibility)
pref-enhanceCompatibility = Enhance compatibility (enables skip clean / disable rich text and may force translation first)
pref-translateTableText = Translate table text(experimental)
pref-skipReferences = Skip reference list translation (experimental; keeps in-text citations)
pref-prettierTables = Prettier tables
pref-onlyIncludeTranslatedPage = Keep Only Actually Translated Pages (effective with page selection/skipping)

pref-gen = Default Generated File
pref-open = Automatically Open After Generation
pref-mono = Generate Mono File (Contains Only Target Language)
pref-dual = Generate Dual File (Bilingual Comparison)
pref-mono-cut = Generate Single Column Mono File (Optimized for Mobile Reading)
pref-dual-cut = Generate Single Column Dual File (Optimized for Mobile Reading)
pref-crop-compare = Generate Bilingual Comparison File (Vertical Split and Left-Right Concatenation)
pref-compare = Generate Bilingual Comparison File (Direct Left-Right Concatenation)

pref-llmapi-services  = Translation Service Configuration
pref-llmapi-add       = Add
pref-llmapi-remove    = Remove
pref-llmapi-edit      = Edit
pref-llmapi-activate  = Activate
pref-llmapi-totop     = Pin
pref-check-connection = Check Connection
pref-ignoreCache      = Skip translation cache (re-requests the service, may cost extra; off by default)

pref-local-service-directory = Local server folder
pref-local-service-auto-start = Automatically start the local server before PDF operations (Windows, localhost / 127.0.0.1 only)

pref-mathCompatibility = Math compatibility (experimental, improves some radicals, variables and fraction rules)

pref-wenyi-book-understanding-description = Analyze the document before translating. Adds model calls, token usage and waiting time. Off by default.
pref-wenyi-translation-mode-description = Generate multiple drafts and synthesize them; also enables polishing. Substantially increases token usage and runtime. Off by default.
pref-wenyi-polish-description = Polish the initial translation with extra model calls. Off by default.
pref-wenyi-review-description = Check the translated document and potentially revise it in multiple rounds. Long documents may take much longer. Off by default.
pref-wenyi-annotation-alignment-description = Attempt to align annotation and link anchors. Adds processing steps. Off by default.
