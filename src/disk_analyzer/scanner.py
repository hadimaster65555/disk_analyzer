from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from .models import DiskNode, ScanCancelled, ScanOptions, ScanResult, ScanWarning

CancelChecker = Callable[[], bool]
ProgressCallback = Callable[[Path], None]


def scan_path(
    root: Path,
    options: ScanOptions | None = None,
    *,
    should_cancel: CancelChecker | None = None,
    on_progress: ProgressCallback | None = None,
) -> ScanResult:
    """Recursively scan root and return an inclusive-size tree."""
    options = options or ScanOptions()
    root = Path(root).expanduser()
    warnings: list[ScanWarning] = []
    started = time.perf_counter()
    cancelled = False

    def cancelled_now() -> bool:
        return bool(should_cancel and should_cancel())

    try:
        node = _scan_node(root, options, warnings, cancelled_now, on_progress)
    except ScanCancelled:
        cancelled = True
        node = DiskNode(
            path=root,
            name=root.name or str(root),
            size=0,
            is_dir=True,
            warning="Scan cancelled",
        )

    elapsed = time.perf_counter() - started
    return ScanResult(
        root=node,
        total_bytes=node.size,
        elapsed_seconds=elapsed,
        warnings=tuple(warnings),
        cancelled=cancelled,
    )


def _scan_node(
    path: Path,
    options: ScanOptions,
    warnings: list[ScanWarning],
    should_cancel: CancelChecker,
    on_progress: ProgressCallback | None,
) -> DiskNode:
    if should_cancel():
        raise ScanCancelled
    if on_progress:
        on_progress(path)

    try:
        stat_result = path.stat() if options.follow_symlinks else path.lstat()
    except OSError as exc:
        warning = ScanWarning(path, str(exc))
        warnings.append(warning)
        return DiskNode(path=path, name=_display_name(path), size=0, is_dir=False, warning=warning.message)

    is_symlink = path.is_symlink()
    is_dir = path.is_dir() if options.follow_symlinks else _stat_is_dir(stat_result.st_mode)
    modified_ns = getattr(stat_result, "st_mtime_ns", None)

    if is_symlink and not options.follow_symlinks:
        return DiskNode(
            path=path,
            name=_display_name(path),
            size=int(stat_result.st_size),
            is_dir=False,
            extension=path.suffix.lower(),
            modified_ns=modified_ns,
            warning="Symlink not followed",
        )

    if not is_dir:
        return DiskNode(
            path=path,
            name=_display_name(path),
            size=int(stat_result.st_size),
            is_dir=False,
            extension=path.suffix.lower(),
            modified_ns=modified_ns,
        )

    children: list[DiskNode] = []
    total_size = 0
    dir_warning: str | None = None

    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if should_cancel():
                    raise ScanCancelled
                if not options.count_hidden and entry.name.startswith("."):
                    continue
                child_path = Path(entry.path)
                child = _scan_node(child_path, options, warnings, should_cancel, on_progress)
                total_size += child.size
                children.append(child)
    except ScanCancelled:
        raise
    except OSError as exc:
        dir_warning = str(exc)
        warnings.append(ScanWarning(path, dir_warning))

    children.sort(key=lambda child: (child.size, child.name.lower()), reverse=True)
    return DiskNode(
        path=path,
        name=_display_name(path),
        size=total_size,
        is_dir=True,
        children=children,
        modified_ns=modified_ns,
        warning=dir_warning,
    )


def _display_name(path: Path) -> str:
    return path.name or str(path)


def _stat_is_dir(mode: int) -> bool:
    return (mode & 0o170000) == 0o040000
