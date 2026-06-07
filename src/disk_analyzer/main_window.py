from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from .delete_service import DeleteError, move_to_trash
from .models import DiskNode, ScanOptions, ScanResult
from .scanner import scan_path
from .tree_refresh import replace_subtree
from .tree_model import DiskTreeModel
from .treemap_widget import TreemapWidget
from .units import format_bytes, format_percent


class ScanWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, root_path: Path, options: ScanOptions) -> None:
        super().__init__()
        self._root_path = root_path
        self._options = options
        self._cancel_requested = False
        self._last_progress = 0.0

    @Slot()
    def run(self) -> None:
        try:
            result = scan_path(
                self._root_path,
                self._options,
                should_cancel=lambda: self._cancel_requested,
                on_progress=self._emit_progress,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)

    @Slot()
    def cancel(self) -> None:
        self._cancel_requested = True

    def _emit_progress(self, path: Path) -> None:
        now = time.perf_counter()
        if now - self._last_progress < 0.15:
            return
        self._last_progress = now
        self.progress.emit(str(path))


class InspectorPanel(QWidget):
    deleteRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._path = QLabel("")
        self._path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._size = QLabel("")
        self._percent_root = QLabel("")
        self._percent_parent = QLabel("")
        self._type = QLabel("")
        self._children = QLabel("")
        self._modified = QLabel("")
        self._warning = QLabel("")
        self._copy_button = QPushButton("Copy Path")
        self._copy_button.clicked.connect(self._copy_path)
        self._trash_button = QPushButton("Move to Trash")
        self._trash_button.clicked.connect(self.deleteRequested.emit)

        form = QFormLayout()
        form.addRow("Path", self._path)
        form.addRow("Size", self._size)
        form.addRow("Root", self._percent_root)
        form.addRow("Parent", self._percent_parent)
        form.addRow("Type", self._type)
        form.addRow("Children", self._children)
        form.addRow("Modified", self._modified)
        form.addRow("Warning", self._warning)
        form.addRow("", self._copy_button)
        form.addRow("", self._trash_button)

        title = QLabel("Inspector")
        title.setStyleSheet("font-weight: 600; font-size: 15px;")
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addStretch(1)

        self._current_path = ""
        self.set_node(None, None, None)

    def set_node(
        self,
        node: DiskNode | None,
        root: DiskNode | None,
        parent: DiskNode | None,
        *,
        can_delete: bool = False,
    ) -> None:
        if node is None:
            self._current_path = ""
            for label in (
                self._path,
                self._size,
                self._percent_root,
                self._percent_parent,
                self._type,
                self._children,
                self._modified,
                self._warning,
            ):
                label.setText("-")
            self._copy_button.setEnabled(False)
            self._trash_button.setEnabled(False)
            return

        self._current_path = str(node.path)
        self._path.setText(self._current_path)
        self._size.setText(format_bytes(node.size))
        self._percent_root.setText(format_percent(node.percent_of(root.size if root else node.size)))
        self._percent_parent.setText(format_percent(node.percent_of(parent.size if parent else node.size)))
        self._type.setText(node.category)
        self._children.setText(str(node.child_count) if node.is_dir else "-")
        self._modified.setText(_format_modified(node.modified_ns))
        self._warning.setText(node.warning or "-")
        self._copy_button.setEnabled(True)
        self._trash_button.setEnabled(can_delete)

    def set_delete_enabled(self, enabled: bool) -> None:
        self._trash_button.setEnabled(enabled)

    def _copy_path(self) -> None:
        if self._current_path:
            QGuiApplication.clipboard().setText(self._current_path)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Disk Capacity Analyzer")
        self.resize(1220, 760)

        self._root_path: Path | None = None
        self._scan_root: DiskNode | None = None
        self._thread: QThread | None = None
        self._worker: ScanWorker | None = None
        self._scanning = False

        self._tree_model = DiskTreeModel()
        self._tree = QTreeView()
        self._tree.setModel(self._tree_model)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(False)
        self._tree.selectionModel().currentChanged.connect(self._tree_current_changed)

        self._treemap = TreemapWidget()
        self._treemap.nodeSelected.connect(self._treemap_node_selected)
        self._treemap.nodeActivated.connect(self._treemap_node_activated)

        self._inspector = InspectorPanel()
        self._inspector.deleteRequested.connect(self._delete_selected)

        splitter = QSplitter()
        splitter.addWidget(self._tree)
        splitter.addWidget(self._treemap)
        splitter.addWidget(self._inspector)
        splitter.setSizes([330, 650, 240])
        self.setCentralWidget(splitter)

        self._build_toolbar()
        self.statusBar().showMessage("Ready")
        self._set_scanning(False)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        style = self.style()
        self._choose_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
            "Choose",
            self,
        )
        self._choose_action.triggered.connect(self._choose_folder)
        toolbar.addAction(self._choose_action)

        self._rescan_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
            "Rescan",
            self,
        )
        self._rescan_action.triggered.connect(self._rescan)
        toolbar.addAction(self._rescan_action)

        self._up_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp), "Up", self)
        self._up_action.triggered.connect(self._go_up)
        toolbar.addAction(self._up_action)

        self._stop_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_BrowserStop),
            "Stop",
            self,
        )
        self._stop_action.triggered.connect(self._stop_scan)
        toolbar.addAction(self._stop_action)

        self._delete_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon),
            "Trash",
            self,
        )
        self._delete_action.setShortcut("Delete")
        self._delete_action.triggered.connect(self._delete_selected)
        toolbar.addAction(self._delete_action)

        toolbar.addSeparator()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search path")
        self._search.setClearButtonEnabled(True)
        self._search.returnPressed.connect(self._search_tree)
        self._search.setMaximumWidth(280)
        toolbar.addWidget(self._search)

    @Slot()
    def _choose_folder(self) -> None:
        start = str(self._root_path or Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Choose Folder", start)
        if folder:
            self._start_scan(Path(folder))

    @Slot()
    def _rescan(self) -> None:
        if self._root_path is not None:
            self._start_scan(self._root_path)

    @Slot()
    def _stop_scan(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.statusBar().showMessage("Stopping scan...")

    @Slot()
    def _go_up(self) -> None:
        current = self._treemap.root_node
        if current is None:
            return
        parent = self._tree_model.parent_node(current)
        if parent is None:
            return
        self._treemap.set_root_node(parent)
        self._select_node(parent)

    @Slot()
    def _search_tree(self) -> None:
        node = self._tree_model.find_first(self._search.text())
        if node is None:
            self.statusBar().showMessage("No match")
            return
        self._select_node(node)

    @Slot()
    def _delete_selected(self) -> None:
        node = self._current_node()
        if node is None or self._scan_root is None:
            return
        if not self._can_delete_node(node):
            QMessageBox.information(
                self,
                "Cannot move to Trash",
                "Choose a file or folder inside the scanned root. The scanned root itself cannot be deleted here.",
            )
            return
        if not self._confirm_move_to_trash(node):
            return

        deleted_path = node.path
        refresh_path = deleted_path.parent
        try:
            move_to_trash(deleted_path, self._scan_root.path)
        except DeleteError as exc:
            QMessageBox.critical(self, "Move to Trash failed", str(exc))
            self.statusBar().showMessage("Move to Trash failed")
            return

        self.statusBar().showMessage(f"Moved to Trash: {deleted_path}")
        self._refresh_directory_after_delete(refresh_path)

    def _start_scan(self, root_path: Path) -> None:
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(self, "Scan running", "Stop the current scan before starting another.")
            return

        self._root_path = root_path
        self._set_scanning(True)
        self._tree_model.set_root(None)
        self._scan_root = None
        self._treemap.set_root_node(None)
        self._inspector.set_node(None, None, None)
        self.statusBar().showMessage(f"Scanning {root_path}")

        self._thread = QThread(self)
        self._worker = ScanWorker(root_path, ScanOptions())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._scan_progress)
        self._worker.finished.connect(self._scan_finished)
        self._worker.failed.connect(self._scan_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(lambda: self._set_scanning(False))
        self._thread.start()

    @Slot(str)
    def _scan_progress(self, path: str) -> None:
        self.statusBar().showMessage(f"Scanning {path}")

    @Slot(object)
    def _scan_finished(self, result: ScanResult) -> None:
        self._scan_root = result.root
        self._tree_model.set_root(result.root)
        self._tree.expandToDepth(1)
        for column in range(self._tree_model.columnCount()):
            self._tree.resizeColumnToContents(column)
        self._treemap.set_root_node(result.root)
        self._select_node(result.root)

        warning_text = f", {len(result.warnings)} warning(s)" if result.warnings else ""
        cancelled_text = "Cancelled" if result.cancelled else "Scanned"
        self.statusBar().showMessage(
            f"{cancelled_text} {result.root.path} - {format_bytes(result.total_bytes)} "
            f"in {result.elapsed_seconds:.1f}s{warning_text}"
        )

    @Slot(str)
    def _scan_failed(self, message: str) -> None:
        self.statusBar().showMessage("Scan failed")
        QMessageBox.critical(self, "Scan failed", message)

    def _refresh_directory_after_delete(self, refresh_path: Path) -> None:
        if self._scan_root is None:
            return
        if not refresh_path.exists():
            QMessageBox.warning(
                self,
                "Refresh failed",
                f"Moved item to Trash, but the parent folder no longer exists:\n{refresh_path}",
            )
            return

        self.statusBar().showMessage(f"Refreshing {refresh_path}")
        self._set_scanning(True)
        try:
            result = scan_path(refresh_path, ScanOptions())
        finally:
            self._set_scanning(False)
        if result.cancelled:
            self.statusBar().showMessage("Refresh cancelled")
            return

        if self._scan_root.path == result.root.path:
            self._scan_root = result.root
        else:
            refreshed_root = replace_subtree(self._scan_root, result.root)
            if refreshed_root is None:
                QMessageBox.warning(
                    self,
                    "Refresh failed",
                    f"Moved item to Trash, but could not locate the parent folder in the current scan:\n{refresh_path}",
                )
                self.statusBar().showMessage("Refresh failed")
                return
            self._scan_root = refreshed_root

        self._tree_model.set_root(self._scan_root)
        self._tree.expandToDepth(1)
        for column in range(self._tree_model.columnCount()):
            self._tree.resizeColumnToContents(column)

        refreshed_node = self._tree_model.find_path(refresh_path)
        if refreshed_node is not None:
            self._select_node(refreshed_node)
        elif self._scan_root is not None:
            self._select_node(self._scan_root)

        warning_text = f", {len(result.warnings)} warning(s)" if result.warnings else ""
        self.statusBar().showMessage(f"Refreshed {refresh_path}{warning_text}")

    @Slot(object, object)
    def _tree_current_changed(self, current, previous) -> None:
        node = self._tree_model.node_for_index(current)
        if node is None:
            return
        parent = self._tree_model.parent_node(node)
        if node.is_dir:
            self._treemap.set_root_node(node)
            self._treemap.set_selected_node(node)
        elif parent is not None:
            self._treemap.set_root_node(parent)
            self._treemap.set_selected_node(node)
        else:
            self._treemap.set_selected_node(node)
        self._inspector.set_node(
            node,
            self._scan_root,
            parent,
            can_delete=not self._scanning and self._can_delete_node(node),
        )
        self._refresh_delete_controls()

    @Slot(object)
    def _treemap_node_selected(self, node: DiskNode) -> None:
        self._select_node(node)

    @Slot(object)
    def _treemap_node_activated(self, node: DiskNode) -> None:
        self._treemap.set_root_node(node)
        self._select_node(node)

    def _select_node(self, node: DiskNode) -> None:
        index = self._tree_model.index_for_node(node)
        if not index.isValid():
            return
        self._tree.setCurrentIndex(index)
        self._tree.scrollTo(index)
        self._tree.expand(index)
        parent = self._tree_model.parent_node(node)
        self._inspector.set_node(
            node,
            self._scan_root,
            parent,
            can_delete=not self._scanning and self._can_delete_node(node),
        )
        self._refresh_delete_controls()

    def _set_scanning(self, scanning: bool) -> None:
        self._scanning = scanning
        self._choose_action.setEnabled(not scanning)
        self._rescan_action.setEnabled(not scanning and self._root_path is not None)
        self._stop_action.setEnabled(scanning)
        self._up_action.setEnabled(not scanning)
        self._search.setEnabled(not scanning)
        self._refresh_delete_controls()
        if not scanning:
            self._worker = None
            self._thread = None

    def _current_node(self) -> DiskNode | None:
        return self._tree_model.node_for_index(self._tree.currentIndex())

    def _can_delete_node(self, node: DiskNode | None) -> bool:
        if node is None or self._scan_root is None:
            return False
        if id(node) == id(self._scan_root):
            return False
        return True

    def _refresh_delete_controls(self) -> None:
        enabled = not self._scanning and self._can_delete_node(self._current_node())
        if hasattr(self, "_delete_action"):
            self._delete_action.setEnabled(enabled)
        self._inspector.set_delete_enabled(enabled)

    def _confirm_move_to_trash(self, node: DiskNode) -> bool:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("Move to Trash?")
        message.setText(f"Move '{node.name}' to Trash?")
        message.setInformativeText(
            f"{format_bytes(node.size)}\n{node.path}\n\n"
            "This can usually be undone from the system Trash."
        )
        trash_button = message.addButton("Move to Trash", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = message.addButton(QMessageBox.StandardButton.Cancel)
        message.setDefaultButton(cancel_button)
        message.exec()
        return message.clickedButton() is trash_button


def _format_modified(modified_ns: int | None) -> str:
    if modified_ns is None:
        return "-"
    return datetime.fromtimestamp(modified_ns / 1_000_000_000).strftime("%Y-%m-%d %H:%M")
