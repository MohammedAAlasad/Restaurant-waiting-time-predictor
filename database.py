import sqlite3 
from datetime import datetime , timedelta
from zoneinfo import ZoneInfo

import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "restaurant.db")

conn = sqlite3.connect(
    DB_PATH,
    check_same_thread=False
)

cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at DATETIME,
        started_at DATETIME,
        completed_at DATETIME
    )
""")
cur.execute("""
    CREATE TABLE IF NOT EXISTS resturantINFO (
        id INTEGER PRIMARY KEY,
        customers_in_queue INTEGER,
        employees_working INTEGER
    )
""")

cur.execute("""
    INSERT OR IGNORE INTO resturantINFO
    (id, customers_in_queue, employees_working)
    VALUES (?, ?, ?)
""", (1, 0, 3))

conn.commit()

def create_order():
    now = datetime.now(ZoneInfo("America/Los_Angeles"))

    cur.execute("""
        INSERT INTO orders (created_at)
        VALUES (?)
    """, (
        now.strftime('%Y-%m-%d %H:%M:%S'),
    ))

    conn.commit()


def start_order(order_id):
    now = datetime.now(ZoneInfo("America/Los_Angeles"))

    cur.execute("""
        UPDATE orders
        SET started_at = ?
        WHERE id = ?
    """, (
        now.strftime('%Y-%m-%d %H:%M:%S'),
        order_id
    ))

    conn.commit()
    return cur.rowcount

def end_order(order_id):
    now = datetime.now(ZoneInfo("America/Los_Angeles"))

    cur.execute("""
        UPDATE orders
        SET completed_at = ?
        WHERE id = ?
        AND started_at IS NOT NULL
    """, (
        now.strftime('%Y-%m-%d %H:%M:%S'),
        order_id
    ))

    conn.commit()
    return cur.rowcount


def get_avg_service_time():
    cur.execute("""
        SELECT started_at, completed_at
        FROM orders
        WHERE started_at IS NOT NULL
        AND completed_at IS NOT NULL
        ORDER BY completed_at DESC
        LIMIT 20
    """)

    rows = cur.fetchall()

    if len(rows) < 5:
        return 5.66

    service_times = []

    for row in rows:
        start = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        end = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")

        minutes = (end - start).total_seconds() / 60
        service_times.append(minutes)

    return sum(service_times) / len(service_times)


def get_orders_last_30min():
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    before30min = now - timedelta(minutes=30)

    cur.execute("""
    SELECT COUNT(*)
    FROM orders
    WHERE created_at >= ?
    AND created_at <= ?
    """, (
        before30min.strftime('%Y-%m-%d %H:%M:%S'),
        now.strftime('%Y-%m-%d %H:%M:%S')
    ))

    row = cur.fetchone()

    return row[0]

def get_customers_in_queue():
    cur.execute("""
        SELECT *
        FROM orders
        WHERE started_at IS NULL
        AND completed_at IS NULL
    """)

    rows = cur.fetchall()

    return len(rows)

def get_employees_working():
    cur.execute("""
        SELECT employees_working
        FROM resturantINFO
        WHERE id = ?
    """, (
        1,
    ))

    row = cur.fetchone()

    return row[0]

def update_employees_working(number):
    cur.execute("""
        UPDATE resturantINFO
        SET employees_working = ?
        WHERE id = ?
    """, (
        number,
        1,
    ))

    conn.commit()

    return cur.rowcount

def get_orders_count():
    cur.execute("""
        SELECT COUNT(*)
        FROM orders
    """)

    row = cur.fetchone()

    return row[0]

