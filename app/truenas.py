"""Minimal TrueNAS 25.10 client: JSON-RPC 2.0 over WebSocket at wss://host/api/current.
Always uses wss:// because TrueNAS revokes API keys that are sent over plain ws://."""
import asyncio
import itertools
import json
import ssl
import time

import websockets


class TrueNASError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


class Disconnected(TrueNASError):
    pass


class TrueNASClient:
    END = {"SUCCESS", "FAILED", "ABORTED"}

    def __init__(self, host, port=443, username="", api_key="", verify_tls=False):
        self.host, self.port = host, int(port or 443)
        self.username, self.api_key = username, api_key
        self.verify_tls = verify_tls
        self.ws = None
        self._ids = itertools.count(1)
        self._pending = {}
        self._lock = asyncio.Lock()
        self._reader = None
        self.realtime = {}
        self.realtime_at = 0.0
        self._ev_prefix = None
        self._events = []

    @property
    def url(self):
        return f"wss://{self.host}:{self.port}/api/current"

    def _ssl(self):
        ctx = ssl.create_default_context()
        if not self.verify_tls:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        ctx.set_alpn_protocols(["http/1.1"])
        return ctx

    async def connect(self, login=True):
        async with self._lock:
            if self.ws is not None:
                return
            if not self.host:
                raise TrueNASError("No address set for this device")
            if login and not self.api_key:
                raise TrueNASError("No API key saved for this device")
            try:
                ws = await asyncio.wait_for(
                    websockets.connect(self.url, ssl=self._ssl(), max_size=None, open_timeout=10), 15)
            except Exception as e:
                raise TrueNASError(f"Cannot reach {self.host}:{self.port} ({e.__class__.__name__}: {e})")
            self.ws = ws
            self._reader = asyncio.create_task(self._read(ws))
            if not login:
                return
            try:
                await self._login()
            except Exception:
                await self._drop()
                raise
            try:  # live CPU / memory / network readings; optional
                await self._raw("core.subscribe", ["reporting.realtime"], 10)
            except Exception:
                pass

    async def _login(self):
        try:
            r = await self._raw("auth.login_ex", [{
                "mechanism": "API_KEY_PLAIN", "username": self.username, "api_key": self.api_key}], 15)
            ok = isinstance(r, dict) and r.get("response_type") == "SUCCESS"
        except TrueNASError as e:
            if e.code == -32601 or "not found" in str(e).lower():
                ok = (await self._raw("auth.login_with_api_key", [self.api_key], 15)) is True
            else:
                raise
        if not ok:
            raise TrueNASError("Login rejected. Check the username and API key (the key must belong to that user).")

    async def password_login(self, username, password, otp=None):
        """Checks a TrueNAS username and password. Used only to prove who you are when resetting; nothing is stored."""
        await self.connect(login=False)
        r = await self._raw("auth.login_ex", [{"mechanism": "PASSWORD_PLAIN", "username": username, "password": password}], 20)
        rt = r.get("response_type") if isinstance(r, dict) else None
        if rt == "OTP_REQUIRED":
            if not otp:
                return {"ok": False, "otp_required": True}
            r = await self._raw("auth.login_ex", [{"mechanism": "OTP_TOKEN", "otp_token": otp}], 20)
            rt = r.get("response_type") if isinstance(r, dict) else None
        if rt != "SUCCESS":
            return {"ok": False, "error": "Wrong username, password or code"}
        return {"ok": True, "me": await self._raw("auth.me", [], 15)}

    async def _read(self, ws):
        try:
            async for raw in ws:
                msg = json.loads(raw)
                mid = msg.get("id")
                if mid is not None and mid in self._pending:
                    fut = self._pending.pop(mid)
                    if fut.done():
                        continue
                    if "error" in msg:
                        e = msg["error"] or {}
                        data = e.get("data")
                        reason = data.get("reason") if isinstance(data, dict) else None
                        fut.set_exception(TrueNASError(reason or e.get("message", "TrueNAS error"), e.get("code")))
                    else:
                        fut.set_result(msg.get("result"))
                elif msg.get("method") == "collection_update":
                    p = msg.get("params") or {}
                    coll = str(p.get("collection", ""))
                    if coll == "reporting.realtime" and isinstance(p.get("fields"), dict):
                        self.realtime, self.realtime_at = p["fields"], time.time()
                    elif self._ev_prefix and coll.startswith(self._ev_prefix) and isinstance(p.get("fields"), dict):
                        self._events.append(p["fields"])
        except Exception:
            pass
        finally:
            if self.ws is ws:
                self.ws = None
            for f in list(self._pending.values()):
                if not f.done():
                    f.set_exception(Disconnected("Connection to TrueNAS closed"))
            self._pending.clear()

    async def _raw(self, method, params, timeout):
        ws = self.ws
        if ws is None:
            raise Disconnected("Not connected")
        i = next(self._ids)
        fut = asyncio.get_running_loop().create_future()
        self._pending[i] = fut
        try:
            await ws.send(json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}))
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._pending.pop(i, None)
            raise TrueNASError(f"{method} timed out")
        except websockets.ConnectionClosed:
            self._pending.pop(i, None)
            raise Disconnected("Connection to TrueNAS closed")

    async def call(self, method, params=None, timeout=30):
        for attempt in (1, 2):
            if self.ws is None:
                await self.connect()
            try:
                return await self._raw(method, params or [], timeout)
            except Disconnected:
                if attempt == 2:
                    raise
                self.ws = None

    async def collect_events(self, event_name, seconds=2.5):
        """Subscribes to a TrueNAS event stream (for example app logs), listens for a moment, then lets go."""
        if self.ws is None:
            await self.connect()
        self._ev_prefix = event_name.split(":")[0]
        self._events = []
        try:
            sub = await self._raw("core.subscribe", [event_name], 15)
            await asyncio.sleep(seconds)
            try:
                await self._raw("core.unsubscribe", [sub], 10)
            except Exception:
                pass
            return list(self._events)
        finally:
            self._ev_prefix = None

    async def job(self, method, params=None, timeout=600):
        """Runs a TrueNAS job method and waits until it finishes."""
        jid = await self.call(method, params or [])
        if not isinstance(jid, int):
            return jid
        t0 = time.time()
        while time.time() - t0 < timeout:
            rows = await self.call("core.get_jobs", [[["id", "=", jid]]])
            if rows:
                j = rows[0]
                if j.get("state") in self.END:
                    if j["state"] != "SUCCESS":
                        raise TrueNASError(f"{method} {j['state'].lower()}: {j.get('error') or 'no detail'}")
                    return j.get("result")
            await asyncio.sleep(1.5)
        raise TrueNASError(f"{method} was still running after {int(timeout)} seconds")

    async def _drop(self):
        ws, self.ws = self.ws, None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def close(self):
        await self._drop()
        if self._reader:
            self._reader.cancel()
