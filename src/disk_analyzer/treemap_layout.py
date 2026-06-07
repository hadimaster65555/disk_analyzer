from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import DiskNode


@dataclass(frozen=True, slots=True)
class Rect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class TreemapItem:
    node: DiskNode
    rect: Rect


def layout_treemap(
    nodes: Iterable[DiskNode],
    width: float,
    height: float,
    *,
    min_size: int = 0,
) -> list[TreemapItem]:
    visible_nodes = [node for node in nodes if node.size > 0 and node.size >= min_size]
    if width <= 0 or height <= 0 or not visible_nodes:
        return []

    visible_nodes.sort(key=lambda node: node.size, reverse=True)
    sizes = [node.size for node in visible_nodes]
    rects = _squarify(sizes, 0.0, 0.0, float(width), float(height))
    return [TreemapItem(node=node, rect=rect) for node, rect in zip(visible_nodes, rects, strict=True)]


def _squarify(sizes: list[int], x: float, y: float, width: float, height: float) -> list[Rect]:
    try:
        import squarify
    except ImportError:
        return _fallback_squarify(sizes, x, y, width, height)

    total = float(sum(sizes))
    normalized = squarify.normalize_sizes(sizes, width, height) if total > 0 else []
    raw_rects = squarify.squarify(normalized, x, y, width, height)
    return [
        Rect(
            x=float(rect["x"]),
            y=float(rect["y"]),
            width=float(rect["dx"]),
            height=float(rect["dy"]),
        )
        for rect in raw_rects
    ]


def _fallback_squarify(
    sizes: list[int],
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[Rect]:
    total = float(sum(sizes))
    if total <= 0:
        return []
    areas = [size * width * height / total for size in sizes]
    rects: list[Rect] = []
    _layout_row(areas, rects, x, y, width, height)
    return rects


def _layout_row(
    areas: list[float],
    rects: list[Rect],
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    if not areas:
        return
    if len(areas) == 1:
        rects.append(Rect(x, y, width, height))
        return

    row: list[float] = []
    remaining = areas[:]
    short_side = min(width, height)

    while remaining:
        candidate = row + [remaining[0]]
        if row and _worst_ratio(candidate, short_side) > _worst_ratio(row, short_side):
            break
        row = candidate
        remaining.pop(0)

    row_area = sum(row)
    if width >= height:
        row_height = row_area / width if width else 0
        cursor_x = x
        for area in row:
            rect_width = area / row_height if row_height else 0
            rects.append(Rect(cursor_x, y, rect_width, row_height))
            cursor_x += rect_width
        _layout_row(remaining, rects, x, y + row_height, width, max(height - row_height, 0))
    else:
        row_width = row_area / height if height else 0
        cursor_y = y
        for area in row:
            rect_height = area / row_width if row_width else 0
            rects.append(Rect(x, cursor_y, row_width, rect_height))
            cursor_y += rect_height
        _layout_row(remaining, rects, x + row_width, y, max(width - row_width, 0), height)


def _worst_ratio(row: list[float], short_side: float) -> float:
    if not row or short_side <= 0:
        return float("inf")
    row_sum = sum(row)
    max_area = max(row)
    min_area = min(row)
    if min_area <= 0 or row_sum <= 0:
        return float("inf")
    side_squared = short_side * short_side
    return max(
        side_squared * max_area / (row_sum * row_sum),
        (row_sum * row_sum) / (side_squared * min_area),
    )
