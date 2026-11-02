"""Talks to the Telegram Bot API using only the Python standard library (nothing extra to install)."""
import asyncio
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("TRUEPILOT_TELEGRAM_API", "https://api.telegram.org").rstrip("/")


class TgError(Exception):
    def __init__(self, msg, code=0):
        super().__init__(msg)
        self.code = code


def _scrub(text, token):
    return str(text).replace(token, "<token>") if token else str(text)


def call(token, method, params=None, timeout=20):
    """One blocking call. The token is never put into an error message."""
    url = f"{BASE}/bot{token}/{method}"
    req = urllib.request.Request(url, data=json.dumps(params or {}).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode())
            msg = j.get("description") or f"Telegram answered {e.code}"
        except Exception:
            msg = f"Telegram answered {e.code}"
        raise TgError(_scrub(msg, token), e.code) from None
    except Exception as e:
        raise TgError(_scrub("Couldn't reach Telegram: " + str(e), token)) from None
    try:
        j = json.loads(body.decode())
    except ValueError:
        raise TgError("Telegram sent an answer TruePilot couldn't read") from None
    if not j.get("ok"):
        raise TgError(_scrub(j.get("description") or "Telegram refused the request", token), j.get("error_code") or 0)
    return j.get("result")


async def acall(token, method, params=None, timeout=20):
    return await asyncio.to_thread(call, token, method, params, timeout)
