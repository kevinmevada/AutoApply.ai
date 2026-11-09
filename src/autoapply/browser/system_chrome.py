"""Open URLs in the user's installed Google Chrome profile."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from autoapply.core.exceptions import BrowserLaunchError
from autoapply.url.security import validate_public_url


def find_chrome_executable() -> Path | None:
    """Locate the system Google Chrome executable on Windows."""
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
    ]
    which = shutil.which("chrome") or shutil.which("google-chrome")
    if which:
        candidates.insert(0, Path(which))
    for path in candidates:
        if path and path.exists():
            return path
    return None


def open_in_user_chrome(raw_url: str) -> str:
    """Validate a URL and open it in the user's default Chrome profile.

    If Chrome is already running, Windows typically opens a new tab in that
    existing session — including the user's logged-in cookies and accounts.
    """
    normalized = validate_public_url(raw_url)
    chrome = find_chrome_executable()
    if chrome is None:
        raise BrowserLaunchError(
            "Google Chrome was not found. Install Chrome or check your PATH."
        )

    try:
        # Opening with the system chrome.exe while Chrome is already running
        # reuses the existing profile/session instead of Chrome for Testing.
        subprocess.Popen(
            [str(chrome), normalized],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        raise BrowserLaunchError("Failed to open Google Chrome.") from exc

    return normalized
