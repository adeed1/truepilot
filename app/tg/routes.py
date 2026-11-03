"""The web addresses the Settings screen uses to manage Telegram. Tokens are never sent back to the browser."""
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .api import TgError
from .store import PURPOSES

TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")


class BotIn(BaseModel):
    label: str = ""
    token: str = ""
    purpose: str = "control"
    enabled: bool | None = None


class PauseIn(BaseModel):
    minutes: int | None = None
    until: str = ""   # "morning" or "off"


def make_router(eng, auth):
    r = APIRouter(prefix="/api/telegram")
    tp, store = eng.tp, eng.store

    def need_bot(bid):
        b = store.bot(bid)
        if not b:
            raise HTTPException(404, "That bot isn't in the list")
        return b

    @r.get("")
    async def overview(s=Depends(auth)):
        return eng.view()

    @r.put("/config")
    async def set_config(body: dict, s=Depends(auth)):
        before = store.cfg()
        store.patch(body)
        after = store.cfg()
        for k in ("on", "sender"):
            if before[k] != after[k]:
                tp.audit(s["label"], 0, "telegram_" + k, "on" if after[k] else "off")
        if before["parts"]["powerful"] != after["parts"]["powerful"]:
            tp.audit(s["label"], 0, "telegram_powerful", "on" if after["parts"]["powerful"] else "off")
        return eng.view()

    @r.post("/bots")
    async def add_bot(body: BotIn, s=Depends(auth)):
        token = body.token.strip()
        if not TOKEN_RE.match(token):
            raise HTTPException(400, "That doesn't look like a bot token. It looks like 123456789:ABC... and BotFather gives it to you.")
        if body.purpose not in PURPOSES:
            raise HTTPException(400, "Pick what the bot does")
        try:
            me = await eng.check_token(token)
        except TgError as e:
            raise HTTPException(400, f"Telegram says: {e}")
        if any(b["bot_id"] == me["id"] for b in store.bots()):
            raise HTTPException(409, "That bot is already added")
        first = not store.bots()
        bid = store.add_bot(body.label.strip()[:40] or "My phone", me["username"], me["id"], token, body.purpose)
        if first and not store.cfg()["on"]:
            store.patch({"on": True})
        tp.audit(s["label"], 0, "telegram_add_bot", "@" + me["username"], PURPOSES[body.purpose])
        return {"id": bid, **eng.view()}

    @r.put("/bots/{bid}")
    async def edit_bot(bid: int, body: BotIn, s=Depends(auth)):
        b = need_bot(bid)
        kw = {}
        if body.label.strip():
            kw["label"] = body.label.strip()[:40]
        if body.purpose in PURPOSES and body.purpose != b["purpose"]:
            kw["purpose"] = body.purpose
        if body.enabled is not None:
            kw["enabled"] = int(body.enabled)
        if body.token.strip():
            token = body.token.strip()
            if not TOKEN_RE.match(token):
                raise HTTPException(400, "That doesn't look like a bot token")
            try:
                me = await eng.check_token(token)
            except TgError as e:
                raise HTTPException(400, f"Telegram says: {e}")
            if any(x["bot_id"] == me["id"] and x["id"] != bid for x in store.bots()):
                raise HTTPException(409, "That bot is already added")
            kw.update(token=token, username=me["username"], bot_id=me["id"])
            tp.audit(s["label"], 0, "telegram_change_token", "@" + me["username"])
        store.update_bot(bid, **kw)
        return eng.view()

    @r.delete("/bots/{bid}")
    async def del_bot(bid: int, s=Depends(auth)):
        b = need_bot(bid)
        store.del_bot(bid)
        eng.pair.pop(bid, None)
        eng.state.pop(bid, None)
        tp.audit(s["label"], 0, "telegram_remove_bot", "@" + (b["username"] or ""))
        return eng.view()

    @r.post("/bots/{bid}/pair")
    async def pair(bid: int, s=Depends(auth)):
        need_bot(bid)
        if not eng.active():
            raise HTTPException(409, "Telegram is switched off on this copy of TruePilot. Turn it on first.")
        return eng.pair_start(bid)

    @r.post("/bots/{bid}/unlink")
    async def unlink(bid: int, s=Depends(auth)):
        need_bot(bid)
        store.update_bot(bid, chat_id=None, chat_name="")
        tp.audit(s["label"], 0, "telegram_unlink", str(bid))
        return eng.view()

    @r.post("/bots/{bid}/test")
    async def test(bid: int, s=Depends(auth)):
        need_bot(bid)
        try:
            await eng.send_test(bid)
        except TgError as e:
            raise HTTPException(400, str(e))
        return {"ok": True}

    @r.post("/bots/{bid}/check")
    async def check(bid: int, s=Depends(auth)):
        need_bot(bid)
        return {"steps": await eng.check_connection(bid)}

    @r.post("/pause")
    async def pause(body: PauseIn, s=Depends(auth)):
        if body.until == "morning":
            t = eng.next_morning()
        elif body.minutes and body.minutes > 0:
            t = time.time() + min(body.minutes, 60 * 24 * 14) * 60
        else:
            t = 0
        store.patch({"pause_until": t})
        tp.audit(s["label"], 0, "telegram_pause", "resumed" if not t else "paused")
        return eng.view()

    @r.post("/disable-now")
    async def disable_now(s=Depends(auth)):
        store.patch({"on": False, "parts": {"powerful": False}})
        tp.audit(s["label"], 0, "telegram_disable_now", "Telegram and powerful commands turned off")
        return eng.view()

    return r
