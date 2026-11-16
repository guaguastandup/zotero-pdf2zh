"""Detect PDFs whose math is typeset with MathType / Advance fonts.

BabelDOC decides whether a text run is a formula by font name. Its default
broad pattern misses some ``AdvMacMth*`` / ``AdvP4C4E*`` / ``AdvEls-*``
/ ``AdvPi*`` families, so affected glyph runs can reach the language model as
prose. Their broken ToUnicode mappings then turn math into garbage (radical
rules even become literal ``ffi`` runs) and the translated PDF shows ``f``/``ffi``
noise. Adding the detected families to the formula pattern keeps them out of
translation, so the original math glyphs survive.

Everything here is plain data so it stays testable without pdf2zh-next.
"""
import base64
import re

# BabelDOC's broad defaults in the three explicitly validated versions.
# 0.7.1 runs formula classification in Rust, so a Python function hook is
# insufficient. Carry defaults forward when supplying the configuration regex.
DEFAULT_BROAD_PATTERN = (
    r'(CM[^RB]|(MS|XY|MT|BL|RM|EU|LA|RS)[A-Z]|LINE|LCIRCLE|TeX-'
    r'|rsfs|txsy|wasy|stmary|.*Mono|.*Code|.*Sym|.*Math'
    r'|AdvP4C4E74|AdvPSSym|AdvP4C4E59)'
)


def extend_native_pattern(additions):
    return DEFAULT_BROAD_PATTERN[:-1] + '|' + '|'.join(
        re.escape(name) + (r'(?:-.*)?$' if name == 'ZoteroMathItalic' else '$')
        for name in sorted(additions)) + ')'

# Fonts that MathType and Advanced Grafx emit for math symbols / extensions.
# Body text uses the separate ``AdvOT*`` (Times) families and must not match.
SUSPECT = re.compile(
    r'^(AdvMacMth.*|AdvP4C4E.*|AdvEls-.*|AdvPi.*|AdvPSSym.*|MathType.*|MTExtra.*)$'
)

# Characters a broken math-font ToUnicode mapping produces in extracted text.
SUSPICIOUS_CHARS = '\uFB03\u00BC\u00D0\u00F0\u00DE\u00FE'


def base_name(font_name):
    """Return the family name the engine matches on (``subset+Name`` -> ``Name``)."""
    name = str(font_name or '').strip()
    if not name:
        return ''
    if name.startswith('BASE64:'):
        try:
            name = base64.b64decode(name[7:]).decode('latin-1')
        except Exception:
            return ''
    parts = [part.strip() for part in name.split('+') if part.strip()]
    return parts[-1] if parts else ''


def detect(font_names):
    """Base names of suspicious math fonts, order preserved and deduplicated."""
    hits = []
    for name in font_names or ():
        base = base_name(name)
        if base and SUSPECT.match(base) and base not in hits:
            hits.append(base)
    return hits


def suspicious_chars(text):
    """Count chars that usually mean a math font has no usable ToUnicode."""
    value = str(text or '')
    return sum(value.count(char) for char in SUSPICIOUS_CHARS)


def tex_roman_math_fonts(doc, indices):
    """Protect CMR operators only when that family is not also used for prose.

    CMR is normally excluded by BabelDOC because LaTeX documents may use it for
    their entire body. In Times-body papers it often contains only formula
    digits, parentheses, and roman operators such as exp. Leaving exp as prose
    splits fractions and prevents their rules from attaching to the formula.
    Inspect every selected page before deciding at document scope.
    """
    operators = {'exp', 'log', 'ln', 'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
                 'sinh', 'cosh', 'tanh', 'min', 'max', 'lim', 'sup', 'inf',
                 'arg', 'det', 'dim', 'ker', 'Pr', 'Var', 'Cov', 'Norm',
                 'diag', 'rank', 'softmax', 'sigmoid', 'ReLU'}
    prose_short = {'a', 'an', 'as', 'at', 'be', 'by', 'do', 'he', 'if',
                   'in', 'is', 'it', 'of', 'on', 'or', 'so', 'to', 'up', 'we'}
    seen, prose = set(), set()
    try:
        for index in indices:
            for block in doc[index].get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        name = base_name(span['font'])
                        if not re.fullmatch(r'CMR\d+', name) or not span['text'].strip():
                            continue
                        seen.add(name)
                        words = re.findall(r'[A-Za-z]+', span['text'])
                        if any((len(word) > 2 or (len(word) == 2 and word in prose_short))
                               and word not in operators for word in words):
                            prose.add(name)
    except Exception:
        return []  # An incomplete scan cannot establish that a font is math-only.
    return sorted(seen - prose)


def diagnostics(font_names, char_hits=0):
    families = detect(font_names)
    return {
        'mathFonts': families,
        'formulaProtected': bool(families),
        'suspiciousChars': int(char_hits or 0),
    }
