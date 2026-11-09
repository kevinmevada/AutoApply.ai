"""Secure browser navigation and request interception."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import (
    BrowserContext,
    Page,
    Route,
)

from autoapply.browser.manager import BrowserManager
from autoapply.core.exceptions import (
    BrowserErrorCode,
    NavigationError,
    URLValidationError,
)
from autoapply.core.models import BrowserStatus
from autoapply.url.security import validate_public_url

Resolver = Callable[..., list]

_HTTP_SCHEMES = frozenset({"http", "https"})
_REDIRECT_STATUS = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 20


class NavigationController:
    """Enforce destination validation during browser navigation."""

    def __init__(
        self,
        manager: BrowserManager,
        *,
        resolver: Resolver = socket.getaddrinfo,
        timeout_ms: int = 60_000,
    ) -> None:
        self._manager = manager
        self._resolver = resolver
        self._timeout_ms = timeout_ms
        self._installed = False
        self._blocked_main_navigation = False
        self._allowed_hosts: set[str] = set()
        self._blocked_hosts: set[str] = set()
        # Bound methods are recreated on access; keep one identity for route/unroute.
        self._route_handler = self._handle_route

    def install(self) -> None:
        """Activate request interception on the browser context."""
        context = self._require_context()
        if self._installed:
            return
        try:
            context.route("**/*", self._route_handler)
            self._installed = True
        except Exception as exc:
            self._manager.report_status(
                BrowserStatus.ERROR,
                "Browser request protection could not be installed.",
                BrowserErrorCode.INTERCEPTION_FAILED,
            )
            raise NavigationError("Could not install browser request protection.") from exc

    def navigate(self, url: str) -> Page:
        """Validate and navigate to a public HTTP(S) destination."""
        if not self._installed:
            self.install()

        try:
            normalized = validate_public_url(
                url,
                resolver=self._resolver,
            )
        except URLValidationError as exc:
            self._manager.report_status(
                BrowserStatus.ERROR,
                "Destination blocked by security policy.",
                BrowserErrorCode.DESTINATION_BLOCKED,
            )
            raise NavigationError("Requested destination is not allowed.") from exc

        page = self._require_page()
        self._blocked_main_navigation = False
        self._manager.report_status(
            BrowserStatus.NAVIGATING,
            "Navigating to application.",
        )

        try:
            page.goto(
                normalized,
                wait_until="domcontentloaded",
                timeout=self._timeout_ms,
            )
            # Job-board SPAs often keep the initial shell title until scripts finish.
            page.wait_for_load_state("load", timeout=self._timeout_ms)
            try:
                page.bring_to_front()
            except Exception:  # noqa: BLE001, S110 - best-effort window focus
                pass
        except NavigationError:
            raise
        except Exception as exc:
            if self._blocked_main_navigation:
                self._manager.report_status(
                    BrowserStatus.ERROR,
                    "Destination blocked by security policy.",
                    BrowserErrorCode.DESTINATION_BLOCKED,
                )
                raise NavigationError(
                    "Navigation was blocked because the destination is not publicly reachable."
                ) from exc
            self._manager.report_status(
                BrowserStatus.ERROR,
                "Navigation failed.",
                BrowserErrorCode.NAVIGATION_FAILED,
            )
            raise NavigationError("Navigation failed.") from exc

        if self._blocked_main_navigation:
            self._manager.report_status(
                BrowserStatus.ERROR,
                "Destination blocked by security policy.",
                BrowserErrorCode.DESTINATION_BLOCKED,
            )
            raise NavigationError(
                "Navigation was blocked because the destination is not publicly reachable."
            )

        self._manager.report_status(
            BrowserStatus.RUNNING,
            "Navigation complete.",
        )
        return page

    def close(self) -> None:
        """Remove interception and release controller state."""
        context = self._manager.context
        if self._installed and context is not None:
            try:
                context.unroute("**/*", self._route_handler)
            except Exception:  # noqa: BLE001, S110 - best-effort cleanup
                pass
        self._installed = False
        self._blocked_main_navigation = False
        self._allowed_hosts.clear()
        self._blocked_hosts.clear()

    def _require_context(self) -> BrowserContext:
        context = self._manager.context
        if context is None or not self._manager.is_running:
            raise NavigationError("Browser is not running.")
        return context

    def _require_page(self) -> Page:
        page = self._manager.page
        if page is None or not self._manager.is_running:
            raise NavigationError("Browser is not running.")
        return page

    def _is_main_document_request(self, request) -> bool:
        if not request.is_navigation_request():
            return False
        frame = getattr(request, "frame", None)
        if frame is None:
            return True
        parent = getattr(frame, "parent_frame", None)
        return parent is None

    def _host_key(self, url: str) -> str | None:
        hostname = urlsplit(url).hostname
        if hostname is None:
            return None
        return hostname.lower().rstrip(".")

    def _is_ip_literal(self, host: str) -> bool:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return False
        return True

    def _validate_destination(self, url: str) -> None:
        host = self._host_key(url)
        if host is not None:
            if host in self._blocked_hosts:
                raise URLValidationError(
                    "URLs targeting private or non-public IP addresses are not allowed."
                )
            # Cache DNS hostnames only. IP literals are rechecked every time so a
            # one-off allowlist cannot unlock other paths on the same address.
            if host in self._allowed_hosts and not self._is_ip_literal(host):
                return

        validate_public_url(url, resolver=self._resolver)
        if host is not None and not self._is_ip_literal(host):
            self._allowed_hosts.add(host)

    def _fetch_with_redirect_policy(self, route: Route, start_url: str):
        """Fetch a main-document URL while validating every redirect hop.

        Playwright's ``route.continue_()`` lets Chromium follow redirects
        outside the route handler. Fetching with ``max_redirects=0`` keeps
        each hop under our destination policy before the response is fulfilled.
        """
        current = start_url
        response = None
        for _ in range(_MAX_REDIRECTS):
            scheme = urlsplit(current).scheme.lower()
            if scheme not in _HTTP_SCHEMES:
                raise URLValidationError("Only HTTP and HTTPS URLs are supported.")
            self._validate_destination(current)
            response = route.fetch(url=current, max_redirects=0)
            if response.status not in _REDIRECT_STATUS:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            current = urljoin(current, location)
        raise URLValidationError("Too many redirects.")

    def _handle_route(self, route: Route) -> None:
        request = route.request
        url = request.url
        scheme = urlsplit(url).scheme.lower()

        # Non-HTTP(S) schemes (about:, data:, blob:) are not destination SSRF vectors
        # for this controller; leave them alone.
        if scheme not in _HTTP_SCHEMES:
            route.continue_()
            return

        try:
            if self._is_main_document_request(request):
                # Main navigations: inspect redirects hop-by-hop, then fulfill.
                response = self._fetch_with_redirect_policy(route, url)
                route.fulfill(response=response)
            else:
                # Subresources: validate destination, then let Chromium fetch natively.
                # Re-proxying every script/XHR via fetch+fulfill stalls modern job SPAs.
                self._validate_destination(url)
                route.continue_()
        except URLValidationError:
            host = self._host_key(url)
            if host is not None:
                self._blocked_hosts.add(host)
            if self._is_main_document_request(request):
                self._blocked_main_navigation = True
            # Fail closed. Do not log the URL or query string.
            route.abort("blockedbyclient")
        except Exception:  # noqa: BLE001 - fail closed on unexpected fetch/route errors
            if self._is_main_document_request(request):
                self._blocked_main_navigation = True
            route.abort("failed")
