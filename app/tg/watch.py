"""Watches your NAS about once a minute and tells you on Telegram when something goes wrong, and when it is fixed.
Rules: one message when a problem starts, one when it ends, a reminder every few hours while it lasts,
nothing while alerts are paused or in quiet hours, and several problems in one check become one message."""
import asyncio
import hashlib
import logging
import math
import time
from datetime import datetime

from .ui import B, esc, size

log = logging.getLogger("truepilot.telegram.watch")
LEVELS = ["INFO", "NOTICE", "WARNING", "ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
ICON = {"bad": "🔴", "warn": "🟠", "info": "🔵", "ok": "🟢"}
RANK = {"ok": 0, "info": 1, "warn": 2, "bad": 3}


def cond(cat, sev, title, detail="", rows=None, dev=None, recover=None, confirm=2, repeat=True, names=None):
    return {"cat": cat, "sev": sev, "title": title, "detail": detail, "rows": rows or [], "dev": dev,
            "recover": recover, "confirm": confirm, "repeat": repeat, "names": names}


class Watcher:
    def __init__(self, eng):
        self.eng, self.tp = eng, eng.tp
        self.state = {}       # condition key -> what we know
        self.app_prev = {}    # (device, app) -> last state
        self.stopped = {}     # (device, app) -> when it was seen stopped
        self.pc_prev = {}
        self.daily_done = ""

    async def run(self):
        await asyncio.sleep(min(20, self.eng.tick_seconds))
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("alert check failed")
            await asyncio.sleep(self.eng.tick_seconds)

    async def _snap(self, d):
        try:
            return await asyncio.wait_for(self.tp.hub.snapshot(d["id"]), 30)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _intentional(self, name):
        """True when someone stopped or restarted this app through TruePilot in the last 10 minutes."""
        rows = self.tp.db.q("SELECT 1 AS x FROM audit WHERE ts>? AND target=? AND action IN ('app_stop','app_restart','app_upgrade','stop_app','restart_app') LIMIT 1",
                            (time.time() - 600, name))
        return bool(rows)

    # ---------- what is wrong right now ----------
    async def collect(self, c):
        found, offline = {}, set()
        types = c["types"]
        devs = self.tp.db.q("SELECT * FROM devices WHERE kind IN ('truenas','demo') ORDER BY id")
        snaps = await asyncio.gather(*[self._snap(d) for d in devs])
        for d, s in zip(devs, snaps):
            did, nm = d["id"], d["name"]
            if not s.get("ok"):
                offline.add(did)
                if types["nas"]:
                    ticks = max(1, math.ceil(c["offline_min"] * 60 / max(1, self.eng.tick_seconds)))
                    found[f"nas:{did}"] = cond("nas", "bad", f"{nm} is not answering", str(s.get("error") or "")[:160],
                                               [[B("Wake NAS", f"w:dev{did}")]] if d["mac"] else [], did, f"{nm} is back online", confirm=ticks)
                continue
            for p in s.get("pools") or []:
                if types["pool"] and (p["status"] != "ONLINE" or p.get("healthy") is False):
                    found[f"pool:{did}:{p['name']}"] = cond("pool", "bad", f"Pool {p['name']} is {str(p['status']).lower()}", "A disk may have failed. Open TrueNAS to check.",
                                                            [[B("Storage", "sto")]], did, f"Pool {p['name']} is healthy again")
                if types["space"] and p.get("pct", 0) >= c["space_pct"]:
                    found[f"space:{did}:{p['name']}"] = cond("space", "bad" if p["pct"] >= 95 else "warn", f"Pool {p['name']} is {p['pct']:.0f}% full",
                                                             f"{size(p.get('free'))} free", [[B("Storage", "sto")]], did, f"Pool {p['name']} has enough space again")
            for k in s.get("disks") or []:
                if not types["pool"]:
                    break
                t, hot = k.get("temp"), ((70, 80) if k.get("type") == "SSD" else (50, 60))
                if k.get("smart") == "fail":
                    found[f"disk:{did}:{k['name']}"] = cond("pool", "bad", f"Disk {k['name']} failed a SMART test", "", [[B("Disks", "dk")]], did, f"Disk {k['name']} passes again")
                elif isinstance(t, (int, float)) and t >= hot[0]:
                    found[f"temp:{did}:{k['name']}"] = cond("pool", "bad" if t >= hot[1] else "warn", f"Disk {k['name']} is hot ({t:.0f}°C)", "", [[B("Disks", "dk")]], did, f"Disk {k['name']} has cooled down")
            if types["app"]:
                for a in s.get("apps") or []:
                    key, st, name, title = (did, a["name"]), a["state"], a["name"], a["title"]
                    prev = self.app_prev.get(key)
                    if st == "CRASHED":
                        found[f"app:{did}:{name}"] = cond("app", "bad", f"{title} crashed", "", [[B("Restart", f"x:restart:{name}"), B("Logs", f"lg:{name}")]], did, f"{title} is running again")
                    elif st == "STOPPED":
                        if key in self.stopped or (prev in ("RUNNING", "DEPLOYING") and not self._intentional(name)):
                            self.stopped.setdefault(key, time.time())
                            found[f"app:{did}:{name}"] = cond("app", "warn", f"{title} stopped", "", [[B("Start", f"x:start:{name}"), B("Logs", f"lg:{name}")]], did, f"{title} is running again", repeat=False)
                    else:
                        self.stopped.pop(key, None)
                    self.app_prev[key] = st
            if types["updates"]:
                names = sorted(a["title"] for a in s.get("apps") or [] if a.get("upgrade"))
                if names:
                    found[f"upd:{did}"] = cond("updates", "info", f"{len(names)} app update{'s' if len(names) != 1 else ''} waiting", ", ".join(esc(n) for n in names[:12]),
                                               [[B("Updates", "up")]], did, None, repeat=False, names=names)
            if types["truenas"]:
                for a in s.get("alerts") or []:
                    lv = LEVELS.index(a["level"]) if a["level"] in LEVELS else 0
                    if lv >= 2:
                        ident = a.get("id") or hashlib.md5((a.get("text") or "").encode()).hexdigest()[:10]
                        found[f"ta:{did}:{ident}"] = cond("truenas", "bad" if lv >= 3 else "warn", "TrueNAS alert", esc((a.get("text") or "")[:300]), [[B("Alerts", "al")]], did, None, repeat=False)
        return found, offline

    # ---------- one check ----------
    async def tick(self):
        eng = self.eng
        c = eng.store.cfg()
        if not eng.active() or not c["parts"]["alerts"] or not eng.alert_bots():
            self.state.clear()
            return
        found, offline = await self.collect(c)
        now, events = time.time(), []
        for key, cd in found.items():
            st = self.state.setdefault(key, {"seen": 0, "notified": 0, "sev": None, "names": None})
            st["seen"] += 1
            st["cond"] = cd
            if st["seen"] < cd["confirm"]:
                continue
            was = st["notified"]
            changed = bool(was) and (st["sev"] != cd["sev"] or (cd["names"] is not None and st["names"] != cd["names"]))
            repeat = bool(was) and cd["repeat"] and cd["sev"] in ("bad", "warn") and now - was >= c["repeat_h"] * 3600
            if (not was or changed or repeat) and eng.hold_reason(cd["sev"]) == "":
                head = ("Still: " if repeat else "") + esc(cd["title"])
                events.append((cd["sev"], f"{ICON[cd['sev']]} <b>{head}</b>" + (f"\n{cd['detail']}" if cd["detail"] else ""), cd["rows"]))
                st.update(notified=now, sev=cd["sev"], names=cd["names"])
        for key in list(self.state):
            if key in found:
                continue
            st = self.state[key]
            cd = st["cond"]
            if cd.get("dev") in offline:
                continue
            del self.state[key]
            if st["notified"] and cd.get("recover") and c["types"].get(cd["cat"], True) and eng.hold_reason("ok") == "":
                events.append(("ok", f"🟢 {esc(cd['recover'])}", []))
        if c["types"]["daily"]:
            ev = await self._daily(c)
            if ev:
                events.append(ev)
        if events:
            rows = [r for _, _, rr in events for r in rr][:8]
            worst = max((e[0] for e in events), key=lambda s: RANK[s])
            await eng.notify("\n\n".join(e[1] for e in events), rows, worst)

    async def _daily(self, c):
        now = datetime.now()
        key = now.strftime("%Y-%m-%d")
        if self.daily_done == key or now.strftime("%H:%M") < c["daily_at"]:
            return None
        self.daily_done = key
        lines = ["☀️ <b>Daily summary</b>"]
        for d in self.tp.db.q("SELECT * FROM devices WHERE kind IN ('truenas','demo') ORDER BY id"):
            s = await self._snap(d)
            if not s.get("ok"):
                lines.append(f"🔴 {esc(d['name'])} is not answering")
                continue
            apps = s.get("apps") or []
            run = len([a for a in apps if a["state"] == "RUNNING"])
            pools = ", ".join(f"{esc(p['name'])} {p['pct']:.0f}%" for p in s.get("pools") or [])
            ups = len([a for a in apps if a.get("upgrade")])
            al = len(s.get("alerts") or [])
            lines.append(f"🟢 <b>{esc(d['name'])}</b>: {run} of {len(apps)} apps running" + (f", {ups} to update" if ups else "") + (f"\nStorage: {pools}" if pools else "") + (f"\n{al} TrueNAS alert{'s' if al != 1 else ''}" if al else ""))
        return ("info", "\n".join(lines), [[B("Status", "st")]])

    # ---------- called by the scheduler when a job finishes ----------
    def job_done(self, name, result):
        c = self.eng.store.cfg()
        if not self.eng.active() or not c["types"]["jobs"] or str(result).startswith("ok: skipped"):
            return
        bad = str(result).startswith("failed")
        self.eng.spawn(self.eng.notify(f"{'❌' if bad else '✅'} <b>Scheduled job: {esc(name)}</b>\n{esc(str(result))[:300]}", [], "bad" if bad else "info"))
