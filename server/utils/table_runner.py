"""Run the installed engine with an opt-in table policy, without editing it."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from importlib.metadata import distribution

    from utils.table_process import install_table_process_policy

    mode = sys.argv.pop(1)
    restore = install_table_process_policy(mode)
    try:
        entry = next(
            entry
            for entry in distribution("pdf2zh-next").entry_points
            if entry.group == "console_scripts" and entry.name == "pdf2zh_next"
        )
        sys.argv[0] = "pdf2zh_next"
        return entry.load()()
    finally:
        restore()


if __name__ == "__main__":
    sys.exit(main())
