"""Demo device: fake TrueNAS data so the dashboard can be tried with no NAS. Actions really change the demo state."""
import asyncio
import random
import time

from .backend import finish, offline

TIB = 1024 ** 4


class DemoBackend:
    kind = "demo"

    def __init__(self, name="Demo NAS"):
        self.name = name
        self.boot = time.time() - 86400 * 12 - 3600 * 4
        self.down_until = 0.0
        self.is_off = False
        self.cpu = 14.0
        self.cron = {}
        self._cid = 100
        self.apps = [
            {"name": "plex", "title": "Plex", "state": "RUNNING", "version": "1.41.4", "upgrade": False, "icon": "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2048%2048%22%3E%3Crect%20width%3D%2248%22%20height%3D%2248%22%20rx%3D%2210%22%20fill%3D%22%23282a2d%22%2F%3E%3Cpath%20d%3D%22M14%208h10l10%2016-10%2016H14l10-16z%22%20fill%3D%22%23e5a00d%22%2F%3E%3C%2Fsvg%3E", "links": [{"name": "Web UI", "url": "http://192.168.1.50:32400/web", "source": "truenas"}]},
            {"name": "home-assistant", "title": "Home Assistant", "state": "RUNNING", "version": "2025.10.2", "upgrade": True, "icon": "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2048%2048%22%3E%3Crect%20width%3D%2248%22%20height%3D%2248%22%20rx%3D%2210%22%20fill%3D%22%2341bdf5%22%2F%3E%3Cpath%20d%3D%22M24%208L6%2024h5v16h26V24h5z%22%20fill%3D%22%23fff%22%2F%3E%3C%2Fsvg%3E", "links": [{"name": "Web UI", "url": "http://192.168.1.50:8123", "source": "truenas"}]},
            {"name": "nextcloud", "title": "Nextcloud", "state": "RUNNING", "version": "31.0.2", "upgrade": False, "links": [{"name": "Web UI", "url": "https://192.168.1.50:30027", "source": "truenas"}, {"name": "Admin", "url": "https://192.168.1.50:30027/settings/admin", "source": "truenas"}]},
            {"name": "pi-hole", "title": "Pi-hole", "state": "RUNNING", "version": "2025.08.0", "upgrade": True, "icon": "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2048%2048%22%3E%3Crect%20width%3D%2248%22%20height%3D%2248%22%20rx%3D%2210%22%20fill%3D%22%2396060c%22%2F%3E%3Ccircle%20cx%3D%2224%22%20cy%3D%2224%22%20r%3D%2212%22%20fill%3D%22%23fff%22%2F%3E%3Ccircle%20cx%3D%2224%22%20cy%3D%2224%22%20r%3D%226%22%20fill%3D%22%2396060c%22%2F%3E%3C%2Fsvg%3E", "links": [{"name": "Port 8081", "url": "http://192.168.1.50:8081/admin", "source": "guess"}]},
            {"name": "syncthing", "title": "Syncthing", "state": "STOPPED", "version": "1.29.6", "upgrade": False, "links": []},
        ]

    async def snapshot(self):
        if self.is_off or time.time() < self.down_until:
            return offline(f"Cannot reach {self.name} (connection timed out)")
        self.cpu = min(85, max(4, self.cpu + random.uniform(-4, 4)))
        up = time.time() - self.boot
        rx, tx = random.randint(40_000, 900_000), random.randint(20_000, 400_000)
        disks = [
            {"name": f"sd{c}", "model": "WDC WD60EFPX-68C5ZN0", "size": 6_001_175_126_016, "type": "HDD",
             "pool": "tank", "temp": 36 + i * 2 + random.randint(0, 1), "smart": "pass"}
            for i, c in enumerate("abcdef")
        ] + [
            {"name": "nvme0n1", "model": "Samsung SSD 980 1TB", "size": 1_000_204_886_016, "type": "SSD",
             "pool": "fast", "temp": 41 + random.randint(0, 2), "smart": "pass"},
            {"name": "nvme1n1", "model": "Samsung SSD 980 1TB", "size": 1_000_204_886_016, "type": "SSD",
             "pool": "fast", "temp": 43 + random.randint(0, 2), "smart": "pass"},
        ]
        snap = {
            "ok": True, "at": time.time(), "errors": {},
            "system": {
                "version": "25.10.1", "hostname": "demo-nas", "uptime": up, "load": [0.42, 0.51, 0.47],
                "cores": 8, "model": "Intel N100", "timezone": "Australia/Perth",
                "mem_total": 32 * 1024 ** 3, "mem_used": int(11.4 * 1024 ** 3), "cpu": round(self.cpu, 1),
                "net_rx": rx, "net_tx": tx, "update": {"available": False, "version": None},
            },
            "pools": [
                {"name": "tank", "status": "ONLINE", "healthy": True, "size": int(21.8 * TIB),
                 "allocated": int(13.6 * TIB), "free": int(8.2 * TIB), "pct": 62.4,
                 "scan": {"function": "SCRUB", "state": "FINISHED", "pct": 100},
                 "vdevs": [{"role": "data", "name": "raidz2-0", "type": "RAIDZ2", "status": "ONLINE",
                            "disks": [{"name": f"sd{c}", "status": "ONLINE"} for c in "abcdef"]}]},
                {"name": "fast", "status": "ONLINE", "healthy": True, "size": int(0.9 * TIB),
                 "allocated": int(0.78 * TIB), "free": int(0.12 * TIB), "pct": 86.7, "scan": None,
                 "vdevs": [{"role": "data", "name": "mirror-0", "type": "MIRROR", "status": "ONLINE",
                            "disks": [{"name": "nvme0n1", "status": "ONLINE"}, {"name": "nvme1n1", "status": "ONLINE"}]}]},
            ],
            "disks": disks,
            "apps": [dict(a) for a in self.apps],
            "network": {"ports": [{"name": "eno1", "up": True, "speed": "1000Base-T", "mac": "00:11:22:33:44:55",
                                   "addrs": [{"ip": "192.168.1.50", "prefix": 24, "broadcast": "192.168.1.255"}]},
                                  {"name": "eno2", "up": False, "speed": "", "mac": "00:11:22:33:44:56", "addrs": []}],
                        "gateway": "192.168.1.1", "dns": ["192.168.1.1", "1.1.1.1"], "hostname": "demo-nas", "domain": "local"},
            "alerts": [
                {"id": "a1", "level": "WARNING", "text": "Pool fast is 87% full. Free some space soon.", "when": int((time.time() - 3600) * 1000)},
                {"id": "a2", "level": "NOTICE", "text": "Scrub of pool tank finished with 0 errors.", "when": int((time.time() - 86400 * 2) * 1000)},
            ],
        }
        return finish(snap)

    async def busy_reasons(self):
        return []

    async def app_action(self, name, action):
        a = next((x for x in self.apps if x["name"] == name), None)
        if not a:
            raise RuntimeError(f"No app called {name}")
        a["state"] = "DEPLOYING"
        await asyncio.sleep(2.5 if action != "upgrade" else 5)
        if action == "stop":
            a["state"] = "STOPPED"
        else:
            a["state"] = "RUNNING"
        if action == "upgrade":
            a["upgrade"] = False
        return f"{a['title']} {({'start': 'started', 'stop': 'stopped', 'restart': 'restarted', 'upgrade': 'upgraded'})[action]}"

    async def host_action(self, action):
        if action == "restart":
            self.down_until = time.time() + 12
        else:
            self.is_off = True
        return f"{action.capitalize()} command sent"

    async def app_logs(self, name, container="", lines=200):
        base = time.time()
        out = [f"2026-10-26T{(int(base) // 3600 % 24):02d}:{(int(base) // 60 % 60):02d}:{i:02d}Z INFO  {name}: " + m for i, m in enumerate(
            ["starting up", "listening on port 8080", "loaded configuration", "connected to storage", "health check ok", "health check ok", "WARN  slow response from upstream (812 ms)", "health check ok"])]
        return {"lines": out[-lines:], "containers": [{"id": "demo1", "name": name, "state": "running"}, {"id": "demo2", "name": name + "-db", "state": "running"}],
                "container": container or "demo1", "note": "", "debug": []}

    async def cron_create(self, payload):
        self._cid += 1
        self.cron[self._cid] = payload
        return self._cid

    async def cron_update(self, cid, patch):
        self.cron.get(cid, {}).update(patch)

    async def cron_delete(self, cid):
        self.cron.pop(cid, None)

    async def wake(self):
        self.is_off = False
        self.down_until = time.time() + 6
        self.boot = time.time() + 6

    async def diagnostics(self):
        return [{"method": "demo", "ok": True, "text": "Demo device: nothing to diagnose"}]

    async def close(self):
        pass
