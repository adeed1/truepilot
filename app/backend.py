"""Turns raw TrueNAS answers into one tidy snapshot, and runs write actions."""
import asyncio
import json
import re
import time
from urllib.parse import urlsplit, urlunsplit

from .truenas import TrueNASClient, TrueNASError, Disconnected

BUSY = {
    "pool.scrub": "a scrub is running",
    "replication.run": "a replication task is running",
    "replication.run_onetime": "a replication task is running",
    "app.upgrade": "an app upgrade is running",
    "cloudsync.sync": "a cloud sync is running",
    "rsynctask.run": "an rsync task is running",
    "update.update": "a system update is running",
}
LEVELS = ["INFO", "NOTICE", "WARNING", "ERROR", "CRITICAL", "ALERT", "EMERGENCY"]


def _g(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict):
            return default
        d = d.get(p)
        if d is None:
            return default
    return d


def _vdevs(topo):
    res = []
    for role in ("data", "cache", "log", "spare", "special", "dedup"):
        for v in (topo or {}).get(role) or []:
            kids = v.get("children") or []
            src = kids if kids else [v]
            res.append({
                "role": role, "name": v.get("name"), "type": v.get("type"), "status": v.get("status"),
                "disks": [{"name": k.get("disk") or k.get("device") or k.get("name"), "status": k.get("status")}
                          for k in src],
            })
    return res


def _pools(raw):
    out = []
    for p in raw or []:
        size, alloc = p.get("size") or 0, p.get("allocated") or 0
        scan = p.get("scan") or {}
        out.append({
            "name": p.get("name"), "status": p.get("status") or "UNKNOWN", "healthy": p.get("healthy"),
            "size": size, "allocated": alloc, "free": p.get("free") or max(size - alloc, 0),
            "pct": round(100 * alloc / size, 1) if size else 0,
            "scan": {"function": scan.get("function"), "state": scan.get("state"),
                     "pct": scan.get("percentage")} if scan.get("function") else None,
            "vdevs": _vdevs(p.get("topology")),
        })
    return out


def _smart_map(raw):
    res = {}
    for item in raw or []:
        tests = item.get("tests") or []
        if tests:
            st = str(tests[0].get("status", "")).upper()
            res[item.get("disk")] = "pass" if st == "SUCCESS" else ("running" if "PROGRESS" in st or "RUNNING" in st else "fail")
    return res


def _disks(raw, temps, smart):
    out = []
    for d in raw or []:
        n = d.get("name")
        out.append({"name": n, "model": d.get("model"), "size": d.get("size"), "type": d.get("type"),
                    "pool": d.get("pool"), "temp": (temps or {}).get(n), "smart": smart.get(n)})
    return sorted(out, key=lambda x: (x["pool"] or "~", x["name"] or ""))


def _fix_host(url, host):
    """TrueNAS lists app addresses with a placeholder host (0.0.0.0). Swap in the NAS address you saved."""
    try:
        u = urlsplit(url)
        if (u.hostname or "") in ("", "0.0.0.0", "127.0.0.1", "localhost", "::"):
            netloc = host + (f":{u.port}" if u.port else "")
            return urlunsplit((u.scheme or "http", netloc, u.path, u.query, u.fragment))
    except ValueError:
        pass
    return url


def _links(a, host):
    out = []
    for name, url in (a.get("portals") or {}).items():
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            out.append({"name": name, "url": _fix_host(url, host), "source": "truenas"})
    if not out:  # no listed address: guess from the ports the app publishes
        seen = set()
        for p in _g(a, "active_workloads", "used_ports", default=[]) or []:
            if str(p.get("protocol", "tcp")).lower() != "tcp":
                continue
            for hp in p.get("host_ports") or []:
                port = hp.get("host_port")
                if port and port not in seen:
                    seen.add(port)
                    out.append({"name": f"Port {port}", "url": f"http://{host}:{port}", "source": "guess"})
    return out[:4]


def _icon(a):
    for v in (_g(a, "metadata", "icon"), a.get("icon_url"), a.get("icon")):
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            return v
    return None


def _title(a):
    """TrueNAS gives every app installed from YAML the title "Custom App". Use the app's own name instead."""
    t, n = (_g(a, "metadata", "title") or "").strip(), a.get("name") or ""
    if t.lower() not in ("", "custom app", "custom-app"):
        return t
    if n.lower() == "truepilot":
        return "TruePilot"
    return " ".join(w.capitalize() for w in re.split(r"[-_\s]+", n) if w) or n


