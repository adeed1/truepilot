"""The home panel, help, and a few small things about the bot itself."""
from ..registry import COMMANDS, callback, command
from ..ui import B, Say, Screen, esc


async def menu_screen(call):
    try:
        d = call.device()
        s = await call.tp.hub.snapshot(d["id"])
        if s.get("ok"):
            apps = s.get("apps") or []
            head = f"🖥 <b>{esc(d['name'])}</b>: 🟢 online\nApps: {len([a for a in apps if a['state'] == 'RUNNING'])} of {len(apps)} running"
        else:
            head = f"🖥 <b>{esc(d['name'])}</b>: 🔴 not answering"
    except Say as e:
        head = e.text
    except Exception:
        head = "🖥 NAS status unavailable"
    cfg = call.eng.store.cfg()
    if cfg["pause_until"] > __import__("time").time():
        head += "\n🔕 Alerts are paused"
    return Screen("🚀 <b>TruePilot</b>\n" + head, [
        [B("📊 Status", "st"), B("📦 Apps", "ap:0:a")],
        [B("💽 Storage", "sto"), B("💻 PCs", "pc")],
        [B("⏰ Schedules", "sc"), B("⬆️ Updates", "up")],
        [B("⏻ Power", "pw"), B("🌐 Web Apps", "wa")],
        [B("🔕 Snooze", "sn"), B("❓ Help", "hp")],
    ])


@command("menu", "Open the home panel")
async def menu_cmd(call):
    return await menu_screen(call)


@callback("m")
async def menu_cb(call):
    return await menu_screen(call)


@command("start", "Home panel, or start an app: /start plex", menu=False, args="[app]")
async def start_cmd(call):
    if call.args:
        from .apps import app_command
        return await app_command(call, "start")
    return await menu_screen(call)


@command("help", "What I can do")
async def help_cmd(call):
    return help_screen(call)


@callback("hp")
async def help_cb(call):
    return help_screen(call)


def help_screen(call):
    powerful = call.eng.store.cfg()["parts"]["powerful"]
    groups = [("Look (safe)", "safe"), ("Do (one tap)", "act")] + ([("Powerful", "power")] if powerful else [])
    out = ["❓ <b>What I can do</b>", "Tap <b>Menu</b> next to the typing box for the list. You never have to type."]
    for title, level in groups:
        rows = sorted((c for c in COMMANDS.values() if c.level == level), key=lambda c: c.name)
        if rows:
            out.append(f"\n<b>{title}</b>")
            out += [f"/{c.name}{(' ' + esc(c.args)) if c.args else ''} {esc(c.desc)}" for c in rows]
    return Screen("\n".join(out)[:3900], [[B("« Menu", "m")]])


@command("test", "Check that Telegram works")
async def test_cmd(call):
    return Screen("✅ <b>Telegram works.</b> This message came from TruePilot on " + esc(call.tp.computer) + ".", [[B("« Menu", "m")]])


@command("whoami", "Which chat I'm linked to")
async def whoami_cmd(call):
    b = call.bot
    return Screen(f"👤 Linked chat: <b>{esc(b['chat_name'] or '?')}</b> (id {b['chat_id']})\nBot: @{esc(b['username'])} · {esc(b['label'])}\nRunning on: {esc(call.tp.computer)}", [[B("« Menu", "m")]])
