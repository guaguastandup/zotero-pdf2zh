"""Install the table adapter in both CLI and spawned translation processes."""

from functools import partial

from utils.table_runtime import (
    install_table_policy,
    table_policy_supported,
    warn_native_table_fallback,
)
from utils.table_mode import parse_table_mode

_native_worker = None
_parent_restore = None


def _run_table_worker(mode, *args, **kwargs):
    # Under spawn this module starts fresh and the engine still has its native
    # target. Under fork, use the saved target and undo inherited policy hooks
    # before installing fresh per-document state in this child.
    from pdf2zh_next import high_level

    native = _native_worker or high_level._translate_wrapper
    if _parent_restore is not None:
        _parent_restore()
    restore = install_table_policy(mode)
    try:
        return native(*args, **kwargs)
    finally:
        restore()


def install_table_process_policy(mode):
    parse_table_mode(mode)
    if not table_policy_supported():
        warn_native_table_fallback()
        return lambda: None
    from pdf2zh_next import high_level

    global _native_worker, _parent_restore
    if _native_worker is not None:
        raise RuntimeError("Table process policy is already installed")
    # Also covers the engine's explicit debug/in-process path and validates the
    # supported engine API before any translation request is sent.
    restore_policy = install_table_policy(mode)
    native = high_level._translate_wrapper
    _native_worker, _parent_restore = native, restore_policy
    high_level._translate_wrapper = partial(_run_table_worker, mode)

    def restore():
        global _native_worker, _parent_restore
        high_level._translate_wrapper = native
        _native_worker = _parent_restore = None
        restore_policy()

    return restore
