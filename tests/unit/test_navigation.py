from types import SimpleNamespace

import pytest

from autoapply.browser.navigation import NavigationController
from autoapply.core.exceptions import BrowserErrorCode, NavigationError
from autoapply.core.models import BrowserStatus

PUBLIC_RESOLVER = lambda *args, **kwargs: [
    (
        2,
        1,
        6,
        "",
        ("93.184.216.34", 443),
    )
]


class FakeRequest:
    def __init__(self, url, *, navigation=False, frame=None):
        self.url = url
        self._navigation = navigation
        self.frame = frame

    def is_navigation_request(self):
        return self._navigation


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b"ok"):
        self.status = status
        self.headers = headers or {"content-type": "text/plain"}
        self._body = body

    def body(self):
        return self._body


class FakeRoute:
    def __init__(self, request, *, fetch_response=None):
        self.request = request
        self.action = None
        self.abort_error = None
        self.fulfill_args = None
        self.fetch_calls = []
        self.fetch_response = fetch_response or FakeResponse()

    def continue_(self):
        self.action = "continue"

    def abort(self, error_code="failed"):
        self.action = "abort"
        self.abort_error = error_code

    def fetch(self, url=None, max_redirects=None, **kwargs):
        self.fetch_calls.append({"url": url or self.request.url, "max_redirects": max_redirects})
        return self.fetch_response

    def fulfill(self, **kwargs):
        self.action = "fulfill"
        self.fulfill_args = kwargs


class FakeContext:
    def __init__(self):
        self.routes = []
        self.unroute_calls = []

    def route(self, pattern, handler):
        self.routes.append((pattern, handler))

    def unroute(self, pattern, handler=None):
        self.unroute_calls.append((pattern, handler))
        self.routes = [
            (p, h)
            for (p, h) in self.routes
            if not (p == pattern and (handler is None or h is handler))
        ]


class FakePage:
    def __init__(self):
        self.goto_calls = []
        self.load_state_calls = []
        self.goto_error = None
        self.closed = False

    def is_closed(self):
        return self.closed

    def goto(self, url, **kwargs):
        self.goto_calls.append((url, kwargs))
        if self.goto_error is not None:
            raise self.goto_error

    def wait_for_load_state(self, state, **kwargs):
        self.load_state_calls.append((state, kwargs))
        if self.goto_error is not None:
            raise self.goto_error


class FakeManager:
    def __init__(self, *, running=True):
        self.context = FakeContext()
        self.page = FakePage()
        self._running = running
        self.status_events = []

    @property
    def is_running(self):
        return self._running

    def report_status(self, status, message, error_code=None):
        self.status_events.append((status, message, error_code))


def _controller(manager=None, resolver=PUBLIC_RESOLVER):
    return NavigationController(
        manager or FakeManager(),
        resolver=resolver,
        timeout_ms=5_000,
    )


def test_install_registers_context_route():
    manager = FakeManager()
    controller = _controller(manager)

    controller.install()

    assert len(manager.context.routes) == 1
    pattern, handler = manager.context.routes[0]
    assert pattern == "**/*"
    assert callable(handler)


def test_install_is_idempotent():
    manager = FakeManager()
    controller = _controller(manager)

    controller.install()
    controller.install()

    assert len(manager.context.routes) == 1


def test_install_requires_running_browser():
    manager = FakeManager(running=False)
    manager.context = None
    controller = _controller(manager)

    with pytest.raises(NavigationError, match="Browser is not running"):
        controller.install()


def test_navigate_validates_and_calls_goto():
    manager = FakeManager()
    controller = _controller(manager)

    page = controller.navigate("https://example.com/jobs")

    assert page is manager.page
    assert manager.page.goto_calls == [
        (
            "https://example.com/jobs",
            {"wait_until": "domcontentloaded", "timeout": 5_000},
        )
    ]
    assert len(manager.context.routes) == 1


def test_navigate_rejects_invalid_url_before_goto():
    manager = FakeManager()
    controller = _controller(manager)

    with pytest.raises(NavigationError):
        controller.navigate("javascript:alert(1)")

    assert manager.page.goto_calls == []


def test_route_continues_public_subresource():
    controller = _controller()
    controller.install()
    route = FakeRoute(FakeRequest("https://example.com/style.css"))

    controller._handle_route(route)

    assert route.action == "continue"
    assert route.fetch_calls == []


