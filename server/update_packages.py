#!/usr/bin/env python3
"""One-command updater for Zotero PDF2zh translation packages.

Normal users should run only:

    python update_packages.py

The detailed diagnostics and advanced options remain available through
manage_packages.py.
"""

from __future__ import annotations

import sys

import manage_packages


def main() -> int:
    # Executing this dedicated script is itself the user's explicit consent to
    # update. Reuse the guarded updater: network probe, mirror ranking,
    # dependency dry-run, compatible upgrade, and validated-source fallback.
    forwarded = [sys.argv[0], "update", "--yes", *sys.argv[1:]]
    original = sys.argv
    try:
        sys.argv = forwarded
        return manage_packages.main()
    finally:
        sys.argv = original


if __name__ == "__main__":
    raise SystemExit(main())
