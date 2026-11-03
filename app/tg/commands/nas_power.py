"""Restart or shut down the NAS. Always asks Approve first."""
from fastapi import HTTPException

from ..registry import command
from ..ui import B, Screen, esc
from ._util import wait_task


def make(call, d, action, run_anyway):
    verb = "Restart" if action == "restart" else "Shut down"

    async def run():
        try:
            tid = await call.tp.host(d["id"], action, "Telegram", run_anyway)
        except HTTPException as e:
            if e.status_code == 409 and not run_anyway:
                return call.eng.confirm(call, f"{esc(str(e.detail))}\n{verb} <b>{esc(d['name'])}</b> anyway?", make(call, d, action, True), "⚠️ Do it anyway")
            raise

        async def then():
            t = await wait_task(call.tp, tid, 60)
            if t.get("status") == "failed":
                return Screen(f"❌ {esc(str(t.get('message') or ''))[:300]}", [[B("« Menu", "m")]])
            return Screen(f"✅ {verb} command sent to <b>{esc(d['name'])}</b>. I'll message you when it goes offline and when it is back.", [[B("« Menu", "m")]])
        return Screen(f"⏳ Sending the {verb.lower()} command to <b>{esc(d['name'])}</b>…", [[B("« Menu", "m")]], then)
    return run


async def ask(call, action):
    d, s = await call.snap()
    call.tp.need_write(call.tp.hub.row(d["id"]))
    verb = "Restart" if action == "restart" else "Shut down"
    why = "Apps and shares will be unavailable for a few minutes." if action == "restart" else "It stays off until you wake it with Wake-on-LAN or the power button."
    return call.eng.confirm(call, f"{verb} <b>{esc(d['name'])}</b>?\n{why}", make(call, d, action, False))


@command("nasrestart", "Restart the NAS (asks Approve first)", level="act")
async def restart(call):
    return await ask(call, "restart")


@command("nasshutdown", "Shut down the NAS (asks Approve first)", level="act")
async def shutdown(call):
    return await ask(call, "shutdown")
