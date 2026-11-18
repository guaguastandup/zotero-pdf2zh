"""漏翻检测与自动补译。

背景（为什么会漏翻）
--------------------
pdf2zh_next 会把待译正文切成片段、按批提交给翻译服务。若某个批次的请求失败
（免费端点限流 / 超时 / 连接被重置），该批次里的片段既不会写进翻译缓存，也不会
报错中断整个任务，最终排版时只能"保留原文"——于是就出现某一整段、或某一段的
尾部仍是英文的情况。由于失败片段没有进缓存，重跑一次时这些片段会被重新请求，
而已翻译的片段直接命中缓存，所以补译的代价通常只有一次版面解析的时间。

本模块在翻译结束后做三件事：
1. 漏翻自检：逐块比对译文页与原文页，找出"文字仍是原文、位置却在译文页"的段落；
2. 自动补译：发现漏翻就按原命令重跑引擎，最多 max_attempts 次；
3. 兜底：若上一次重跑没有任何改善，最后一次重跑追加 --ignore-cache，避免命中
   缓存里已经被污染（返回原文）的结果。
"""

from __future__ import annotations

import re
from pathlib import Path

try:  # PyMuPDF 新版本改名为 pymupdf，fitz 仍可用但不推荐
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz

# 参考文献标题：其后的页面默认不翻译，不能算漏翻
_REFERENCE_HEADING = re.compile(
    r'^\s*(references|reference|bibliography|literature cited|参考文献|參考文獻)\s*$',
    re.IGNORECASE | re.MULTILINE,
)

# 中文字符（含中文标点区之外的常用汉字）
_CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
)

DEFAULT_MIN_BLOCK_CHARS = 80    # 少于这个字符数的块（页眉、编号、公式）不参与判断
DEFAULT_PAGE_MIN_CHARS = 120    # 一页里"原文残留"累计超过这个字符数才算漏翻
DEFAULT_MIN_WIDTH_RATIO = 0.28  # 块宽至少占页宽的比例，用来排除表格单元格


def _normalize(text: str) -> str:
    """归一化：合并空白、还原合字，便于跨行比较。"""
    if not text:
        return ''
    text = (
        text.replace('\ufb01', 'fi')
        .replace('\ufb02', 'fl')
        .replace('\ufb00', 'ff')
        .replace('\u00ad', '')
        .replace('\u00a0', ' ')
    )
    return re.sub(r'\s+', ' ', text).strip()


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    hits = 0
    for ch in text:
        code = ord(ch)
        for low, high in _CJK_RANGES:
            if low <= code <= high:
                hits += 1
                break
    return hits / len(text)


def _latin_letter_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    latin = sum(1 for ch in letters if ch.isascii())
    return latin / len(letters)


def _page_texts(doc):
    return [_normalize(page.get_text()) for page in doc]


def _reference_start_index(source_doc) -> int:
    """原文里参考文献标题出现的页码（0 基）；找不到返回 -1。

    注意必须用带换行的原始文本匹配，归一化后的文本没有行结构，会漏判。
    """
    for index, page in enumerate(source_doc):
        raw = page.get_text()
        if not raw:
            continue
        head, tail = raw[:600], raw[-1200:]
        # 标题可能在页首（单独成页）也可能在页中，取整页判断
        if _REFERENCE_HEADING.search(head) or _REFERENCE_HEADING.search(tail):
            return index
    return -1


def _block_is_untranslated(block_text: str, source_norm: str) -> bool:
    block_text = _normalize(block_text)
    if len(block_text) < DEFAULT_MIN_BLOCK_CHARS:
        return False
    # 已经含中文的块不再处理
    if _cjk_ratio(block_text) > 0.15:
        return False
    if _latin_letter_ratio(block_text) < 0.55:
        return False
    # 主判据：这段文字在原文页里能原样找到，说明排版时保留了原文字形
    probe = block_text[:100]
    if probe and probe in source_norm:
        return True
    # 兜底：长英文句子（避免把表格数值、地址、代码当成漏翻）
    words = block_text.split()
    if len(words) >= 25 and block_text.count('. ') >= 1 and block_text.endswith(('.', '。')):
        return True
    return False


def _is_body_block(block, page_width: float, min_width_ratio: float) -> bool:
    """正文段落是"宽块 + 多行"；表格单元格、竖排表头、页边注都是窄块。"""
    if page_width <= 0:
        return True
    width = block[2] - block[0]
    height = block[3] - block[1]
    if width < page_width * min_width_ratio:
        return False
    return height >= 24


