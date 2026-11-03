"""Update apps. Always asks Approve first."""
from ..registry import callback, command
from ..ui import B, Say, Screen, esc
from ._util import wait_task
from .apps import find

BACK = [[B("« Menu", "m")]]


def one(call, d, a):
    async def run():
        tid = await call.tp.upgrade(d["id"], a["name"], "Telegram")

        async def then():
            t = await wait_task(call.tp, tid, 1800)
            if t.get("status") == "failed":
                return Screen(f"❌ <b>{esc(a['title'])}</b>: {esc(str(t.get('message') or ''))[:300]}", [[B("« App", f"a:{a['name']}"), B("« Menu", "m")]])
            if t.get("status") == "running":
                return Screen(f"⏳ <b>{esc(a['title'])}</b> is still updating. Check its card in a while.", [[B("« App", f"a:{a['name']}")]])
            return Screen(f"✅ <b>{esc(a['title'])}</b> is updated.", [[B("« App", f"a:{a['name']}"), B("« Menu", "m")]])
        return Screen(f"⏳ Updating <b>{esc(a['title'])}</b>. This can take several minutes…", [[B("« Menu", "m")]], then)
    return run


async def ask_one(call, name):
    d, s = await call.snap()
    call.tp.need_write(call.tp.hub.row(d["id"]))
    a = next((x for x in s.get("apps") or [] if x["name"] == name), None)
    if not a:
        raise Say(f"There is no app called <b>{esc(name)}</b>.", "ap:0:a")
    if not a.get("upgrade"):
        return Screen(f"✅ <b>{esc(a['title'])}</b> is already up to date.", [[B("« App", f"a:{name}"), B("« Menu", "m")]])
    return call.eng.confirm(call, f"Update <b>{esc(a['title'])}</b> ({esc(str(a.get('version') or ''))})?\nTruePilot takes a snapshot of its storage first. The app is unavailable while it updates.", one(call, d, a))


@command("upgrade", "Update an app (asks Approve first)", level="act", args="<app>")
async def upgrade_cmd(call):
    d, s = await call.snap()
    apps = s.get("apps") or []
    if not call.args:
        ups = [a for a in apps if a.get("upgrade")]
        if not ups:
            return Screen("✅ All apps are up to date.", BACK)
        return Screen("⬆️ <b>Which app?</b>", [[B(a["title"], f"ug:{a['name']}")] for a in ups[:12]] + BACK)
    hits = find(apps, call.text)
    if not hits:
        raise Say(f"I couldn't find an app called <b>{esc(call.text)}</b>.", "ap:0:a")
    if len(hits) > 1:
        return Screen("Which one?", [[B(h["title"], f"ug:{h['name']}")] for h in hits[:8]] + BACK)
    return await ask_one(call, hits[0]["name"])


@callback("ug", "act")
async def upgrade_cb(call):
    return await ask_one(call, call.data[0])


@command("upgradeall", "Update every app that has an update (asks Approve first)", level="act")
async def upgradeall(call):
    return await ask_all(call)


@callback("uga", "act")
async def upgradeall_cb(call):
    return await ask_all(call)


async def ask_all(call):
    d, s = await call.snap()
    call.tp.need_write(call.tp.hub.row(d["id"]))
    ups = [a for a in s.get("apps") or [] if a.get("upgrade")]
    if not ups:
        return Screen("✅ All apps are up to date.", BACK)

    async def run():
        async def then():
            ok, bad = [], []
            for a in ups:
                try:
                    t = await wait_task(call.tp, await call.tp.upgrade(d["id"], a["name"], "Telegram"), 1800)
                    (ok if t.get("status") == "done" else bad).append(a["title"] + ("" if t.get("status") == "done" else f" ({str(t.get('message') or 'still running')[:60]})"))
                except Exception as e:
                    bad.append(f"{a['title']} ({str(getattr(e, 'detail', e))[:60]})")
            out = ["⬆️ <b>Updates finished</b>"] + ([f"✅ {esc(', '.join(ok))}"] if ok else []) + ([f"❌ {esc('; '.join(bad))}"] if bad else [])
            return Screen("\n".join(out), BACK)
        return Screen(f"⏳ Updating {len(ups)} app{'s' if len(ups) != 1 else ''} one by one. This can take a while…", BACK, then)
    return call.eng.confirm(call, f"Update {len(ups)} app{'s' if len(ups) != 1 else ''}?\n" + "\n".join("• " + esc(a["title"]) for a in ups[:12]), run)
