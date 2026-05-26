import re


GREEK_SYMBOLS = {
    "alpha": "\u03b1",
    "beta": "\u03b2",
    "gamma": "\u03b3",
    "delta": "\u03b4",
    "epsilon": "\u03b5",
    "lambda": "\u03bb",
    "mu": "\u03bc",
    "pi": "\u03c0",
    "sigma": "\u03c3",
    "tau": "\u03c4",
    "theta": "\u03b8",
    "omega": "\u03c9",
    "Delta": "\u0394",
    "Gamma": "\u0393",
    "Lambda": "\u039b",
    "Omega": "\u03a9",
}

LATEX_TEXT_SYMBOLS = {
    "neq": "\u2260",
    "ne": "\u2260",
    "leq": "\u2264",
    "le": "\u2264",
    "geq": "\u2265",
    "ge": "\u2265",
    "in": "\u2208",
    "notin": "\u2209",
    "sum": "\u2211",
    "cdot": "\u00b7",
    "times": "\u00d7",
    "pm": "\u00b1",
    "to": "\u2192",
    "rightarrow": "\u2192",
    "leftarrow": "\u2190",
    "mid": "|",
}


def normalize_latex_for_text(text):
    text = repair_latex_text(text)
    text = normalize_inline_math(text)
    text = strip_math_delimiters(text)
    text = strip_latex_environments(text)
    text = normalize_latex_commands(text)
    text = normalize_simple_fractions(text)
    text = normalize_dot_commands(text)
    text = normalize_scripts(text)
    text = text.replace("\\{", "{").replace("\\}", "}")
    text = strip_latex_sizing_commands(text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\s+([,.;:，。；：、])", r"\1", text)
    text = re.sub(r"([({\[])\s+", r"\1", text)
    text = re.sub(r"\s+([)}\]])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_latex_for_mathtext(text):
    text = repair_latex_text(text)
    text = strip_math_delimiters(text)
    text = text.replace("\\\\", "\n")
    text = strip_latex_environments(text)
    text = compact_math_commands(text)
    text = re.sub(r"\\tag\s*\{\s*([^{}]+)\s*\}", r"\\qquad(\1)", text)
    text = strip_latex_sizing_commands(text)
    text = text.replace("&", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\s*([_=+\-*/(),{}])\s*", r"\1", text)
    text = re.sub(r"([A-Za-z0-9)}])\s*([_^])\s*([A-Za-z0-9])", r"\1\2{\3}", text)
    text = unwrap_outer_braces(text.strip())
    return text.strip(" $`")


def mathtext_lines(text, max_chars=82):
    text = clean_latex_for_mathtext(text)
    if not text:
        return []
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not raw_lines:
        raw_lines = [text]
    lines = []
    for line in raw_lines:
        lines.extend(split_long_math_line(line, max_chars=max_chars))
    return lines


def looks_like_math_text(text):
    text = str(text or "").strip()
    if not text:
        return False
    latex_hits = len(re.findall(
        r"\\(?:frac|sum|mathcal|mathbb|mathrm|text|alpha|beta|lambda|tau|dot|hat|tilde|min|max|begin|end|left|right)",
        text,
    ))
    script_hits = len(re.findall(r"[A-Za-z0-9)}]\s*[_^]\s*(?:\{|[A-Za-z0-9])", text))
    broken_hits = len(re.findall(r"\b(?:egin|rac)\s*\{", text))
    return latex_hits + script_hits + broken_hits > 0


def is_display_math_line(text):
    stripped = str(text or "").strip()
    if not stripped or is_markdown_non_math_line(stripped):
        return False
    if stripped.startswith("`") and stripped.endswith("`"):
        return is_standalone_math_expression(stripped.strip("`").strip())
    if stripped.startswith("$$") and stripped.endswith("$$"):
        return is_standalone_math_expression(stripped[2:-2].strip())
    return is_standalone_math_expression(stripped, allow_plain=False)


def display_math_from_line(text):
    stripped = str(text or "").strip()
    if stripped.startswith("$$") and stripped.endswith("$$"):
        return stripped[2:-2].strip()
    if stripped.startswith("`") and stripped.endswith("`"):
        return stripped.strip("`").strip()
    return stripped


def is_markdown_non_math_line(text):
    stripped = str(text or "").strip()
    if stripped.startswith(("![", "#", ">", "- ", "* ", "|")):
        return True
    if re.match(r"^\d+[.)]\s+\S", stripped):
        return True
    if re.match(r"^\d+\s*:\s+\S", stripped) and re.search(r"\\text|\\leftarrow|\\rightarrow|\\gets|\b(?:for|if|return|Require|Ensure)\b", stripped):
        return True
    return False


def is_standalone_math_expression(text, allow_plain=True):
    stripped = str(text or "").strip()
    if len(stripped) < 3 or contains_cjk(stripped):
        return False
    if re.search(r"https?://", stripped):
        return False
    if not looks_like_math_text(stripped):
        return False

    latex_command_count = len(re.findall(r"\\[A-Za-z]+", stripped))
    if latex_command_count == 0 and looks_like_path_text(stripped):
        return False
    operator_count = len(re.findall(r"[=+\-*/^_]", stripped))
    math_chars = sum(1 for char in stripped if char.isalnum() or char in "\\{}_^=+-*/(),.[]|: ")
    math_density = math_chars / max(1, len(stripped))
    if not allow_plain and latex_command_count < 1:
        return False
    if latex_command_count + operator_count < 2:
        return False
    return math_density > 0.86


def looks_like_path_text(text):
    stripped = str(text or "").strip()
    if re.search(r"\.(?:png|jpe?g|gif|webp|pdf|md|json|zip)\b", stripped, flags=re.I):
        return True
    return bool(re.search(r"(?:^|[\s(])(?:[A-Za-z]:)?[./\\]?[A-Za-z0-9_. -]+[/\\][A-Za-z0-9_./\\ -]+", stripped))


def contains_cjk(text):
    return any("\u4e00" <= char <= "\u9fff" for char in str(text or ""))


def repair_latex_text(text):
    text = str(text or "")
    text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    text = text.replace("\ufe63", "-").replace("\uff0d", "-")
    text = re.sub(r"(?<![A-Za-z\\])egin\s*\{", r"\\begin{", text)
    text = re.sub(r"(?<![A-Za-z\\])end\s*\{", r"\\end{", text)
    text = re.sub(r"(?<![A-Za-z\\])rac\s*\{", r"\\frac{", text)
    text = re.sub(r"(?<![A-Za-z\\])mathrm\s*\{", r"\\mathrm{", text)
    text = re.sub(r"(?<![A-Za-z\\])mathcal\s*\{", r"\\mathcal{", text)
    text = re.sub(r"(?<![A-Za-z\\])mathsf\s*\{", r"\\mathsf{", text)
    text = re.sub(r"(?<![A-Za-z\\])mathbb\s*\{", r"\\mathbb{", text)
    text = re.sub(r"\\\s+([A-Za-z]+)", r"\\\1", text)
    return text


def normalize_inline_math(text):
    def repl(match):
        body = match.group(1).strip()
        if not body:
            return ""
        return normalize_latex_fragment_for_text(body)

    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\$([^$\n]+)\$", repl, text)
    return text


def normalize_latex_fragment_for_text(text):
    text = repair_latex_text(text)
    text = strip_latex_environments(text)
    text = normalize_latex_commands(text)
    text = normalize_simple_fractions(text)
    text = normalize_dot_commands(text)
    text = normalize_scripts(text)
    text = text.replace("\\{", "{").replace("\\}", "}")
    text = strip_latex_sizing_commands(text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\s+([,.;:，。；：、])", r"\1", text)
    text = re.sub(r"([({\[])\s+", r"\1", text)
    text = re.sub(r"\s+([)}\]])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_math_delimiters(text):
    text = str(text or "").strip()
    if text.startswith("$$") and text.endswith("$$") and len(text) >= 4:
        return text[2:-2].strip()
    if text.startswith("$") and text.endswith("$") and len(text) >= 2:
        return text[1:-1].strip()
    return text


def strip_latex_environments(text):
    text = re.sub(r"\\begin\s*\{\s*(?:array|aligned|align|equation|split)\s*\}\s*(?:\{[^{}]*\})?", " ", text)
    text = re.sub(r"\\end\s*\{\s*(?:array|aligned|align|equation|split)\s*\}", " ", text)
    return text


def normalize_latex_commands(text):
    text = compact_text_commands(text)
    text = re.sub(r"\\mathcal\s*\{\s*([A-Za-z])\s*\}", r"\1", text)
    text = re.sub(r"\\mathbb\s*\{\s*([A-Za-z])\s*\}", r"\1", text)
    text = re.sub(r"\\mathsf\s*\{\s*([^{}]+?)\s*\}", lambda m: compact_text_argument(m.group(1)), text)
    text = re.sub(r"\\bar\s*\{\s*([^{}]+?)\s*\}", lambda m: "bar(" + normalize_latex_fragment_for_text(m.group(1)) + ")", text)
    for name, symbol in {**GREEK_SYMBOLS, **LATEX_TEXT_SYMBOLS}.items():
        text = re.sub(rf"\\{name}(?![A-Za-z])", symbol, text)
    text = strip_latex_sizing_commands(text)
    return text


def strip_latex_sizing_commands(text):
    text = re.sub(r"\\left\s*\\\{", r"\\{", text)
    text = re.sub(r"\\right\s*\\\}", r"\\}", text)
    text = re.sub(r"\\(?:left|right)\s*\.", "", text)
    text = re.sub(r"\\(?:left|right)\s*([()\[\]|])", r"\1", text)
    return re.sub(r"\\(?:left|right)\b\s*", "", text)


def compact_text_commands(text):
    def repl(match):
        content = match.group(1).strip()
        if re.fullmatch(r"(?:[A-Za-z]\s*)+", content):
            return "".join(content.split())
        return re.sub(r"\s+", " ", content)

    previous = None
    while previous != text:
        previous = text
        text = re.sub(
            r"\\(?:mathrm|text|mathbf|mathit|mathbb|operatorname)\s*\{\s*([^{}]+?)\s*\}",
            repl,
            text,
        )
    return text


def compact_text_argument(text):
    text = str(text or "").strip()
    if re.fullmatch(r"(?:[A-Za-z]\s*)+", text):
        return "".join(text.split())
    return re.sub(r"\s+", " ", text)


def compact_math_commands(text):
    def repl(match):
        command = match.group(1)
        content = match.group(2).strip()
        if re.fullmatch(r"(?:[A-Za-z]\s*)+", content):
            content = "".join(content.split())
        else:
            content = re.sub(r"\s+", " ", content)
        if command in {"text", "operatorname"}:
            command = "mathrm"
        return f"\\{command}{{{content}}}"

    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\\(mathrm|mathcal|mathbb|mathbf|mathit|text|operatorname)\s*\{\s*([^{}]+?)\s*\}", repl, text)
    return text


def normalize_simple_fractions(text):
    return replace_two_arg_command(
        text,
        "frac",
        lambda numerator, denominator: f"({normalize_latex_for_text(numerator)})/({normalize_latex_for_text(denominator)})",
    )


def normalize_dot_commands(text):
    return replace_one_arg_command(
        text,
        "dot",
        lambda value: f"dot({normalize_latex_for_text(value)})",
    )


def normalize_scripts(text):
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"([A-Za-z0-9\u0370-\u03ff\u2200-\u22ff{}()]+)\s*_\s*\{\s*([^{}]+?)\s*\}", lambda m: f"{m.group(1)}_{compact_script(m.group(2))}", text)
        text = re.sub(r"([A-Za-z0-9\u0370-\u03ff\u2200-\u22ff{}()]+)\s*\^\s*\{\s*([^{}]+?)\s*\}", lambda m: f"{m.group(1)}^{compact_script(m.group(2))}", text)
    text = re.sub(r"\s*([_^])\s*", r"\1", text)
    return text


def compact_script(value):
    value = normalize_latex_commands(value)
    value = value.replace("{", "").replace("}", "")
    return re.sub(r"\s+", "", value)


def replace_one_arg_command(text, command, formatter):
    marker = f"\\{command}"
    result = []
    index = 0
    while index < len(text):
        start = text.find(marker, index)
        if start < 0:
            result.append(text[index:])
            break
        result.append(text[index:start])
        pos = skip_spaces(text, start + len(marker))
        arg, end = read_braced_group(text, pos)
        if arg is None:
            result.append(text[start:start + len(marker)])
            index = start + len(marker)
            continue
        result.append(formatter(arg))
        index = end
    return "".join(result)


def replace_two_arg_command(text, command, formatter):
    marker = f"\\{command}"
    result = []
    index = 0
    while index < len(text):
        start = text.find(marker, index)
        if start < 0:
            result.append(text[index:])
            break
        result.append(text[index:start])
        pos = skip_spaces(text, start + len(marker))
        first, pos = read_braced_group(text, pos)
        if first is None:
            result.append(text[start:start + len(marker)])
            index = start + len(marker)
            continue
        pos = skip_spaces(text, pos)
        second, end = read_braced_group(text, pos)
        if second is None:
            result.append(text[start:end])
            index = end
            continue
        result.append(formatter(first, second))
        index = end
    return "".join(result)


def skip_spaces(text, index):
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def read_braced_group(text, index):
    if index >= len(text) or text[index] != "{":
        return None, index
    depth = 0
    start = index + 1
    escaped = False
    for pos in range(index, len(text)):
        char = text[pos]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:pos], pos + 1
    return None, len(text)


def unwrap_outer_braces(text):
    previous = None
    text = str(text or "").strip()
    while previous != text and text.startswith("{") and text.endswith("}"):
        previous = text
        inner, end = read_braced_group(text, 0)
        if inner is None or end != len(text):
            break
        text = inner.strip()
    return text


def split_long_math_line(line, max_chars=82):
    if len(line) <= max_chars:
        return [line]
    break_points = safe_math_break_points(line)
    if not break_points:
        return [line]

    parts = []
    start = 0
    last_break = None
    for point in break_points:
        if point - start <= max_chars:
            last_break = point
            continue
        if last_break and last_break > start:
            parts.append(line[start:last_break].strip())
            start = last_break
            last_break = point if point - start <= max_chars else None
        else:
            return [line]
    tail = line[start:].strip()
    if tail:
        parts.append(tail)
    return parts if all(is_balanced_math_fragment(part) for part in parts) else [line]


def safe_math_break_points(line):
    points = []
    depth = 0
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth = max(0, depth - 1)
            continue
        if depth == 0 and char in "=+-":
            if char in "+-" and is_unary_operator(line, index):
                continue
            points.append(index + 1)
    return points


def is_unary_operator(line, index):
    if index <= 0:
        return True
    previous = line[index - 1]
    return previous in "=({[,*/+-"


def is_balanced_math_fragment(text):
    depth = 0
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0
