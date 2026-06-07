from __future__ import annotations

import math
from pathlib import Path

from disk_analyzer.models import DiskNode
from disk_analyzer.treemap_layout import layout_treemap


def test_layout_treemap_fits_rectangles_inside_bounds():
    nodes = [
        DiskNode(Path("a"), "a", 60, False),
        DiskNode(Path("b"), "b", 30, False),
        DiskNode(Path("c"), "c", 10, False),
    ]

    items = layout_treemap(nodes, 200, 100)

    assert [item.node.name for item in items] == ["a", "b", "c"]
    assert len(items) == 3
    for item in items:
        assert item.rect.x >= 0
        assert item.rect.y >= 0
        assert item.rect.x + item.rect.width <= 200.0001
        assert item.rect.y + item.rect.height <= 100.0001

    total_area = sum(item.rect.width * item.rect.height for item in items)
    assert math.isclose(total_area, 20_000, rel_tol=0.0001)


def test_layout_treemap_filters_empty_and_small_nodes():
    nodes = [
        DiskNode(Path("a"), "a", 60, False),
        DiskNode(Path("b"), "b", 4, False),
        DiskNode(Path("c"), "c", 0, False),
    ]

    items = layout_treemap(nodes, 100, 100, min_size=5)

    assert [item.node.name for item in items] == ["a"]
