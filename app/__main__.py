import socket

import uvicorn

from .main import cfg


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    print(f"\n  TruePilot is starting\n  On this PC:   http://localhost:{cfg['port']}")
    print(f"  On your LAN:  http://{lan_ip()}:{cfg['port']}\n")
    uvicorn.run("app.main:app", host=cfg["host"], port=cfg["port"], log_level="warning")