def _apps(raw, host=""):
    return [{"name": a.get("name"), "title": _title(a),
             "state": a.get("state") or "UNKNOWN", "version": a.get("human_version") or a.get("version"),
             "upgrade": bool(a.get("upgrade_available")), "links": _links(a, host), "icon": _icon(a) or ("/icon.svg" if (a.get("name") or "").lower() == "truepilot" else None)} for a in raw or []]


def _alerts(raw):
    items = [a for a in raw or [] if not a.get("dismissed")]
    out = [{"id": a.get("id") or a.get("uuid"), "level": a.get("level") or "INFO",
            "text": a.get("formatted") or a.get("text") or "", "when": _g(a, "datetime", "$date")} for a in items]
    return sorted(out, key=lambda x: LEVELS.index(x["level"]) if x["level"] in LEVELS else 0, reverse=True)


def _system(info, upd, rt):
    info = info or {}
    cpu = _g(rt, "cpu", "cpu", "usage")
    mem_total = _g(rt, "memory", "physical_memory_total") or info.get("physmem")
    avail = _g(rt, "memory", "physical_memory_available")
    rx = tx = None
    for iface in (rt.get("interfaces") or {}).values():
        if isinstance(iface, dict) and iface.get("link_state", True):
            rx = (rx or 0) + (iface.get("received_bytes_rate") or 0)
            tx = (tx or 0) + (iface.get("sent_bytes_rate") or 0)
    st = (upd or {}).get("status") or {}
    nv = st.get("new_version") if isinstance(st, dict) else None
    return {
        "version": info.get("version"), "hostname": info.get("hostname"), "uptime": info.get("uptime_seconds"),
        "load": info.get("loadavg"), "cores": info.get("cores"), "model": info.get("model"),
        "timezone": info.get("timezone"), "mem_total": mem_total,
        "mem_used": (mem_total - avail) if (mem_total and avail is not None) else None,
        "cpu": round(cpu, 1) if isinstance(cpu, (int, float)) else None, "net_rx": rx, "net_tx": tx,
        "update": {"available": bool(nv), "version": nv.get("version") if isinstance(nv, dict) else None},
    }


def _network(ifaces, cfg):
    ports = []
    for i in ifaces or []:
        name = i.get("name") or i.get("id") or ""
        if name.startswith(("veth", "docker", "br-", "lo")):
            continue
        st = i.get("state") or {}
        raw = st.get("aliases") or i.get("aliases") or []
        addrs = [{"ip": a.get("address"), "prefix": a.get("netmask"), "broadcast": a.get("broadcast")}
                 for a in raw if a.get("type") in (None, "INET") and a.get("address")]
        ports.append({"name": name, "up": str(st.get("link_state", "")).upper().endswith("UP"),
                      "speed": st.get("active_media_subtype") or "", "mac": st.get("link_address") or st.get("hardware_link_address") or "",
                      "addrs": addrs})
    c = cfg or {}
    return {"ports": ports, "gateway": c.get("ipv4gateway"), "dns": [c[k] for k in ("nameserver1", "nameserver2", "nameserver3") if c.get(k)],
            "hostname": c.get("hostname"), "domain": c.get("domain")}


