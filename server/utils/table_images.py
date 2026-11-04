"""Image obstacles from native IL, independent of layout detector labels."""

import math


def rect(box):
    return box.x, box.y, box.x2, box.y2


def overlaps(a, b, tolerance=0.0):
    """Require positive area; touching edges are safe."""
    return (
        min(a[2], b[2]) - max(a[0], b[0]) > tolerance + 1e-8
        and min(a[3], b[3]) - max(a[1], b[1]) > tolerance + 1e-8
    )


def image_boxes(page, table_box):
    result = []
    for form in getattr(page, "pdf_form", ()):
        box = getattr(form, "box", None)
        if getattr(form, "form_type", None) != "image" or box is None:
            continue
        bounds = rect(box)
        if all(math.isfinite(v) for v in bounds) and overlaps(bounds, rect(table_box)):
            result.append(bounds)
    return result


def avoid_images(bounds, source, images, tolerance=0.0):
    """Trim whitespace expansion along a separating source/image axis.

    Return None when the source already overlays an image, or no safe rectangle
    remains. Never move source text or an image to make room.
    """
    left, bottom, right, top = bounds
    for image in images:
        if overlaps(source, image, tolerance):
            return None
        if not overlaps((left, bottom, right, top), image, tolerance):
            continue
        if source[2] <= image[0] + tolerance:
            right = min(right, image[0] + tolerance)
        elif source[0] >= image[2] - tolerance:
            left = max(left, image[2] - tolerance)
        elif source[3] <= image[1] + tolerance:
            top = min(top, image[1] + tolerance)
        elif source[1] >= image[3] - tolerance:
            bottom = max(bottom, image[3] - tolerance)
    result = left, bottom, right, top
    if (
        right <= left
        or top <= bottom
        or any(overlaps(result, b, tolerance) for b in images)
    ):
        return None
    return result
