"""PCs and the NAS: see what is on, wake things up, and open your Web Apps."""
import asyncio

from ..registry import callback, command
from ..ui import B, Say, Screen, esc

STATE = {"on": "🟢 on", "off": "⚪ off", "waking": "🟡 waking", "unknown": "⚪ unknown"}


async def pcs_screen(call, only_off=False):
    rows = await call.tp.pcs_with_status()
    if only_off:
        rows = [r for r in rows if r["state"] != "on"]
    out = ["🔌 <b>Wake a PC</b>" if only_off else "💻 <b>PCs and NAS</b>"]
    kb = []
    for r in rows:
        out.append(f"{STATE.get(r['state'], '⚪')} · {esc(r['name'])}" + (" (NAS)" if r["kind"] == "nas" else ""))
        if r["state"] in ("off", "unknown"):
            kb.append([B(f"⏻ Wake {r['name']}", f"w:{r['id']}")])
    if not rows:
        out.append("No PCs in the wake list yet. Add them in TruePilot under Power.")
    kb.append([B("🔄 Refresh", "pcw" if only_off else "pc"), B("« Menu", "m")])
    return Screen("\n".join(out), kb)


@command("pcs", "Your PCs and whether they are on")
async def pcs_cmd(call):
    return await pcs_screen(call)


@callback("pc")
async def pcs_cb(call):
    return await pcs_screen(call)


@callback("pcw")
async def pcw_cb(call):
    return await pcs_screen(call, True)


async def wake_row(call, row):
    tp = call.tp
    if row["state"] == "on":
        return Screen(f"🟢 <b>{esc(row['name'])}</b> is already on.", [[B("« PCs", "pc"), B("« Menu", "m")]])
    if row["state"] == "waking":
        return Screen(f"🟡 <b>{esc(row['name'])}</b> is already being woken.", [[B("« PCs", "pc"), B("« Menu", "m")]])
    tp.audit("Telegram", 0, "wake", row["name"])
    if row["kind"] == "nas":
        d = tp.hub.row(row["device_id"])
        tid = tp.new_task(d["id"], f"Wake {d['name']}", lambda: tp.watch_wake(d["name"], d["mac"], d["broadcast"], d["host"], d["port"]), kind="wake", target=f"dev:{d['id']}")
    else:
        pc = tp.db.one("SELECT * FROM wol_targets WHERE id=?", (row["id"],))
        if not pc:
            raise Say("That PC isn't in the list any more.", "pc")
        tid = tp.wake_pc_task(pc)

    async def then():
        for _ in range(330):
            t = tp.tasks.get(tid)
            if not t or t["status"] != "running":
                break
            await asyncio.sleep(1)
        t = tp.tasks.get(tid) or {}
        if t.get("status") == "failed":
            return Screen(f"❌ <b>{esc(row['name'])}</b>: {esc(str(t.get('message') or ''))[:300]}", [[B("« PCs", "pc"), B("« Menu", "m")]])
        return Screen(f"🟢 {esc(str(t.get('message') or row['name'] + ' is on'))}", [[B("« PCs", "pc"), B("« Menu", "m")]])

    return Screen(f"⏳ Wake packet sent to <b>{esc(row['name'])}</b>. Watching for it to start…", [[B("« PCs", "pc")]], then)


@command("wake", "Wake a PC or the NAS", level="act", args="[name]")
async def wake_cmd(call):
    rows = await call.tp.pcs_with_status()
    if not call.args:
        return await pcs_screen(call, True)
    t = call.text.lower()
    hits = [r for r in rows if r["name"].lower() == t] or [r for r in rows if t in r["name"].lower()]
    if not hits:
        raise Say(f"I couldn't find a PC called <b>{esc(call.text)}</b>. Try /pcs.", "pc")
    if len(hits) > 1:
        return Screen("Which one?", [[B(h["name"], f"w:{h['id']}")] for h in hits[:8]] + [[B("« Menu", "m")]])
    return await wake_row(call, hits[0])


@callback("w", "act")
async def wake_cb(call):
    rows = await call.tp.pcs_with_status()
    row = next((r for r in rows if str(r["id"]) == call.data[0]), None)
    if not row:
        raise Say("That PC isn't in the list any more.", "pc")
    return await wake_row(call, row)


@command("webapps", "Your Web Apps, with a button to open each")
async def webapps_cmd(call):
    return await webapps_screen(call)


@callback("wa")
async def webapps_cb(call):
    return await webapps_screen(call)


async def webapps_screen(call):
    rows = await call.tp.webapps_with_status()
    out = ["🌐 <b>Web Apps</b>"]
    kb = []
    for r in rows[:14]:
        out.append(f"{'🟢' if r['state'] == 'on' else '🔴'} {esc(r['name'])}")
        kb.append([B(f"🔗 {r['name']}", url=r["url"])] + ([B("⏻ Wake host", f"w:{r['wake_id']}")] if r["state"] != "on" and r.get("wake_id") else []))
    if not rows:
        out.append("No Web Apps yet. Add them in TruePilot under Power.")
    kb.append([B("🔄 Refresh", "wa"), B("« Menu", "m")])
    return Screen("\n".join(out), kb)
