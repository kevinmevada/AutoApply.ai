"""Real Chromium smoke checks for P1.5 navigation interception."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from playwright.sync_api import Error as PlaywrightError

from autoapply.browser import navigation as navigation_module
from autoapply.browser.manager import BrowserManager
from autoapply.browser.navigation import NavigationController
from autoapply.core.exceptions import NavigationError
from autoapply.url.security import validate_public_url

PUBLIC_URL = "https://example.com/"
PRIVATE_URL = "http://127.0.0.1/"


class _RedirectHandler(BaseHTTPRequestHandler):
    """Local fixture: /jump 302s to a loopback private path."""

    def do_GET(self):
        if self.path.startswith("/jump"):
            port = self.server.server_address[1]
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{port}/private")
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"private-resource")

    def log_message(self, format, *args):
        return


@pytest.fixture
def redirect_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield {
            "jump": f"http://127.0.0.1:{port}/jump",
            "private": f"http://127.0.0.1:{port}/private",
        }
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def browser_stack():
    manager = BrowserManager(headless=True)
    controller = NavigationController(manager, timeout_ms=45_000)
    manager.start()
    controller.install()
    try:
        yield manager, controller
    finally:
        controller.close()
        manager.close()


def test_smoke_public_https_page_loads(browser_stack):
    _manager, controller = browser_stack

    page = controller.navigate(PUBLIC_URL)

    assert page.url.startswith("https://example.com")
    assert "Example Domain" in page.title()


def test_smoke_chromium_blocks_direct_loopback_request(browser_stack):
    manager, controller = browser_stack
    controller.navigate(PUBLIC_URL)
    controller._blocked_main_navigation = False

    # Bypass NavigationController.navigate pre-check so Chromium's routed
    # request path is the thing under test.
    with pytest.raises(PlaywrightError):
        manager.page.goto(PRIVATE_URL, timeout=10_000, wait_until="domcontentloaded")

    assert controller._blocked_main_navigation is True


def test_smoke_chromium_blocks_public_to_local_redirect(
    browser_stack,
    redirect_server,
    monkeypatch,
):
    """Chromium follows a 302; the unsafe Location target must be aborted.

    External public redirectors (httpbin/httpbingo) currently return 403 from
    this environment, so the first hop is a local /jump fixture allowlisted
    only for this smoke test. The redirect target remains subject to the real
    destination policy.
    """
    _manager, controller = browser_stack
    jump_url = redirect_server["jump"]
    private_url = redirect_server["private"]

    real_validate = validate_public_url

    def validate_allow_jump(url, resolver=None):
        if url.rstrip("/") == jump_url.rstrip("/") or url.startswith(jump_url):
            return url
        return real_validate(url, resolver=resolver)

    monkeypatch.setattr(navigation_module, "validate_public_url", validate_allow_jump)

    with pytest.raises(NavigationError, match="not publicly reachable"):
        controller.navigate(jump_url)

    assert controller._blocked_main_navigation is True
    assert _manager.page.url.rstrip("/") != private_url.rstrip("/")
