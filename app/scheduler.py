"""Schedules. App jobs run inside NAS Pilot; host jobs (restart / shutdown) become native TrueNAS cron jobs
so they still fire if NAS Pilot is stopped."""
import asyncio
import logging
import time
from datetime import datetime

from croniter import croniter

log = logging.getLogger("naspilot.scheduler")

APP_ACTIONS = {"restart_app": "restart", "start_app": "start", "stop_app": "stop"}
HOST_ACTIONS = {"restart_host": "restart", "shutdown_host": "shutdown"}
WAKE_ACTIONS = {"wake_device"}

# Skip the job if one of these long tasks is running at that moment.
GUARD = ("midclt call core.get_jobs '[[\"state\",\"=\",\"RUNNING\"]]' | grep -Eq "
         "'\"method\": *\"(pool.scrub|replication.run|replication.run_onetime|app.upgrade|cloudsync.sync|rsynctask.run|update.update)\"'")


def valid_cron(expr: str) -> bool:
    return len(expr.split()) == 5 and "%" not in expr and croniter.is_valid(expr)


def next_run(expr: str, count: int = 1):
    try:
        it = croniter(expr, datetime.now().astimezone())
        runs = [it.get_next(datetime).timestamp() for _ in range(count)]
        return runs[0] if count == 1 else runs
    except Exception:
        return None if count == 1 else []


def host_command(action: str) -> str:
    verb = "restart" if action == "restart_host" else "shutdown"
    method = "system.reboot" if verb == "restart" else "system.shutdown"
    return (f"if {GUARD}; then echo \"NAS Pilot: {verb} skipped, a long task is running\"; "
            f"else midclt call {method} \"NAS Pilot scheduled {verb}\"; fi")


def host_payload(s: dict) -> dict:
    m, h, dom, mon, dow = s["cron"].split()
    return {"user": "root", "command": host_command(s["action"]), "enabled": bool(s["enabled"]),
            "description": f"NAS Pilot: {s['name']} (schedule {s['id']})", "stdout": False, "stderr": False,
            "schedule": {"minute": m, "hour": h, "dom": dom, "month": mon, "dow": dow}}


async def loop(db, run_one):
    while True:
        await asyncio.sleep(20)
        try:
            now = datetime.now().astimezone()
            for s in db.q("SELECT * FROM schedules WHERE enabled=1 AND kind IN ('app','wake')"):
                if not croniter.is_valid(s["cron"]):
                    continue
                prev = croniter(s["cron"], now).get_prev(datetime).timestamp()
                window = 900 if s["kind"] == "wake" else 300
                if prev > (s["last_run"] or 0) and time.time() - prev <= window:
                    db.x("UPDATE schedules SET last_run=? WHERE id=?", (time.time(), s["id"]))
                    asyncio.create_task(run_one(s))
        except Exception:
            log.exception("scheduler tick failed")