def finish(s):
    """Adds the annunciator lamps: ok / warn / bad / unk."""
    L = {"link": {"state": "ok", "text": "Connected"}}
    pools = s.get("pools")
    if pools is None:
        L["pools"] = {"state": "unk", "text": "No data"}
    else:
        bad = [p for p in pools if p["status"] != "ONLINE" or p.get("healthy") is False]
        full = [p for p in pools if p["pct"] >= 85]
        if bad:
            L["pools"] = {"state": "bad", "text": f"{bad[0]['name']} {bad[0]['status'].lower()}"}
        elif full:
            L["pools"] = {"state": "warn", "text": f"{full[0]['name']} {full[0]['pct']:.0f}% full"}
        else:
            L["pools"] = {"state": "ok", "text": f"{len(pools)} online" if pools else "No pools"}
    disks = s.get("disks")
    if disks is None:
        L["disks"] = {"state": "unk", "text": "No data"}
    else:
        worst, state, text = 0, "ok", f"{len(disks)} disks"
        for d in disks:
            t = d.get("temp")
            hot = (70, 80) if d.get("type") == "SSD" else (50, 60)
            if d.get("smart") == "fail":
                state, text = "bad", f"{d['name']} failed a test"
                break
            if isinstance(t, (int, float)):
                worst = max(worst, t)
                if t >= hot[1]:
                    state, text = "bad", f"{d['name']} at {t:.0f}°C"
                elif t >= hot[0] and state != "bad":
                    state, text = "warn", f"{d['name']} at {t:.0f}°C"
        if state == "ok" and worst:
            text = f"Hottest {worst:.0f}°C"
        L["disks"] = {"state": state, "text": text}
    apps = s.get("apps")
    if apps is None:
        L["apps"] = {"state": "unk", "text": "No data"}
    else:
        crashed = [a for a in apps if a["state"] == "CRASHED"]
        deploying = [a for a in apps if a["state"] == "DEPLOYING"]
        running = len([a for a in apps if a["state"] == "RUNNING"])
        ups = len([a for a in apps if a["upgrade"]])
        if crashed:
            L["apps"] = {"state": "bad", "text": f"{crashed[0]['title']} crashed"}
        elif deploying:
            L["apps"] = {"state": "warn", "text": f"{deploying[0]['title']} starting"}
        else:
            L["apps"] = {"state": "ok", "text": f"{running} running" + (f", {ups} to update" if ups else "")}
    alerts = s.get("alerts")
    if alerts is None:
        L["alerts"] = {"state": "unk", "text": "No data"}
    else:
        lv = [LEVELS.index(a["level"]) if a["level"] in LEVELS else 0 for a in alerts]
        n_bad, n_warn = len([x for x in lv if x >= 3]), len([x for x in lv if x == 2])
        if n_bad:
            L["alerts"] = {"state": "bad", "text": f"{n_bad} need attention"}
        elif n_warn:
            L["alerts"] = {"state": "warn", "text": f"{n_warn} warning" + ("s" if n_warn > 1 else "")}
        else:
            L["alerts"] = {"state": "ok", "text": f"{len(alerts)} notices" if alerts else "All clear"}
    s["lamps"] = L
    return s


def log_line(e):
    v = e.get("data") if e.get("data") is not None else (e.get("line") if e.get("line") is not None else json.dumps(e))
    return str(v).rstrip("\r\n")


def offline(error):
    return {"ok": False, "error": error, "at": time.time(),
            "lamps": {"link": {"state": "bad", "text": "Offline"}}}


async def collect(c: TrueNASClient):
    try:
        await c.connect()
    except TrueNASError as e:
        return offline(str(e))
    errors = {}

    async def safe(key, coro):
        try:
            return await coro
        except Exception as e:  # one failing method must not blank the dashboard
            errors[key] = str(e)
            return None

    info, pools, disks, alerts, apps, upd, smart, ifaces, netcfg = await asyncio.gather(
        safe("system", c.call("system.info")), safe("pools", c.call("pool.query")),
        safe("disks", c.call("disk.query")), safe("alerts", c.call("alert.list")),
        safe("apps", c.call("app.query")), safe("update", c.call("update.status")),
        safe("smart", c.call("smart.test.results")), safe("network", c.call("interface.query")),
        safe("netconfig", c.call("network.configuration.config")))
    names = [d.get("name") for d in (disks or []) if d.get("name")]
    temps = await safe("temps", c.call("disk.temperatures", [names])) if names else {}
    rt = c.realtime if time.time() - c.realtime_at < 30 else {}
    snap = {
        "ok": True, "at": time.time(), "errors": errors, "system": _system(info, upd, rt),
        "pools": _pools(pools) if pools is not None else None,
        "disks": _disks(disks, temps, _smart_map(smart)) if disks is not None else None,
        "apps": _apps(apps, c.host) if apps is not None else None,
        "alerts": _alerts(alerts) if alerts is not None else None,
        "network": _network(ifaces, netcfg) if (ifaces is not None or netcfg is not None) else None,
    }
    return finish(snap)


DIAG_CALLS = ["system.info", "pool.query", "disk.query", "disk.temperatures", "alert.list", "app.query",
              "update.status", "smart.test.results", "interface.query", "network.configuration.config", "core.get_jobs", "cronjob.query"]


