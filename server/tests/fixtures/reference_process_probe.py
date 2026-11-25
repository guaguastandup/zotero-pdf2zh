"""Verify the real Rust-layout config wrapper survives engine worker startup."""
import multiprocessing
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
profile = tempfile.TemporaryDirectory(prefix="pdf2zh-reference-test-")
profile_path = Path(profile.name)
original_expanduser = Path.expanduser
with patch.object(Path, "home", return_value=profile_path), patch.object(
    Path, "expanduser", lambda path: profile_path / str(path)[2:]
    if str(path).startswith("~/") else original_expanduser(path)
):
    from pdf2zh_next import high_level
    from babeldoc import rust_layout_service
from utils import table_process
from utils.reference_layout import ReferenceLayoutModel


class Model:
    stride = 32


def config(*args, **kwargs):
    return SimpleNamespace(doc_layout_model=Model())


def worker(queue):
    value = high_level.create_babeldoc_config()
    queue.put((isinstance(value.doc_layout_model, ReferenceLayoutModel),
               value.doc_layout_model.stride))


high_level.create_babeldoc_config = config
high_level._translate_wrapper = worker
native_needs_characters = rust_layout_service.needs_characters

if __name__ == '__main__':
    context = multiprocessing.get_context(sys.argv[1])
    queue = context.Queue()
    restore = table_process.install_table_process_policy(None, reference_skip=True)
    try:
        child = context.Process(target=high_level._translate_wrapper, args=(queue,))
        child.start()
        assert queue.get(timeout=30) == (True, 32)
        child.join(timeout=30)
        assert child.exitcode == 0
        worker(queue)
        assert queue.get(timeout=5) == (True, 32)
    finally:
        restore()
        queue.close()
        queue.join_thread()
    assert high_level.create_babeldoc_config is config
    assert high_level._translate_wrapper is worker
    assert rust_layout_service.needs_characters is native_needs_characters
