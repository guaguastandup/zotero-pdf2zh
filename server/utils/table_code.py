"""Code-region guard, independent of ordinary table grouping and translation."""

from utils.table_structure import join_wrapped_text


def protect_code_region(result, units, text_of_run, policies, status):
    """Return True for a code block; leave ordinary tables entirely unchanged."""
    if type(result.get("is_code")) is not bool:
        raise ValueError("Missing code-region decision")
    if not result["is_code"]:
        return False
    captions = result.get("caption_ids", [])
    if (
        not isinstance(captions, list)
        or any(type(i) is not int or not 0 <= i < len(units) for i in captions)
        or len(set(captions)) != len(captions)
    ):
        raise ValueError("Invalid code caption IDs")
    captions = set(captions)
    if policies is not None:
        for i, unit in enumerate(units):
            chars = frozenset(id(c) for run in unit for c in run)
            source = join_wrapped_text([text_of_run(run) for run in unit])
            policies[chars] = [{"text": source, "translate": i in captions}]
    if status is not None:
        status.update(success=True, is_code=True)
        status["preserve_ids"] = [i for i in range(len(units)) if i not in captions]
    return True