class TrueNASBackend:
    kind = "truenas"

    def __init__(self, dev, read_key, write_key=""):
        self.dev = dev
        self.r = TrueNASClient(dev["host"], dev["port"], dev["username"], read_key, bool(dev["verify_tls"]))
        self.w = TrueNASClient(dev["host"], dev["port"], dev.get("wuser") or dev["username"], write_key,
                               bool(dev["verify_tls"])) if write_key else None

    async def snapshot(self):
        return await collect(self.r)

    async def busy_reasons(self):
        reasons = []
        try:
            for j in await self.r.call("core.get_jobs", [[["state", "=", "RUNNING"]]]):
                why = BUSY.get(j.get("method"))
                if why and why not in reasons:
                    reasons.append(why)
            for p in await self.r.call("pool.query") or []:
                sc = p.get("scan") or {}
                if sc.get("state") == "SCANNING" and "a scrub is running" not in reasons:
                    reasons.append(f"pool {p.get('name')} is {'resilvering' if sc.get('function') == 'RESILVER' else 'scrubbing'}")
        except TrueNASError as e:
            reasons.append(f"could not check running tasks ({e})")
        return reasons

    def _need_write(self):
        if not self.w:
            raise TrueNASError("No write key saved for this device")
        return self.w

    async def app_action(self, name, action):
        w = self._need_write()
        if action == "start":
            await w.job("app.start", [name], 600)
            return f"{name} started"
        if action == "stop":
            await w.job("app.stop", [name], 600)
            return f"{name} stopped"
        if action == "restart":
            await w.job("app.stop", [name], 600)
            await w.job("app.start", [name], 600)
            return f"{name} restarted"
        if action == "upgrade":
            await w.job("app.upgrade", [name, {"app_version": "latest", "snapshot_hostpaths": True}], 1800)
            return f"{name} upgraded"
        raise TrueNASError(f"Unknown action {action}")

    async def host_action(self, action):
        w = self._need_write()
        method = {"restart": "system.reboot", "shutdown": "system.shutdown"}[action]
        try:
            await w.call(method, [f"NAS Pilot: {action} requested"], 20)
        except Disconnected:
            pass  # the NAS went away while answering, which is expected
        return f"{action.capitalize()} command sent"

    async def app_logs(self, name, container="", lines=200):
        ids = await self.r.call("app.container_ids", [name]) or {}
        containers = [{"id": k, "name": ((v.get("service_name") or v.get("image") or k) if isinstance(v, dict) else k),
                       "state": (v.get("state") if isinstance(v, dict) else None)} for k, v in ids.items()]
        if not containers:
            return {"lines": [], "containers": [], "container": "", "note": "TrueNAS reports no containers for this app. Is it running?", "debug": []}
        cid = container if any(c["id"] == container for c in containers) else containers[0]["id"]
        event = "app.container_log_follow: " + json.dumps({"app_name": name, "container_id": cid, "tail_lines": lines})
        evs = await self.r.collect_events(event, 2.5)
        out = [log_line(e) for e in evs]
        note = "" if out else "TrueNAS sent no log lines. The app may be quiet, or this part of the API differs on your version."
        return {"lines": out, "containers": containers, "container": cid, "note": note, "debug": [] if out else evs[:2]}

    async def cron_create(self, payload):
        return (await self._need_write().call("cronjob.create", [payload]))["id"]

    async def cron_update(self, cid, patch):
        await self._need_write().call("cronjob.update", [cid, patch])

    async def cron_delete(self, cid):
        await self._need_write().call("cronjob.delete", [cid])

    async def wake(self):
        return None

    async def diagnostics(self):
        res = []
        try:
            await self.r.connect()
        except TrueNASError as e:
            return [{"method": "connect", "ok": False, "text": str(e)}]
        names = []
        for m in DIAG_CALLS:
            params = [[n for n in names]] if m == "disk.temperatures" else (
                [[["state", "=", "RUNNING"]]] if m == "core.get_jobs" else [])
            try:
                out = await self.r.call(m, params, 20)
                if m == "disk.query":
                    names = [d.get("name") for d in out or []]
                import json as _j
                res.append({"method": m, "ok": True, "text": _j.dumps(out, default=str)[:300]})
            except Exception as e:
                res.append({"method": m, "ok": False, "text": str(e)})
        return res

    async def close(self):
        await self.r.close()
        if self.w:
            await self.w.close()
