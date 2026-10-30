"""Integrations answer offline, through httpx.MockTransport.

The point is not just coverage: these tests prove the failure paths return a
sentence instead of raising, because a raise inside a webhook handler makes
Telegram retry the same update forever.
"""

import asyncio

import httpx

from bot import integrations


def transport(handler):
    return httpx.MockTransport(handler)


def run(coro):
    return asyncio.run(coro)


GEO = {"results": [{"name": "Lisbon", "latitude": 38.7, "longitude": -9.1}]}
FORECAST = {"current": {"temperature_2m": 21.4, "weather_code": 0}}


def routing_handler(routes):
    def handler(request):
        for path_fragment, response in routes.items():
            if path_fragment in str(request.url):
                return response
        return httpx.Response(404, json={"error": "unmapped"})
    return handler


def test_weather_reads_geocoding_then_forecast():
    handler = routing_handler({
        "geocoding": httpx.Response(200, json=GEO),
        "forecast": httpx.Response(200, json=FORECAST),
    })
    assert run(integrations.weather("Lisbon", transport=transport(handler))) == \
        "Lisbon: 21°C, clear sky."


def test_an_unknown_place_is_reported_kindly():
    handler = routing_handler({"geocoding": httpx.Response(200, json={"results": []})})
    assert "could not find" in run(integrations.weather("Atlantis", transport=transport(handler)))


def test_an_http_failure_in_weather_is_caught():
    handler = routing_handler({"geocoding": httpx.Response(500, json={})})
    assert "failed" in run(integrations.weather("Lagos", transport=transport(handler)))


def test_a_network_error_is_caught_not_raised():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    assert "failed" in run(integrations.weather("Lagos", transport=transport(handler)))


def test_github_formats_repo_stats():
    payload = {"full_name": "fastapi/fastapi", "stargazers_count": 80000,
               "forks_count": 7000, "open_issues_count": 12}
    handler = lambda request: httpx.Response(200, json=payload)  # noqa: E731
    text = run(integrations.github_repo("fastapi/fastapi", transport=transport(handler)))
    assert "80000 stars" in text and "12 open issues" in text


def test_github_404_is_explained():
    handler = lambda request: httpx.Response(404, json={"message": "Not Found"})  # noqa: E731
    text = run(integrations.github_repo("nobody/nothing", transport=transport(handler)))
    assert "No such repository" in text


def test_github_needs_owner_and_name():
    assert "fastapi/fastapi" in run(integrations.github_repo("fastapi"))


def test_github_auth_header_is_sent_when_a_token_exists():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"full_name": "a/b", "stargazers_count": 1,
                                         "forks_count": 0, "open_issues_count": 0})

    run(integrations.github_repo("a/b", token="ghp_example", transport=transport(handler)))
    assert seen["auth"] == "Bearer ghp_example"


def test_ai_without_a_key_returns_instructions():
    assert "OPENAI_API_KEY" in run(integrations.ask_ai("hi", api_key=""))


def test_ai_returns_the_model_answer():
    payload = {"choices": [{"message": {"content": "A decorator wraps a function."}}]}
    handler = lambda request: httpx.Response(200, json=payload)  # noqa: E731
    text = run(integrations.ask_ai("what is a decorator", api_key="sk-test",
                                   transport=transport(handler)))
    assert text == "A decorator wraps a function."


def test_ai_failure_is_caught():
    handler = lambda request: httpx.Response(401, json={"error": {"message": "bad key"}})  # noqa: E731
    assert "failed" in run(integrations.ask_ai("hi", api_key="sk-bad",
                                               transport=transport(handler)))
