"""Opt-in, process-local compatibility for legacy math fonts and TeX rules.

Adapted from csukingzq/dsh-pdf-translator (AGPL-3.0), November 2026.
Only disposable inputs are changed. Installed engines and user PDFs stay intact.
"""
import logging
import shutil
import tempfile
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from utils import math_fonts, math_variables, math_rules

FLAG = "--zotero-math-compat"
SUPPORTED = {("2.9.0", "0.6.2"), ("2.9.0", "0.6.4"), ("2.10.2", "0.7.1")}
logger = logging.getLogger(__name__)


def policy_supported():
    try:
        return (version("pdf2zh-next"), version("BabelDOC")) in SUPPORTED
    except PackageNotFoundError:
        return False


def warn_native_fallback():
    logger.warning("数学兼容模式尚未验证当前引擎版本；使用原生处理，不修改 PDF 或已安装引擎。")


def prepare_input(config):
    """Return a temporary-directory handle, font additions and diagnostic counts."""
    import pymupdf

    # Explicit font patterns retain their original semantics, including callers
    # intentionally opting a family out. A forced OCR workaround rewrites the
    # page and is out of scope. auto_enable_ocr_workaround is only permission
    # for the engine to OCR a page after scan detection; the plugin turns it on
    # for ordinary PDFs, so treating it as "this file is scanned" would make
    # the opt-in checkbox do nothing.
    if config.formular_font_pattern or config.ocr_workaround:
        return None, set(), {}
    source = Path(config.input_file)
    with pymupdf.open(source) as doc:
        indices = [i for i in range(len(doc)) if config.should_translate_page(i + 1)]
        fonts = {font[3] for i in indices for font in doc[i].get_fonts(full=True)}
        additions = set(math_fonts.detect(fonts))
        roman = set(math_fonts.tex_roman_math_fonts(doc, indices))
    tex = math_rules.has_tex_math(fonts)
    # The Python 0.6.x typesetter still separates some Advance radical pieces
    # after reclassification. Keep those documents native until that backend
    # has equivalent formula placement; do not advertise font detection as a
    # complete fix on a backend that fails the visual regression case.
    if additions and version("BabelDOC") != "0.7.1":
        message = (
            f"Advance/MathType 字体兼容需 BabelDOC 0.7.1；"
            f"当前是 {version('BabelDOC')}，本次整篇保持原生处理，不修改 PDF。"
        )
        logger.warning(message)
        print(f"⚠️ {message}")
        return None, set(), {}
    if not additions and not tex and not roman:
        return None, set(), {}
    temporary = tempfile.TemporaryDirectory(prefix="zotero-math-")
    target = Path(temporary.name) / source.name
    try:
        shutil.copyfile(source, target)
        variables = math_variables.protect_variables(target, indices) if additions else 0
        rules = math_rules.normalize_rules(target, indices) if tex else 0
        if variables:
            additions.add(math_variables.PROTECTED_PREFIX)
        additions.update(roman)
        if additions:
            config.formular_font_pattern = math_fonts.extend_native_pattern(additions)
        config.input_file = target
        # Some legacy Advance pages label prose with radicals as a display
        # equation. Font protection alone cannot correct those layout regions.
        if math_fonts.detect(fonts):
            from utils.math_layout import MathLayoutModel
            config.doc_layout_model = MathLayoutModel(config.doc_layout_model)
        info = {"variable_runs": variables, "rule_lines": rules, "font_families": sorted(additions)}
        logger.info("Math compatibility: %s", info)
        return temporary, additions, info
    except BaseException:
        temporary.cleanup()
        raise


def install_math_policy():
    """Supply engine configuration and restore the adapter after the PDF job."""
    if not policy_supported():
        warn_native_fallback()
        return lambda: None
    from pdf2zh_next import high_level
    native_config = high_level.create_babeldoc_config
    temporary_inputs = []

    def create_config(*args, **kwargs):
        config = native_config(*args, **kwargs)
        temporary, _, _ = prepare_input(config)
        if temporary is not None:
            temporary_inputs.append(temporary)
        return config

    high_level.create_babeldoc_config = create_config

    def restore():
        high_level.create_babeldoc_config = native_config
        for temporary in temporary_inputs:
            temporary.cleanup()
        temporary_inputs.clear()

    return restore
