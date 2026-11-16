"""Protect isolated Advance italic variables without protecting italic prose.

Work on the disposable input copy only. A font switch containing exactly one
ASCII letter in an AdvOT*.I font is a variable candidate. Give that run a
separate font resource (same embedded glyphs and metrics) so BabelDOC can keep
it together with adjacent math symbols. Whole italic words keep their font.
"""
import re
from pathlib import Path

ITALIC = re.compile(r'^(?:[A-Z]{6}\+)?AdvOT[^+]*\.I(?:\+\w+)?$')
PROTECTED_PREFIX = 'ZoteroMathItalic'


def variable_run(operations):
    """Return whether a font run contains just one literal ASCII variable."""
    text = bytearray()
    for args, op in operations:
        if op == b'Tj':
            values = args[:1]
        elif op == b'TJ':
            values = args[0]
        elif op in (b"'", b'"'):
            return False  # line-moving text operators need their own treatment
        else:
            continue
        for value in values:
            if isinstance(value, (str, bytes)):
                try:
                    data = value.original_bytes if isinstance(value, str) else value
                except AttributeError:
                    data = value.encode('latin-1')
                text.extend(data)
    return bool(re.fullmatch(rb'[A-Za-z]', bytes(text).strip()))


def protect_variables(path, page_indices):
    """Return the number of protected runs; preserve input bytes if none match."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ContentStream, DictionaryObject, NameObject

    path = Path(path)
    reader = PdfReader(path)
    writer = PdfWriter(clone_from=reader)
    count = 0
    for index in page_indices:
        page = writer.pages[index]
        resources = page.get('/Resources')
        if resources is None:
            continue
        resources = resources.get_object()
        fonts = resources.get('/Font')
        if fonts is None:
            continue
        fonts = fonts.get_object()
        candidates = {name for name, ref in fonts.items()
                      if ITALIC.fullmatch(str(ref.get_object().get('/BaseFont', ''))[1:])}
        if not candidates:
            continue
        # Resource dictionaries can be shared with unselected pages.
        resources = DictionaryObject(resources)
        fonts = DictionaryObject(fonts)
        resources[NameObject('/Font')] = fonts
        page[NameObject('/Resources')] = resources
        content = ContentStream(page.get_contents(), writer)
        operations = content.operations
        aliases = {}
        restores = []
        for pos, (args, op) in enumerate(operations):
            if op != b'Tf' or args[0] not in candidates:
                continue
            end = pos + 1
            while end < len(operations) and operations[end][1] not in (b'Tf', b'ET', b'BT', b'q', b'Q', b'Do'):
                end += 1
            # Only change a run that ends with a font reset or text-object end.
            # This avoids leaking our alias through a graphics-state save.
            if end == len(operations) or operations[end][1] not in (b'Tf', b'ET'):
                continue
            if not variable_run(operations[pos + 1:end]):
                continue
            original = args[0]
            if original not in aliases:
                alias = NameObject('/' + PROTECTED_PREFIX + str(len(aliases)))
                while alias in fonts:
                    alias = NameObject(str(alias) + '_')
                font = DictionaryObject(fonts[original].get_object())
                font[NameObject('/BaseFont')] = NameObject(f'/{PROTECTED_PREFIX}-{index}-{len(aliases)}')
                descriptor = font.get('/FontDescriptor')
                if descriptor is not None:
                    descriptor = DictionaryObject(descriptor.get_object())
                    descriptor[NameObject('/FontName')] = font[NameObject('/BaseFont')]
                    font[NameObject('/FontDescriptor')] = writer._add_object(descriptor)
                fonts[alias] = writer._add_object(font)
                aliases[original] = alias
            operations[pos] = ([aliases[original], args[1]], op)
            if operations[end][1] == b'ET':
                # BT/ET do not reset the current font in the PDF text state.
                restores.append((end, ([original, args[1]], b'Tf')))
            count += 1
        if aliases:
            for end, operation in reversed(restores):
                operations.insert(end, operation)
            page.replace_contents(content)
    if count:
        temp = path.with_suffix('.math.tmp.pdf')
        try:
            writer.write(temp)
            reader.close()
            writer.close()
            temp.replace(path)
        finally:
            if temp.exists():
                temp.unlink()
    else:
        reader.close()
        writer.close()
    return count
