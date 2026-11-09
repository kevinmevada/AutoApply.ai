"""Configuration loading contract; implementation is finalized in Phase 1."""

from pathlib import Path
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    """Load and validate application configuration from YAML."""
    raise NotImplementedError("Configuration loader is scaffolded in Phase 0.")