def detect_untranslated_pages(
    source_pdf: str,
    target_pdf: str,
    skip_last_pages: int = 0,
    min_block_chars: int = DEFAULT_MIN_BLOCK_CHARS,
    page_min_chars: int = DEFAULT_PAGE_MIN_CHARS,
    min_width_ratio: float = DEFAULT_MIN_WIDTH_RATIO,
) -> list[int]:
    """返回译文里仍然保留原文的页码（1 基）。"""
    source_path = Path(source_pdf)
    target_path = Path(target_pdf)
    if not source_path.exists() or not target_path.exists():
        return []
    if source_path.suffix.lower() != '.pdf' or target_path.suffix.lower() != '.pdf':
        return []

    with fitz.open(str(source_path)) as source_doc, fitz.open(str(target_path)) as target_doc:
        # 只有在"译文页数与原文一一对应"时才能逐页比对（如 only_include_translated_page
        # 会把未翻译页删掉，此时直接跳过自检）
        if len(target_doc) != len(source_doc):
            return []
        source_texts = _page_texts(source_doc)
        ref_start = _reference_start_index(source_doc)
        limit = len(target_doc)
        if skip_last_pages and skip_last_pages > 0:
            limit = max(0, limit - skip_last_pages)

        dirty_pages: list[int] = []
        for index in range(min(limit, len(source_texts))):
            if ref_start >= 0 and index >= ref_start:
                # 参考文献默认不翻译，不视为漏翻
                break
            source_norm = source_texts[index]
            if not source_norm:
                continue
            residual = 0
            page_width = target_doc[index].rect.width
            for block in target_doc[index].get_text('blocks'):
                if len(block) < 7 or block[6] != 0:
                    continue  # 非文本块（图片）
                if not _is_body_block(block, page_width, min_width_ratio):
                    continue
                block_text = _normalize(block[4])
                if len(block_text) < min_block_chars:
                    continue
                if _block_is_untranslated(block_text, source_norm):
                    residual += len(block_text)
            if residual >= page_min_chars:
                dirty_pages.append(index + 1)
        return dirty_pages


def pick_mono_pdf(paths) -> str | None:
    """从输出文件里挑出单页译文版（mono）；没有则返回 None。"""
    for path in paths:
        name = Path(path).name.lower()
        if name.endswith('.mono.pdf'):
            return path
    return None


def _format_pages(pages) -> str:
    return '、'.join(str(p) for p in pages[:20]) + ('…' if len(pages) > 20 else '')


def repair_translation_gaps(
    command,
    source_pdf: str,
    output_paths,
    run_command,
    max_attempts: int = 2,
    skip_last_pages: int = 0,
    ignore_cache_last: bool = False,
    log=print,
) -> list[int]:
    """检测漏翻并重跑引擎补译。返回补译后仍然漏翻的页码（1 基）。

    command           : 首次成功执行过的引擎命令（list）
    output_paths      : 首次生成的产物路径（用于定位 mono 译文）
    run_command       : 以命令 list 为参数、执行引擎的可调用对象
    max_attempts      : 最多补译次数（不含首轮）
    ignore_cache_last : 最后一次重跑是否追加 --ignore-cache。默认关闭：失败批次本就
                        没有进缓存，带缓存重跑即可补齐，代价只是版面重排；打开后会
                        重新请求全部片段，可修掉"模型返回原文并被缓存"的情况，但很慢。
    """
    mono = pick_mono_pdf(output_paths)
    if not mono:
        # 只看得到双页对照版时无法可靠定位原文残留，交由用户处理
        return []

    try:
        dirty = detect_untranslated_pages(
            source_pdf, mono, skip_last_pages=skip_last_pages
        )
    except Exception as error:  # 检测本身不能影响主流程
        log(f'⚠️ 漏翻自检跳过：{error}')
        return []

    if not dirty:
        return []

    log(
        f'⚠️ 漏翻自检：第 {_format_pages(dirty)} 页仍保留原文段落，'
        f'开始自动补译（最多 {max_attempts} 次）'
    )

    attempt = 0
    while dirty and attempt < max_attempts:
        attempt += 1
        retry_cmd = list(command)
        force_ignore_cache = (
            ignore_cache_last
            and attempt >= 2
            and '--ignore-cache' not in retry_cmd
        )
        if force_ignore_cache:
            retry_cmd.append('--ignore-cache')
        log(
            f'🔁 第 {attempt}/{max_attempts} 次补译'
            + ('（忽略翻译缓存，重新请求全部片段，耗时较长）'
               if force_ignore_cache
               else '（复用缓存，只重新请求缺失片段）')
        )
        try:
            run_command(retry_cmd)
        except Exception as error:
            log(f'⚠️ 补译进程失败，保留已有结果：{error}')
            break

        previous = dirty
        try:
            dirty = detect_untranslated_pages(
                source_pdf, mono, skip_last_pages=skip_last_pages
            )
        except Exception as error:
            log(f'⚠️ 补译后自检失败：{error}')
            break
        if dirty and len(dirty) >= len(previous):
            log('   ↳ 本次补译没有减少漏翻页，继续重试')
        elif dirty:
            log(f'   ↳ 漏翻页减少到：第 {_format_pages(dirty)} 页')

    if dirty:
        log(
            f'⚠️ 仍有第 {_format_pages(dirty)} 页存在漏翻。可在插件设置里勾选'
            f'"忽略缓存"后重新翻译，或把翻译服务换成更稳定的接口（如 OpenAI / DeepSeek / 智谱）。'
        )
    else:
        log('✅ 漏翻自检通过：译文页面已无原文残留')
    return dirty
