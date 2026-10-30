"""One test per command, because each command is one branch."""

import asyncio

from bot import handlers, integrations
from bot.config import Settings


def run(update, bot, settings=None):
    asyncio.run(handlers.handle_update(update, bot, settings or Settings()))


def message(text, chat_id=99):
    return {"update_id": 1, "message": {"chat": {"id": chat_id}, "text": text}}


def test_start_greets_with_buttons(bot, settings):
    run(message("/start"), bot, settings)
    assert "webhook bot" in bot.texts()[0]
    assert bot.messages[0]["reply_markup"]["inline_keyboard"]


def test_help_lists_the_commands(bot):
    run(message("/help"), bot)
    assert "/weather" in bot.texts()[0] and "/github" in bot.texts()[0]


def test_joke_rotates(bot):
    run(message("/joke"), bot)
    run(message("/joke"), bot)
    assert bot.texts()[0] in handlers.JOKES
    assert bot.texts()[0] != bot.texts()[1], "the first two jokes should differ"


def test_quote_is_one_of_the_quotes(bot):
    run(message("/quote"), bot)
    assert bot.texts()[0] in handlers.QUOTES


def test_unknown_command_says_so(bot):
    run(message("/teleport"), bot)
    assert "do not know /teleport" in bot.texts()[0]


def test_a_command_with_a_bot_suffix_still_works(bot):
    run(message("/help@my_first_bot"), bot)
    assert "/weather" in bot.texts()[0]


def test_plain_text_is_echoed_and_escaped(bot):
    run(message("<b>bold</b> & <script>"), bot)
    assert "&lt;b&gt;bold&lt;/b&gt;" in bot.texts()[0]
    assert "<script>" not in bot.texts()[0], "user text must not be injected as HTML"


def test_a_non_text_message_gets_a_polite_redirect(bot):
    run({"update_id": 1, "message": {"chat": {"id": 5}, "photo": [{"file_id": "x"}]}}, bot)
    assert "text messages" in bot.texts()[0]


def test_weather_without_a_city_explains_the_usage(bot):
    run(message("/weather"), bot)
    assert "/weather Lagos" in bot.texts()[0]


def test_weather_with_a_city_calls_the_integration(bot, monkeypatch):
    async def fake(city, **kwargs):
        return "Lisbon: 21°C, clear sky."

    monkeypatch.setattr(integrations, "weather", fake)
    run(message("/weather Lisbon"), bot)
    assert "Lisbon" in bot.texts()[0]


def test_ai_without_a_key_explains_what_to_set(bot):
    run(message("/ai what is a decorator"), bot, Settings())
    assert "OPENAI_API_KEY" in bot.texts()[0]


def test_github_without_an_argument_explains_the_usage(bot):
    run(message("/github"), bot)
    assert "/github fastapi/fastapi" in bot.texts()[0]


def test_github_with_a_slug_calls_the_integration(bot, monkeypatch):
    async def fake(slug, **kwargs):
        return "fastapi/fastapi: 80k stars"

    monkeypatch.setattr(integrations, "github_repo", fake)
    run(message("/github fastapi/fastapi"), bot)
    assert "80k stars" in bot.texts()[0]


def test_id_reports_the_chat_id(bot):
    run(message("/id", chat_id=1234567), bot)
    assert "1234567" in bot.texts()[0]


def callback(data, chat_id=99):
    return {"update_id": 2, "callback_query": {"id": "cb-1", "data": data,
                                               "message": {"chat": {"id": chat_id}}}}


def test_a_button_tap_is_acknowledged_and_answered(bot):
    run(callback("menu:help"), bot)
    assert bot.callback_answers[0]["id"] == "cb-1"
    assert "/weather" in bot.texts()[0]


def test_the_weather_button_uses_lagos(bot, monkeypatch):
    async def fake(city, **kwargs):
        return "{}: 30°C".format(city)

    monkeypatch.setattr(integrations, "weather", fake)
    run(callback("menu:weather"), bot)
    assert "Lagos" in bot.texts()[0]


def test_an_unknown_button_says_so(bot):
    run(callback("menu:nope"), bot)
    assert "does nothing yet" in bot.texts()[0]


def test_channel_posts_are_ignored(bot):
    run({"update_id": 3, "channel_post": {"chat": {"id": -100}, "text": "/start"}}, bot)
    assert bot.messages == []
