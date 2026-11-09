"""Standalone P1.8 acceptance runner (one check per process via --check N)."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from autoapply.browser.manager import BrowserManager
from autoapply.ui.main_window import MainWindow


# Acceptance harness uses headless Chromium for stability in automation.
_orig_init = BrowserManager.__init__


def _headless_init(self, *args, headless: bool = False, **kwargs):
    return _orig_init(self, *args, headless=True, **kwargs)


BrowserManager.__init__ = _headless_init  # type: ignore[method-assign]


def wait_until(predicate, timeout_s: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout_s
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(100)

    def tick() -> None:
        if predicate() or time.monotonic() >= deadline:
            loop.quit()

    timer.timeout.connect(tick)
    timer.start()
    loop.exec()
    timer.stop()
    return bool(predicate())


def activity(window: MainWindow) -> str:
    return window.activity_log.output.toPlainText()


def status(window: MainWindow) -> str:
    return window.browser_status.status_label.text()


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


def open_url(window: MainWindow, url: str) -> None:
    window.url_input.set_busy(False)
    window.url_input.url_field.setText(url)
    window.url_input._open()


def shutdown(window: MainWindow) -> None:
    if window._thread.isRunning():
        window._worker.shutdown_requested.emit()
        wait_until(lambda: not window._thread.isRunning(), timeout_s=30.0)
    window._allow_close = True
    window.close()
    QApplication.processEvents()


def run_check(number: int) -> tuple[bool, str]:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    app.processEvents()

    try:
        if number == 1:
            open_url(window, "https://example.com")
            ok = wait_until(lambda: "Application website loaded." in activity(window))
            detail = f"status={status(window)!r}"
            return ok and status(window) == "Browser ready", detail

        if number == 2:
            open_url(window, "https://example.com")
            if not wait_until(lambda: "Application website loaded." in activity(window)):
                return False, "failed to load before stop"
            window.url_input.stop_requested.emit()
            ok = wait_until(lambda: status(window) == "Stopped")
            detail = f"status={status(window)!r}"
            return ok and "Browser stopped." in activity(window), detail

        if number == 3:
            open_url(window, "https://example.com")
            if not wait_until(lambda: "Application website loaded." in activity(window)):
                return False, "failed to load before disconnect"
            killed = kill_playwright_chromium()
            ok = killed >= 1 and wait_until(
                lambda: status(window) == "Browser disconnected",
                timeout_s=30.0,
            )
            detail = f"status={status(window)!r}, killed={killed}"
            return ok and "Browser was closed." in activity(window), detail

        if number == 4:
            open_url(window, "http://127.0.0.1/")
            ok = wait_until(
                lambda: "Requested destination is not allowed." in activity(window)
            )
            log = activity(window)
            detail = f"status={status(window)!r}"
            return (
                ok
                and status(window) == "Browser error"
                and "Destination blocked by security policy." in log
                and "127.0.0.1" not in log
            ), detail

        if number == 5:
            open_url(window, "https://example.com")
            if not wait_until(lambda: "Application website loaded." in activity(window)):
                return False, "failed to load before quit"
            shutdown(window)
            leftover = kill_playwright_chromium()
            detail = f"leftover_chromium={leftover}"
            return leftover == 0 and window._worker._manager is None, detail

        return False, f"unknown check {number}"
    finally:
        try:
            shutdown(window)
        except Exception:
            kill_playwright_chromium()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", type=int, choices=range(1, 6))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    names = {
        1: "1/5 Open https://example.com",
        2: "2/5 Stop Browser",
        3: "3/5 Manual Chromium close",
        4: "4/5 Block http://127.0.0.1/",
        5: "5/5 Quit AutoApply",
    }

    if args.check:
        ok, detail = run_check(args.check)
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {names[args.check]}: {detail}", flush=True)
        return 0 if ok else 1

    # Run each check in an isolated subprocess to avoid Playwright/Qt teardown AV.
    codes = []
    for number in range(1, 6):
        proc = subprocess.run(
            [sys.executable, __file__, "--check", str(number)],
            check=False,
        )
        codes.append(proc.returncode)
    passed = sum(code == 0 for code in codes)
    print(f"\nP1.8 acceptance: {passed}/5 passed", flush=True)
    return 0 if passed == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
