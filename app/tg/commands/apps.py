"""Apps: list, open, start, stop, restart, logs, favourites."""
import asyncio

from ..registry import callback, command
from ..ui import B, Say, Screen, esc

PAGE = 14
LAMP = {"RUNNING": "🟢", "STOPPED": "⚪", "DEPLOYING": "🟡", "CRASHED": "🔴"}
WORD = {"RUNNING": "Running", "STOPPED": "Stopped", "DEPLOYING": "Starting", "CRASHED": "Crashed"}


def favs(call, did):
    return {r["app"] for r in call.tp.db.q("SELECT app FROM app_favs WHERE device_id=?", (did,))}


def find(apps, text):
    """Exact name or title first, then a single starts-with, then a single contains. Returns a list (1 = found)."""
    t = (text or "").strip().lower()
    if not t:
        return []
    exact = [a for a in apps if t in (a["name"].lower(), a["title"].lower())]
    if exact:
        return exact[:1]
    for test in (lambda a: a["name"].lower().startswith(t) or a["title"].lower().startswith(t), lambda a: t in a["name"].lower() or t in a["title"].lower()):
        hits = [a for a in apps if test(a)]
        if hits:
            return hits
    return []


async def apps_screen(call, page=0, mode="a", query=""):
    d, s = await call.snap()
    apps, fv = s.get("apps") or [], favs(call, d["id"])
    if mode == "f":
        apps = [a for a in apps if a["name"] in fv]
    if query:
        q = query.lower()
        apps = [a for a in apps if q in a["name"].lower() or q in a["title"].lower()]
    apps = sorted(apps, key=lambda a: (a["name"] not in fv, a["title"].casefold()))
    total = len(apps)
    chunk = apps[page * PAGE:(page + 1) * PAGE]
    rows = [[B(f"{'⭐ ' if a['name'] in fv else ''}{LAMP.get(a['state'], '⚪')} {a['title']}{' ⬆️' if a.get('upgrade') else ''}", f"a:{a['name']}")] for a in chunk]
    nav = []
    if page > 0:
        nav.append(B("‹ Back", f"ap:{page - 1}:{mode}"))
    if (page + 1) * PAGE < total:
        nav.append(B("More ›", f"ap:{page + 1}:{mode}"))
    if nav:
        rows.append(nav)
    rows.append([B("📦 All apps" if mode == "f" else "⭐ Favourites", "ap:0:a" if mode == "f" else "ap:0:f"), B("« Menu", "m")])
    run = len([a for a in s.get("apps") or [] if a["state"] == "RUNNING"])
    title = "Search results" if query else ("Favourite apps" if mode == "f" else "Apps")
    note = "" if total else ("\nNo apps found." if (query or mode == "f") else "\nNo apps on this NAS.")
    return Screen(f"📦 <b>{title}</b> on {esc(d['name'])}\n{run} of {len(s.get('apps') or [])} running{note}", rows)


async def app_card(call, name, note=""):
    d, s = await call.snap()
    a = next((x for x in s.get("apps") or [] if x["name"] == name), None)
    if not a:
        raise Say(f"There is no app called <b>{esc(name)}</b> on {esc(d['name'])}.", "ap:0:a")
    fv = a["name"] in favs(call, d["id"])
    custom = call.tp.db.one("SELECT url FROM app_links WHERE device_id=? AND app=?", (d["id"], name))
    links = ([{"name": "My link", "url": custom["url"]}] if custom else []) + (a.get("links") or [])
    lines = [f"{LAMP.get(a['state'], '⚪')} <b>{esc(a['title'])}</b>", f"{WORD.get(a['state'], esc(a['state'].lower()))}" + (f" · version {esc(str(a['version']))}" if a.get("version") else "")]
    if a.get("upgrade"):
        lines.append("⬆️ An update is waiting")
    if note:
        lines.insert(1, note)
    rows = []
    if a["state"] == "RUNNING" and links:
        rows.append([B("🔗 Open" if len(links) == 1 else f"🔗 {l['name']}", url=l["url"]) for l in links[:3]])
    if a["state"] in ("STOPPED", "CRASHED"):
        rows.append([B("▶ Start", f"x:start:{name}"), B("📜 Logs", f"lg:{name}")])
    else:
        rows.append([B("🔄 Restart", f"x:restart:{name}"), B("⏹ Stop", f"x:stop:{name}")])
        rows.append([B("📜 Logs", f"lg:{name}"), B("⭐ Unfavourite" if fv else "☆ Favourite", f"fv:{name}")])
    rows.append([B("« Apps", "ap:0:a"), B("« Menu", "m")])
    return Screen("\n".join(lines), rows)


