"""Request-level table policy. Missing modes keep the legacy engine behavior."""

TABLE_MODES = ("preserve", "fixed")


def parse_table_mode(value):
    if value is None or value == "":
        return None
    if value not in TABLE_MODES:
        raise ValueError(
            "Unsupported tableMode. Available modes: preserve, fixed. "
            "Adaptive table layout is not implemented yet."
        )
    return value


def validate_table_runtime(mode, *, engine, winexe=False):
    if mode is None:
        return
    if engine != "pdf2zh_next":
        raise ValueError("Table modes require the pdf2zh_next Python engine.")
    if winexe:
        raise ValueError(
            "Table modes require the Python engine; disable enable_winexe. "
            "The standalone executable does not support the table adapter."
        )
