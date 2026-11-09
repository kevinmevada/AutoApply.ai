import pytest

from autoapply.browser import manager as browser_module
from autoapply.browser.manager import BrowserManager
from autoapply.core.exceptions import BrowserErrorCode, BrowserLaunchError
from autoapply.core.models import BrowserStatus


class FakeEventObject:
    def __init__(self):
        self.handlers = {}

    def on(self, event, callback):
        self.handlers[event] = callback

    def emit(self, event):
        if event in self.handlers:
            self.handlers[event]()


class FakePage:
    def __init__(self):
        self.closed = False

    def is_closed(self):
        return self.closed


class FakeContext(FakeEventObject):
    def __init__(self):
        super().__init__()
        self.page = FakePage()
        self.close_called = False

    def new_page(self):
        return self.page

    def close(self):
        self.close_called = True


class FakeBrowser(FakeEventObject):
    def __init__(self):
        super().__init__()
        self.context = FakeContext()
        self.context_options = None
        self.close_called = False
        self.connected = True

    def is_connected(self):
        return self.connected

    def new_context(self, **kwargs):
        self.context_options = kwargs
        return self.context

    def close(self):
        self.close_called = True
        self.connected = False
        self.emit("disconnected")


class FakeChromium:
    def __init__(self, browser: FakeBrowser):
        self.browser = browser
        self.launch_calls = 0
        self.fail = False
        self.last_headless = None

    def launch(self, headless=False, args=None, channel=None):
        self.launch_calls += 1
        self.last_headless = headless
        self.last_args = args
        self.last_channel = channel
        if self.fail:
            raise RuntimeError("launch exploded")
        return self.browser


class FakePlaywright:
    def __init__(self, browser: FakeBrowser):
        self.chromium = FakeChromium(browser)
        self.stop_called = False

    def stop(self):
        self.stop_called = True


class FakePlaywrightFactory:
    def __init__(self, playwright: FakePlaywright):
        self.playwright = playwright
        self.start_calls = 0

    def __call__(self):
        return self

    def start(self):
        self.start_calls += 1
        return self.playwright


@pytest.fixture
def fake_stack(monkeypatch):
    browser = FakeBrowser()
    playwright = FakePlaywright(browser)
    factory = FakePlaywrightFactory(playwright)
    monkeypatch.setattr(browser_module, "sync_playwright", factory)
    return browser, playwright, factory


def test_is_running_false_before_start():
    manager = BrowserManager()
    assert manager.is_running is False
    assert manager.browser is None
    assert manager.context is None
    assert manager.page is None


def test_start_returns_page_and_exposes_handles(fake_stack):
    browser, playwright, factory = fake_stack
    manager = BrowserManager(headless=False)

    page = manager.start()

    assert page is browser.context.page
    assert manager.is_running is True
    assert manager.browser is browser
    assert manager.context is browser.context
    assert manager.page is page
    assert factory.start_calls == 1
    assert playwright.chromium.launch_calls == 1
    assert playwright.chromium.last_headless is False
    assert playwright.chromium.last_channel == "chrome"
    assert playwright.chromium.browser.context_options == {
        "service_workers": "block",
        "no_viewport": True,
    }
    assert playwright.chromium.last_args == ["--start-maximized"]


def test_start_is_idempotent(fake_stack):
    _browser, playwright, factory = fake_stack
    manager = BrowserManager()

    first = manager.start()
    second = manager.start()

    assert first is second
    assert factory.start_calls == 1
    assert playwright.chromium.launch_calls == 1


def test_close_releases_resources_and_notifies(fake_stack):
    browser, playwright, _factory = fake_stack
    closed = []
    manager = BrowserManager(on_closed=lambda: closed.append("closed"))

    manager.start()
    manager.close()

    assert manager.is_running is False
    assert browser.close_called is True
    assert browser.context.close_called is True
    assert playwright.stop_called is True
    assert manager.browser is None
    assert manager.context is None
    assert manager.page is None
    assert closed == ["closed"]


def test_manual_disconnect_triggers_on_closed(fake_stack):
    browser, playwright, _factory = fake_stack
    closed = []
    manager = BrowserManager(on_closed=lambda: closed.append("closed"))

    manager.start()
    browser.connected = False
    browser.emit("disconnected")

    assert manager.is_running is False
    assert playwright.stop_called is True
    assert closed == ["closed"]


def test_close_does_not_double_notify_on_disconnect(fake_stack):
    browser, _playwright, _factory = fake_stack
    closed = []
    manager = BrowserManager(on_closed=lambda: closed.append("closed"))

    manager.start()
    manager.close()

    assert closed == ["closed"]
    # FakeBrowser.close emits disconnected; manager must ignore it while closing.
    assert browser.close_called is True


def test_launch_failure_raises_browser_launch_error(fake_stack):
    _browser, playwright, factory = fake_stack
    playwright.chromium.fail = True
    manager = BrowserManager()

    with pytest.raises(BrowserLaunchError, match="Failed to launch"):
        manager.start()

    assert manager.is_running is False
    assert manager.browser is None
    assert factory.start_calls == 1
    assert playwright.stop_called is True


def test_close_when_not_started_is_safe():
    closed = []
    manager = BrowserManager(on_closed=lambda: closed.append("closed"))

    manager.close()

    assert manager.is_running is False
    assert closed == []


def test_start_emits_starting_and_running(fake_stack):
    events = []
    manager = BrowserManager(on_status=events.append)

    manager.start()

    assert [event.status for event in events] == [
        BrowserStatus.STARTING,
        BrowserStatus.RUNNING,
    ]
    assert manager.status == BrowserStatus.RUNNING


def test_manual_close_emits_disconnected(fake_stack):
    browser, _playwright, _factory = fake_stack
    events = []
    manager = BrowserManager(on_status=events.append)

    manager.start()
    browser.emit("disconnected")

    assert manager.status == BrowserStatus.DISCONNECTED
    assert events[-1].error_code == BrowserErrorCode.BROWSER_DISCONNECTED


def test_intentional_close_emits_stopped(fake_stack):
    events = []
    manager = BrowserManager(on_status=events.append)

    manager.start()
    manager.close()

    assert manager.status == BrowserStatus.STOPPED
    assert events[-1].status == BrowserStatus.STOPPED
    assert events[-1].error_code is None


def test_launch_failure_emits_error(fake_stack):
    _browser, playwright, _factory = fake_stack
    playwright.chromium.fail = True
    events = []
    manager = BrowserManager(on_status=events.append)

    with pytest.raises(BrowserLaunchError):
        manager.start()

    assert manager.status == BrowserStatus.ERROR
    assert events[-1].error_code == BrowserErrorCode.LAUNCH_FAILED
    assert "could not be started" in events[-1].message.lower()
