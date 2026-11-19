"""Audit preprocessing only, without translation APIs or changing input PDFs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import math_fonts, math_variables, math_rules


def audit(source):
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="math-audit-") as folder:
        target = Path(folder) / source.name
        shutil.copyfile(source, target)
        with pymupdf.open(source) as doc:
            indices = list(range(len(doc)))
            fonts = {f[3] for page in doc for f in page.get_fonts(full=True)}
        variables = math_variables.protect_variables(target, indices) if math_fonts.detect(fonts) else 0
        rules = math_rules.normalize_rules(target, indices) if math_rules.has_tex_math(fonts) else 0
        text_changes, raster_changes = [], []
        with pymupdf.open(source) as before, pymupdf.open(target) as after:
            for i in indices:
                if before[i].get_text() != after[i].get_text():
                    text_changes.append(i + 1)
                matrix = pymupdf.Matrix(1.5, 1.5)
                if before[i].get_pixmap(matrix=matrix).samples != after[i].get_pixmap(matrix=matrix).samples:
                    raster_changes.append(i + 1)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    return {"name": source.name, "sha256": original_hash, "pages": len(indices),
            "variable_runs": variables, "short_rules": rules,
            "text_changed_pages": text_changes, "raster_changed_pages": raster_changes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve() in {p.resolve() for p in args.pdfs}:
        parser.error("the report must not overwrite an input PDF")
    results = [audit(path) for path in args.pdfs]
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Audited {len(results)} PDFs; report: {args.output}")
