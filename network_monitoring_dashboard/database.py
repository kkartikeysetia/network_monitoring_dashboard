"""SQLite persistence for monitoring checks and incident tickets."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("noc_demo.db")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT NOT NULL, url TEXT NOT NULL, status TEXT NOT NULL,
            latency_ms REAL, http_status INTEGER, resolved_ip TEXT,
            diagnosis TEXT, checked_at TEXT NOT NULL, is_simulated INTEGER DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            service TEXT NOT NULL, severity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            diagnosis TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, resolution_note TEXT DEFAULT ''
        )""")


def save_check(result: dict):
    with connect() as conn:
        conn.execute("""INSERT INTO checks
            (service,url,status,latency_ms,http_status,resolved_ip,diagnosis,checked_at,is_simulated)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (result["service"], result["url"], result["status"], result["latency_ms"],
             result["http_status"], result["resolved_ip"], result["diagnosis"],
             result["checked_at"], result["is_simulated"]))


def create_or_update_incident(result: dict, severity: str):
    if result["status"] == "UP":
        return
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM incidents WHERE service=? AND status!='RESOLVED' ORDER BY id DESC LIMIT 1",
            (result["service"],),
        ).fetchone()
        if existing:
            conn.execute("UPDATE incidents SET severity=?, diagnosis=?, updated_at=? WHERE id=?",
                         (severity, result["diagnosis"], result["checked_at"], existing["id"]))
        else:
            next_num = conn.execute("SELECT COALESCE(MAX(id), 0) + 1001 FROM incidents").fetchone()[0]
            ticket_id = f"INC-{next_num}"
            conn.execute("""INSERT INTO incidents
                (ticket_id,service,severity,status,diagnosis,created_at,updated_at)
                VALUES (?,?,?,'OPEN',?,?,?)""",
                (ticket_id, result["service"], severity, result["diagnosis"],
                 result["checked_at"], result["checked_at"]))


def get_checks(limit: int = 100):
    with connect() as conn:
        rows = conn.execute("SELECT * FROM checks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def get_incidents():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM incidents ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def update_incident(ticket_id: str, status: str, note: str = ""):
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect() as conn:
        conn.execute("UPDATE incidents SET status=?, updated_at=?, resolution_note=? WHERE ticket_id=?",
                     (status, now, note, ticket_id))
