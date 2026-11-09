"""Application exception hierarchy."""

from enum import Enum


class AutoApplyError(Exception):
    """Base exception for expected AutoApply failures."""


class ConfigurationError(AutoApplyError):
    """Raised when configuration is missing or invalid."""


class URLValidationError(AutoApplyError):
    """Raised when a supplied URL is invalid or disallowed."""


class BrowserLaunchError(AutoApplyError):
    """Raised when the controlled browser cannot be launched."""


class NavigationError(AutoApplyError):
    """Raised when browser navigation fails."""


class BrowserErrorCode(str, Enum):
    LAUNCH_FAILED = "launch_failed"
    BROWSER_DISCONNECTED = "browser_disconnected"
    NAVIGATION_FAILED = "navigation_failed"
    DESTINATION_BLOCKED = "destination_blocked"
    INTERCEPTION_FAILED = "interception_failed"
    UNKNOWN = "unknown"
