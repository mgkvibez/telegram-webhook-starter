"""What each message means.

Read this file first if you want to add a command: one branch in `_on_message`
is the whole job. Handlers never talk to HTTP directly, they call the passed-in
`bot`, which is what makes them testable without a network.
"""

from __future__ import annotations

import html
import itertools
import logging
from typing import Any, Dict

from . import integrations
from .config import Settings
from .keyboards import main_menu

log = logging.getLogger("handlers")

HELP_TEXT = """<b>Commands</b>
/start - say hello
/help - this list
/joke - a programmer joke
/quote - a line worth reading
/weather Lisbon - live weather, no API key
/ai explain decorators - AI answer (needs OPENAI_API_KEY)
/github fastapi/fastapi - repo stats
/id - your chat id, handy for debugging

Anything else, and I will echo it back."""

JOKES = (
    "Why did the developer go broke? Too much cache.",
    "Two hard things in computing: cache invalidation, naming things, and off-by-one errors.",
    "A QA engineer walks into a bar. Orders 1 beer, 0 beers, -1 beers, then a lizard.",
)

QUOTES = (
    "Make it work, make it right, make it fast.",
    "The best error message is the one that never had to be shown.",
    "Simplicity is prerequisite for reliability. - Dijkstra",
)

# Rotate rather than index by message length, which made /joke repeat itself.
_joke_turn = itertools.count()
_quote_turn = itertools.count()


def _command(text: str):
    """Split '/weather@my_bot Lisbon' into ('/weather', ['Lisbon'])."""
    head, _, rest = text.partition(" ")
    name = head.split("@", 1)[0].lower()
    args = rest.split() if rest.strip() else []
    return name, args


async def handle_update(update: Dict[str, Any], bot, settings: Settings) -> None:
    """The single entry point used by the webhook."""
    if "message" in update:
        await _on_message(update["message"], bot, settings)
    elif "callback_query" in update:
        await _on_callback_query(update["callback_query"], bot, settings)
    # edited_message, channel_post, my_chat_member and friends are ignored on
    # purpose: a starter that answers only to what it was taught is easier to read.


async def _on_message(message: Dict[str, Any], bot, settings: Settings) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    text = (message.get("text") or "").strip()

    if not text:
        await bot.send_message(chat_id, "I understand text messages for now. Try /help.")
        return

    if text.startswith("/"):
        name, args = _command(text)
        if name == "/start":
            await bot.send_message(chat_id,
                                   "Hi! I am a webhook bot: no polling loop, just a URL that "
                                   "Telegram calls.\n\nTap a button or try /help.",
                                   reply_markup=main_menu())
        elif name == "/help":
            await bot.send_message(chat_id, HELP_TEXT)
        elif name == "/joke":
            await bot.send_message(chat_id, JOKES[next(_joke_turn) % len(JOKES)])
        elif name == "/quote":
            await bot.send_message(chat_id, QUOTES[next(_quote_turn) % len(QUOTES)])
        elif name == "/weather":
            if not args:
                await bot.send_message(chat_id, "Which city? Try <code>/weather Lagos</code>")
            else:
                await bot.send_message(chat_id, await integrations.weather(" ".join(args)))
        elif name == "/ai":
            if not args:
                await bot.send_message(
                    chat_id, "Ask me something: <code>/ai what is a decorator</code>")
            else:
                await bot.send_message(chat_id, await integrations.ask_ai(
                    " ".join(args), api_key=settings.openai_api_key,
                    model=settings.openai_model))
        elif name == "/github":
            if not args:
                await bot.send_message(chat_id, "Try <code>/github fastapi/fastapi</code>")
            else:
                await bot.send_message(chat_id, await integrations.github_repo(
                    args[0], token=settings.github_token))
        elif name == "/id":
            await bot.send_message(chat_id, "This chat id is <code>{}</code>".format(chat_id))
        else:
            await bot.send_message(chat_id, "I do not know {} yet. Try /help.".format(
                html.escape(name)))
        return

    # escape() matters: this string is sent with parse_mode=HTML, so a message
    # containing "<b>" would otherwise break the send or inject formatting.
    await bot.send_message(chat_id, "You said: <b>{}</b>\n\nTry /help.".format(
        html.escape(text)))


async def _on_callback_query(query: Dict[str, Any], bot, settings: Settings) -> None:
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    data = query.get("data") or ""
    await bot.answer_callback_query(query.get("id", ""), text="On it")
    if chat_id is None:
        return
    if data == "menu:help":
        await bot.send_message(chat_id, HELP_TEXT)
    elif data == "menu:joke":
        await bot.send_message(chat_id, JOKES[next(_joke_turn) % len(JOKES)])
    elif data == "menu:weather":
        await bot.send_message(chat_id, await integrations.weather("Lagos"))
    else:
        await bot.send_message(chat_id, "That button does nothing yet.")
