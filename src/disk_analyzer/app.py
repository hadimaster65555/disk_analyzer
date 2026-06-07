from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is required to run the desktop app. Install with: python -m pip install -e .", file=sys.stderr)
        return 1

    from .main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Disk Capacity Analyzer")
    window = MainWindow()
    window.show()
    return app.exec()
