"""Stock management. DEMO CODE WITH PLANTED BUGS — do not deploy."""

from app.db import get_conn


def reserve_stock(sku: str, quantity: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT available FROM stock WHERE sku = ?", (sku,)).fetchone()
    available = row["available"]
    # planted: read-modify-write race — two concurrent orders can both pass this check
    if available >= quantity:
        conn.execute(
            "UPDATE stock SET available = ? WHERE sku = ?", (available - quantity, sku)
        )
        conn.commit()
        return True
    return False
