"""Observe Flash hook installation in real fork/spawn worker processes."""

import json
import multiprocessing
import os
import sys
from types import ModuleType

from utils import table_process

STATE = {"flash_hooks": 0}


def install_flash():
    STATE["flash_hooks"] += 1

    def restore():
        STATE["flash_hooks"] -= 1

    return restore


def native_worker(queue):
    queue.put({**STATE, "pid": os.getpid()})


engine = ModuleType("pdf2zh_next.high_level")
engine._translate_wrapper = native_worker
package = ModuleType("pdf2zh_next")
package.high_level = engine
sys.modules["pdf2zh_next"] = package
sys.modules["pdf2zh_next.high_level"] = engine
table_process.install_deepseek_flash_patch = install_flash


def main():
    ctx = multiprocessing.get_context(sys.argv[1])
    queue = ctx.Queue()
    restore = table_process.install_table_process_policy(
        None, flash_patch=True
    )
    try:
        child = ctx.Process(target=engine._translate_wrapper, args=(queue,))
        child.start()
        result = queue.get(timeout=20)
        child.join(timeout=20)
        assert child.exitcode == 0, child.exitcode
        assert result == {"flash_hooks": 1, "pid": child.pid}, result
        assert child.pid != os.getpid()
        # Debug/in-process path remains patched in the parent as well.
        native_worker(queue)
        assert queue.get(timeout=5)["flash_hooks"] == 1
        assert STATE["flash_hooks"] == 1
    finally:
        restore()
        queue.close()
        queue.join_thread()
    assert engine._translate_wrapper is native_worker
    assert STATE["flash_hooks"] == 0
    print(json.dumps(result))


if __name__ == "__main__":
    main()
