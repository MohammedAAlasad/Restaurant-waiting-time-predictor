import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DB_PATH = os.getenv("DB_PATH", "restaurant.db")

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS restaurants (
    id                INTEGER PRIMARY KEY,
    name              TEXT NOT NULL DEFAULT 'My Restaurant',
    latitude          REAL,
    longitude         REAL,
    timezone          TEXT NOT NULL DEFAULT 'America/Los_Angeles',
    country_code      TEXT NOT NULL DEFAULT 'US',
    employees_working INTEGER NOT NULL DEFAULT 3 CHECK (employees_working >= 1)
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    status        TEXT NOT NULL DEFAULT 'CREATED'
                  CHECK (status IN ('CREATED', 'IN_PROGRESS', 'COMPLETED')),
    item_count    INTEGER NOT NULL DEFAULT 1 CHECK (item_count >= 1),
    created_at    TEXT NOT NULL,   -- always UTC, e.g. 2026-10-05T14:03:00+00:00
    started_at    TEXT,
    completed_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_queue ON orders (restaurant_id, status, id);

INSERT OR IGNORE INTO restaurants (id) VALUES (1);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def get_restaurant(restaurant_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)).fetchone()
    return dict(row) if row else None


def set_location(restaurant_id: int, lat: float, lon: float, tz: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE restaurants SET latitude = ?, longitude = ?, timezone = ? WHERE id = ?",
            (lat, lon, tz, restaurant_id),
        )
        return cur.rowcount


def set_employees(restaurant_id: int, count: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE restaurants SET employees_working = ? WHERE id = ?", (count, restaurant_id)
        )
        return cur.rowcount


def create_order(restaurant_id: int, item_count: int = 1) -> dict:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO orders (restaurant_id, item_count, created_at) VALUES (?, ?, ?)",
            (restaurant_id, item_count, utc_now()),
        )
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_order(order_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


def _transition(order_id: int, expected: str, new: str, time_column: str) -> int:
 
    with connect() as conn:
        cur = conn.execute(
            f"UPDATE orders SET status = ?, {time_column} = ? WHERE id = ? AND status = ?",
            (new, utc_now(), order_id, expected),
        )
        return cur.rowcount


def start_order(order_id: int) -> int:
    return _transition(order_id, "CREATED", "IN_PROGRESS", "started_at")


def complete_order(order_id: int) -> int:
    return _transition(order_id, "IN_PROGRESS", "COMPLETED", "completed_at")


def local_midnight_utc(tz_name: str) -> str:
    now = datetime.now(ZoneInfo(tz_name))
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(timezone.utc).isoformat(timespec="seconds")


def list_queue_orders(restaurant_id: int, tz_name: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT * FROM orders
               WHERE restaurant_id = ? AND (status != 'COMPLETED' OR created_at >= ?)
               ORDER BY id""",
            (restaurant_id, local_midnight_utc(tz_name)),
        ).fetchall()
    return [dict(r) for r in rows]


def queue_counts(restaurant_id: int) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE restaurant_id = ? AND status = 'CREATED'",
            (restaurant_id,),
        ).fetchone()
    return row["n"]


def waiting_ahead_of(order: dict) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE restaurant_id = ? AND status = 'CREATED' AND id < ?",
            (order["restaurant_id"], order["id"]),
        ).fetchone()
    return row["n"]


def orders_created_last_minutes(restaurant_id: int, minutes: int = 30) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE restaurant_id = ? AND created_at >= ?",
            (restaurant_id, cutoff),
        ).fetchone()
    return row["n"]


def avg_service_minutes(restaurant_id: int, default: float = 5.66) -> float:
    """Average of the last 20 finished orders; falls back to the training-set mean."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT started_at, completed_at FROM orders
               WHERE restaurant_id = ? AND status = 'COMPLETED'
               ORDER BY completed_at DESC LIMIT 20""",
            (restaurant_id,),
        ).fetchall()
    if len(rows) < 5:
        return default
    minutes = [
        (datetime.fromisoformat(r["completed_at"]) - datetime.fromisoformat(r["started_at"])).total_seconds() / 60
        for r in rows
    ]
    return sum(minutes) / len(minutes)


def hourly_analytics(restaurant_id: int, tz_name: str, days: int = 28) -> dict:
    """Average orders per hour-of-day and average queue wait per hour-of-day."""
    tz = ZoneInfo(tz_name)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    with connect() as conn:
        rows = conn.execute(
            "SELECT created_at, started_at FROM orders WHERE restaurant_id = ? AND created_at >= ?",
            (restaurant_id, cutoff),
        ).fetchall()

    volume = [0] * 24
    wait_sum = [0.0] * 24
    wait_n = [0] * 24
    active_days = set()
    for r in rows:
        created = datetime.fromisoformat(r["created_at"])
        local = created.astimezone(tz)
        hour = local.hour
        active_days.add(local.date())
        volume[hour] += 1
        if r["started_at"]:
            wait_sum[hour] += (datetime.fromisoformat(r["started_at"]) - created).total_seconds() / 60
            wait_n[hour] += 1

    n_days = max(1, len(active_days))
    return {
        "hourly_volume": [round(v / n_days, 1) for v in volume],
        "typical_wait": [round(wait_sum[h] / wait_n[h], 1) if wait_n[h] else None for h in range(24)],
    }