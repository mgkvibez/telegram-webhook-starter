import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from bot.config import Settings  # noqa: E402


class RecordingBot:
    """Stands in for TelegramClient: records instead of sending."""

    def __init__(self):
        self.calls = []
        self.messages = []
        self.callback_answers = []
        self.webhooks = []
        self.info = {"ok": True, "result": {"url": "https://example.test/webhook"}}

    async def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        self.calls.append(("sendMessage", {"chat_id": chat_id, "text": text}))
        return {"ok": True}

    async def answer_callback_query(self, callback_query_id, text=None):
        self.callback_answers.append({"id": callback_query_id, "text": text})
        return {"ok": True}

    async def set_webhook(self, url, secret_token=None):
        self.webhooks.append({"url": url, "secret_token": secret_token})
        return {"ok": True, "description": "Webhook was set"}

    async def get_webhook_info(self):
        return self.info

    async def delete_webhook(self):
        return {"ok": True}

    def texts(self):
        return [m["text"] for m in self.messages]


@pytest.fixture
def bot():
    return RecordingBot()


@pytest.fixture
def settings():
    return Settings(bot_token="123:TEST", webhook_secret="s3cret", admin_token="admin-token",
                    openai_api_key="", github_token="")
