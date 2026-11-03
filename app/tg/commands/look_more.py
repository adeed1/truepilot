"""More ways to look: network details, what TrueNAS is busy with, and the diagnostics check."""
from ..registry import command
from ..ui import B, Screen, esc

BACK = [[B("📊 Status", "st"), B("« Menu", "m")]]


@command("network", "NAS network details")
async def network_cmd(call):
    d, s = await call.snap()
    n = s.get("network") or {}
    out = [f"🌐 <b>Network on {esc(d['name'])}</b>"]
    for p in n.get("ports") or []:
        addrs = ", ".join(f"{a['ip']}/{a['prefix']}" if a.get("prefix") else a["ip"] for a in p.get("addrs") or [])
        out.append(f"{'🟢' if p.get('up') else '⚪'} {esc(p['name'])} {esc(p.get('speed') or '')} {esc(addrs)}\n   MAC {esc(p.get('mac') or '-')}")
    if n.get("gateway"):
        out.append(f"Gateway {esc(n['gateway'])}")
    if n.get("dns"):
        out.append("DNS " + esc(", ".join(n["dns"])))
    return Screen("\n".join(out)[:3900], BACK)


@command("jobs", "What TrueNAS is busy with right now")
async def jobs_cmd(call):
    d = call.device()
    try:
        busy = await call.tp.hub.get(d["id"]).busy_reasons()
    except Exception as e:
        return Screen(f"⚠️ Couldn't check: {esc(str(e))[:200]}", BACK)
    text = "🟢 Nothing important is running. It is a good time to restart." if not busy else "🟡 <b>TrueNAS is busy</b>\n" + "\n".join("• " + esc(b) for b in busy)
    return Screen(text, BACK)


@command("diag", "Check that TrueNAS answers each call")
async def diag_cmd(call):
    d = call.device()
    try:
        res = await call.tp.hub.get(d["id"]).diagnostics()
    except Exception as e:
        return Screen(f"⚠️ Couldn't run the check: {esc(str(e))[:200]}", BACK)
    bad = [r for r in res if not r["ok"]]
    out = [f"🩺 <b>Diagnostics for {esc(d['name'])}</b>", f"{len(res) - len(bad)} of {len(res)} calls answered."]
    out += [f"❌ {esc(r['method'])}: {esc(str(r['text'])[:120])}" for r in bad[:10]]
    if not bad:
        out.append("🟢 Everything answered.")
    return Screen("\n".join(out)[:3900], BACK)
