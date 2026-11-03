"""Look at the NAS: status, storage, disks, alerts, updates."""
from ..registry import callback, command
from ..ui import B, LAMP, Screen, esc, size, span


def _row(l):
    return LAMP.get((l or {}).get("state"), "⚪")


async def status_screen(call):
    d, s = await call.snap()
    y, L = s.get("system") or {}, s.get("lamps") or {}
    apps = s.get("apps") or []
    run, stopped = [a for a in apps if a["state"] == "RUNNING"], [a for a in apps if a["state"] == "STOPPED"]
    crashed = [a for a in apps if a["state"] == "CRASHED"]
    ups = [a for a in apps if a.get("upgrade")]
    mt, mu = y.get("mem_total"), y.get("mem_used")
    out = [f"🖥 <b>{esc(d['name'])}</b>: 🟢 online · up {span(y.get('uptime'))}"]
    if y.get("cpu") is not None or mt:
        out.append(f"CPU {y['cpu']:.0f}%" + (f" · Memory {100 * mu / mt:.0f}%" if mt and mu is not None else ""))
    pools = s.get("pools") or []
    out.append(f"{_row(L.get('pools'))} Storage: " + (", ".join(f"{esc(p['name'])} {p['pct']:.0f}% used ({esc(str(p['status']).lower())})" for p in pools) or "no pools"))
    out.append(f"{_row(L.get('disks'))} Disks: {esc((L.get('disks') or {}).get('text', ''))}")
    line = f"{_row(L.get('apps'))} Apps: {len(run)} running"
    if stopped:
        line += f", {len(stopped)} stopped ({esc(', '.join(a['title'] for a in stopped[:4]))})"
    if crashed:
        line += f", {len(crashed)} crashed ({esc(', '.join(a['title'] for a in crashed[:4]))})"
    if ups:
        line += f", {len(ups)} to update"
    out.append(line)
    out.append(f"{_row(L.get('alerts'))} Alerts: {esc((L.get('alerts') or {}).get('text', ''))}")
    if y.get("update", {}).get("available"):
        out.append(f"⬆️ TrueNAS update available ({esc(str(y['update'].get('version') or ''))})")
    return Screen("\n".join(out), [[B("🔄 Refresh", "st"), B("📦 Apps", "ap:0:a")], [B("💽 Storage", "sto"), B("🚨 Alerts", "al")], [B("« Menu", "m")]])


@command("status", "NAS health at a glance")
async def status_cmd(call):
    return await status_screen(call)


@callback("st")
async def status_cb(call):
    return await status_screen(call)


@command("storage", "Pools: health, space used")
async def storage_cmd(call):
    return await storage_screen(call)


@callback("sto")
async def storage_cb(call):
    return await storage_screen(call)


async def storage_screen(call):
    d, s = await call.snap()
    out = [f"💽 <b>Storage on {esc(d['name'])}</b>"]
    for p in s.get("pools") or []:
        ok = p["status"] == "ONLINE" and p.get("healthy") is not False
        lamp = "🟢" if ok and p["pct"] < 85 else ("🔴" if not ok else "🟠")
        out.append(f"{lamp} <b>{esc(p['name'])}</b> {esc(str(p['status']).lower())}: {p['pct']:.0f}% used, {size(p.get('free'))} free of {size(p.get('size'))}")
        sc = p.get("scan")
        if sc and sc.get("state") == "SCANNING":
            out.append(f"   {esc(str(sc.get('function') or 'scan').lower())} running" + (f", {sc['pct']:.0f}%" if sc.get("pct") is not None else ""))
    if len(out) == 1:
        out.append("No pools found.")
    return Screen("\n".join(out), [[B("💿 Disks", "dk"), B("📊 Status", "st")], [B("« Menu", "m")]])


@command("disks", "Every disk: temperature and last test")
async def disks_cmd(call):
    return await disks_screen(call)


@callback("dk")
async def disks_cb(call):
    return await disks_screen(call)


async def disks_screen(call):
    d, s = await call.snap()
    out = [f"💿 <b>Disks on {esc(d['name'])}</b>"]
    for k in s.get("disks") or []:
        t, sm = k.get("temp"), k.get("smart")
        lamp = "🔴" if sm == "fail" else ("🟢" if sm == "pass" or sm is None else "🟡")
        out.append(f"{lamp} {esc(k['name'])} · {size(k.get('size'))} {esc(k.get('type') or '')} · " + (f"{t:.0f}°C" if isinstance(t, (int, float)) else "no temperature") + (f" · test {esc(sm)}" if sm else "") + (f" · {esc(k['pool'])}" if k.get("pool") else ""))
    return Screen("\n".join(out)[:3900], [[B("💽 Storage", "sto"), B("« Menu", "m")]])


@command("alerts", "TrueNAS's own alerts")
async def alerts_cmd(call):
    return await alerts_screen(call)


@callback("al")
async def alerts_cb(call):
    return await alerts_screen(call)


async def alerts_screen(call):
    d, s = await call.snap()
    al = s.get("alerts") or []
    if not al:
        return Screen(f"🟢 <b>{esc(d['name'])}</b> has no alerts.", [[B("📊 Status", "st"), B("« Menu", "m")]])
    icon = {"INFO": "🔵", "NOTICE": "🔵", "WARNING": "🟠"}
    out = [f"🚨 <b>Alerts on {esc(d['name'])}</b> ({len(al)})"] + [f"{icon.get(a['level'], '🔴')} {esc((a.get('text') or '')[:300])}" for a in al[:10]]
    if len(al) > 10:
        out.append(f"…and {len(al) - 10} more. Open TrueNAS to see them all.")
    return Screen("\n".join(out)[:3900], [[B("📊 Status", "st"), B("« Menu", "m")]])


@command("updates", "Apps and TrueNAS with updates waiting")
async def updates_cmd(call):
    return await updates_screen(call)


@callback("up")
async def updates_cb(call):
    return await updates_screen(call)


async def updates_screen(call):
    d, s = await call.snap()
    ups = [a for a in s.get("apps") or [] if a.get("upgrade")]
    out = [f"⬆️ <b>Updates on {esc(d['name'])}</b>"]
    out += [f"• {esc(a['title'])} ({esc(str(a.get('version') or ''))})" for a in ups] or ["All apps are up to date."]
    u = (s.get("system") or {}).get("update") or {}
    if u.get("available"):
        out.append(f"• TrueNAS itself ({esc(str(u.get('version') or ''))})")
    out.append("\nTap an app to update it. TruePilot asks Approve first." if ups else "")
    rows = [[B(f"⬆️ {a['title']}", f"ug:{a['name']}")] for a in ups[:10]]
    if len(ups) > 1:
        rows.append([B("⬆️ Update all", "uga")])
    return Screen("\n".join(out).strip(), rows + [[B("📦 Apps", "ap:0:a"), B("« Menu", "m")]])
