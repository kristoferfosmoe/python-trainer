"""Capture a student's variables for the variables panel and visualizer."""

from pybricks.parameters import Color, _Constant

MAX_ITEMS = 8
MAX_TEXT = 40


def format_value(value, depth=0):
    """Short display text for a value, or None if it isn't worth showing."""
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, int):
        return repr(value)
    if isinstance(value, float):
        return repr(round(value, 2))
    if isinstance(value, str):
        text = repr(value)
        return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 2] + "…" + text[0]
    if isinstance(value, (Color, _Constant)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        if depth >= 2:
            return "[…]" if isinstance(value, list) else "(…)"
        parts = []
        for item in value[:MAX_ITEMS]:
            text = format_value(item, depth + 1)
            parts.append(text if text is not None else "…")
        if len(value) > MAX_ITEMS:
            parts.append("…")
        if isinstance(value, list):
            return "[" + ", ".join(parts) + "]"
        return "(" + ", ".join(parts) + ("," if len(value) == 1 else "") + ")"
    if isinstance(value, dict):
        if depth >= 2:
            return "{…}"
        parts = []
        for key, item in list(value.items())[:MAX_ITEMS]:
            k = format_value(key, depth + 1) or "…"
            v = format_value(item, depth + 1) or "…"
            parts.append(f"{k}: {v}")
        if len(value) > MAX_ITEMS:
            parts.append("…")
        return "{" + ", ".join(parts) + "}"
    return None


def snapshot(frame):
    """List of [name, value_text, scope] for the student's variables."""
    out = []
    seen = set()

    def add(name, value, scope):
        if name in seen or name.startswith("_"):
            return
        text = format_value(value)
        if text is not None:
            seen.add(name)
            out.append([name, text, scope])

    if frame.f_code.co_name != "<module>":
        for name, value in list(frame.f_locals.items()):
            add(name, value, "local")
    for name, value in list(frame.f_globals.items()):
        add(name, value, "global")
    return out
