"""P1.8 engine-level acceptance (no Qt) covering the five Phase 1 behaviors."""

from __future__ import annotations

import subprocess
import sys

from autoapply.browser.manager import BrowserManager
from autoapply.browser.navigation import NavigationController
from autoapply.core.exceptions import BrowserErrorCode, NavigationError
from autoapply.core.models import BrowserStatus, BrowserStatusEvent


def kill_playwright_chromium() -> int:
    ps = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.Name -match 'chrome|chromium' -and "
                "$_.CommandLine -match 'playwright|chrome-win' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
                "-ErrorAction SilentlyContinue; $_.ProcessId }"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return len([line for line in ps.stdout.splitlines() if line.strip().isdigit()])


def main() -> int:
    events: list[BrowserStatusEvent] = []
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)

    manager = BrowserManager(headless=True, on_status=events.append)
    nav = NavigationController(manager)

    # 1/5 Open example.com
    try:
        manager.start()
        nav.install()
        nav.navigate("https://example.com")
        ok = manager.status == BrowserStatus.RUNNING and manager.is_running
        record("1/5 Open https://example.com", ok, f"status={manager.status.value}")
    except Exception as exc:
        record("1/5 Open https://example.com", False, type(exc).__name__)

    # 2/5 Stop Browser
    try:
        nav.close()
        manager.close()
        ok = manager.status == BrowserStatus.STOPPED and not manager.is_running
        record("2/5 Stop Browser", ok, f"status={manager.status.value}")
    except Exception as exc:
        record("2/5 Stop Browser", False, type(exc).__name__)

    # 3/5 Manual Chromium close → DISCONNECTED
    try:
        events.clear()
        manager = BrowserManager(headless=True, on_status=events.append)
        nav = NavigationController(manager)
        manager.start()
        nav.install()
        nav.navigate("https://example.com")
        # Simulate the user closing the Chromium window (not Stop Browser).
        browser = manager.browser
        assert browser is not None
        try:
            browser.close()
        except Exception:
            # Browser may already be gone; disconnect callback still required.
            pass
        import time

        deadline = time.monotonic() + 10
        while (
            time.monotonic() < deadline
            and manager.status != BrowserStatus.DISCONNECTED
        ):
            time.sleep(0.1)
        ok = manager.status == BrowserStatus.DISCONNECTED and any(
            e.error_code == BrowserErrorCode.BROWSER_DISCONNECTED for e in events
        )
        record(
            "3/5 Manual Chromium close",
            ok,
            f"status={manager.status.value}",
        )
        try:
            nav.close()
            manager.close()
        except Exception:
            pass
        kill_playwright_chromium()
    except Exception as exc:
        record("3/5 Manual Chromium close", False, type(exc).__name__)
        kill_playwright_chromium()

    # 4/5 Block loopback with safe error
    try:
        kill_playwright_chromium()
        events.clear()
        manager = BrowserManager(headless=True, on_status=events.append)
        nav = NavigationController(manager)
        manager.start()
        nav.install()
        blocked = False
        message = "no error"
        try:
            nav.navigate("http://127.0.0.1/")
        except NavigationError as exc:
            blocked = "not allowed" in str(exc).lower() or "blocked" in str(exc).lower()
            message = str(exc)
        ok = (
            blocked
            and manager.status == BrowserStatus.ERROR
            and any(e.error_code == BrowserErrorCode.DESTINATION_BLOCKED for e in events)
            and "127.0.0.1" not in message
        )
        record("4/5 Block http://127.0.0.1/", ok, f"status={manager.status.value}")
        nav.close()
        manager.close()
    except Exception as exc:
        record("4/5 Block http://127.0.0.1/", False, type(exc).__name__)
        kill_playwright_chromium()

    # 5/5 Quit / clean shutdown
    try:
        kill_playwright_chromium()
        events.clear()
        manager = BrowserManager(headless=True, on_status=events.append)
        nav = NavigationController(manager)
        manager.start()
        nav.install()
        nav.navigate("https://example.com")
        nav.close()
        manager.close()
        leftover = kill_playwright_chromium()
        ok = (
            leftover == 0
            and not manager.is_running
            and manager.status == BrowserStatus.STOPPED
        )
        record("5/5 Quit / clean shutdown", ok, f"leftover_chromium={leftover}")
    except Exception as exc:
        record("5/5 Quit / clean shutdown", False, type(exc).__name__)
        kill_playwright_chromium()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nP1.8 engine acceptance: {passed}/{len(results)} passed", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
