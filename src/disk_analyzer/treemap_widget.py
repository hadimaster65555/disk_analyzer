from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from .models import DiskNode
from .treemap_layout import TreemapItem, layout_treemap
from .units import format_bytes


class TreemapWidget(QWidget):
    nodeSelected = Signal(object)
    nodeActivated = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._root_node: DiskNode | None = None
        self._selected_node: DiskNode | None = None
        self._items: list[TreemapItem] = []
        self._margin = 8
        self.setMouseTracking(True)
        self.setMinimumSize(360, 280)

    @property
    def root_node(self) -> DiskNode | None:
        return self._root_node

    def set_root_node(self, node: DiskNode | None) -> None:
        self._root_node = node
        if self._selected_node is not None and node is not None:
            visible_ids = {id(child) for child in node.children}
            if id(self._selected_node) not in visible_ids and id(self._selected_node) != id(node):
                self._selected_node = None
        self._recalculate()
        self.update()

    def set_selected_node(self, node: DiskNode | None) -> None:
        self._selected_node = node
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f7f8fa"))

        if self._root_node is None:
            painter.setPen(QColor("#5f6773"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Choose a folder to scan")
            return

        if not self._items:
            painter.setPen(QColor("#5f6773"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No files to display")
            return

        for item in self._items:
            self._paint_item(painter, item)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._recalculate()
        super().resizeEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        node = self._node_at(event.position().toPoint())
        if node is None:
            self.setToolTip("")
            return
        self.setToolTip(f"{node.name}\n{format_bytes(node.size)}\n{node.path}")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        node = self._node_at(event.position().toPoint())
        if node is None:
            return
        self._selected_node = node
        self.nodeSelected.emit(node)
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        node = self._node_at(event.position().toPoint())
        if node is not None and node.is_dir and node.children:
            self.nodeActivated.emit(node)

    def leaveEvent(self, event) -> None:  # noqa: N802
        QToolTip.hideText()
        super().leaveEvent(event)

    def _recalculate(self) -> None:
        if self._root_node is None:
            self._items = []
            return
        content_width = max(self.width() - self._margin * 2, 0)
        content_height = max(self.height() - self._margin * 2, 0)
        self._items = layout_treemap(
            self._root_node.sorted_children(),
            content_width,
            content_height,
        )

    def _paint_item(self, painter: QPainter, item: TreemapItem) -> None:
        rect = QRectF(
            item.rect.x + self._margin,
            item.rect.y + self._margin,
            max(item.rect.width - 1, 0),
            max(item.rect.height - 1, 0),
        )
        if rect.width() <= 0 or rect.height() <= 0:
            return

        color = _color_for_node(item.node)
        painter.fillRect(rect, color)
        is_selected = self._selected_node is not None and id(item.node) == id(self._selected_node)
        painter.setPen(QPen(QColor("#111827") if is_selected else QColor("#ffffff"), 3 if is_selected else 1))
        painter.drawRect(rect)

        if rect.width() < 56 or rect.height() < 30:
            return

        painter.setPen(QColor("#111827"))
        metrics = QFontMetrics(painter.font())
        name = metrics.elidedText(item.node.name, Qt.TextElideMode.ElideRight, int(rect.width()) - 10)
        size = metrics.elidedText(format_bytes(item.node.size), Qt.TextElideMode.ElideRight, int(rect.width()) - 10)
        painter.drawText(rect.adjusted(5, 4, -5, -4), Qt.AlignmentFlag.AlignLeft, name)
        if rect.height() >= 48:
            painter.setPen(QColor("#374151"))
            painter.drawText(rect.adjusted(5, 22, -5, -4), Qt.AlignmentFlag.AlignLeft, size)

    def _node_at(self, point: QPoint) -> DiskNode | None:
        for item in reversed(self._items):
            rect = QRectF(
                item.rect.x + self._margin,
                item.rect.y + self._margin,
                item.rect.width,
                item.rect.height,
            )
            if rect.contains(point):
                return item.node
        return None


def _color_for_node(node: DiskNode) -> QColor:
    palette = {
        "Folder": QColor("#8ecae6"),
        ".jpg": QColor("#ffb703"),
        ".jpeg": QColor("#ffb703"),
        ".png": QColor("#fb8500"),
        ".gif": QColor("#f48c06"),
        ".mp4": QColor("#90be6d"),
        ".mov": QColor("#43aa8b"),
        ".mp3": QColor("#577590"),
        ".wav": QColor("#4d908e"),
        ".zip": QColor("#b56576"),
        ".dmg": QColor("#9d4edd"),
        ".pdf": QColor("#e63946"),
        ".py": QColor("#48cae4"),
        ".js": QColor("#ffd166"),
        ".ts": QColor("#06d6a0"),
    }
    if node.category in palette:
        return palette[node.category]
    seed = sum(ord(char) for char in node.category)
    hue = seed % 360
    return QColor.fromHsv(hue, 95, 220)
