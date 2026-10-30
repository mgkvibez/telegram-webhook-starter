"""Small pieces that keep app.py readable.

config     reads the environment once, in one place
client     talks to the Telegram API (async, and swappable in tests)
handlers   decides what a message means
keyboards  the buttons you can tap
integrations  optional examples: AI, GitHub, weather
dedupe     makes Telegram's retries harmless
"""
