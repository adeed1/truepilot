import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS devices(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'truenas',
  host TEXT, port INTEGER DEFAULT 443, username TEXT, key_enc TEXT, wuser TEXT, wkey_enc TEXT,
  verify_tls INTEGER DEFAULT 0, write_enabled INTEGER DEFAULT 0, mac TEXT, broadcast TEXT, created REAL);
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT UNIQUE, label TEXT, created REAL, last_seen REAL, ip TEXT);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, who TEXT, device_id INTEGER, action TEXT,
  target TEXT, detail TEXT, result TEXT);
CREATE TABLE IF NOT EXISTS schedules(
  id INTEGER PRIMARY KEY AUTOINCREMENT, device_id INTEGER, name TEXT, kind TEXT, action TEXT, target TEXT,
  cron TEXT, enabled INTEGER DEFAULT 1, last_run REAL, last_result TEXT, host_cron_id INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS app_links(
  device_id INTEGER, app TEXT, url TEXT, PRIMARY KEY(device_id, app));
CREATE TABLE IF NOT EXISTS app_favs(
  device_id INTEGER, app TEXT, PRIMARY KEY(device_id, app));
CREATE TABLE IF NOT EXISTS agent_tokens(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, token_hash TEXT UNIQUE, level TEXT, created REAL, last_used REAL);
CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, token_id INTEGER, token_name TEXT, action TEXT, device_id INTEGER, app TEXT,
  reason TEXT, status TEXT, created REAL, decided REAL, task TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS web_apps(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, host TEXT, port INTEGER, secure INTEGER DEFAULT 0, kind TEXT DEFAULT 'other', runs_on TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS wol_targets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, mac TEXT, broadcast TEXT, ip TEXT, port INTEGER);
"""


class DB:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.c.executescript(SCHEMA)
            cols = [r[1] for r in self.c.execute("PRAGMA table_info(wol_targets)")]
            for col, typ in (("ip", "TEXT"), ("port", "INTEGER")):
                if col not in cols:
                    self.c.execute(f"ALTER TABLE wol_targets ADD COLUMN {col} {typ}")
            acols = [r[1] for r in self.c.execute("PRAGMA table_info(approvals)")]
            for col in ("params", "summary"):
                if col not in acols:
                    self.c.execute(f"ALTER TABLE approvals ADD COLUMN {col} TEXT")
            self.c.commit()

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.c.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def x(self, sql, args=()):
        with self.lock:
            cur = self.c.execute(sql, args)
            self.c.commit()
            return cur.lastrowid

    def get(self, key, default=None):
        r = self.one("SELECT v FROM settings WHERE k=?", (key,))
        return r["v"] if r else default

    def put(self, key, value):
        self.x("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, value))
