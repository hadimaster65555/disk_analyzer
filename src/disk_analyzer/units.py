from __future__ import annotations


UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


def format_bytes(value: int | float) -> str:
    size = float(max(value, 0))
    unit_index = 0
    while size >= 1024 and unit_index < len(UNITS) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} B"
    if size >= 100:
        return f"{size:.0f} {UNITS[unit_index]}"
    if size >= 10:
        return f"{size:.1f} {UNITS[unit_index]}"
    return f"{size:.2f} {UNITS[unit_index]}"


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"
