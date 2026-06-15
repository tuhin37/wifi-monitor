"""SQLite-backed storage for AP data, speed tests, and scheduled tasks."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: str = "/data/wifi_monitor.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS access_points (
                    bssid TEXT PRIMARY KEY,
                    ssid TEXT, channel INTEGER, band TEXT,
                    frequency INTEGER, rssi REAL, signal_dbm REAL,
                    snr REAL, encryption TEXT, vendor TEXT,
                    width_mhz INTEGER, first_seen INTEGER,
                    last_seen INTEGER, type TEXT
                );
                CREATE TABLE IF NOT EXISTS speed_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bssid TEXT, ssid TEXT,
                    download_mbps REAL, upload_mbps REAL,
                    ping_ms REAL, jitter_ms REAL,
                    packet_loss REAL,
                    server_name TEXT, server_location TEXT,
                    interface TEXT, timestamp INTEGER
                );
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL, bssid TEXT, ssid TEXT,
                    credentials TEXT, schedule TEXT,
                    enabled INTEGER DEFAULT 1,
                    last_run INTEGER, last_status TEXT,
                    created_at INTEGER, type TEXT DEFAULT 'speedtest'
                );
                CREATE INDEX IF NOT EXISTS idx_speed_tests_bssid ON speed_tests(bssid);
                CREATE INDEX IF NOT EXISTS idx_speed_tests_ts ON speed_tests(timestamp);
            """)

    # ---- Access Points ----
    def upsert_ap(self, bssid: str, data: dict) -> None:
        now = int(time.time())
        with self._conn() as conn:
            row = conn.execute("SELECT first_seen FROM access_points WHERE bssid=?", (bssid,)).fetchone()
            first = row["first_seen"] if row else now
            conn.execute(
                """INSERT OR REPLACE INTO access_points
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (bssid, data.get("ssid",""), data.get("channel",0),
                 data.get("band",""), data.get("frequency",0),
                 data.get("rssi",0), data.get("signal_dbm",0),
                 data.get("snr",0), data.get("encryption",""),
                 data.get("vendor",""), data.get("width_mhz",0),
                 first, now, data.get("type","unknown")),
            )

    def get_aps(self, limit: int = 200) -> list[dict]:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM access_points ORDER BY last_seen DESC LIMIT ?", (limit,)).fetchall()]

    # ---- Speed Tests ----
    def add_speedtest(self, data: dict) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO speed_tests
                   (bssid,ssid,download_mbps,upload_mbps,ping_ms,jitter_ms,
                    packet_loss,server_name,server_location,interface,timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (data.get("bssid",""), data.get("ssid",""),
                 data.get("download_mbps",0), data.get("upload_mbps",0),
                 data.get("ping_ms",0), data.get("jitter_ms",0),
                 data.get("packet_loss",0),
                 data.get("server_name",""), data.get("server_location",""),
                 data.get("interface",""), int(time.time())),
            )
            return cur.lastrowid

    def get_speedtests(self, limit: int = 100, bssid: Optional[str] = None) -> list[dict]:
        with self._conn() as conn:
            if bssid:
                rows = conn.execute(
                    "SELECT * FROM speed_tests WHERE bssid=? ORDER BY timestamp DESC LIMIT ?",
                    (bssid, limit)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM speed_tests ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_latest_speedtest(self, bssid: Optional[str] = None) -> Optional[dict]:
        with self._conn() as conn:
            if bssid:
                r = conn.execute(
                    "SELECT * FROM speed_tests WHERE bssid=? ORDER BY timestamp DESC LIMIT 1",
                    (bssid,)).fetchone()
            else:
                r = conn.execute(
                    "SELECT * FROM speed_tests ORDER BY timestamp DESC LIMIT 1").fetchone()
            return dict(r) if r else None

    # ---- Scheduled Tasks ----
    def add_task(self, name: str, bssid: str, ssid: str,
                 credentials: str, schedule: str, task_type: str = "speedtest") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO scheduled_tasks (name,bssid,ssid,credentials,schedule,enabled,created_at,type) "
                "VALUES (?,?,?,?,?,1,?,?)",
                (name, bssid, ssid, credentials, schedule, int(time.time()), task_type))
            return cur.lastrowid

    def get_tasks(self, enabled_only: bool = False) -> list[dict]:
        with self._conn() as conn:
            q = "SELECT * FROM scheduled_tasks"
            if enabled_only:
                q += " WHERE enabled=1"
            q += " ORDER BY created_at DESC"
            results = []
            for r in conn.execute(q).fetchall():
                d = dict(r)
                if d.get("credentials"):
                    try:
                        d["credentials_dict"] = json.loads(d["credentials"])
                    except (json.JSONDecodeError, TypeError):
                        d["credentials_dict"] = {}
                else:
                    d["credentials_dict"] = {}
                results.append(d)
            return results

    def get_task(self, task_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM scheduled_tasks WHERE id=?", (task_id,)).fetchone()
            if r:
                d = dict(r)
                if d.get("credentials"):
                    try:
                        d["credentials_dict"] = json.loads(d["credentials"])
                    except (json.JSONDecodeError, TypeError):
                        d["credentials_dict"] = {}
                else:
                    d["credentials_dict"] = {}
                return d
            return None

    def update_task_status(self, task_id: int, status: str):
        with self._conn() as conn:
            conn.execute("UPDATE scheduled_tasks SET last_run=?, last_status=? WHERE id=?",
                        (int(time.time()), status, task_id))

    def toggle_task(self, task_id: int, enabled: bool):
        with self._conn() as conn:
            conn.execute("UPDATE scheduled_tasks SET enabled=? WHERE id=?",
                        (1 if enabled else 0, task_id))

    def delete_task(self, task_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM scheduled_tasks WHERE id=?", (task_id,))
