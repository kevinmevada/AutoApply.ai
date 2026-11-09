"""Run browser operations outside the PySide6 GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from autoapply.browser.manager import BrowserManager
from autoapply.browser.navigation import NavigationController
from autoapply.browser.system_chrome import open_in_user_chrome
from autoapply.core.exceptions import (
    BrowserErrorCode,
    BrowserLaunchError,
    NavigationError,
    URLValidationError,
)
from autoapply.core.models import BrowserStatus, BrowserStatusEvent


class BrowserWorker(QObject):
    """Own browser operations and expose safe Qt signals to the GUI."""

    status_changed = Signal(object)
    activity = Signal(str)
    operation_failed = Signal(str)
    operation_finished = Signal()
    browser_available = Signal(bool)
    shutdown_requested = Signal()
    shutdown_complete = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._manager: BrowserManager | None = None
        self._navigation: NavigationController | None = None
        self._shutting_down = False

    def _emit_status(
        self,
        status: BrowserStatus,
        message: str,
        error_code: BrowserErrorCode | None = None,
    ) -> None:
        self.status_changed.emit(
            BrowserStatusEvent(
                status=status,
                message=message,
                error_code=error_code,
            )
        )

    def _on_browser_status(self, event: BrowserStatusEvent) -> None:
        self.status_changed.emit(event)
        if event.status == BrowserStatus.RUNNING:
            self.browser_available.emit(True)
        elif event.status in {
            BrowserStatus.DISCONNECTED,
            BrowserStatus.STOPPED,
        }:
            self.browser_available.emit(False)

    def _ensure_browser(self) -> None:
        if self._manager is None:
            self._manager = BrowserManager(
                headless=False,
                on_status=self._on_browser_status,
            )

        if not self._manager.is_running:
            if self._navigation is not None:
                self._navigation.close()
                self._navigation = None
            self._manager.start()

        if self._navigation is None:
            self._navigation = NavigationController(self._manager)
        self._navigation.install()
        self.browser_available.emit(True)

    @Slot(str)
    def open_application(self, url: str) -> None:
        """Open a job application URL in the user's logged-in Google Chrome."""
        try:
            self._emit_status(
                BrowserStatus.NAVIGATING,
                "Opening application in your Google Chrome...",
            )
            self.activity.emit("Opening application in your Google Chrome.")
            open_in_user_chrome(url)
            self.activity.emit(
                "Opened in your Google Chrome (logged-in profile / new tab)."
            )
            self._emit_status(
                BrowserStatus.RUNNING,
                "Opened in your Google Chrome.",
            )
            # Stop Browser does not apply to the user's main Chrome session.
            self.browser_available.emit(False)
        except URLValidationError:
            self._emit_status(
                BrowserStatus.ERROR,
                "Destination blocked by security policy.",
                BrowserErrorCode.DESTINATION_BLOCKED,
            )
            self.operation_failed.emit("Requested destination is not allowed.")
        except (BrowserLaunchError, NavigationError) as exc:
            self._emit_status(
                BrowserStatus.ERROR,
                "Browser could not be started.",
                BrowserErrorCode.LAUNCH_FAILED,
            )
            self.operation_failed.emit(str(exc))
        except Exception:  # noqa: BLE001 - map unexpected failures to a safe UI message
            self._emit_status(
                BrowserStatus.ERROR,
                "Navigation failed.",
                BrowserErrorCode.NAVIGATION_FAILED,
            )
            self.operation_failed.emit("An unexpected browser error occurred.")
        finally:
            self.operation_finished.emit()

    @Slot()
    def stop_browser(self) -> None:
        """Stop any controlled Playwright browser; never close the user's Chrome."""
        if self._navigation is not None:
            self._navigation.close()
            self._navigation = None
        if self._manager is not None:
            self._manager.close()
            self._manager = None
        self.browser_available.emit(False)
        self.activity.emit(
            "Controlled browser stopped. Your main Google Chrome was left open."
        )
        self._emit_status(
            BrowserStatus.STOPPED,
            "Controlled browser stopped.",
        )

    @Slot()
    def shutdown(self) -> None:
        """Release controlled browser resources and terminate the worker lifecycle."""
        if self._shutting_down:
            return
        self._shutting_down = True
        try:
            self.stop_browser()
        finally:
            self.shutdown_complete.emit()
