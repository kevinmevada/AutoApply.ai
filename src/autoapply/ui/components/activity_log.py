"""Safe application activity log widget."""

from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit, QSizePolicy, QVBoxLayout, QWidget


class ActivityLog(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Application activity will appear here.")
        self.output.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.output.setMinimumHeight(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.output)

    def add_message(self, message: str) -> None:
        self.output.appendPlainText(message)

    def clear(self) -> None:
        self.output.clear()
