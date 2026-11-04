"""Opt-in, document-scoped reference skipping for BabelDOC 0.6.4.

Never patch installed package files. Reference paragraphs remain in the PDF;
only LLM translation and automatic terminology extraction skip them.
"""

from __future__ import annotations

import copy
import logging
import re
from importlib.metadata import PackageNotFoundError, version

logger = logging.getLogger(__name__)
SUPPORTED_BABELDOC = "0.6.4"
SUPPORTED_PDF2ZH_NEXT = "2.9.0"

REFERENCE_HEADINGS = {
    "references", "reference list", "bibliography", "works cited",
    "literature cited", "references cited", "cited literature",
    "references and notes", "further reading", "参考文献",
}
POST_REFERENCE_HEADINGS = {
    "appendix", "appendices", "online appendix", "web appendix",
    "supplement", "supplementary material", "supplementary materials",
    "supplementary information", "supporting information",
    "data availability", "data availability statement",
    "acknowledgments", "acknowledgements", "author contributions",
    "funding", "conflict of interest", "conflicts of interest",
    "competing interests", "figure legends", "figure captions",
    "table captions",
}
NOISE_LABELS = {"header", "footer", "page", "page number", "abandon"}
HEADING_LABELS = {
    "title", "heading", "section", "section heading", "section title",
    "chapter title", "chapter heading",
}
CAPTION_LABELS = {"table caption", "figure caption", "image caption"}


def policy_supported() -> bool:
    """Fail closed when upstream private APIs have not been checked."""
    try:
        from packaging.version import Version

        return (
            Version(version("BabelDOC")) == Version(SUPPORTED_BABELDOC)
            and Version(version("pdf2zh-next")) == Version(SUPPORTED_PDF2ZH_NEXT)
        )
    except (PackageNotFoundError, ValueError, ImportError):
        return False


def warn_native_fallback() -> None:
    logger.warning(
        "参考文献跳过仅验证 pdf2zh-next %s + BabelDOC %s；"
        "当前环境未经验证，本次使用原生翻译（不会修改安装的引擎）。",
        SUPPORTED_PDF2ZH_NEXT, SUPPORTED_BABELDOC,
    )


def _normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip().casefold()
    text = re.sub(r"^(?:section\s+)?\d+(?:\.\d+)*[.)]?\s+", "", text)
    return text.strip(" .:：;；-–—_")


def _label(paragraph) -> str:
    return re.sub(
        r"[\s_-]+", " ",
        str(getattr(paragraph, "layout_label", "") or "").lower().strip(),
    )


def _text(paragraph) -> str:
    return str(getattr(paragraph, "unicode", "") or "").strip()


def _noise(paragraph) -> bool:
    text = _text(paragraph)
    return (
        not text
        or _label(paragraph) in NOISE_LABELS
        or bool(re.fullmatch(r"\d{1,4}|[ivxlcdm]{1,7}", text, re.I))
    )


def _citation_like(text: str) -> bool:
    text = str(text or "").strip()
    return bool(
        re.match(r"^(?:\[\s*\d{1,4}\s*\]|\d{1,4}[.)])\s+", text)
        or re.search(r"(?:doi\.org/|doi:\s*10\.|arxiv:\s*\d)", text, re.I)
        or (len(text) >= 22 and re.search(r"\b(?:19|20)\d{2}[a-z]?\b", text))
    )


def _is_reference_heading(paragraph) -> bool:
    return (
        _label(paragraph) not in NOISE_LABELS
        and _normalize(_text(paragraph)) in REFERENCE_HEADINGS
    )


def _has_bibliography_evidence(pages, page_index, para_index, heading) -> bool:
    """A TOC or body mention of 'References' must not disable translation."""
    examples = 0
    examined = 0
    for page in pages[page_index:]:
        start = para_index + 1 if page is pages[page_index] else 0
        for paragraph in getattr(page, "pdf_paragraph", ())[start:]:
            if _noise(paragraph):
                continue
            text = _text(paragraph)
            if _normalize(text) in POST_REFERENCE_HEADINGS:
                return examples >= 2
            examined += 1
            if _citation_like(text):
                examples += 1
            if examined >= 10:
                return examples >= 2
    return examples >= 2


