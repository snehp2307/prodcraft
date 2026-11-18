"""Separate 'billing' service that reconciles invoices. DEMO CODE WITH PLANTED BUGS — do not deploy.

Deployed independently from the order API, but writes to the order service's table.
"""

import sqlite3

# planted: second service writes directly into another service's private table (shared database)
ORDERS_DB = "../orders.db"


def mark_invoiced(order_id: int) -> None:
    conn = sqlite3.connect(ORDERS_DB)
    # planted: magic status string both services must agree on (connascence of meaning across a boundary)
    conn.execute("UPDATE orders SET status = 'INVOICED_V2' WHERE id = ?", (order_id,))
    conn.commit()
