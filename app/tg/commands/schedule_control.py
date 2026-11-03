"""Run, pause, resume or delete a scheduled job."""
from fastapi import HTTPException

from ..registry import callback, command
from ..ui import B, Say, Screen, esc

BACK = [[B("⏰ Schedules", "sc"), B("« Menu", "m")]]


def find_jobs(call, text):
    rows = call.tp.db.q("SELECT * FROM schedules ORDER BY id")
    t = (text or "").strip().lower()
    for test in (lambda r: str(r["id"]) == t or r["name"].lower() == t, lambda r: r["name"].lower().startswith(t), lambda r: t in r["name"].lower()):
        hits = [r for r in rows if test(r)]
        if hits:
            return hits
    return []


def pick(call, verb, prefix):
    rows = call.tp.db.q("SELECT * FROM schedules ORDER BY id")
    if not rows:
        raise Say("No scheduled jobs yet. Add them in TruePilot under Schedules.")
    return Screen(f"Which job do you want to {verb}?", [[B(r["name"], f"{prefix}:{r['id']}")] for r in rows[:12]] + [[B("« Menu", "m")]])


async def target(call, verb, prefix):
    if not call.args:
        return pick(call, verb, prefix), None
    hits = find_jobs(call, call.text)
    if not hits:
        raise Say(f"I couldn't find a job called <b>{esc(call.text)}</b>. Try /schedules.", "sc")
    if len(hits) > 1:
        return Screen("Which one?", [[B(r["name"], f"{prefix}:{r['id']}")] for r in hits[:8]] + [[B("« Menu", "m")]]), None
    return None, hits[0]


async def do_run(call, r):
    if r["kind"] == "host":
        raise Say("That job runs inside TrueNAS on its own schedule, so I can't run it from here.", "sc")
    call.tp.audit("Telegram", r["device_id"] or 0, "run_schedule_now", r["name"])
    call.tp.sched_run(r)
    return Screen(f"▶ Started <b>{esc(r['name'])}</b>. I'll message you when it finishes.", BACK)


async def do_toggle(call, r, on):
    try:
        await call.tp.sched_patch(r["id"], on, "Telegram")
    except HTTPException as e:
        raise Say("⚠️ " + esc(str(e.detail)), "sc")
    return Screen(f"{'▶ Resumed' if on else '⏸ Paused'} <b>{esc(r['name'])}</b>.", BACK)


def ask_delete(call, r):
    async def run():
        try:
            await call.tp.sched_delete(r["id"], "Telegram")
        except HTTPException as e:
            raise Say("⚠️ " + esc(str(e.detail)), "sc")
        return Screen(f"🗑 Deleted <b>{esc(r['name'])}</b>.", BACK)
    return call.eng.confirm(call, f"Delete the job <b>{esc(r['name'])}</b>? This can't be undone.", run, "🗑 Delete")


def job(call, rid):
    r = call.tp.db.one("SELECT * FROM schedules WHERE id=?", (int(rid),))
    if not r:
        raise Say("That job isn't in the list any more.", "sc")
    return r


@command("run", "Run a scheduled job now", level="act", args="<job>")
async def run_cmd(call):
    s, r = await target(call, "run", "jr")
    return s or await do_run(call, r)


@command("pausejob", "Pause a scheduled job", level="act", args="<job>")
async def pause_cmd(call):
    s, r = await target(call, "pause", "jp")
    return s or await do_toggle(call, r, False)


@command("resumejob", "Resume a paused job", level="act", args="<job>")
async def resume_cmd(call):
    s, r = await target(call, "resume", "jc")
    return s or await do_toggle(call, r, True)


@command("deljob", "Delete a scheduled job (asks Approve first)", level="act", args="<job>")
async def del_cmd(call):
    s, r = await target(call, "delete", "jd")
    return s or ask_delete(call, r)


@callback("jr", "act")
async def jr(call):
    return await do_run(call, job(call, call.data[0]))


@callback("jp", "act")
async def jp(call):
    return await do_toggle(call, job(call, call.data[0]), False)


@callback("jc", "act")
async def jc(call):
    return await do_toggle(call, job(call, call.data[0]), True)


@callback("jd", "act")
async def jd(call):
    return ask_delete(call, job(call, call.data[0]))
