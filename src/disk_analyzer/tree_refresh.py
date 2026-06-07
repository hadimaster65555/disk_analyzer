from __future__ import annotations

from pathlib import Path

from .models import DiskNode


def find_node_by_path(root: DiskNode | None, path: Path) -> DiskNode | None:
    if root is None:
        return None
    if _same_path(root.path, path):
        return root
    for child in root.children:
        found = find_node_by_path(child, path)
        if found is not None:
            return found
    return None


def replace_subtree(root: DiskNode, replacement: DiskNode) -> DiskNode | None:
    """Replace a node by path and update ancestor directory sizes."""
    if _same_path(root.path, replacement.path):
        return replacement
    if not _replace_child(root, replacement):
        return None
    recompute_directory_sizes(root)
    return root


def recompute_directory_sizes(node: DiskNode) -> int:
    if node.is_dir:
        node.size = sum(recompute_directory_sizes(child) for child in node.children)
        node.children.sort(key=lambda child: (child.size, child.name.lower()), reverse=True)
    return node.size


def _replace_child(node: DiskNode, replacement: DiskNode) -> bool:
    for index, child in enumerate(node.children):
        if _same_path(child.path, replacement.path):
            node.children[index] = replacement
            return True
        if child.is_dir and _replace_child(child, replacement):
            return True
    return False


def _same_path(left: Path, right: Path) -> bool:
    return Path(left) == Path(right)
