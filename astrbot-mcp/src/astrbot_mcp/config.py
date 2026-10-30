"""Environment-driven configuration for the AstrBot MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "http://127.0.0.1:6185"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str | None
    username: str | None
    password: str | None
    timeout: float

    @property
    def auth_mode(self) -> str:
        if self.api_key:
            return "api_key"
        if self.username and self.password:
            return "password"
        return "none"


def load_settings() -> Settings:
    """Load settings from environment variables.

    Supported variables:
      - ASTRBOT_BASE_URL:   Dashboard base URL (default http://127.0.0.1:6185)
      - ASTRBOT_API_KEY:    API key created in the AstrBot dashboard (preferred)
      - ASTRBOT_USERNAME / ASTRBOT_PASSWORD: fallback JWT login credentials
      - ASTRBOT_TIMEOUT:    request timeout in seconds (default 30)
    """
    base_url = os.environ.get("ASTRBOT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    api_key = os.environ.get("ASTRBOT_API_KEY", "").strip() or None
    username = os.environ.get("ASTRBOT_USERNAME", "").strip() or None
    password = os.environ.get("ASTRBOT_PASSWORD", "").strip() or None
    try:
        timeout = float(os.environ.get("ASTRBOT_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    return Settings(
        base_url=base_url,
        api_key=api_key,
        username=username,
        password=password,
        timeout=max(timeout, 1.0),
    )
