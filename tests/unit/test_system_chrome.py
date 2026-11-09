from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoapply.browser import system_chrome
from autoapply.core.exceptions import BrowserLaunchError, URLValidationError


def test_open_in_user_chrome_rejects_unsafe_url(monkeypatch):
    monkeypatch.setattr(system_chrome, "find_chrome_executable", lambda: Path("C:/chrome.exe"))
    with pytest.raises(URLValidationError):
        system_chrome.open_in_user_chrome("http://127.0.0.1/")


def test_open_in_user_chrome_launches_system_chrome(monkeypatch):
    chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    monkeypatch.setattr(system_chrome, "find_chrome_executable", lambda: chrome)
    popen = MagicMock()
    monkeypatch.setattr(system_chrome.subprocess, "Popen", popen)

    result = system_chrome.open_in_user_chrome("https://example.com/jobs")

    assert result == "https://example.com/jobs"
    popen.assert_called_once()
    args = popen.call_args.args[0]
    assert args[0] == str(chrome)
    assert args[1] == "https://example.com/jobs"


def test_open_in_user_chrome_requires_chrome(monkeypatch):
    monkeypatch.setattr(system_chrome, "find_chrome_executable", lambda: None)
    with pytest.raises(BrowserLaunchError, match="not found"):
        system_chrome.open_in_user_chrome("https://example.com/")
