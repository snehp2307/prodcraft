"""Database access for the order service. DEMO CODE WITH PLANTED BUGS — do not deploy."""

import sqlite3

DB_PATH = "orders.db"
DB_PASSWORD = "Ord3rsProdPassw0rd!"  # planted: hard-coded production credential


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def find_orders_by_customer(customer_name: str) -> list[dict]:
    conn = get_conn()
    # planted: SQL built with string formatting (injection)
    rows = conn.execute(
        f"SELECT * FROM orders WHERE customer_name = '{customer_name}'"
    ).fetchall()
    return [dict(r) for r in rows]


def get_order(order_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return dict(row) if row else None
