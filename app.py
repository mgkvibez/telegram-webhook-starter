"""A Telegram bot that runs on webhooks, in one file.

    pip install -r requirements.txt
    uvicorn app:app --reload          # local
    # then point Telegram at your public URL (see README)

Three things here are deliberate and worth reading even if you skip the rest:

1. The webhook verifies Telegram's secret token. Without it, anyone who learns
   your URL can post fake updates to your bot.
2. /admin/set-webhook is behind a token. A public endpoint that sets your bot's
   webhook is a bot-hijacking endpoint.
3. Duplicate update ids are ignored, because Telegram retries anything that does
   not answer 200 fast enough.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import FastAPI, Header, HTTPException, Request

from bot.client import TelegramClient
from bot.config import Settings
from bot.dedupe import UpdateGuard
from bot.handlers import handle_update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app")


def create_app(settings: Settings | None = None, client: TelegramClient | None = None) -> FastAPI:
    """Build the app. Tests pass their own settings and client; production takes defaults."""
    settings = settings or Settings.from_env()
    bot = client or TelegramClient(settings.bot_token, api_base=settings.api_base,
                                   timeout=settings.request_timeout)
    guard = UpdateGuard(ttl_seconds=settings.dedupe_ttl_seconds,
                        max_entries=settings.dedupe_max_entries)

    app = FastAPI(title="Telegram Webhook Starter", version="0.1.0",
                  description="The smallest correct Telegram webhook bot.")
    app.state.settings = settings
    app.state.bot = bot
    app.state.guard = guard

    def require_admin(authorization: str | None) -> None:
        if not settings.admin_token:
            raise HTTPException(503, detail="ADMIN_TOKEN is not set; admin routes are disabled. "
                                            "See .env.example.")
        expected = "Bearer " + settings.admin_token
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(401, detail="bad or missing bearer token")

    @app.get("/")
    async def home() -> dict:
        """Something to look at when the deploy finishes."""
        return {"status": "ok", "bot": "telegram-webhook-starter",
                "webhook_endpoint": "/webhook", "health": "/health", "docs": "/docs"}

    @app.get("/health")
    async def health() -> dict:
        """Render and Fly both want a health check. This one does not call Telegram."""
        return {"ok": True, "configured": settings.is_configured()}

    @app.post("/webhook")
    async def webhook(request: Request,
                      x_telegram_bot_api_secret_token: str | None = Header(default=None)) -> dict:
        if not settings.webhook_secret:
            raise HTTPException(503, detail="WEBHOOK_SECRET is not set, so this endpoint refuses "
                                            "unverified updates. See .env.example.")
        if not hmac.compare_digest(x_telegram_bot_api_secret_token or "", settings.webhook_secret):
            raise HTTPException(401, detail="secret token mismatch")

        try:
            update = await request.json()
        except Exception:
            raise HTTPException(400, detail="body must be JSON")
        if not isinstance(update, dict) or "update_id" not in update:
            raise HTTPException(400, detail="not a Telegram update")

        if guard.seen(int(update["update_id"])):
            log.info("duplicate update %s ignored", update["update_id"])
            return {"ok": True, "duplicate": True}

        try:
            await handle_update(update, bot, settings)
        except Exception:
            # Answer 200 anyway: a 500 makes Telegram retry the same broken update
            # in a loop. Log it and fix the handler.
            log.exception("handler failed for update %s", update["update_id"])
        return {"ok": True}

    @app.post("/admin/set-webhook")
    async def set_webhook(url: str, authorization: str | None = Header(default=None)) -> dict:
        """Register this deploy with Telegram, with the secret token attached."""
        require_admin(authorization)
        if not url.startswith("https://"):
            raise HTTPException(400, detail="Telegram only accepts https:// webhook URLs")
        return await bot.set_webhook(url, secret_token=settings.webhook_secret or None)

    @app.get("/admin/webhook-info")
    async def webhook_info(authorization: str | None = Header(default=None)) -> dict:
        """What Telegram currently thinks your webhook is. The first thing to check."""
        require_admin(authorization)
        return await bot.get_webhook_info()

    return app


app = create_app()