def _exit_reference(paragraph, first_meaningful: bool, new_page: bool) -> bool:
    text = _normalize(_text(paragraph))
    label = _label(paragraph)
    if text in POST_REFERENCE_HEADINGS:
        return True
    if re.match(
        r"^(?:appendix|online appendix|web appendix|supplementary|"
        r"supplement|supporting information)\s+[a-z0-9](?:[.:\s]|$)",
        text,
    ) and len(text) < 100:
        return True
    if new_page and first_meaningful and not _citation_like(_text(paragraph)):
        return label in HEADING_LABELS or label in CAPTION_LABELS
    return False


def find_reference_paragraph_ids(document) -> frozenset[int]:
    """Detect bibliography entries without page-ratio assumptions.

    Only a standalone References heading followed by >=2 citation-like
    entries activates the skip. Ambiguous documents fail open.
    """
    pages = list(getattr(document, "page", ()) or ())
    skipped: set[int] = set()
    in_references = False
    start_page = -1
    sections = 0
    for page_index, page in enumerate(pages):
        meaningful_count = 0
        for paragraph_index, paragraph in enumerate(
            getattr(page, "pdf_paragraph", ()) or ()
        ):
            first_meaningful = meaningful_count == 0
            if not _noise(paragraph):
                meaningful_count += 1
            else:
                continue

            if not in_references:
                if (
                    _is_reference_heading(paragraph)
                    and _has_bibliography_evidence(
                        pages, page_index, paragraph_index, paragraph
                    )
                ):
                    in_references = True
                    start_page = page_index
                    sections += 1
                # The References heading itself is still translated.
                continue

            if _exit_reference(
                paragraph,
                first_meaningful=first_meaningful,
                new_page=page_index > start_page,
            ):
                in_references = False
                continue

            # Only real text with a debug ID would enter the normal translator.
            if getattr(paragraph, "debug_id", None) is not None:
                skipped.add(id(paragraph))

    logger.info(
        "Reference Skip: %s section(s), %s paragraph(s) preserved",
        sections, len(skipped),
    )
    return frozenset(skipped)


def _plan_for(document) -> frozenset[int]:
    """Share one decision between terminology and translation for a document."""
    previous = getattr(document, "_zotero_reference_skip_ids", None)
    if previous is not None:
        return previous
    ids = find_reference_paragraph_ids(document)
    try:
        document._zotero_reference_skip_ids = ids
    except (AttributeError, TypeError):
        pass  # Some IL implementations may forbid extra attributes.
    return ids


def _page_without(page, skipped):
    view = copy.copy(page)
    # Nested table-page views keep a pointer to the original Document page.
    view._zotero_real_page = getattr(page, "_zotero_real_page", page)
    view.pdf_paragraph = [
        paragraph for paragraph in page.pdf_paragraph
        if id(paragraph) not in skipped
    ]
    return view


class _RealPageExecutor:
    """Preserve the actual PDF page in queued translation/fallback tasks."""

    def __init__(self, executor, page, source=None):
        self.executor = executor
        self.page = page
        self.source = source

    def submit(self, function, batch, *args, **kwargs):
        if hasattr(batch, "pages"):
            batch.pages = [self.page] * len(batch.paragraphs)
        elif self.source is not None and args and args[0] is self.source:
            # Non-LLM ILTranslator passes a paragraph and then a Page.
            args = (self.page, *args[1:])
        return self.executor.submit(function, batch, *args, **kwargs)


