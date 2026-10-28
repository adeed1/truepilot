"""App settings. Devices (NAS address + keys) live in the database, not here."""
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
VERSION = "2.5"


def env(name, default=None):
    return os.environ.get("TRUEPILOT_" + name, os.environ.get("NASPILOT_" + name, default))


def load() -> dict:
    cfg = {
        "host": "0.0.0.0",
        "port": 8080,
        "data_dir": str(BASE / "data"),
        "demo_mode": False,
        "read_only": False,
        "refresh_seconds": 5,
    }
    p = Path(env("CONFIG", BASE / "config.json"))
    if p.exists():
        cfg.update(json.loads(p.read_text(encoding="utf-8")))
    if env("PORT"):
        cfg["port"] = int(env("PORT"))
    if env("DATA_DIR"):
        cfg["data_dir"] = env("DATA_DIR")
    if env("DEMO"):
        cfg["demo_mode"] = env("DEMO").lower() in ("1", "true", "yes")
    return cfg
