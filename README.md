# telegram-webhook-starter

[![ci](https://github.com/mgkvibez/telegram-webhook-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/mgkvibez/telegram-webhook-starter/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-black.svg)](LICENSE)
[![python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![no polling loop](https://img.shields.io/badge/polling-none-brightgreen.svg)](#why-webhooks-and-not-polling)

A Telegram bot that runs on **webhooks**, in one readable FastAPI file. No `while True`, no
long-polling loop, no framework to learn. Clone it, paste a token, deploy, and you have a bot
that answers messages, shows buttons, and can plug into any API.

```
you:   /start
bot:   Hi! I am a webhook bot: no polling loop, just a URL that Telegram calls.
       [ Help ]  [ Tell me a joke ]
       [ Weather in Lagos ]

you:   /weather Lisbon
bot:   Lisbon: 21°C, clear sky.
```

## Why webhooks and not polling

Almost every Telegram tutorial starts with `while True: getUpdates()`. It works on your laptop
and falls apart the moment you deploy: the process must stay awake forever, you cannot scale it
past one instance, and platforms that sleep idle apps break it at random.

| | Long polling | Webhook (this repo) |
|---|---|---|
| Where it runs | a process that never stops | any HTTP host, including a free tier |
| Latency | one poll interval | immediate |
| Scaling | one consumer per bot | many instances behind a load balancer |
| Sleeps when idle | no | yes, and wakes on the next message |
| Extra libraries | none | none |
| Needs HTTPS | no | yes (every deploy target below gives you one) |

## Deploy in 60 seconds

**1. Get a token from @BotFather** (30 seconds)

1. Open Telegram, search for `@BotFather`, start a chat.
2. Send `/newbot`, pick a display name, then a username ending in `bot`.
3. BotFather replies with a token like `123456789:AAH...`. That string is your `BOT_TOKEN`.
   Treat it like a password: anyone with it controls your bot.

**2. Deploy this repo**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/mgkvibez/telegram-webhook-starter)

Paste `BOT_TOKEN` when Render asks. Leave `WEBHOOK_SECRET` and `ADMIN_TOKEN` on *generate*:
Render invents strong values and injects them for you. Wait for the first deploy to finish and
copy your URL, for example `https://my-bot.onrender.com`.

Any host works the same way. Docker:

```bash
docker build -t telegram-starter .
docker run -p 8000:8000 -e BOT_TOKEN=... -e WEBHOOK_SECRET=... -e ADMIN_TOKEN=... telegram-starter
```

**3. Tell Telegram where to send messages**

```bash
curl -X POST "https://my-bot.onrender.com/admin/set-webhook?url=https://my-bot.onrender.com/webhook" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

You should get `{"ok":true,"description":"Webhook was set"}`. Message your bot `/start`. That is
the whole setup.

Verify at any time with the other admin route, which reports what Telegram actually thinks:

```bash
curl "https://my-bot.onrender.com/admin/webhook-info" -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                  # paste your BOT_TOKEN
export $(grep -v '^#' .env | xargs)                   # or use any dotenv loader
uvicorn app:app --reload
```

Open <http://127.0.0.1:8000/health> to confirm it started, and <http://127.0.0.1:8000/docs> for
the interactive API page. Everything except the webhook itself works without a public URL, and
the test suite needs no URL at all.

Telegram only deliver to a public HTTPS address, so to talk to a bot running on your laptop,
point the webhook at a staging deploy, or expose the port with whichever HTTPS tunnel your
platform already provides. On Render or Fly you get that URL the moment the first deploy lands,
so most people skip local exposure entirely.

## Project layout

```
app.py                  FastAPI app: /, /health, /webhook, /admin/* (about 120 lines)
bot/
├── config.py           every environment variable, read once
├── client.py           the only code that calls Telegram (async httpx)
├── handlers.py         what each message means - start here to add a command
├── keyboards.py        the buttons people tap
├── integrations.py     AI, GitHub and weather, ~15 lines each
└── dedupe.py           makes Telegram's retries harmless
tests/                  48 offline tests: no network, no token, no account
scripts/verify.sh       local gate: ruff, tests, import smoke, live server smoke
render.yaml             one-click deploy target
Dockerfile              the same thing, portable
```

## Add your own command

Three lines in `bot/handlers.py`, inside `_on_message`:

```python
elif name == "/ping":
    await bot.send_message(chat_id, "pong")
```

Add it to `HELP_TEXT` so people can find it. That is the whole pattern: parse the command, call
`bot.send_message`. If it needs an API, put the call in `bot/integrations.py` and import it, so
the handler stays readable and the network stays testable.

## Integrations, already wired

| Command | What it shows | Needs |
|---|---|---|
| `/weather Lisbon` | a plain JSON API with **no key at all** (Open-Meteo) | nothing |
| `/ai explain decorators` | a chat model behind a key | `OPENAI_API_KEY` |
| `/github fastapi/fastapi` | any REST API, with an optional token | optional `GITHUB_TOKEN` |

Each one is around fifteen lines in `bot/integrations.py`, which is the point: copy the shape for
Notion, Stripe, your own backend, anything. They all fail soft. If an API is down, the bot replies
with a sentence instead of raising, because an exception in a webhook handler makes Telegram
retry the same update forever.

## Three security details most starters get wrong

1. **The webhook verifies Telegram's secret token.** `setWebhook` registers a `secret_token`, and
   Telegram sends it back in `X-Telegram-Bot-Api-Secret-Token` on every call. The app compares it
   with `hmac.compare_digest` and rejects anything else with 401. Without this, anyone who learns
   your URL can post fake updates and drive your bot. If `WEBHOOK_SECRET` is unset the endpoint
   answers **503 and refuses to run unverified**, which fails closed on purpose.
2. **`/admin/set-webhook` is behind `ADMIN_TOKEN`.** A public endpoint that sets your webhook lets
   a stranger point your bot at their server and read everything users send it. With no admin
   token configured, those routes are disabled entirely.
3. **Duplicates are dropped.** Telegram retries any update that does not get a fast 200. The guard
   in `bot/dedupe.py` remembers `update_id` for 15 minutes, so a slow response does not send the
   same reply twice.

Two smaller habits worth copying: the container runs as a non-root user, and user text is passed
through `html.escape()` before it goes back out with `parse_mode=HTML` (otherwise a message
containing `<b>` breaks the send or injects formatting).

## Why `httpx` and not `requests`

A `requests.post` inside an `async def` blocks the event loop: while Telegram is slow, every other
request your app is serving waits behind it. `httpx.AsyncClient` does not. This is the same trap
described in the [FastAPI async docs](https://fastapi.tiangolo.com/async/), and it matters more
for a bot than for most apps because every message you handle is a new request.

## Tests

48 tests, all offline: no token, no network, no Telegram account. The httpx calls are answered by
`httpx.MockTransport`, so the success *and* failure paths are exercised deterministically.

```bash
pytest                       # the suite
./scripts/verify.sh          # suite + ruff + import smoke + a real uvicorn server smoke test
```

The gate starts uvicorn on a spare port and checks with `curl` that `/health` reports configured,
that `/webhook` returns 401 without the secret header, 400 with the secret and a junk body, and
that the admin route returns 401 without a bearer. It also greps for the polling call and fails
if polling ever creeps in.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Messages get no reply | webhook not registered | `GET /admin/webhook-info`, look at `last_error_message` |
| `401` in `webhook-info` | Telegram's calls do not match your secret | re-run `set-webhook` so the current `WEBHOOK_SECRET` is registered |
| `503` from `/webhook` | `WEBHOOK_SECRET` unset | set it, redeploy, re-register |
| Reply arrives twice | Telegram retried a slow response | the guard covers this; check your handler is not sleeping |
| Works locally, silent on Render | free instances sleep | first message may take ~30s to wake it; that is the platform |
| Buttons do nothing | `allowed_updates` excludes callbacks | this repo registers `message` and `callback_query` for you |

## Honest limits

This is a starter, not a framework. Duplicate detection is in-memory, so it holds for one
instance and resets on redeploy; several instances need a shared store (`SET key NX EX 900` in
Redis is the same idea). There is no database, no conversation state, no rate limiting per user,
and no handling of media beyond a polite "I only understand text". Long jobs should be pushed to a
background task instead of run inside the handler, because Telegram times out at about 60 seconds.

## License

MIT. Do whatever you want with it.
