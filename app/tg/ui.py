"""Small helpers for building Telegram messages."""
from html import escape as esc  # noqa: F401

LAMP = {"ok": "🟢", "bad": "🔴", "warn": "🟠", "off": "⚪", "unk": "⚪", "info": "🔵", "run": "🟡"}


class B:
    """A button. Give it data (a tap that TruePilot handles) or a url (opens a web page)."""
    __slots__ = ("text", "data", "url")

    def __init__(self, text, data=None, url=None):
        self.text, self.data, self.url = text, data, url


class Screen:
    """One message: HTML text, rows of buttons, and an optional follow-up that edits the same message later."""

    def __init__(self, text, rows=None, then=None):
        self.text, self.rows, self.then = text, rows or [], then


class Say(Exception):
    """Raise this from a command to show a plain message instead of a screen."""

    def __init__(self, text, back="m"):
        super().__init__(text)
        self.text, self.back = text, back


def size(n):
    if n is None:
        return "-"
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB", "PB"):
        if n < 1000 or u == "PB":
            return f"{n:.0f} {u}" if (n >= 100 or u == "B") else f"{n:.1f} {u}"
        n /= 1000


def span(seconds):
    if seconds is None:
        return "-"
    s = int(seconds)
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return f"{d} d {h} h" if d else (f"{h} h {m} min" if h else f"{m} min")


def back_row(to="m", text="« Menu"):
    return [B(text, to)]


def parse_duration(text):
    """'30m', '2h', '1d' -> seconds. Returns None when it can't be read."""
    import re
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?)\s*", (text or "").lower())
    if not m:
        return None
    n, u = float(m.group(1)), m.group(2)
    return int(n * (60 if u.startswith("m") else 3600 if u.startswith("h") else 86400))
