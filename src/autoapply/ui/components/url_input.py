"""URL input and browser control widget."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class URLInput(QWidget):
    open_requested = Signal(str)
    stop_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.url_field = QLineEdit()
        self.url_field.setPlaceholderText("Paste a job application URL...")
        self.url_field.setClearButtonEnabled(True)
        self.url_field.setMinimumHeight(52)

        self.open_button = QPushButton("Open Application")
        self.open_button.setObjectName("openButton")
        self.open_button.setMinimumHeight(48)

        self.stop_button = QPushButton("Stop Browser")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setMinimumHeight(48)
        self.stop_button.setEnabled(False)

        self.open_button.clicked.connect(self._open)
        self.url_field.returnPressed.connect(self._open)
        self.stop_button.clicked.connect(self.stop_requested.emit)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.addWidget(self.open_button, stretch=2)
        controls.addWidget(self.stop_button, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.url_field)
        layout.addLayout(controls)

        self._busy = False
        self._browser_available = False

    def _open(self) -> None:
        url = self.url_field.text().strip()
        if not url or self._busy:
            return
        self.set_busy(True)
        self.open_requested.emit(url)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.open_button.setEnabled(not busy)
        self.url_field.setEnabled(not busy)
        self.stop_button.setEnabled(self._browser_available and not busy)

    def set_browser_available(self, available: bool) -> None:
        self._browser_available = available
        self.stop_button.setEnabled(available and not self._busy)
