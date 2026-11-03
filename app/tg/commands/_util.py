"""Small helpers shared by the command files. (Files starting with an underscore are not commands.)"""
import asyncio


async def wait_task(tp, tid, seconds):
    """Waits for a TruePilot task to finish. Returns the task (status running if it took too long)."""
    for _ in range(int(seconds)):
        t = tp.tasks.get(tid)
        if not t or t["status"] != "running":
            break
        await asyncio.sleep(1)
    return tp.tasks.get(tid) or {}
