"""Dependency-free engine double for real multiprocessing start-method tests."""

import json
import multiprocessing
import os
import sys
from types import ModuleType

from utils import table_process

STATE = {"mode": None, "installs": 0}


def policy(mode):
    STATE["mode"] = mode
    STATE["installs"] += 1

    def restore():
        STATE["mode"] = None
        STATE["installs"] -= 1

    return restore


def native_worker(queue):
    queue.put({**STATE, "pid": os.getpid()})


# This setup also runs when spawn reimports the main module. It supplies an
# engine double, not an installed policy: that is the worker adapter's job.
engine = ModuleType("pdf2zh_next.high_level")
engine._translate_wrapper = native_worker
package = ModuleType("pdf2zh_next")
package.high_level = engine
sys.modules["pdf2zh_next"] = package
sys.modules["pdf2zh_next.high_level"] = engine
table_process.install_table_policy = policy
table_process.table_policy_supported = lambda: True


def main():
    context = multiprocessing.get_context(sys.argv[1])
    queue = context.Queue()
    restore = table_process.install_table_process_policy("fixed")
    try:
        child = context.Process(target=engine._translate_wrapper, args=(queue,))
        child.start()
        result = queue.get(timeout=20)
        child.join(timeout=20)
        assert child.exitcode == 0, child.exitcode
        assert result == {"mode": "fixed", "installs": 1, "pid": child.pid}, result
        assert child.pid != os.getpid()
        # The debug/in-process path is covered by the parent's own policy.
        native_worker(queue)
        assert queue.get(timeout=5)["mode"] == "fixed"
        assert STATE["installs"] == 1
    finally:
        restore()
        queue.close()
        queue.join_thread()
    assert engine._translate_wrapper is native_worker
    assert STATE == {"mode": None, "installs": 0}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
