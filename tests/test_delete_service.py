from __future__ import annotations

from pathlib import Path

import pytest

from disk_analyzer.delete_service import DeleteError, move_to_trash


def test_move_to_trash_calls_backend_for_file_inside_root(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_text("delete me")
    trashed: list[Path] = []

    monkeypatch.setattr("disk_analyzer.delete_service._send_to_trash", trashed.append)

    move_to_trash(target, tmp_path)

    assert trashed == [target]


def test_move_to_trash_calls_backend_for_folder_inside_root(tmp_path, monkeypatch):
    target = tmp_path / "folder"
    target.mkdir()
    trashed: list[Path] = []

    monkeypatch.setattr("disk_analyzer.delete_service._send_to_trash", trashed.append)

    move_to_trash(target, tmp_path)

    assert trashed == [target]


def test_move_to_trash_rejects_scan_root(tmp_path, monkeypatch):
    monkeypatch.setattr("disk_analyzer.delete_service._send_to_trash", lambda path: None)

    with pytest.raises(DeleteError, match="scanned root"):
        move_to_trash(tmp_path, tmp_path)


def test_move_to_trash_rejects_paths_outside_scan_root(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    monkeypatch.setattr("disk_analyzer.delete_service._send_to_trash", lambda path: None)

    with pytest.raises(DeleteError, match="outside"):
        move_to_trash(outside, root)


def test_move_to_trash_rejects_missing_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("disk_analyzer.delete_service._send_to_trash", lambda path: None)

    with pytest.raises(DeleteError, match="no longer exists"):
        move_to_trash(tmp_path / "missing.txt", tmp_path)
