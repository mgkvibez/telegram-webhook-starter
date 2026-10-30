"""The only code that talks to Telegram.

Async on purpose. A plain `requests.post` inside an `async def` blocks the event
loop, which means one slow Telegram call stalls every other request your app is
serving. `httpx.AsyncClient` does not.

`transport` exists so tests can answer without a network: pass an
`httpx.MockTransport` and every call is answered offline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("telegram")

API_BASE = "https://api.telegram.org"


class TelegramClient:
    def __init__(self, token: str, api_base: str = API_BASE, timeout: float = 10.0,
                 transport: Optional[httpx.AsyncBaseTransport] = None):
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.transport = transport
        self.calls: List[Dict[str, Any]] = []   # every call made, handy in tests

    async def call(self, method: str, **payload: Any) -> Dict[str, Any]:
        self.calls.append({"method": method, "payload": payload})
        if not self.token:
            log.warning("BOT_TOKEN is not set; skipping %s", method)
            return {"ok": False, "description": "BOT_TOKEN is not set"}
        url = "{}/bot{}/{}".format(self.api_base, self.token, method)
        try:
            async with httpx.AsyncClient(transport=self.transport,
                                         timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            log.warning("telegram %s failed: %s", method, exc)
            return {"ok": False, "description": str(exc)}
        try:
            return response.json()
        except ValueError:
            return {"ok": False, "description": "non-JSON response from Telegram"}

    async def send_message(self, chat_id: int, text: str,
                           reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "text": text,
                                   "parse_mode": "HTML",
                                   "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.call("sendMessage", **payload)

    async def answer_callback_query(self, callback_query_id: str,
                                    text: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return await self.call("answerCallbackQuery", **payload)

    async def set_webhook(self, url: str, secret_token: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"url": url, "drop_pending_updates": True,
                                   "allowed_updates": ["message", "callback_query"]}
        if secret_token:
            payload["secret_token"] = secret_token
        return await self.call("setWebhook", **payload)

    async def get_webhook_info(self) -> Dict[str, Any]:
        return await self.call("getWebhookInfo")

    async def delete_webhook(self) -> Dict[str, Any]:
        return await self.call("deleteWebhook")
