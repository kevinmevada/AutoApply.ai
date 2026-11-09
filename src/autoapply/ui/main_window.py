"""Main HIVI AutoApply desktop window."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from autoapply.browser.worker import BrowserWorker
from autoapply.core.models import BrowserStatus, BrowserStatusEvent
from autoapply.ui.components.activity_log import ActivityLog
from autoapply.ui.components.browser_status import BrowserStatusWidget
from autoapply.ui.components.url_input import URLInput

_FULLSCREEN_STYLE = """
QMainWindow, QWidget#centralRoot {
    background-color: #0f1419;
    color: #e7ecf1;
}
QLabel#appTitle {
    font-family: "Segoe UI Semibold", "Segoe UI", sans-serif;
    font-size: 42px;
    font-weight: 600;
    color: #f4f7fa;
    letter-spacing: 0.5px;
}
QLabel#appSubtitle {
    font-family: "Segoe UI", sans-serif;
    font-size: 16px;
    color: #9aa7b5;
    padding-bottom: 12px;
}
QLabel.sectionHeading {
    font-family: "Segoe UI Semibold", "Segoe UI", sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: #7d8b99;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    padding-top: 18px;
    padding-bottom: 6px;
}
QLabel#hintLabel {
    font-family: "Segoe UI", sans-serif;
    font-size: 12px;
    color: #667788;
}
QLineEdit {
    font-size: 18px;
    padding: 14px 16px;
    border: 1px solid #2a3540;
    border-radius: 8px;
    background: #182029;
    color: #f4f7fa;
    selection-background-color: #3d6f99;
}
QLineEdit:focus {
    border-color: #4f8fbf;
}
QPushButton {
    font-size: 15px;
    font-weight: 600;
    padding: 12px 22px;
    border-radius: 8px;
    border: none;
}
QPushButton#openButton {
    background: #2f7d57;
    color: #ffffff;
}
QPushButton#openButton:hover:enabled {
    background: #369568;
}
QPushButton#openButton:disabled {
    background: #243038;
    color: #6a7784;
}
QPushButton#stopButton {
    background: #3a4552;
    color: #e7ecf1;
}
QPushButton#stopButton:hover:enabled {
    background: #4a5664;
}
QPushButton#stopButton:disabled {
    background: #243038;
    color: #6a7784;
}
QLabel#statusValue {
    font-family: "Segoe UI Semibold", "Segoe UI", sans-serif;
    font-size: 28px;
    font-weight: 600;
    color: #f4f7fa;
}
QLabel#statusMessage {
    font-size: 15px;
    color: #9aa7b5;
}
QPlainTextEdit {
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 14px;
    border: 1px solid #2a3540;
    border-radius: 8px;
    background: #121820;
    color: #c5d0da;
    padding: 10px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HIVI AutoApply")
        self.setMinimumSize(960, 640)

        self._allow_close = False
        self._closing = False
        self._thread = QThread(self)
        self._worker = BrowserWorker()
        self._worker.moveToThread(self._thread)

        self.url_input = URLInput()
        self.browser_status = BrowserStatusWidget()
        self.activity_log = ActivityLog()

        self._build_ui()
        self._connect_signals()
        self._install_shortcuts()
        self.setStyleSheet(_FULLSCREEN_STYLE)
        self._thread.start()
        self.activity_log.add_message("HIVI AutoApply is ready.")

    def show_fullscreen_ui(self) -> None:
        """Present the control panel as a full-screen desktop surface."""
        self.showFullScreen()

    def _install_shortcuts(self) -> None:
        # Esc leaves exclusive fullscreen but keeps a maximized control panel.
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._exit_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, activated=self._toggle_fullscreen)

    def _exit_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showMaximized()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def _build_ui(self) -> None:
        title = QLabel("HIVI AutoApply")
        title.setObjectName("appTitle")

        subtitle = QLabel("Open a job application URL in a controlled browser.")
        subtitle.setObjectName("appSubtitle")
        subtitle.setWordWrap(True)

        url_heading = QLabel("Job application URL")
        url_heading.setProperty("class", "sectionHeading")
        url_heading.setObjectName("urlHeading")

        status_heading = QLabel("Browser status")
        status_heading.setProperty("class", "sectionHeading")

        activity_heading = QLabel("Activity")
        activity_heading.setProperty("class", "sectionHeading")

        hint = QLabel("F11 toggles fullscreen · Esc exits fullscreen")
        hint.setObjectName("hintLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Qt stylesheets match object names more reliably than dynamic class props.
        for heading in (url_heading, status_heading, activity_heading):
            heading.setStyleSheet(
                "font-family: 'Segoe UI Semibold', 'Segoe UI', sans-serif;"
                "font-size: 13px; font-weight: 600; color: #7d8b99;"
                "letter-spacing: 1.2px; padding-top: 18px; padding-bottom: 6px;"
            )

        self.activity_log.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        central = QWidget()
        central.setObjectName("centralRoot")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(64, 48, 64, 36)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(url_heading)
        layout.addWidget(self.url_input)
        layout.addWidget(status_heading)
        layout.addWidget(self.browser_status)
        layout.addWidget(activity_heading)
        layout.addWidget(self.activity_log, stretch=1)
        layout.addWidget(hint)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.url_input.open_requested.connect(self._worker.open_application)
        self.url_input.stop_requested.connect(self._worker.stop_browser)

        self._worker.status_changed.connect(self._handle_status_event)
        self._worker.activity.connect(self.activity_log.add_message)
        self._worker.operation_failed.connect(self._handle_operation_failed)
        self._worker.operation_finished.connect(self._handle_operation_finished)
        self._worker.browser_available.connect(self.url_input.set_browser_available)
        self._worker.shutdown_requested.connect(self._worker.shutdown)
        self._worker.shutdown_complete.connect(self._on_shutdown_complete)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.finished.connect(self._worker.deleteLater)

    @Slot(object)
    def _handle_status_event(self, event: BrowserStatusEvent) -> None:
        self.browser_status.update_status(event)
        self.activity_log.add_message(event.message)
        available = event.status in {
            BrowserStatus.RUNNING,
            BrowserStatus.NAVIGATING,
            BrowserStatus.ERROR,
            BrowserStatus.STARTING,
        }
        if event.status in {
            BrowserStatus.DISCONNECTED,
            BrowserStatus.STOPPED,
        }:
            available = False
        self.url_input.set_browser_available(available)

    @Slot(str)
    def _handle_operation_failed(self, message: str) -> None:
        self.activity_log.add_message(message)

    @Slot()
    def _handle_operation_finished(self) -> None:
        self.url_input.set_busy(False)

    @Slot()
    def _on_shutdown_complete(self) -> None:
        self._thread.quit()

    @Slot()
    def _on_thread_finished(self) -> None:
        if self._closing:
            self._allow_close = True
            self.close()

    def closeEvent(self, event) -> None:
        if self._allow_close:
            event.accept()
            return

        event.ignore()
        if self._closing:
            return

        if not self._thread.isRunning():
            self._allow_close = True
            self.close()
            return

        self._closing = True
        self.activity_log.add_message("Shutting down browser...")
        self.url_input.set_busy(True)
        self._worker.shutdown_requested.emit()
