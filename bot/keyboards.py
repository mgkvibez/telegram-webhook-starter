"""Buttons. One place for the text people see and the data your code receives."""

from __future__ import annotations

from typing import Any, Dict

HELP = "menu:help"
JOKE = "menu:joke"
WEATHER_DEMO = "menu:weather"


def main_menu() -> Dict[str, Any]:
    """An inline keyboard: what beginners actually want to build first."""
    return {"inline_keyboard": [[
        {"text": "Help", "callback_data": HELP},
        {"text": "Tell me a joke", "callback_data": JOKE},
    ], [
        {"text": "Weather in Lagos", "callback_data": WEATHER_DEMO},
    ]]}
