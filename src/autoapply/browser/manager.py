"""Manage the lifecycle of the application-controlled Chromium browser."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from autoapply.core.exceptions import BrowserErrorCode, BrowserLaunchError
from autoapply.core.models import BrowserStatus, BrowserStatusEvent

ClosedCallback = Callable[[], None]
StatusCallback = Callable[[BrowserStatusEvent], None]


class BrowserManager:
    """Own one visible Chromium browser, context, and page.

    All methods must be called from the same thread that created the
    manager. GUI integration will place this manager in a worker thread.
    """

    def __init__(
        self,
        *,
        headless: bool = False,
        channel: str = "chrome",
        on_closed: ClosedCallback | None = None,
        on_status: StatusCallback | None = None,
    ) -> None:
        self._headless = headless
        # "chrome" uses the system-installed Google Chrome instead of
        # Playwright's bundled "Chrome for Testing" build.
        self._channel = channel
        self._on_closed = on_closed
        self._on_status = on_status
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._closing = False
        self._status = BrowserStatus.STOPPED
        self._error_code: BrowserErrorCode | None = None

    @property
    def status(self) -> BrowserStatus:
        return self._status

    @property
    def error_code(self) -> BrowserErrorCode | None:
        return self._error_code

    @property
    def is_running(self) -> bool:
        if self._browser is None or self._page is None:
            return False
        try:
            return self._browser.is_connected() and not self._page.is_closed()
        except Exception:  # noqa: BLE001 - treat any probe failure as not running
            return False

    @property
    def browser(self) -> Browser | None:
        return self._browser

    @property
    def context(self) -> BrowserContext | None:
        return self._context

    @property
    def page(self) -> Page | None:
        return self._page

    def report_status(
        self,
        status: BrowserStatus,
        message: str,
        error_code: BrowserErrorCode | None = None,
    ) -> None:
        """Publish a safe status event for the application UI."""
        if status == self._status and error_code == self._error_code:
            return
        self._status = status
        self._error_code = error_code
        if self._on_status is not None:
            self._on_status(
                BrowserStatusEvent(
                    status=status,
                    message=message,
                    error_code=error_code,
                )
            )

    def start(self) -> Page:
        """Launch Chromium if needed and return the application-controlled page."""
        if self.is_running and self._page is not None:
            return self._page

        if self._playwright is not None or self._browser is not None:
            self._shutdown(notify=False)

        self.report_status(
            BrowserStatus.STARTING,
            "Starting browser.",
        )

        try:
            self._playwright = sync_playwright().start()
            launch_kwargs: dict[str, Any] = {
                "headless": self._headless,
            }
            if self._channel:
                launch_kwargs["channel"] = self._channel
            if not self._headless:
                launch_kwargs["args"] = ["--start-maximized"]
            self._browser = self._playwright.chromium.launch(**launch_kwargs)
            context_kwargs: dict[str, Any] = {
                "service_workers": "block",
            }
            if not self._headless:
                # Use the real window size instead of a small default viewport.
                context_kwargs["no_viewport"] = True
            self._context = self._browser.new_context(**context_kwargs)
            self._page = self._context.new_page()
            self._browser.on("disconnected", self._handle_disconnected)
            self.report_status(
                BrowserStatus.RUNNING,
                "Browser is ready.",
            )
            return self._page
        except BrowserLaunchError:
            self._shutdown(notify=False)
            self.report_status(
                BrowserStatus.ERROR,
                "Browser could not be started.",
                BrowserErrorCode.LAUNCH_FAILED,
            )
            raise
        except Exception as exc:
            self._shutdown(notify=False)
            self.report_status(
                BrowserStatus.ERROR,
                "Browser could not be started.",
                BrowserErrorCode.LAUNCH_FAILED,
            )
            raise BrowserLaunchError(
                "Failed to launch Google Chrome. Is Chrome installed?"
            ) from exc

    def close(self) -> None:
        """Release browser resources owned by this manager."""
        self._shutdown(notify=True, reason="stopped")

    def _handle_disconnected(self, *_args: Any) -> None:
        if self._closing:
            return
        self._shutdown(notify=True, reason="disconnected")

    def _shutdown(self, *, notify: bool, reason: str = "stopped") -> None:
        if self._closing:
            return

        self._closing = True
        had_session = self._playwright is not None or self._browser is not None
        try:
            if self._context is not None:
                try:
                    self._context.close()
                except Exception:  # noqa: BLE001, S110 - best-effort shutdown
                    pass
            if self._browser is not None:
                try:
                    self._browser.close()
                except Exception:  # noqa: BLE001, S110 - best-effort shutdown
                    pass
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                except Exception:  # noqa: BLE001, S110 - best-effort shutdown
                    pass
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._closing = False
            if notify and had_session:
                if reason == "disconnected":
                    self.report_status(
                        BrowserStatus.DISCONNECTED,
                        "Browser was closed.",
                        BrowserErrorCode.BROWSER_DISCONNECTED,
                    )
                else:
                    self.report_status(
                        BrowserStatus.STOPPED,
                        "Browser stopped.",
                    )
                if self._on_closed is not None:
                    self._on_closed()
