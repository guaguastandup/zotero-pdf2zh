"""No-API probe of the real formula classifier in a spawned engine worker."""
import multiprocessing
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
profile = tempfile.TemporaryDirectory(prefix="pdf2zh-math-test-")
profile_path = Path(profile.name)
original_expanduser = Path.expanduser
with patch.object(Path, "home", return_value=profile_path), patch.object(
    Path, "expanduser", lambda path: profile_path / str(path)[2:]
    if str(path).startswith("~/") else original_expanduser(path)
):
    from pdf2zh_next import high_level
    from babeldoc.format.pdf.document_il.utils import formular_helper
from utils import math_compat, table_process

native_font = formular_helper.is_formulas_font


def config(*args, **kwargs):
    return SimpleNamespace()


def prepare(value):
    from utils.math_fonts import extend_native_pattern
    value.formular_font_pattern = extend_native_pattern({"ZoteroMathItalic"})
    return None, {"ZoteroMathItalic"}, {}


def worker(queue):
    value = high_level.create_babeldoc_config()
    queue.put((formular_helper.is_formulas_font("ZoteroMathItalic-0-0", value.formular_font_pattern),
               formular_helper.is_formulas_font("Arial", value.formular_font_pattern)))


# Replayed by spawn. Only the process policy installs the real classifier hook.
high_level.create_babeldoc_config = config
high_level._translate_wrapper = worker
math_compat.prepare_input = prepare


if __name__ == "__main__":
    context = multiprocessing.get_context(sys.argv[1])
    queue = context.Queue()
    restore = table_process.install_table_process_policy(None, math_compat=True)
    try:
        child = context.Process(target=high_level._translate_wrapper, args=(queue,))
        child.start()
        assert queue.get(timeout=30) == (True, False)
        child.join(timeout=30)
        assert child.exitcode == 0
        worker(queue)
        assert queue.get(timeout=5) == (True, False)
    finally:
        restore()
        queue.close()
        queue.join_thread()
    assert high_level._translate_wrapper is worker
    assert high_level.create_babeldoc_config is config
    assert formular_helper.is_formulas_font is native_font
