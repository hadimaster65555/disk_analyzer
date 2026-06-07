from __future__ import annotations

from pathlib import Path

from disk_analyzer.models import DiskNode
from disk_analyzer.tree_refresh import find_node_by_path, replace_subtree


def test_replace_subtree_updates_parent_and_ancestor_sizes():
    root = DiskNode(
        path=Path("/scan"),
        name="scan",
        size=110,
        is_dir=True,
        children=[
            DiskNode(
                path=Path("/scan/a"),
                name="a",
                size=70,
                is_dir=True,
                children=[
                    DiskNode(path=Path("/scan/a/deleted.bin"), name="deleted.bin", size=50, is_dir=False),
                    DiskNode(path=Path("/scan/a/keep.bin"), name="keep.bin", size=20, is_dir=False),
                ],
            ),
            DiskNode(path=Path("/scan/b.bin"), name="b.bin", size=40, is_dir=False),
        ],
    )
    refreshed_parent = DiskNode(
        path=Path("/scan/a"),
        name="a",
        size=20,
        is_dir=True,
        children=[
            DiskNode(path=Path("/scan/a/keep.bin"), name="keep.bin", size=20, is_dir=False),
        ],
    )

    updated = replace_subtree(root, refreshed_parent)

    assert updated is root
    assert root.size == 60
    refreshed = find_node_by_path(root, Path("/scan/a"))
    assert refreshed is refreshed_parent
    assert [child.name for child in refreshed.children] == ["keep.bin"]


def test_replace_subtree_can_replace_root():
    old_root = DiskNode(path=Path("/scan"), name="scan", size=10, is_dir=True)
    new_root = DiskNode(path=Path("/scan"), name="scan", size=5, is_dir=True)

    assert replace_subtree(old_root, new_root) is new_root


def test_replace_subtree_returns_none_when_path_is_not_found():
    root = DiskNode(path=Path("/scan"), name="scan", size=10, is_dir=True)
    replacement = DiskNode(path=Path("/other"), name="other", size=5, is_dir=True)

    assert replace_subtree(root, replacement) is None
