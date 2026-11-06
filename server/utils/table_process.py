"""Install opt-in BabelDOC policies in both CLI and spawned workers.

No global patch leaks between PDF jobs; fork children undo inherited hooks and
spawn children install their own set. Order matters when both policies are on.
"""

from functools import partial

from utils.table_runtime import (
    install_table_policy,
    table_policy_supported,
    warn_native_table_fallback,
)
from utils.table_mode import parse_table_mode
from utils.deepseek_flash_patch import install_deepseek_flash_patch
from utils.reference_skip import (
    install_reference_skip_policy,
    policy_supported as reference_policy_supported,
    warn_native_fallback as warn_reference_fallback,
)

_native_worker = None
_parent_restore = None


def _install_policies(mode, reference_skip, flash_patch=False):
    restores = []
    try:
        # This must run in the child too: DeepSeekSettings.transform() executes
        # in create_babeldoc_config() inside pdf2zh_next's translation worker.
        if flash_patch:
            restores.append(install_deepseek_flash_patch())
        # Table process_page wraps the reference filter, not vice versa.
        if reference_skip:
            restores.append(install_reference_skip_policy())
        if mode:
            restores.append(install_table_policy(mode))
    except Exception:
        for restore in reversed(restores):
            restore()
        raise

    def restore():
        for callback in reversed(restores):
            callback()

    return restore


def _run_table_worker(
    mode, *args, reference_skip=False, flash_patch=False, **kwargs
):
    from pdf2zh_next import high_level

    native = _native_worker or high_level._translate_wrapper
    if _parent_restore is not None:
        _parent_restore()
    restore = _install_policies(mode, reference_skip, flash_patch)
    try:
        return native(*args, **kwargs)
    finally:
        restore()


def install_table_process_policy(mode, reference_skip=False, flash_patch=False):
    parse_table_mode(mode)
    if mode and not table_policy_supported():
        warn_native_table_fallback()
        mode = None
    if reference_skip and not reference_policy_supported():
        warn_reference_fallback()
        reference_skip = False
    if not mode and not reference_skip and not flash_patch:
        return lambda: None

    from pdf2zh_next import high_level

    global _native_worker, _parent_restore
    if _native_worker is not None:
        raise RuntimeError("BabelDOC process policy is already installed")
    restore_policy = _install_policies(mode, reference_skip, flash_patch)
    native = high_level._translate_wrapper
    _native_worker, _parent_restore = native, restore_policy
    high_level._translate_wrapper = partial(
        _run_table_worker, mode,
        reference_skip=reference_skip, flash_patch=flash_patch,
    )

    def restore():
        global _native_worker, _parent_restore
        high_level._translate_wrapper = native
        _native_worker = _parent_restore = None
        restore_policy()

    return restore
