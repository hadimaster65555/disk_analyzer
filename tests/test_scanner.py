from __future__ import annotations

import os

import pytest

from disk_analyzer.models import ScanOptions
from disk_analyzer.scanner import scan_path


def test_scan_path_aggregates_nested_file_sizes(tmp_path):
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "a.txt").write_bytes(b"a" * 10)
    (tmp_path / "beta.bin").write_bytes(b"b" * 25)

    result = scan_path(tmp_path)

    assert result.total_bytes == 35
    assert result.root.size == 35
    assert [child.name for child in result.root.children] == ["beta.bin", "alpha"]
    alpha = next(child for child in result.root.children if child.name == "alpha")
    assert alpha.is_dir
    assert alpha.size == 10
    assert alpha.children[0].extension == ".txt"


def test_scan_path_can_skip_hidden_entries(tmp_path):
    (tmp_path / ".hidden").write_bytes(b"x" * 20)
    (tmp_path / "visible").write_bytes(b"y" * 5)

    result = scan_path(tmp_path, ScanOptions(count_hidden=False))

    assert result.total_bytes == 5
    assert [child.name for child in result.root.children] == ["visible"]


def test_scan_path_records_scandir_warnings(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (tmp_path / "ok").write_bytes(b"x" * 3)
    real_scandir = os.scandir

    def fake_scandir(path):
        if os.fspath(path) == os.fspath(blocked):
            raise PermissionError("blocked for test")
        return real_scandir(path)

    monkeypatch.setattr("disk_analyzer.scanner.os.scandir", fake_scandir)

    result = scan_path(tmp_path)

    assert result.total_bytes == 3
    assert len(result.warnings) == 1
    assert result.warnings[0].path == blocked
    assert "blocked for test" in result.warnings[0].message


def test_scan_path_does_not_follow_symlinked_directories_by_default(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "large.bin").write_bytes(b"x" * 100)
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    result = scan_path(link)

    assert not result.root.is_dir
    assert result.root.warning == "Symlink not followed"
    assert result.root.size != 100


def test_scan_path_returns_cancelled_result(tmp_path):
    (tmp_path / "file").write_bytes(b"x" * 10)

    result = scan_path(tmp_path, should_cancel=lambda: True)

    assert result.cancelled
    assert result.total_bytes == 0
    assert result.root.warning == "Scan cancelled"
