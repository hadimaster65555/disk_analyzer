from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScanOptions:
    follow_symlinks: bool = False
    count_hidden: bool = True
    min_display_size: int = 0
    size_mode: str = "logical"


@dataclass(slots=True)
class DiskNode:
    path: Path
    name: str
    size: int
    is_dir: bool
    children: list["DiskNode"] = field(default_factory=list)
    extension: str = ""
    modified_ns: int | None = None
    warning: str | None = None

    @property
    def child_count(self) -> int:
        return len(self.children)

    @property
    def category(self) -> str:
        if self.is_dir:
            return "Folder"
        if self.extension:
            return self.extension.lower()
        return "File"

    def sorted_children(self, *, min_size: int = 0) -> list["DiskNode"]:
        return sorted(
            (child for child in self.children if child.size >= min_size),
            key=lambda child: (child.size, child.name.lower()),
            reverse=True,
        )

    def percent_of(self, total: int) -> float:
        if total <= 0:
            return 0.0
        return self.size / total


@dataclass(frozen=True, slots=True)
class ScanWarning:
    path: Path
    message: str


@dataclass(frozen=True, slots=True)
class ScanResult:
    root: DiskNode
    total_bytes: int
    elapsed_seconds: float
    warnings: tuple[ScanWarning, ...] = ()
    cancelled: bool = False


class ScanCancelled(RuntimeError):
    """Raised internally when a caller cancels a running scan."""
