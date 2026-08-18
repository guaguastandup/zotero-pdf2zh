from pathlib import Path

source_path = Path('.github/scripts/apply_release_hardening_v4_1.py')
source = source_path.read_text(encoding='utf-8')
marker = '# Permanent CI regression coverage for every release blocker fixed above.'
pos = source.find(marker)
if pos < 0:
    raise SystemExit('CI marker not found in hardening migration')
# Include the separator comments before the CI block only; all product, docs,
# release, and config changes live before this marker.
prefix = source[:pos]
exec(compile(prefix, str(source_path), 'exec'), {'__name__': '__main__'})
