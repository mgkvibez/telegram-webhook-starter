"""Every setting in one place, read from the environment.

Nothing here raises on a missing token: the app must be importable (and /health
must answer) even when half the environment is unset. The endpoints that need a
secret refuse to work instead, so a misconfigured deploy fails loudly at the edge
rather than at import time in a way that looks like a crash.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    bot_token: str = ""
    webhook_secret: str = ""      # Telegram echoes this back in a header; we verify it
    admin_token: str = ""         # protects /admin/set-webhook
    api_base: str = "https://api.telegram.org"
    dedupe_ttl_seconds: int = 900
    dedupe_max_entries: int = 4096
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    github_token: str = ""
    request_timeout: float = 10.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bot_token=os.getenv("BOT_TOKEN", "").strip(),
            webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip(),
            admin_token=os.getenv("ADMIN_TOKEN", "").strip(),
            api_base=os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/"),
            dedupe_ttl_seconds=_int("DEDUPE_TTL_SECONDS", 900),
            dedupe_max_entries=_int("DEDUPE_MAX_ENTRIES", 4096),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
            github_token=os.getenv("GITHUB_TOKEN", "").strip(),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT", "10") or 10),
        )

    def is_configured(self) -> bool:
        """What /health reports. Not a security boundary, just a smoke test."""
        return bool(self.bot_token and self.webhook_secret)
