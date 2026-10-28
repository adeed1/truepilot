"""Is a PC on? Tries a port if one is set, otherwise ping, then a few common ports."""
import asyncio
import re
import shutil
import sys

DEMO_PCS = {}
_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]*$")


async def tcp_ok(ip, port, timeout=1.5):
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(ip, int(port)), timeout)
        w.close()
        try:
            await w.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def ping_ok(ip):
    exe = shutil.which("ping")
    if not exe or not _OK.match(ip):
        return None
    if sys.platform.startswith("win"):
        args, kw = [exe, "-n", "1", "-w", "1500", ip], {"creationflags": 0x08000000}
    else:
        args, kw = [exe, "-c", "1", "-W", "2", ip], {}
    try:
        p = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **kw)
        out, _ = await asyncio.wait_for(p.communicate(), 6)
        return b"ttl=" in out.lower()
    except Exception:
        return None


async def check_online(ip, port=None):
    """True, False, or None when there is no address to check."""
    ip = (ip or "").strip()
    if not ip:
        return None
    if ip.startswith("demo-"):
        return bool(DEMO_PCS.get(ip))
    if not _OK.match(ip):
        return None
    if port:
        return await tcp_ok(ip, port)
    if await ping_ok(ip):
        return True
    for p in (445, 3389, 22, 80, 443):
        if await tcp_ok(ip, p, 1.0):
            return True
    return False


async def find_mac(ip):
    """Looks up a MAC address in this computer's ARP table (the PC must be on the same network and recently reachable)."""
    ip = (ip or "").strip()
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        return None
    await ping_ok(ip)
    for _ in range(2):
        try:
            if sys.platform.startswith("linux"):
                for line in open("/proc/net/arp").read().splitlines()[1:]:
                    f = line.split()
                    if f and f[0] == ip and f[3] != "00:00:00:00:00:00":
                        return f[3].upper()
            else:
                exe = shutil.which("arp")
                if exe:
                    args = [exe, "-a"] if sys.platform.startswith("win") else [exe, "-n", ip]
                    kw = {"creationflags": 0x08000000} if sys.platform.startswith("win") else {}
                    pr = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **kw)
                    out, _ = await asyncio.wait_for(pr.communicate(), 6)
                    for line in out.decode(errors="ignore").splitlines():
                        if re.search(r"(?<![\d.])" + re.escape(ip) + r"(?![\d.])", line):
                            m = re.search(r"([0-9a-fA-F]{1,2}[:-]){5}[0-9a-fA-F]{1,2}", line)
                            if m:
                                return ":".join(x.zfill(2) for x in re.split(r"[:-]", m.group(0))).upper()
        except Exception:
            pass
        await asyncio.sleep(0.6)
    return None
