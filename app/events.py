"""A tiny message board inside TruePilot. Power events (restart, shut down, wake, NAS offline or back) are posted here once,
and anything that wants to tell you about them listens: the tray icon on Windows and Telegram."""
import logging
import time

log = logging.getLogger("truepilot.events")
subs = {}                     # who is listening: name -> function(event)
state = {"tray": False}       # True when the Windows tray icon is running in this process
expect = {}                   # NAS id -> (what, when): a restart or shutdown we sent ourselves
recent = {}                   # small memory used to avoid saying the same thing twice
enabled = lambda name: True   # main.py replaces this with a check of the saved settings  # noqa: E731

# kinds: restart, shutdown, wake, wake_done, wake_failed, power_failed, online, offline, pc_on, pc_off


def subscribe(name, fn):
    subs[name] = fn


def emit(kind, title, text="", sev="info", **extra):
    ev = {"kind": kind, "title": title, "text": text, "sev": sev, "ts": time.time(), **extra}
    for name, fn in list(subs.items()):
        try:
            fn(ev)
        except Exception:
            log.exception("event listener %s failed", name)
    return ev
