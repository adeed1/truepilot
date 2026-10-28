"""TruePilot for Windows: runs the server in the background and shows an icon near the clock.
Started by the installer (and at sign-in) with:  pythonw -m app.tray"""
import logging
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from . import config

GREEN, AMBER = "#2fb67c", "#e0a02b"


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def healthy(port, timeout=2):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def icon_image(color=GREEN, size=64):
    from PIL import Image, ImageDraw
    s = size / 64
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(14 * s), fill="#15222B")
    d.rounded_rectangle([10 * s, 19 * s, 54 * s, 45 * s], radius=int(4 * s), fill="#1E2E38", outline="#3A505E", width=max(1, int(2 * s)))
    for cx, c in ((20, "#34C38F"), (32, color), (44, "#34C38F")):
        d.ellipse([(cx - 5) * s, (32 - 5) * s, (cx + 5) * s, (32 + 5) * s], fill=c)
    return im


def start_server(host, port):
    import uvicorn
    from .main import app
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_config=None))
    server.install_signal_handlers = lambda: None  # not the main thread
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return server, t


def _log_setup(data_dir):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    f = open(Path(data_dir) / "truepilot.log", "a", buffering=1, encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = f
    if sys.stderr is None:
        sys.stderr = f
    logging.basicConfig(stream=f, level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")


def _alert(text):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "TruePilot", 0x10)
    except Exception:
        print(text)


def main():
    cfg = config.load()
    port, host = cfg["port"], cfg["host"]
    _log_setup(cfg["data_dir"])
    url = f"http://localhost:{port}"
    if healthy(port):  # already running: just open it
        webbrowser.open(url)
        return
    server, _ = start_server(host, port)
    for _ in range(80):
        if server.started:
            break
        time.sleep(0.25)
    if not server.started:
        _alert(f"TruePilot could not start. Another program may be using port {port}.\nDetails are in {Path(cfg['data_dir']) / 'truepilot.log'}")
        return
    import pystray
    phone = f"http://{lan_ip()}:{port}"

    def open_(icon=None, item=None):
        webbrowser.open(url)

    def copy_(icon, item):
        try:
            subprocess.run(["clip"], input=phone.encode("ascii"), creationflags=0x08000000, check=False)
            icon.notify("Phone address copied. Open it in your phone's browser on the same Wi-Fi.", "TruePilot")
        except Exception:
            pass

    def quit_(icon, item):
        server.should_exit = True
        icon.stop()

    menu = pystray.Menu(pystray.MenuItem("Open TruePilot", open_, default=True),
                        pystray.MenuItem(f"Phone address: {phone}", copy_),
                        pystray.MenuItem("Quit TruePilot", quit_))
    icon = pystray.Icon("TruePilot", icon_image(GREEN), "TruePilot is running", menu)

    def watch(ic):
        ic.visible = True
        last = True
        while not server.should_exit:
            time.sleep(10)
            ok = healthy(port)
            if ok != last:
                ic.icon = icon_image(GREEN if ok else AMBER)
                ic.title = "TruePilot is running" if ok else "TruePilot is not responding"
                last = ok

    icon.run(setup=watch)


if __name__ == "__main__":
    main()
