# Disk Capacity Analyzer

A Python desktop app for scanning folders and visualizing disk usage with a Disk Inventory X-style treemap plus a synchronized folder tree.

## Features

- Recursively scans a selected folder and computes inclusive folder sizes.
- Shows disk usage as a proportional treemap.
- Provides a synchronized expandable tree view sorted by size.
- Displays selected item details in an inspector panel.
- Supports search, rescan, stop-scan, drill-down, copy-path, and Move to Trash actions.
- Moves selected files or folders to the system Trash after confirmation.

## Requirements

- Python 3.11 or newer
- macOS, Linux, or Windows with PySide6 support

## Run

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the app:

```bash
python -m pip install -e ".[dev]"
```

Launch it:

```bash
python -m disk_analyzer
```

Or use the installed script:

```bash
disk-analyzer
```

## Usage

1. Click **Choose** and select a folder to scan.
2. Use the left tree or center treemap to inspect large folders and files.
3. Double-click a folder in the treemap to drill into it, or use **Up** to return to the parent folder.
4. Select an item and use **Copy Path** to copy its full path.
5. Select a file or subfolder and use **Trash** or the inspector's **Move to Trash** button to send it to the system Trash.

Move to Trash is disabled while scanning, for the scanned root itself, and when no deletable item is selected.

## Development

Run tests:

```bash
pytest
```

Run a compile check:

```bash
python -m compileall -q src tests
```

## Project Layout

```text
src/disk_analyzer/
  app.py              Application entrypoint
  main_window.py      PySide6 main window and scan workflow
  scanner.py          Recursive disk scanner
  delete_service.py   Safe Move-to-Trash guardrails
  tree_refresh.py     Partial subtree refresh after deletion
  models.py           Scan result and node data models
  tree_model.py       Qt tree model adapter
  treemap_widget.py   Custom treemap widget
  treemap_layout.py   Treemap rectangle layout adapter
tests/
  test_delete_service.py
  test_scanner.py
  test_treemap_layout.py
  test_tree_refresh.py
```

## Safety Notes

The scanner does not follow symlinked directories by default, which avoids loops and unexpected traversal outside the selected folder. Permission errors are collected as warnings and do not stop the scan.

Delete capability is implemented as Move to Trash through `Send2Trash`, not permanent deletion. The app checks that the selected path is inside the scanned root, refuses to delete the scanned root folder, asks for confirmation, and rescans only the deleted item's parent directory after a successful Trash operation.
