"""The Telegram engine: one listening loop per bot, command handling, and sending.
TruePilot reaches OUT to Telegram, so no ports are opened on your router."""
import asyncio
import html
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta

from fastapi import HTTPException

from . import registry
from .api import TgError, acall
from .store import PURPOSES, Store
from .ui import B, Say, Screen, esc

log = logging.getLogger("truepilot.telegram")
POLL_SECONDS = 8


class Call:
    """What a command receives: the bot, the words typed (args) or the button tapped (data)."""

    def __init__(self, eng, bot, args, data, is_cb):
        self.eng, self.tp, self.bot = eng, eng.tp, bot
        self.args, self.data, self.is_cb = args, data, is_cb

    @property
    def text(self):
        return " ".join(self.args)

    def devices(self):
        return self.tp.db.q("SELECT * FROM devices WHERE kind IN ('truenas','demo') ORDER BY id")

    def device(self):
        rows = self.devices()
        if not rows:
            raise Say("No NAS is added on this copy of TruePilot. Add it in Settings > Devices.")
        sel = self.eng.sel.get(self.bot["id"])
        return next((r for r in rows if r["id"] == sel), rows[0])

    async def snap(self):
        """The newest picture of the selected NAS: (device row, snapshot)."""
        d = self.device()
        try:
            s = await self.tp.hub.snapshot(d["id"])
        except Exception as e:
            raise Say(f"🔴 Couldn't reach {esc(d['name'])}.\n<i>{esc(str(e))[:200]}</i>")
        if not s.get("ok"):
            raise Say(f"🔴 <b>{esc(d['name'])}</b> isn't answering.\n<i>{esc(str(s.get('error') or ''))[:200]}</i>")
        return d, s


