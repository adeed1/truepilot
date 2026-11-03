"""Answer a request from Hermes (or another agent) with Approve or Deny."""
import time

from fastapi import HTTPException

from ..registry import callback, command
from ..ui import B, Screen, esc
from ._util import wait_task

BACK = [[B("« Menu", "m")]]


async def answer(call, rid, approve, run_anyway=False):
    try:
        text, tid = await call.tp.resolve(rid, approve, "Telegram", run_anyway)
    except HTTPException as e:
        if e.status_code == 409 and approve and not run_anyway:
            r = call.tp.db.one("SELECT action FROM approvals WHERE id=?", (rid,))
            rows = [[B("⚠️ Do it anyway", f"ayf:{rid}"), B("❌ Deny", f"an:{rid}")]] if r and r["action"] in ("restart_nas", "shutdown_nas") else [[B("❌ Deny", f"an:{rid}")]]
            return Screen(f"⚠️ {esc(str(e.detail))}", rows)
        return Screen("⚠️ " + esc(str(e.detail)), BACK)
    mark = "✅" if approve else "❌"
    if not tid:
        return Screen(f"{mark} {esc(text)}", BACK)

    async def then():
        t = await wait_task(call.tp, tid, 1800)
        if t.get("status") == "failed":
            return Screen(f"❌ {esc(str(t.get('message') or 'It did not work'))[:300]}", BACK)
        if t.get("status") == "running":
            return Screen(f"⏳ {esc(text)}. Still working, I'll stop watching now.", BACK)
        return Screen(f"✅ {esc(text)}. Done.", BACK)

    return Screen(f"⏳ {mark} {esc(text)}…", BACK, then)


@callback("ay", "approve")
async def yes(call):
    return await answer(call, int(call.data[0]), True)


@callback("ayf", "approve")
async def yes_anyway(call):
    return await answer(call, int(call.data[0]), True, True)


@callback("an", "approve")
async def no(call):
    return await answer(call, int(call.data[0]), False)


@command("approvals", "Requests waiting for your approval", level="approve")
async def approvals_cmd(call):
    rows = [r for r in call.tp.db.q("SELECT * FROM approvals WHERE status='pending' ORDER BY id DESC LIMIT 8") if time.time() - r["created"] < 1800]
    if not rows:
        return Screen("✅ Nothing is waiting for your approval.", BACK)
    kb = []
    out = ["🤖 <b>Waiting for your approval</b>"]
    for r in rows:
        out.append(f"• {esc(r['token_name'])}: {esc(r['summary'] or r['action'])}")
        kb.append([B(f"✅ {r['id']}", f"ay:{r['id']}"), B(f"❌ {r['id']}", f"an:{r['id']}")])
    return Screen("\n".join(out), kb + BACK)
