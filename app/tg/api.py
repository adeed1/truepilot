"""Talks to the Telegram Bot API using only the Python standard library (nothing extra to install)."""
import asyncio
import http.client
import json
import os
import socket
import ssl
from urllib.parse import urlparse

BASE = os.environ.get("TRUEPILOT_TELEGRAM_API", "https://api.telegram.org").rstrip("/")


class TgError(Exception):
    def __init__(self, msg, code=0):
        super().__init__(msg)
        self.code = code


def _scrub(text, token):
    return str(text).replace(token, "<token>") if token else str(text)


_GOOD = {}   # host -> the address that worked last time, tried first next time
PER_TRY = 6  # seconds to wait for ONE address before trying the next


def _addresses(host, port):
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    v4 = [i for i in infos if i[0] == socket.AF_INET]
    v6 = [i for i in infos if i[0] != socket.AF_INET]
    order = v4 + v6
    good = _GOOD.get(host)
    return sorted(order, key=lambda i: 0 if i[4] == good else 1)


def _connect(host, port, tls, timeout):
    """Opens the connection. A silent address only costs a few seconds, then the next one is tried
    (some networks leave one address unanswered, and a plain connection would then wait the full timeout)."""
    last = None
    for fam, typ, proto, _, addr in _addresses(host, port):
        s = socket.socket(fam, typ, proto)
        s.settimeout(min(PER_TRY, timeout))
        try:
            s.connect(addr)
            if tls:
                s = ssl.create_default_context().wrap_socket(s, server_hostname=host)
            s.settimeout(timeout)
            _GOOD[host] = addr
            return s
        except Exception as e:
            last = e
            try:
                s.close()
            except Exception:
                pass
    raise last or OSError("no address to connect to")


def call(token, method, params=None, timeout=20):
    """One blocking call. The token is never put into an error message."""
    u = urlparse(BASE)
    https = u.scheme == "https"
    host, port = u.hostname, u.port or (443 if https else 80)
    body = json.dumps(params or {}).encode()
    conn = None
    try:
        sock = _connect(host, port, https, timeout)
        conn = (http.client.HTTPSConnection if https else http.client.HTTPConnection)(host, port, timeout=timeout)
        conn.sock = sock
        conn.request("POST", f"{u.path.rstrip('/')}/bot{token}/{method}", body, {"Content-Type": "application/json", "Connection": "close"})
        r = conn.getresponse()
        raw, status = r.read(), r.status
    except Exception as e:
        raise TgError(_scrub("Couldn't reach Telegram: " + str(e), token)) from None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    try:
        j = json.loads(raw.decode())
    except ValueError:
        raise TgError(f"Telegram answered {status}" if status != 200 else "Telegram sent an answer TruePilot couldn't read", status if status != 200 else 0) from None
    if not j.get("ok"):
        raise TgError(_scrub(j.get("description") or "Telegram refused the request", token), j.get("error_code") or status)
    return j.get("result")


async def acall(token, method, params=None, timeout=20):
    return await asyncio.to_thread(call, token, method, params, timeout)


def diagnose(token):
    """Tries each step of reaching Telegram and times it, so you can see exactly where it is slow or stuck. Never shows the token."""
    import time
    u = urlparse(BASE)
    https = u.scheme == "https"
    host, port = u.hostname, u.port or (443 if https else 80)
    out = []

    def step(name, fn):
        t = time.time()
        try:
            r = fn()
            out.append({"step": name, "ok": True, "ms": int((time.time() - t) * 1000), "text": str(r or "")})
            return True
        except Exception as e:
            out.append({"step": name, "ok": False, "ms": int((time.time() - t) * 1000), "text": _scrub(str(e), token)[:160]})
            return False

    try:
        addrs = _addresses(host, port)
        out.append({"step": "Find Telegram (DNS)", "ok": True, "ms": 0, "text": f"{len(addrs)} address{'es' if len(addrs) != 1 else ''}"})
    except Exception as e:
        return [{"step": "Find Telegram (DNS)", "ok": False, "ms": 0, "text": _scrub(str(e), token)[:160]}]
    worked = False
    for fam, typ, proto, _, addr in addrs[:6]:
        def one(fam=fam, typ=typ, proto=proto, addr=addr):
            s = socket.socket(fam, typ, proto)
            s.settimeout(8)
            try:
                s.connect(addr)
                if https:
                    ssl.create_default_context().wrap_socket(s, server_hostname=host).close()
            finally:
                s.close()
            return "connected" + (" and secure" if https else "")
        worked = step(f"Connect to {addr[0]} ({'IPv4' if fam == socket.AF_INET else 'IPv6'})", one) or worked
    if worked:
        step("Ask Telegram who the bot is", lambda: "answered as @" + str((call(token, "getMe", {}, 30) or {}).get("username")))
    return out