class Telegram:
    def __init__(self, tp):
        self.tp = tp
        self.store = Store(tp.db, tp.vault)
        self.polls = {}      # bot id -> (task, token)
        self.state = {}      # bot id -> (True ok / False problem / None off, text)
        self.pair = {}       # bot id -> {code, exp, tries}
        self.sel = {}        # bot id -> the NAS chosen with /nas
        self.cbmap = {}      # long button data
        self.confirms = {}   # one-time Approve/Deny questions asked by your own commands
        self.bg = set()
        self.warned = {}
        self.tasks = []
        self.tick_seconds = int(os.environ.get("TRUEPILOT_TG_TICK", "60"))
        registry.load()
        from .watch import Watcher
        self.watcher = Watcher(self)

    # ---------- lifecycle ----------
    def start(self):
        from .. import events
        events.subscribe("telegram", self.on_event)
        self.tasks = [asyncio.create_task(self._supervise()), asyncio.create_task(self.watcher.run())]

    async def stop(self):
        for t in self.tasks + [p[0] for p in self.polls.values()]:
            t.cancel()
        self.polls.clear()

    def job_done(self, name, result):
        """Called by the scheduler when a scheduled job finishes."""
        try:
            self.watcher.job_done(name, result)
        except Exception:
            log.exception("job notice failed")

    ICONS = {"restart": "🔄", "shutdown": "⏻", "wake": "⏰", "wake_done": "🟢", "wake_failed": "🔴", "power_failed": "🔴", "online": "🟢", "offline": "🟠", "pc_on": "🟢", "pc_off": "⚪"}

    def on_event(self, ev):
        """A power event from the message board (restart, shut down, wake, NAS offline or back)."""
        k = ev["kind"]
        if k not in self.ICONS or not self.active():
            return
        if not self.store.cfg()["types"].get("pc" if k.startswith("pc_") else "power", False):
            return
        rows = []
        if k == "offline" and ev.get("can_wake"):
            rows = [[B("Wake NAS", f"w:dev{ev['dev_id']}")]]
        elif k == "online" or (k == "wake_done" and str(ev.get("target", "")).startswith("dev:")):
            rows = [[B("📊 Status", "st")]]
        text = f"{self.ICONS[k]} <b>{esc(ev['title'])}</b>" + (f"\n{esc(ev['text'])}" if ev.get("text") else "")
        self.spawn(self.notify(text, rows, ev["sev"] if ev["sev"] in ("bad", "warn", "info") else "info"))

    def active(self):
        c = self.store.cfg()
        return bool(c["on"] and c["sender"])

    def spawn(self, coro):
        t = asyncio.create_task(coro)
        self.bg.add(t)
        t.add_done_callback(self.bg.discard)

    async def _supervise(self):
        while True:
            try:
                self._sync()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("telegram supervisor failed")
            await asyncio.sleep(3)

    def _sync(self):
        c = self.store.cfg()
        bots = {b["id"]: b for b in self.store.bots()}
        want = {}
        if c["on"] and c["sender"]:
            want = {i: self.store.token(b) for i, b in bots.items() if b["enabled"]}
        for bid in list(self.polls):
            t, tok = self.polls[bid]
            if bid not in want or want[bid] != tok or t.done():
                t.cancel()
                self.polls.pop(bid)
        for bid, tok in want.items():
            if tok and bid not in self.polls:
                self.polls[bid] = (asyncio.create_task(self._poll(bid, tok)), tok)
        for bid in list(self.state):
            if bid not in want:
                self.state[bid] = (None, "")
            if bid not in bots:
                self.state.pop(bid, None)

    # ---------- listening ----------
    async def _poll(self, bid, token):
        offset, first = None, True
        self.state[bid] = (None, "Connecting…")
        while True:
            try:
                if first:  # skip anything sent while TruePilot was off, so old taps never run later
                    old = await acall(token, "getUpdates", {"offset": -1, "timeout": 0}, 15)
                    if old:
                        offset = old[-1]["update_id"] + 1
                    first = False
                    await self._publish_commands(bid, token)
                params = {"timeout": POLL_SECONDS, "allowed_updates": ["message", "callback_query"]}
                if offset:
                    params["offset"] = offset
                ups = await acall(token, "getUpdates", params, POLL_SECONDS + 10)
                self.state[bid] = (True, "")
                for u in ups:
                    offset = u["update_id"] + 1
                    try:
                        await self._handle(bid, token, u)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        log.exception("telegram update failed")
            except asyncio.CancelledError:
                raise
            except TgError as e:
                if e.code == 409:
                    msg = "Another copy of TruePilot is using this bot. Turn Telegram off on one of them."
                elif e.code in (401, 404):
                    msg = "Telegram doesn't accept this bot token. Use Change token."
                else:
                    msg = str(e)
                self.state[bid] = (False, msg)
                await asyncio.sleep(30 if e.code in (401, 404, 409) else 8)
            except Exception as e:
                self.state[bid] = (False, str(e)[:150])
                await asyncio.sleep(8)

    async def _publish_commands(self, bid, token):
        b = self.store.bot(bid)
        if not b or b["purpose"] != "control":
            return
        cmds = [{"command": c.name, "description": c.desc[:80]} for c in registry.COMMANDS.values() if c.menu and c.level != "power"]
        try:
            await acall(token, "setMyCommands", {"commands": sorted(cmds, key=lambda x: x["command"])[:90]}, 15)
        except TgError:
            pass

    # ---------- who is allowed ----------
    @staticmethod
    def _owner(b, uid, chat):
        return bool(b["chat_id"]) and uid == b["chat_id"] and chat == b["chat_id"]

    def _stranger(self, b, uid):
        k = (b["id"], uid)
        if time.time() - self.warned.get(k, 0) > 600:
            self.warned[k] = time.time()
            self.tp.audit("Telegram", 0, "telegram_stranger", f"user {uid}", "Someone who is not linked messaged your bot. Ignored.", "blocked")

    def _allowed(self, b, level):
        parts = self.store.cfg()["parts"]
        if level == "approve":
            return "" if parts["approvals"] else "Approval requests are switched off in TruePilot Settings."
        if not parts["commands"]:
            return "Telegram commands are switched off in TruePilot Settings."
        if level == "power" and not parts["powerful"]:
            return "The powerful commands are switched off in TruePilot Settings."
        return ""

    async def _handle(self, bid, token, u):
        b = self.store.bot(bid)
        if not b:
            return
        cq, m = u.get("callback_query"), u.get("message")
        if cq:
            msg = cq.get("message") or {}
            chat = msg.get("chat") or {}
            uid = (cq.get("from") or {}).get("id")
            if chat.get("type") != "private":
                return
            if not self._owner(b, uid, chat.get("id")):
                self._stranger(b, uid)
                return
            await self._callback(b, token, cq, msg)
        elif m:
            chat, frm = m.get("chat") or {}, m.get("from") or {}
            if chat.get("type") != "private" or frm.get("is_bot"):
                return
            text = (m.get("text") or "").strip()
            if bid in self.pair and await self._try_pair(b, token, frm, text):
                return
            if not b["chat_id"]:
                return
            if not self._owner(b, frm.get("id"), chat.get("id")):
                self._stranger(b, frm.get("id"))
                return
            if b["purpose"] != "control":
                return
            await self._command(b, token, chat["id"], text)

    # ---------- pairing (links your Telegram account to the bot) ----------
    def pair_start(self, bid):
        code = f"{secrets.randbelow(10 ** 6):06d}"
        self.pair[bid] = {"code": code, "exp": time.time() + 600, "tries": 0}
        return {"code": code, "expires": self.pair[bid]["exp"]}

    async def _try_pair(self, b, token, frm, text):
        p = self.pair.get(b["id"])
        if not p or time.time() > p["exp"]:
            self.pair.pop(b["id"], None)
            return False
        code = re.sub(r"^/start(@\S+)?\s*", "", text).strip()
        if not re.fullmatch(r"\d{6}", code):
            return False
        p["tries"] += 1
        if code != p["code"]:
            if p["tries"] >= 5:
                self.pair.pop(b["id"], None)
            return True
        self.pair.pop(b["id"], None)
        uid = frm.get("id")
        name = " ".join(x for x in (frm.get("first_name"), frm.get("last_name")) if x) or frm.get("username") or str(uid)
        self.store.update_bot(b["id"], chat_id=uid, chat_name=name)
        self.tp.audit("TruePilot", 0, "telegram_linked", b["label"], f"linked to {name}")
        if b["purpose"] == "control":
            from .commands.menu import menu_screen
            await self._send(token, uid, Screen("✅ <b>Linked.</b> TruePilot will only answer you.\n\n" + "Tap a button, or tap <b>Menu</b> next to the typing box.", []))
            try:
                call = Call(self, self.store.bot(b["id"]), [], [], False)
                await self._send(token, uid, await menu_screen(call))
            except Exception:
                pass
        else:
            await self._send(token, uid, Screen("✅ <b>Linked.</b> This bot will send you TruePilot alerts."))
        return True

    # ---------- handling what you send ----------
    async def _command(self, b, token, chat, text):
        mt = re.match(r"^/([A-Za-z0-9_]+)(?:@\S+)?\s*(.*)$", text, re.S)
        if not mt:
            await self._send(token, chat, Screen("Tap <b>Menu</b> next to the typing box, or send /menu."))
            return
        name, args = mt.group(1).lower(), mt.group(2).split()
        cmd = registry.COMMANDS.get(name)
        if not cmd:
            await self._send(token, chat, Screen(f"I don't know /{esc(name)}. Try /help.", [[B("« Menu", "m")]]))
            return
        err = self._allowed(b, cmd.level)
        if err:
            await self._send(token, chat, Screen("🔒 " + esc(err)))
            return
        await self._run(token, chat, None, cmd.fn, Call(self, b, args, [], False))

    async def _callback(self, b, token, cq, msg):
        try:
            await acall(token, "answerCallbackQuery", {"callback_query_id": cq["id"]}, 10)
        except TgError:
            pass
        if b["purpose"] != "control":
            return
        data = cq.get("data") or ""
        if data.startswith("~"):
            data = self.cbmap.get(data, "")
        prefix, *rest = data.split(":")
        ent = registry.CALLBACKS.get(prefix)
        if not ent:
            return
        chat, mid = msg["chat"]["id"], msg.get("message_id")
        err = self._allowed(b, ent[1])
        if err:
            await self._send(token, chat, Screen("🔒 " + esc(err), [[B("« Menu", "m")]]), mid)
            return
        await self._run(token, chat, mid, ent[0], Call(self, b, [], rest, True))

    async def _run(self, token, chat, edit_id, fn, call):
        try:
            res = await fn(call)
        except Say as s:
            res = Screen(s.text, [[B("« Menu", s.back)]])
        except HTTPException as e:
            res = Screen("⚠️ " + esc(str(e.detail)), [[B("« Menu", "m")]])
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("telegram command failed")
            res = Screen("⚠️ Something went wrong. Look in TruePilot's Activity log, or try again.", [[B("« Menu", "m")]])
        if res is None:
            return
        mid = await self._send(token, chat, res, edit_id)
        if res.then and mid:
            self.spawn(self._follow(token, chat, mid, res.then))

    async def _follow(self, token, chat, mid, then):
        try:
            res = await then()
        except Say as s:
            res = Screen(s.text, [[B("« Menu", s.back)]])
        except HTTPException as e:
            res = Screen("⚠️ " + esc(str(e.detail)), [[B("« Menu", "m")]])
        except Exception as e:
            log.exception("telegram follow-up failed")
            res = Screen("⚠️ " + esc(str(e))[:200], [[B("« Menu", "m")]])
        if res:
            await self._send(token, chat, res, mid)

    # ---------- sending ----------
    def _data(self, data):
        if len(data.encode()) <= 60:
            return data
        if len(self.cbmap) > 500:
            self.cbmap.pop(next(iter(self.cbmap)))
        key = "~" + secrets.token_hex(4)
        self.cbmap[key] = data
        return key

    def _kb(self, rows, urls=True, taps=True):
        out = []
        for row in rows or []:
            r = []
            for b in row:
                if b.url:
                    if urls:
                        r.append({"text": b.text[:60], "url": b.url})
                elif b.data and taps:
                    r.append({"text": b.text[:60], "callback_data": self._data(b.data)})
            if r:
                out.append(r)
        return out

    @staticmethod
    def _plain(text):
        return html.unescape(re.sub(r"<[^>]+>", "", text))

    async def _send(self, token, chat, screen, edit_id=None, taps=True):
        """Sends or edits one message. If Telegram refuses a link button (it can dislike home-network addresses),
        the links are put into the message text instead."""
        has_url = any(b.url for row in screen.rows for b in row)
        text, mode = screen.text[:3900], "HTML"
        urls = True
        for _ in range(4):
            body = text
            if has_url and not urls:
                links = [f'<a href="{esc(b.url)}">{esc(b.text)}</a>' for row in screen.rows for b in row if b.url]
                body = text + "\n\n" + "\n".join(links)
            params = {"chat_id": chat, "text": body, "disable_web_page_preview": True}
            if mode:
                params["parse_mode"] = mode
            kb = self._kb(screen.rows, urls, taps)
            if kb:
                params["reply_markup"] = {"inline_keyboard": kb}
            try:
                if edit_id:
                    params["message_id"] = edit_id
                    await acall(token, "editMessageText", params, 15)
                    return edit_id
                r = await acall(token, "sendMessage", params, 15)
                return r["message_id"]
            except TgError as e:
                msg = str(e).lower()
                if "not modified" in msg:
                    return edit_id
                if edit_id and ("not found" in msg or "can't be edited" in msg):
                    edit_id = None
                    continue
                if has_url and urls and ("url" in msg or "button" in msg):
                    urls = False
                    continue
                if mode and "parse entities" in msg:
                    mode, text = None, self._plain(text)
                    continue
                raise
        return None

    # ---------- "Are you sure?" with Approve and Deny ----------
    def confirm(self, call, text, run, approve_label="✅ Approve"):
        """Shows Approve and Deny. Nothing happens until Approve is tapped. Each question works once, for 10 minutes."""
        now = time.time()
        for k in [k for k, v in self.confirms.items() if v["exp"] < now]:
            self.confirms.pop(k, None)
        tok = secrets.token_hex(4)
        self.confirms[tok] = {"bot": call.bot["id"], "exp": now + 600, "run": run}
        return Screen("⚠️ " + text + "\n\n<i>Nothing happens until you tap Approve.</i>", [[B(approve_label, f"cy:{tok}"), B("❌ Deny", f"cn:{tok}")]])

    # ---------- requests from agents (Hermes) ----------
    def approval_created(self, rid):
        if self.active() and self.store.cfg()["parts"]["approvals"]:
            self.spawn(self._send_approval(rid))

    async def _send_approval(self, rid):
        r = self.tp.db.one("SELECT * FROM approvals WHERE id=?", (rid,))
        if not r:
            return
        warn = {"restart_nas": "\n⚠️ Apps and shares will be unavailable for a few minutes.", "shutdown_nas": "\n⚠️ The NAS stays off until you wake it.",
                "upgrade_app": "\n⚠️ The app is unavailable while it updates."}.get(r["action"], "")
        text = f"🤖 <b>{esc(r['token_name'])}</b> asks to {esc(r['summary'] or r['action'])}." + (f"\nReason: {esc(r['reason'])}" if r["reason"] else "") + warn + "\n<i>It expires in 30 minutes.</i>"
        rows = [[B("✅ Approve", f"ay:{rid}"), B("❌ Deny", f"an:{rid}")]]
        for b in self.store.bots():
            if b["enabled"] and b["chat_id"] and b["purpose"] == "control":
                try:
                    await self._send(self.store.token(b), b["chat_id"], Screen(text, rows))
                except Exception as e:
                    log.warning("approval message failed: %s", e)

    # ---------- alerts out ----------
    def alert_bots(self):
        if not self.active():
            return []
        return [b for b in self.store.bots() if b["enabled"] and b["chat_id"]]

    def hold_reason(self, sev="info"):
        """'' when an alert may be sent now, otherwise why not."""
        c = self.store.cfg()
        if not (c["on"] and c["sender"]):
            return "off"
        if not c["parts"]["alerts"]:
            return "alerts off"
        if c["pause_until"] > time.time():
            return "paused"
        q = c["quiet"]
        if q["on"] and self.in_quiet(q) and not (q["red"] and sev == "bad"):
            return "quiet hours"
        return ""

    @staticmethod
    def _minutes(hm):
        h, m = hm.split(":")
        return int(h) * 60 + int(m)

    def in_quiet(self, q):
        now = datetime.now()
        n, a, z = now.hour * 60 + now.minute, self._minutes(q["start"]), self._minutes(q["end"])
        return (a <= n < z) if a <= z else (n >= a or n < z)

    def next_morning(self):
        z = self._minutes(self.store.cfg()["quiet"]["end"]) if self.store.cfg()["quiet"]["on"] else 7 * 60
        now = datetime.now()
        t = now.replace(hour=z // 60, minute=z % 60, second=0, microsecond=0)
        if t <= now:
            t += timedelta(days=1)
        return t.timestamp()

    async def notify(self, text, rows=None, sev="info"):
        """Sends one alert to every linked bot that is allowed to send alerts. Returns how many bots got it."""
        if self.hold_reason(sev):
            return 0
        n = 0
        for b in self.alert_bots():
            try:
                tok = self.store.token(b)
                await self._send(tok, b["chat_id"], Screen(text, rows if b["purpose"] == "control" else []))
                n += 1
            except Exception as e:
                log.warning("telegram alert failed: %s", e)
        return n

    # ---------- used by the settings screens ----------
    async def check_token(self, token):
        me = await acall(token.strip(), "getMe", {}, 15)
        return {"id": me.get("id"), "username": me.get("username") or ""}

    async def send_test(self, bid):
        b = self.store.bot(bid)
        if not b or not b["chat_id"]:
            raise TgError("This bot isn't linked to your chat yet. Press Link my chat first.")
        await self._send(self.store.token(b), b["chat_id"], Screen("✅ <b>Telegram works.</b>\nThis is a test message from TruePilot."))

    def view(self):
        c = self.store.cfg()
        bots = []
        for b in self.store.bots():
            ok, txt = self.state.get(b["id"], (None, ""))
            p = self.pair.get(b["id"])
            bots.append({"id": b["id"], "label": b["label"], "username": b["username"], "purpose": b["purpose"], "purpose_label": PURPOSES.get(b["purpose"], b["purpose"]),
                         "enabled": bool(b["enabled"]), "linked": bool(b["chat_id"]), "chat_name": b["chat_name"] or "",
                         "state": "off" if ok is None and not txt else ("ok" if ok else ("bad" if ok is False else "wait")), "problem": txt if ok is False else "",
                         "pair": ({"code": p["code"], "expires": p["exp"]} if p and time.time() < p["exp"] else None)})
        return {"config": c, "bots": bots, "purposes": PURPOSES, "active": bool(c["on"] and c["sender"]), "now": time.time()}