def test_route_fulfills_public_main_navigation():
    controller = _controller()
    controller.install()
    route = FakeRoute(
        FakeRequest(
            "https://example.com/jobs",
            navigation=True,
            frame=SimpleNamespace(parent_frame=None),
        )
    )

    controller._handle_route(route)

    assert route.action == "fulfill"
    assert route.fetch_calls == [
        {"url": "https://example.com/jobs", "max_redirects": 0}
    ]
    assert route.fulfill_args == {"response": route.fetch_response}


def test_route_aborts_private_destination():
    controller = _controller()
    controller.install()
    route = FakeRoute(FakeRequest("https://127.0.0.1/secret"))

    controller._handle_route(route)

    assert route.action == "abort"
    assert route.abort_error == "blockedbyclient"


def test_route_allows_non_http_schemes():
    controller = _controller()
    controller.install()
    route = FakeRoute(FakeRequest("data:text/plain,hello"))

    controller._handle_route(route)

    assert route.action == "continue"


def test_blocked_main_navigation_raises_navigation_error():
    manager = FakeManager()
    controller = _controller(manager)
    controller.install()
    _, handler = manager.context.routes[0]

    def goto_with_block(url, **kwargs):
        handler(
            FakeRoute(
                FakeRequest(
                    "https://192.168.1.10/",
                    navigation=True,
                    frame=SimpleNamespace(parent_frame=None),
                )
            )
        )
        raise RuntimeError("net::ERR_BLOCKED_BY_CLIENT")

    manager.page.goto = goto_with_block

    with pytest.raises(NavigationError, match="not publicly reachable"):
        controller.navigate("https://example.com/")


def test_blocked_subresource_does_not_fail_navigation():
    manager = FakeManager()
    controller = _controller(manager)
    controller.install()
    _, handler = manager.context.routes[0]

    def goto_with_subresource_block(url, **kwargs):
        handler(
            FakeRoute(
                FakeRequest(
                    "https://10.0.0.5/tracker.js",
                    navigation=False,
                )
            )
        )

    manager.page.goto = goto_with_subresource_block

    page = controller.navigate("https://example.com/")
    assert page is manager.page


def test_close_removes_interception():
    manager = FakeManager()
    controller = _controller(manager)
    controller.install()
    handler = manager.context.routes[0][1]

    controller.close()

    assert manager.context.routes == []
    assert manager.context.unroute_calls == [("**/*", handler)]


def test_unexpected_validation_failure_is_fail_closed(monkeypatch):
    controller = _controller()
    controller.install()

    def boom(url, resolver=None):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(
        "autoapply.browser.navigation.validate_public_url",
        boom,
    )
    route = FakeRoute(
        FakeRequest(
            "https://example.com/",
            navigation=True,
            frame=SimpleNamespace(parent_frame=None),
        )
    )

    controller._handle_route(route)

    assert route.action == "abort"
    assert route.abort_error == "failed"
    assert controller._blocked_main_navigation is True


def test_successful_navigation_emits_running():
    manager = FakeManager()
    controller = NavigationController(
        manager,
        resolver=PUBLIC_RESOLVER,
    )

    controller.navigate("https://example.com")

    assert [event[0] for event in manager.status_events] == [
        BrowserStatus.NAVIGATING,
        BrowserStatus.RUNNING,
    ]


def test_blocked_destination_emits_error():
    manager = FakeManager()
    controller = NavigationController(
        manager,
        resolver=PUBLIC_RESOLVER,
    )

    with pytest.raises(NavigationError):
        controller.navigate("http://127.0.0.1/")

    assert manager.status_events[-1][0] == BrowserStatus.ERROR
    assert manager.status_events[-1][2] == BrowserErrorCode.DESTINATION_BLOCKED


def test_navigation_failure_emits_error():
    manager = FakeManager()
    manager.page.goto_error = RuntimeError("timeout")
    controller = NavigationController(
        manager,
        resolver=PUBLIC_RESOLVER,
    )

    with pytest.raises(NavigationError, match="Navigation failed"):
        controller.navigate("https://example.com/")

    assert manager.status_events[-1][0] == BrowserStatus.ERROR
    assert manager.status_events[-1][2] == BrowserErrorCode.NAVIGATION_FAILED