async def do_action(call, action, name):
    if action not in ("start", "stop", "restart"):
        raise Say("I don't know that action.")
    d, s = await call.snap()
    call.tp.need_write(call.tp.hub.row(d["id"]))
    a = next((x for x in s.get("apps") or [] if x["name"] == name), None)
    if not a:
        raise Say(f"There is no app called <b>{esc(name)}</b>.", "ap:0:a")
    tid = call.tp.start_app_task(d["id"], a["name"], action, "Telegram")
    verb = {"start": "Starting", "stop": "Stopping", "restart": "Restarting"}[action]

    async def then():
        for _ in range(300):
            t = call.tp.tasks.get(tid)
            if not t or t["status"] != "running":
                break
            await asyncio.sleep(1)
        t = call.tp.tasks.get(tid) or {}
        if t.get("status") == "failed":
            return Screen(f"❌ <b>{esc(a['title'])}</b>: {esc(str(t.get('message') or 'it did not work'))[:300]}", [[B("« Back to app", f"a:{name}"), B("« Menu", "m")]])
        if t.get("status") == "running":
            return Screen(f"⏳ <b>{esc(a['title'])}</b> is still working. Check again in a moment.", [[B("🔄 Check", f"a:{name}"), B("« Menu", "m")]])
        return await app_card(call, name, "✅ Done")

    return Screen(f"⏳ {verb} <b>{esc(a['title'])}</b>…", [[B("« Apps", "ap:0:a")]], then)


async def app_command(call, action):
    """/start plex, /stop plex, /restart plex."""
    if not call.args:
        return await apps_screen(call)
    d, s = await call.snap()
    hits = find(s.get("apps") or [], call.text)
    if not hits:
        raise Say(f"I couldn't find an app called <b>{esc(call.text)}</b>. Try /apps.", "ap:0:a")
    if len(hits) > 1:
        return Screen(f"Did you mean one of these? ({esc(action)})", [[B(h["title"], f"x:{action}:{h['name']}")] for h in hits[:8]] + [[B("« Menu", "m")]])
    return await do_action(call, action, hits[0]["name"])


@command("apps", "List your apps")
async def apps_cmd(call):
    return await apps_screen(call)


@callback("ap")
async def apps_cb(call):
    page = int(call.data[0]) if call.data and call.data[0].isdigit() else 0
    return await apps_screen(call, page, call.data[1] if len(call.data) > 1 else "a")


@command("favs", "Your favourite apps")
async def favs_cmd(call):
    return await apps_screen(call, 0, "f")


@command("search", "Find an app by name", args="<text>")
async def search_cmd(call):
    if not call.args:
        raise Say("Tell me what to look for, like <code>/search plex</code>.")
    return await apps_screen(call, 0, "a", call.text)


@command("app", "Open one app's card", args="<name>")
async def app_cmd(call):
    if not call.args:
        return await apps_screen(call)
    d, s = await call.snap()
    hits = find(s.get("apps") or [], call.text)
    if not hits:
        raise Say(f"I couldn't find an app called <b>{esc(call.text)}</b>. Try /apps.", "ap:0:a")
    if len(hits) > 1:
        return Screen("Did you mean one of these?", [[B(h["title"], f"a:{h['name']}")] for h in hits[:8]] + [[B("« Menu", "m")]])
    return await app_card(call, hits[0]["name"])


@callback("a")
async def app_cb(call):
    return await app_card(call, call.data[0])


@command("restart", "Restart an app", level="act", args="<app>")
async def restart_cmd(call):
    return await app_command(call, "restart")


@command("stop", "Stop an app", level="act", args="<app>")
async def stop_cmd(call):
    return await app_command(call, "stop")


@callback("x", "act")
async def act_cb(call):
    return await do_action(call, call.data[0], call.data[1])


@callback("fv", "act")
async def fav_cb(call):
    d, s = await call.snap()
    name = call.data[0]
    if name in favs(call, d["id"]):
        call.tp.db.x("DELETE FROM app_favs WHERE device_id=? AND app=?", (d["id"], name))
    else:
        call.tp.db.x("INSERT OR IGNORE INTO app_favs(device_id,app) VALUES(?,?)", (d["id"], name))
    return await app_card(call, name)


@command("logs", "Last lines of an app's log", args="<app>")
async def logs_cmd(call):
    if not call.args:
        return await apps_screen(call)
    d, s = await call.snap()
    hits = find(s.get("apps") or [], call.text)
    if not hits:
        raise Say(f"I couldn't find an app called <b>{esc(call.text)}</b>.", "ap:0:a")
    if len(hits) > 1:
        return Screen("Which app?", [[B(h["title"], f"lg:{h['name']}")] for h in hits[:8]] + [[B("« Menu", "m")]])
    return await logs_screen(call, hits[0]["name"])


@callback("lg")
async def logs_cb(call):
    return await logs_screen(call, call.data[0])


async def logs_screen(call, name):
    d = call.device()
    try:
        r = await call.tp.hub.get(d["id"]).app_logs(name, "", 40)
    except Exception as e:
        raise Say(f"Couldn't read the logs: {esc(str(e))[:200]}", f"a:{name}")
    lines = [str(x)[:300] for x in r.get("lines") or []][-30:]
    body = "\n".join(lines)
    while len(body) > 3000:
        lines = lines[1:]
        body = "\n".join(lines)
    text = f"📜 <b>{esc(name)}</b> log (last {len(lines)} lines)\n" + (f"<pre>{esc(body)}</pre>" if lines else f"<i>{esc(r.get('note') or 'No log lines.')}</i>")
    return Screen(text, [[B("🔄 Refresh", f"lg:{name}"), B("« App", f"a:{name}")]])
