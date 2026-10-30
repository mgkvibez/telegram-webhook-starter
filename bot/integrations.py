"""Three optional examples, each about fifteen lines.

They are deliberately tiny and all fail soft: an integration that cannot answer
returns a friendly sentence instead of raising, because a raise inside a webhook
handler means Telegram marks the update as failed and retries it forever.

Every function takes an optional `transport`, so the tests answer offline.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
    81: "rain showers", 82: "violent rain showers", 95: "a thunderstorm",
    96: "a thunderstorm with hail", 99: "a thunderstorm with heavy hail",
}


async def _get_json(url: str, params: Optional[Dict[str, Any]] = None, *,
                    timeout: float = 10.0, headers: Optional[Dict[str, str]] = None,
                    transport: Optional[httpx.AsyncBaseTransport] = None) -> Any:
    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()


# 1. AI chat, the one everyone wants to plug in.
async def ask_ai(prompt: str, *, api_key: str, model: str = "gpt-4o-mini",
                 timeout: float = 20.0,
                 transport: Optional[httpx.AsyncBaseTransport] = None) -> str:
    if not api_key:
        return ("The AI example is not configured. Set <code>OPENAI_API_KEY</code> in your "
                "environment and restart. See the README section on integrations.")
    try:
        data = await _post_json(
            "https://api.openai.com/v1/chat/completions",
            {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 300},
            timeout=timeout, headers={"Authorization": "Bearer " + api_key}, transport=transport)
        answer = data["choices"][0]["message"]["content"].strip()
        return answer or "The model returned an empty answer."
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        return "The AI call failed ({})".format(type(exc).__name__)


async def _post_json(url: str, payload: Dict[str, Any], *, timeout: float = 10.0,
                     headers: Optional[Dict[str, str]] = None,
                     transport: Optional[httpx.AsyncBaseTransport] = None) -> Any:
    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


# 2. A plain JSON API with no key at all: free, keyless, good first example.
async def weather(city: str, *, timeout: float = 10.0,
                  transport: Optional[httpx.AsyncBaseTransport] = None) -> str:
    if not city.strip():
        return "Give me a city, like <code>/weather Lagos</code>"
    try:
        geo = await _get_json("https://geocoding-api.open-meteo.com/v1/search",
                              {"name": city, "count": 1, "language": "en", "format": "json"},
                              timeout=timeout, transport=transport)
        results = geo.get("results") or []
        if not results:
            return "I could not find a place called <b>{}</b>.".format(city)
        place = results[0]
        forecast = await _get_json("https://api.open-meteo.com/v1/forecast",
                                   {"latitude": place["latitude"],
                                    "longitude": place["longitude"],
                                    "current": "temperature_2m,weather_code"},
                                   timeout=timeout, transport=transport)
        current = forecast.get("current") or {}
        code = int(current.get("weather_code", -1))
        description = WEATHER_CODES.get(code, "unclear weather")
        return "{}: {:.0f}°C, {}.".format(place.get("name", city),
                                          float(current.get("temperature_2m", 0)), description)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        return "The weather call failed ({})".format(type(exc).__name__)


# 3. Anything with a public API: show people the pattern once.
async def github_repo(slug: str, *, token: str = "", timeout: float = 10.0,
                      transport: Optional[httpx.AsyncBaseTransport] = None) -> str:
    if "/" not in slug:
        return "Give me a repository, like <code>/github fastapi/fastapi</code>"
    owner, _, name = slug.partition("/")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        repo = await _get_json("https://api.github.com/repos/{}/{}".format(owner, name),
                               None, timeout=timeout, headers=headers, transport=transport)
        return ("<b>{}</b>\n⭐ {} stars · 🍴 {} forks · {} open issues".format(
            repo.get("full_name", slug), repo.get("stargazers_count", 0),
            repo.get("forks_count", 0), repo.get("open_issues_count", 0)))
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return "No such repository: <code>{}</code>".format(slug)
        return "GitHub answered {}.".format(exc.response.status_code)
    except (httpx.HTTPError, KeyError, TypeError) as exc:
        return "The GitHub call failed ({})".format(type(exc).__name__)
