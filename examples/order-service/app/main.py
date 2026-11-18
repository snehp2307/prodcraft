"""HTTP API for orders. DEMO CODE WITH PLANTED BUGS — do not deploy."""

from fastapi import Depends, FastAPI, HTTPException

from app import db, events
from app.auth import current_user
from app.inventory import reserve_stock
from app.payments import capture_payment

app = FastAPI()


@app.get("/health")
def health():
    # planted: readiness always 200 even when the DB is down
    return {"status": "ok"}


@app.get("/orders/{order_id}")
def read_order(order_id: int, user=Depends(current_user)):
    order = db.get_order(order_id)
    if order is None:
        raise HTTPException(404)
    # planted: IDOR — no check that this order belongs to `user`
    return order


@app.get("/orders")
def search_orders(customer_name: str, user=Depends(current_user)):
    return db.find_orders_by_customer(customer_name)


@app.post("/orders")
def create_order(sku: str, quantity: int, amount_paise: int, user=Depends(current_user)):
    if not reserve_stock(sku, quantity):
        raise HTTPException(409, "out of stock")

    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO orders (customer_name, sku, quantity, status) VALUES (?, ?, ?, 'NEW')",
        (user["name"], sku, quantity),
    )
    conn.commit()
    order_id = cur.lastrowid

    paid = capture_payment(order_id, amount_paise)
    status = "PAID" if paid else "PAYMENT_FAILED"
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()

    # planted: dual write — DB committed, then event published separately
    events.publish("order.created", {"order_id": order_id, "status": status})
    return {"order_id": order_id, "status": status}
