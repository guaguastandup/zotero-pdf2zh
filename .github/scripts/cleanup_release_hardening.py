from pathlib import Path

p = Path('server/utils/environment_lifecycle.py')
text = p.read_text(encoding='utf-8')
text = text.replace(
    '# Do not execute ``pdf2zh_next --help`` here.  Upstream imports\n',
    '# Do not launch the heavyweight pdf2zh_next CLI help path here. Upstream imports\n',
)
p.write_text(text, encoding='utf-8')

for raw in (
    '.github/release-hardening-placeholder.txt',
    '.github/scripts/apply_release_hardening_v4_1.py',
    '.github/scripts/finalize_release_hardening_sources.py',
    '.github/scripts/run_release_hardening_without_ci.py',
    '.github/scripts/release_hardening_notes.txt',
    '.github/scripts/placeholder2.txt',
    '.github/scripts/placeholder3.txt',
    '.github/scripts/placeholder4.txt',
    '.github/scripts/placeholder5.txt',
    '.github/scripts/placeholder6.txt',
    '.github/scripts/placeholder7.txt',
    '.github/scripts/placeholder8.txt',
    '.github/scripts/placeholder9.txt',
    '.github/scripts/placeholder10.txt',
    '.github/scripts/placeholder11.txt',
    '.github/scripts/cleanup_release_hardening.py',
):
    path = Path(raw)
    if path.exists():
        path.unlink()

print('hardening scaffolding removed')
