"""Pause alerts for a while, and set quiet hours."""
import re
import time

from ..registry import callback, command
from ..ui import B, Say, Screen, parse_duration


def _until(text):
    return time.strftime("%a %H:%M", time.localtime(text))


def screen(call, note=""):
    c = call.eng.store.cfg()
    paused = c["pause_until"] > time.time()
    q = c["quiet"]
    lines = ["🔕 <b>Pause alerts</b>"]
    if note:
        lines.append(note)
    lines.append(f"Paused until {_until(c['pause_until'])}. It comes back on its own." if paused else "Alerts are on.")
    lines.append(f"Quiet hours: {'on, ' + q['start'] + ' to ' + q['end'] if q['on'] else 'off'}")
    return Screen("\n".join(lines), [[B("1 hour", "sn:1h"), B("8 hours", "sn:8h"), B("Until morning", "sn:am")], [B("🔔 Resume alerts", "sn:off")], [B("« Menu", "m")]])


def apply(call, what):
    st = call.eng.store
    if what == "off":
        st.patch({"pause_until": 0})
        return "🔔 Alerts are back on."
    if what == "am":
        t = call.eng.next_morning()
    else:
        sec = parse_duration(what)
        if not sec:
            raise Say("I couldn't read that. Try <code>/snooze 2h</code>, <code>/snooze 30m</code> or <code>/snooze morning</code>.")
        t = time.time() + sec
    st.patch({"pause_until": t})
    return f"🔕 Alerts paused until {_until(t)}."


@command("snooze", "Pause alerts: /snooze 2h", level="act", args="[2h|30m|morning]")
async def snooze_cmd(call):
    if not call.args:
        return screen(call)
    a = call.args[0].lower()
    return screen(call, apply(call, "am" if a in ("morning", "am") else a))


@command("unsnooze", "Turn alerts back on", level="act")
async def unsnooze_cmd(call):
    return screen(call, apply(call, "off"))


@callback("sn", "act")
async def snooze_cb(call):
    return screen(call, apply(call, call.data[0]) if call.data else "")


@command("quiet", "Quiet hours: /quiet 22:00 07:00, or /quiet off", level="act", args="<start> <end> | off")
async def quiet_cmd(call):
    st = call.eng.store
    if call.args and call.args[0].lower() == "off":
        st.patch({"quiet": {"on": False}})
        return Screen("🔔 Quiet hours are off.", [[B("« Menu", "m")]])
    if len(call.args) == 2 and all(re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", a) for a in call.args):
        a, z = (x.zfill(5) for x in call.args)
        st.patch({"quiet": {"on": True, "start": a, "end": z}})
        return Screen(f"🌙 Quiet hours are on, {a} to {z}. Serious problems (red) still come through.", [[B("« Menu", "m")]])
    q = st.cfg()["quiet"]
    return Screen(f"🌙 Quiet hours: {'on, ' + q['start'] + ' to ' + q['end'] if q['on'] else 'off'}\nChange them with <code>/quiet 22:00 07:00</code> or turn off with <code>/quiet off</code>.", [[B("« Menu", "m")]])
