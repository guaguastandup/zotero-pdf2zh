#!/usr/bin/env python3
"""Read-only encoding dependency diagnosis; run with the affected engine's Python."""
from importlib.metadata import PackageNotFoundError, version
import warnings


def main():
    import sys
    print(f'Python: {sys.executable}')
    for name in ('requests', 'charset-normalizer', 'chardet', 'urllib3'):
        try:
            print(f'{name}: {version(name)}')
        except PackageNotFoundError:
            print(f'{name}: not installed')
    try:
        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter('always')
            import requests
        for notice in notices:
            print(f'{notice.category.__name__}: {notice.message}')
        if notices:
            print('Check the Requests warning and its declared dependency ranges before changing versions.')
            return 1
        print('Requests imported without dependency warnings. No packages were changed.')
        return 0
    except ImportError as error:
        print(f'Cannot import Requests: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
