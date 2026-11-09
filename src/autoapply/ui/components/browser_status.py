"""Browser status display widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from autoapply.core.models import BrowserStatus, BrowserStatusEvent

STATUS_LABELS = {
    BrowserStatus.STOPPED: "Stopped",
    BrowserStatus.STARTING: "Starting browser...",
    BrowserStatus.RUNNING: "Browser ready",
    BrowserStatus.NAVIGATING: "Navigating...",
    BrowserStatus.DISCONNECTED: "Browser disconnected",
    BrowserStatus.ERROR: "Browser error",
}


class BrowserStatusWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.status_label = QLabel("Stopped")
        self.status_label.setObjectName("statusValue")
        self.message_label = QLabel("Waiting for an application URL.")
        self.message_label.setObjectName("statusMessage")
        self.message_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.status_label)
        layout.addWidget(self.message_label)

    def update_status(self, event: BrowserStatusEvent) -> None:
        self.status_label.setText(STATUS_LABELS.get(event.status, "Unknown"))
        self.message_label.setText(event.message)
