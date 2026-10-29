"""Keep native LLM batching, with body/table boundaries added before batching."""

import copy
from itertools import groupby


def paragraph_group(paragraph):
    if paragraph.layout_label == "table_text":
        # Layout IDs are page-local. The caller groups one page at a time.
        # Missing IDs must not accidentally combine unrelated table fragments.
        table_id = paragraph.layout_id
        return "table", table_id if table_id is not None else id(paragraph)
    return "body", None


class _PageExecutor:
    """Submit native batches with the real page, including for async fallback."""

    def __init__(self, executor, page):
        self.executor = executor
        self.page = page

    def submit(self, function, batch, *args, **kwargs):
        # A shallow page view only limits native batch construction. Workers
        # must see the original page so any fallback annotations are retained.
        batch.pages = [self.page] * len(batch.paragraphs)
        return self.executor.submit(function, batch, *args, **kwargs)


def process_page_in_table_batches(
    native_process_page, translator, page, executor, *args, **kwargs
):
    if not any(p.layout_label == "table_text" for p in page.pdf_paragraph):
        return native_process_page(translator, page, executor, *args, **kwargs)

    for _, paragraphs in groupby(page.pdf_paragraph, key=paragraph_group):
        view = copy.copy(page)
        view.pdf_paragraph = list(paragraphs)
        native_process_page(
            translator, view, _PageExecutor(executor, page), *args, **kwargs
        )
