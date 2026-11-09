"""HIVI AutoApply application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from autoapply.ui.main_window import MainWindow


def main() -> int:
    """Initialize and run the desktop application."""
    app = QApplication(sys.argv)
    app.setApplicationName("HIVI AutoApply")
    app.setOrganizationName("HIVI")

    window = MainWindow()
    window.show_fullscreen_ui()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
