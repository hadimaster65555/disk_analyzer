from __future__ import annotations

from pathlib import Path


class DeleteError(RuntimeError):
    """Raised when a file or folder cannot be moved to Trash."""


def move_to_trash(path: Path, scan_root: Path) -> None:
    """Move a scanned file or folder to the system Trash after safety checks."""
    target = Path(path)
    root = Path(scan_root)
    _validate_delete_target(target, root)

    try:
        _send_to_trash(target)
    except Exception as exc:  # noqa: BLE001
        raise DeleteError(f"Could not move '{target}' to Trash: {exc}") from exc


def _validate_delete_target(path: Path, scan_root: Path) -> None:
    if not path.exists() and not path.is_symlink():
        raise DeleteError(f"Path no longer exists: {path}")

    try:
        root_resolved = scan_root.resolve(strict=True)
    except OSError as exc:
        raise DeleteError(f"Scan root is no longer available: {scan_root}") from exc

    target_identity = path.resolve(strict=False)
    if target_identity == root_resolved:
        raise DeleteError("Refusing to delete the scanned root folder.")

    try:
        parent_resolved = path.parent.resolve(strict=True)
    except OSError as exc:
        raise DeleteError(f"Parent folder is no longer available: {path.parent}") from exc

    if parent_resolved != root_resolved and not parent_resolved.is_relative_to(root_resolved):
        raise DeleteError("Refusing to delete a path outside the scanned folder.")


def _send_to_trash(path: Path) -> None:
    try:
        from send2trash import send2trash
    except ImportError as exc:
        raise DeleteError("Send2Trash is required for safe deletion. Reinstall project dependencies.") from exc

    send2trash(str(path))
