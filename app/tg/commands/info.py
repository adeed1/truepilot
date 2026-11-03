"""Schedules, recent activity, and switching between NAS units."""
import time

from ..registry import callback, command
from ..ui import B, Screen, esc


@command("schedules", "Your scheduled jobs and when they run next")
async def schedules_cmd(call):
    return await schedules_screen(call)


@callback("sc")
async def schedules_cb(call):
    return await schedules_screen(call)


async def schedules_screen(call):
    out = ["⏰ <b>Schedules</b>"]
    rows = call.tp.db.q("SELECT * FROM schedules ORDER BY id")
    for r in rows[:20]:
        j = call.tp.sched_out(r)
        nxt = time.strftime("%a %d %b %H:%M", time.localtime(j["next_run"])) if j.get("next_run") else "paused"
        res = f"\n   last: {esc(str(j['last_result'])[:80])}" if j.get("last_result") else ""
        out.append(f"{'🟢' if j['enabled'] else '⚪'} <b>{esc(j['name'])}</b> · {esc(call.tp.human_cron(j['cron']))}\n   next: {nxt}{res}")
    if not rows:
        out.append("No scheduled jobs yet. Add them in TruePilot under Schedules.")
    kb = []
    for r in rows[:8]:
        j = call.tp.sched_out(r)
        kb.append(([B(f"▶ {r['name'][:22]}", f"jr:{r['id']}")] if r["kind"] != "host" else []) + [B("⏸ Pause" if j["enabled"] else "▶ Resume", f"{'jp' if j['enabled'] else 'jc'}:{r['id']}")])
    return Screen("\n".join(out)[:3900], kb + [[B("🔄 Refresh", "sc"), B("« Menu", "m")]])


@command("activity", "The last things TruePilot did")
async def activity_cmd(call):
    rows = call.tp.db.q("SELECT * FROM audit ORDER BY id DESC LIMIT 10")
    out = ["🕘 <b>Recent activity</b>"]
    for r in rows:
        out.append(f"{'✅' if r['result'] == 'ok' else '⚠️'} {time.strftime('%d %b %H:%M', time.localtime(r['ts']))} · {esc(r['action'].replace('_', ' '))} {esc(r['target'] or '')} · {esc(r['who'])}")
    return Screen("\n".join(out)[:3900], [[B("« Menu", "m")]])


@command("nas", "Switch between NAS units", args="[name]")
async def nas_cmd(call):
    devs = call.devices()
    if call.args:
        t = call.text.lower()
        d = next((x for x in devs if t in x["name"].lower()), None)
        if d:
            call.eng.sel[call.bot["id"]] = d["id"]
            return Screen(f"Now looking at <b>{esc(d['name'])}</b>.", [[B("📊 Status", "st"), B("« Menu", "m")]])
    cur = call.device()
    return Screen("🖥 <b>Which NAS?</b>", [[B(("✅ " if d["id"] == cur["id"] else "") + d["name"], f"nas:{d['id']}")] for d in devs] + [[B("« Menu", "m")]])


@callback("nas")
async def nas_cb(call):
    call.eng.sel[call.bot["id"]] = int(call.data[0])
    d = call.device()
    return Screen(f"Now looking at <b>{esc(d['name'])}</b>.", [[B("📊 Status", "st"), B("« Menu", "m")]])