def install_reference_skip_policy():
    """Install process-local hooks; caller must invoke the returned restore."""
    if not policy_supported():
        warn_native_fallback()
        return lambda: None

    from babeldoc.format.pdf.document_il.midend.il_translator_llm_only import (
        ILTranslatorLLMOnly,
    )
    from babeldoc.format.pdf.document_il.midend.automatic_term_extractor import (
        AutomaticTermExtractor,
    )
    from babeldoc.format.pdf.document_il.midend.il_translator import ILTranslator

    original_plain_translate = ILTranslator.translate
    original_plain_page = ILTranslator.process_page
    original_translate = ILTranslatorLLMOnly.translate
    original_page = ILTranslatorLLMOnly.process_page
    original_should = ILTranslatorLLMOnly._should_translate_paragraph
    original_term_run = AutomaticTermExtractor.procress
    original_term_page = AutomaticTermExtractor.process_page

    def translate(translator, docs):
        translator._zotero_reference_skip_ids = _plan_for(docs)
        try:
            return original_translate(translator, docs)
        finally:
            translator.__dict__.pop("_zotero_reference_skip_ids", None)

    def should_translate(translator, paragraph, *args, **kwargs):
        if id(paragraph) in getattr(
            translator, "_zotero_reference_skip_ids", ()
        ):
            return False
        return original_should(translator, paragraph, *args, **kwargs)

    def process_page(
        translator, page, executor, pbar=None, tracker=None,
        executor2=None, translated_ids=None,
    ):
        skip_ids = getattr(translator, "_zotero_reference_skip_ids", ())
        to_skip = [
            p for p in page.pdf_paragraph
            if id(p) in skip_ids
        ]
        if not to_skip:
            return original_page(
                translator, page, executor, pbar, tracker, executor2, translated_ids
            )
        if translated_ids is not None:
            fresh = [
                p for p in to_skip if id(p) not in translated_ids
                and p.debug_id is not None and p.unicode is not None
            ]
            translated_ids.update(id(p) for p in to_skip)
        else:
            fresh = [
                p for p in to_skip if p.debug_id is not None and p.unicode is not None
            ]
        if pbar is not None and fresh:
            pbar.advance(len(fresh))
        return original_page(
            translator, _page_without(page, skip_ids),
            _RealPageExecutor(executor, getattr(page, "_zotero_real_page", page)),
            pbar, tracker, executor2,
            translated_ids,
        )

    def plain_translate(translator, docs):
        translator._zotero_reference_skip_ids = _plan_for(docs)
        try:
            return original_plain_translate(translator, docs)
        finally:
            translator.__dict__.pop("_zotero_reference_skip_ids", None)

    def plain_page(translator, page, executor, pbar=None, tracker=None):
        skip_ids = getattr(translator, "_zotero_reference_skip_ids", ())
        to_skip = [p for p in page.pdf_paragraph if id(p) in skip_ids]
        if not to_skip:
            return original_plain_page(translator, page, executor, pbar, tracker)
        if pbar is not None:
            pbar.advance(len(to_skip))
        view = _page_without(page, skip_ids)
        return original_plain_page(
            translator, view,
            _RealPageExecutor(
                executor, getattr(page, "_zotero_real_page", page), source=view
            ),
            pbar, tracker,
        )

    def term_run(extractor, docs):
        extractor._zotero_reference_skip_ids = _plan_for(docs)
        try:
            return original_term_run(extractor, docs)
        finally:
            extractor.__dict__.pop("_zotero_reference_skip_ids", None)

    def term_page(extractor, page, executor, pbar=None, tracker=None):
        skip_ids = getattr(extractor, "_zotero_reference_skip_ids", ())
        to_skip = [
            p for p in page.pdf_paragraph if id(p) in skip_ids
        ]
        if not to_skip:
            return original_term_page(extractor, page, executor, pbar, tracker)
        if pbar is not None:
            pbar.advance(len(to_skip))
        return original_term_page(
            extractor, _page_without(page, skip_ids), executor, pbar, tracker
        )

    ILTranslator.translate = plain_translate
    ILTranslator.process_page = plain_page
    ILTranslatorLLMOnly.translate = translate
    ILTranslatorLLMOnly._should_translate_paragraph = should_translate
    ILTranslatorLLMOnly.process_page = process_page
    AutomaticTermExtractor.procress = term_run
    AutomaticTermExtractor.process_page = term_page

    def restore():
        ILTranslator.translate = original_plain_translate
        ILTranslator.process_page = original_plain_page
        ILTranslatorLLMOnly.translate = original_translate
        ILTranslatorLLMOnly._should_translate_paragraph = original_should
        ILTranslatorLLMOnly.process_page = original_page
        AutomaticTermExtractor.procress = original_term_run
        AutomaticTermExtractor.process_page = original_term_page

    return restore
