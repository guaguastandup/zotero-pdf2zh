import csv
import io
import tempfile
from contextlib import contextmanager
from pathlib import Path

MAX_GLOSSARY_BYTES = 1024 * 1024


def validate_glossary_csv(content):
    if not isinstance(content, str) or not content or '\0' in content:
        raise ValueError("术语表必须是非空的 UTF-8 CSV 文件。")
    try:
        size = len(content.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("术语表必须使用 UTF-8 编码。") from exc
    if size > MAX_GLOSSARY_BYTES:
        raise ValueError("术语表大小不能超过 1 MiB。")

    content = content.removeprefix("\ufeff")
    try:
        reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
        header = reader.fieldnames or []
        if not {"source", "target"}.issubset(header) or len(header) != len(set(header)):
            raise ValueError("术语表 CSV 必须包含 source 和 target 列，列名不能重复。")
        has_entries = False
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"术语表 CSV 第 {reader.line_num} 行的列数不正确。")
            if not row["source"].strip() or not row["target"].strip():
                raise ValueError(f"术语表 CSV 第 {reader.line_num} 行缺少原文或译文。")
            has_entries = True
    except csv.Error as exc:
        raise ValueError("术语表 CSV 格式不正确，请检查逗号和引号。") from exc
    if not has_entries:
        raise ValueError("术语表至少需要一条术语。")
    return content


@contextmanager
def temporary_glossary(content):
    if content is None:
        yield None
        return
    with tempfile.TemporaryDirectory(prefix="pdf2zh-glossary-") as directory:
        path = Path(directory) / "user-glossary.csv"
        if "," in str(path):
            raise ValueError("Server 临时目录路径不能包含逗号，请修改临时目录设置。")
        # BabelDOC detects the encoding from the file. A BOM makes it explicit.
        path.write_bytes(content.encode("utf-8-sig"))
        yield str(path)
