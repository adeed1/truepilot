"""Saved Telegram settings and bots. Bot tokens are encrypted with the same vault as your TrueNAS keys."""
import json
import re
import time

DEFAULTS = {
    "on": False,        # master switch
    "sender": True,     # this copy of TruePilot talks to Telegram (turn off on the NAS copy)
    "parts": {"alerts": True, "commands": True, "approvals": True, "powerful": False},
    "types": {"pool": True, "space": True, "app": True, "nas": True, "truenas": True, "pc": False, "updates": True, "jobs": True, "power": True, "daily": False},
    "space_pct": 85, "offline_min": 3, "repeat_h": 6, "daily_at": "08:00",
    "quiet": {"on": False, "start": "22:00", "end": "07:00", "red": True},
    "pause_until": 0,
}
PURPOSES = {"control": "Control and alerts", "alerts": "Alerts only"}
_HM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _merge(base, over):
    out = {}
    for k, v in base.items():
        o = over.get(k)
        if isinstance(v, dict):
            out[k] = _merge(v, o if isinstance(o, dict) else {})
        elif k in over and ((isinstance(v, bool) and isinstance(o, bool)) or (_num(v) and _num(o)) or (isinstance(v, str) and isinstance(o, str))):
            out[k] = o
        else:
            out[k] = v
    return out


class Store:
    def __init__(self, db, vault):
        self.db, self.vault = db, vault

    # ----- settings -----
    def cfg(self):
        try:
            raw = json.loads(self.db.get("tg_cfg") or "{}")
        except ValueError:
            raw = {}
        return _merge(DEFAULTS, raw if isinstance(raw, dict) else {})

    def save(self, cfg):
        self.db.put("tg_cfg", json.dumps(cfg))
        return cfg

    def patch(self, p):
        """Applies a partial change. Unknown keys are ignored; values are checked."""
        c = self.cfg()
        for k in ("on", "sender"):
            if isinstance(p.get(k), bool):
                c[k] = p[k]
        for grp in ("parts", "types"):
            for k, v in (p.get(grp) or {}).items():
                if k in c[grp] and isinstance(v, bool):
                    c[grp][k] = v
        for k, lo, hi in (("space_pct", 50, 99), ("offline_min", 1, 60), ("repeat_h", 1, 48)):
            if isinstance(p.get(k), (int, float)) and not isinstance(p.get(k), bool):
                c[k] = int(max(lo, min(hi, p[k])))
        if isinstance(p.get("daily_at"), str) and _HM.match(p["daily_at"]):
            c["daily_at"] = p["daily_at"]
        q = p.get("quiet") or {}
        for k in ("on", "red"):
            if isinstance(q.get(k), bool):
                c["quiet"][k] = q[k]
        for k in ("start", "end"):
            if isinstance(q.get(k), str) and _HM.match(q[k]):
                c["quiet"][k] = q[k]
        if isinstance(p.get("pause_until"), (int, float)) and not isinstance(p.get("pause_until"), bool):
            c["pause_until"] = float(p["pause_until"])
        return self.save(c)

    # ----- bots -----
    def bots(self):
        return self.db.q("SELECT * FROM tg_bots ORDER BY id")

    def bot(self, bid):
        return self.db.one("SELECT * FROM tg_bots WHERE id=?", (bid,))

    def token(self, b):
        return self.vault.dec(b["token_enc"])

    def add_bot(self, label, username, bot_id, token, purpose):
        return self.db.x("INSERT INTO tg_bots(label,username,bot_id,token_enc,purpose,enabled,chat_id,chat_name,created) VALUES(?,?,?,?,?,1,NULL,'',?)",
                         (label, username, bot_id, self.vault.enc(token), purpose, time.time()))

    def update_bot(self, bid, **kw):
        cols = {"label", "username", "bot_id", "purpose", "enabled", "chat_id", "chat_name"}
        sets, args = [], []
        for k, v in kw.items():
            if k == "token":
                sets.append("token_enc=?")
                args.append(self.vault.enc(v))
            elif k in cols:
                sets.append(f"{k}=?")
                args.append(v)
        if sets:
            self.db.x(f"UPDATE tg_bots SET {', '.join(sets)} WHERE id=?", (*args, bid))

    def del_bot(self, bid):
        self.db.x("DELETE FROM tg_bots WHERE id=?", (bid,))
