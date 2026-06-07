from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from .models import DiskNode
from .units import format_bytes, format_percent

NODE_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class DiskTreeModel(QStandardItemModel):
    def __init__(self) -> None:
        super().__init__()
        self._items_by_node_id: dict[int, QStandardItem] = {}
        self._parents_by_node_id: dict[int, DiskNode | None] = {}
        self.setHorizontalHeaderLabels(["Name", "Size", "%", "Type"])

    def set_root(self, root: DiskNode | None) -> None:
        self.clear()
        self._items_by_node_id.clear()
        self._parents_by_node_id.clear()
        self.setHorizontalHeaderLabels(["Name", "Size", "%", "Type"])
        if root is None:
            return
        self.appendRow(self._row_for_node(root, root.size, None))

    def node_for_index(self, index) -> DiskNode | None:
        if not index.isValid():
            return None
        first_column = index.siblingAtColumn(0)
        return first_column.data(NODE_ROLE)

    def parent_node(self, node: DiskNode) -> DiskNode | None:
        return self._parents_by_node_id.get(id(node))

    def index_for_node(self, node: DiskNode):
        item = self._items_by_node_id.get(id(node))
        return item.index() if item is not None else self.index(-1, -1)

    def iter_nodes(self) -> Iterable[DiskNode]:
        for item in self._items_by_node_id.values():
            node = item.data(NODE_ROLE)
            if node is not None:
                yield node

    def find_first(self, query: str) -> DiskNode | None:
        normalized = query.strip().lower()
        if not normalized:
            return None
        for node in self.iter_nodes():
            path_text = str(node.path).lower()
            if normalized in node.name.lower() or normalized in path_text:
                return node
        return None

    def find_path(self, path) -> DiskNode | None:
        for node in self.iter_nodes():
            if node.path == path:
                return node
        return None

    def _row_for_node(
        self,
        node: DiskNode,
        parent_size: int,
        parent_node: DiskNode | None,
    ) -> list[QStandardItem]:
        name_item = _item(node.name)
        size_item = _item(format_bytes(node.size))
        percent_item = _item(format_percent(node.percent_of(parent_size)))
        type_item = _item(node.category)
        for item in (name_item, size_item, percent_item, type_item):
            item.setData(node, NODE_ROLE)
            item.setToolTip(str(node.path))

        if node.warning:
            name_item.setToolTip(f"{node.path}\n{node.warning}")

        self._items_by_node_id[id(node)] = name_item
        self._parents_by_node_id[id(node)] = parent_node

        for child in node.sorted_children():
            name_item.appendRow(self._row_for_node(child, node.size, node))
        return [name_item, size_item, percent_item, type_item]


def _item(text: str) -> QStandardItem:
    item = QStandardItem(text)
    item.setEditable(False)
    return item
