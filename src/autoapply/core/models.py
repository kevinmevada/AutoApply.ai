"""Shared application domain models."""

from dataclasses import dataclass
from enum import Enum

from autoapply.core.exceptions import BrowserErrorCode


class BrowserStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    NAVIGATING = "navigating"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class BrowserStatusEvent:
    """A safe browser lifecycle or navigation status notification."""

    status: BrowserStatus
    message: str
    error_code: BrowserErrorCode | None = None
