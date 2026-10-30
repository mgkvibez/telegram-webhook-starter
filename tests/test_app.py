"""The HTTP surface: who is allowed in, and what comes back."""


from fastapi.testclient import TestClient

import app as app_module
from bot.config import Settings
from tests.conftest import RecordingBot


def make_client(settings, bot):
    return TestClient(app_module.create_app(settings=settings, client=bot))


def start_update(update_id=1, text="/start", chat_id=42):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": text}}


def headers(secret="s3cret"):
    return {"X-Telegram-Bot-Api-Secret-Token": secret}


def test_home_says_it_is_alive(settings, bot):
    response = make_client(settings, bot).get("/")
    assert response.status_code == 200
    assert response.json()["webhook_endpoint"] == "/webhook"


def test_health_reports_configuration(settings, bot):
    assert make_client(settings, bot).get("/health").json() == {"ok": True, "configured": True}


def test_health_is_honest_when_unconfigured():
    bare = TestClient(app_module.create_app(settings=Settings(), client=RecordingBot()))
    assert bare.get("/health").json()["configured"] is False


def test_webhook_refuses_to_accept_anything_without_a_configured_secret(bot):
    unconfigured = Settings(bot_token="123:TEST", webhook_secret="")
    response = make_client(unconfigured, bot).post("/webhook", json=start_update(),
                                                   headers=headers("anything"))
    assert response.status_code == 503
    assert "WEBHOOK_SECRET" in response.json()["detail"]


def test_webhook_rejects_a_wrong_secret(settings, bot):
    response = make_client(settings, bot).post("/webhook", json=start_update(),
                                               headers=headers("guess"))
    assert response.status_code == 401
    assert bot.messages == []


def test_webhook_rejects_a_missing_secret_header(settings, bot):
    response = make_client(settings, bot).post("/webhook", json=start_update())
    assert response.status_code == 401


def test_webhook_rejects_a_body_that_is_not_json(settings, bot):
    response = make_client(settings, bot).post("/webhook", content=b"not json", headers=headers())
    assert response.status_code == 400


def test_webhook_rejects_json_that_is_not_an_update(settings, bot):
    response = make_client(settings, bot).post("/webhook", json={"hello": "world"},
                                               headers=headers())
    assert response.status_code == 400


def test_a_valid_update_is_answered_and_handled(settings, bot):
    response = make_client(settings, bot).post("/webhook", json=start_update(), headers=headers())
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert bot.messages and bot.messages[0]["chat_id"] == 42


def test_a_replayed_update_is_ignored(settings, bot):
    client = make_client(settings, bot)
    first = client.post("/webhook", json=start_update(update_id=7), headers=headers())
    second = client.post("/webhook", json=start_update(update_id=7), headers=headers())
    assert first.json().get("duplicate") is None
    assert second.json()["duplicate"] is True
    assert len(bot.messages) == 1, "a retried update must not produce a second reply"


def test_a_handler_crash_returns_200_so_telegram_stops_retrying(settings, bot, monkeypatch):
    async def boom(update, client, cfg):
        raise RuntimeError("handler bug")

    monkeypatch.setattr(app_module, "handle_update", boom)
    response = make_client(settings, bot).post("/webhook", json=start_update(), headers=headers())
    assert response.status_code == 200


def test_admin_routes_are_disabled_without_an_admin_token(bot):
    no_admin = Settings(bot_token="123:TEST", webhook_secret="s3cret", admin_token="")
    response = make_client(no_admin, bot).post("/admin/set-webhook?url=https://x.test/webhook")
    assert response.status_code == 503


def test_admin_routes_reject_a_bad_bearer(settings, bot):
    client = make_client(settings, bot)
    response = client.post("/admin/set-webhook?url=https://x.test/webhook",
                           headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401
    assert bot.webhooks == []


def test_set_webhook_rejects_non_https(settings, bot):
    client = make_client(settings, bot)
    response = client.post("/admin/set-webhook?url=http://x.test/webhook",
                           headers={"Authorization": "Bearer admin-token"})
    assert response.status_code == 400


def test_set_webhook_registers_the_url_with_the_secret(settings, bot):
    client = make_client(settings, bot)
    response = client.post("/admin/set-webhook?url=https://x.test/webhook",
                           headers={"Authorization": "Bearer admin-token"})
    assert response.status_code == 200
    assert bot.webhooks == [{"url": "https://x.test/webhook", "secret_token": "s3cret"}]


def test_webhook_info_requires_auth_and_reports_telegram_state(settings, bot):
    client = make_client(settings, bot)
    assert client.get("/admin/webhook-info").status_code == 401
    ok = client.get("/admin/webhook-info", headers={"Authorization": "Bearer admin-token"})
    assert ok.status_code == 200 and ok.json()["result"]["url"].endswith("/webhook")
