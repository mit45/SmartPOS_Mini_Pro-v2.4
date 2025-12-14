"""Sales service: wrapper over sales_repository for business rules and queries."""
from repositories import sales_repository as repo
from services import product_service as product_svc

def insert_sale_line(conn, cursor, fis_id: str, product_name: str, quantity: float, price: float, total: float, payment_method: str = 'cash', warehouse_id: int = None) -> None:
    repo.insert_line(conn, cursor, fis_id, product_name, float(quantity), price, total, payment_method=payment_method, warehouse_id=warehouse_id)

def list_sales_between(cursor, from_dt: str, to_dt: str):
    return repo.get_sales_between(cursor, from_dt, to_dt)


def list_recent_receipts(cursor, limit: int = 200):
    return repo.list_recent_receipts(cursor, limit)


def list_receipts_between(cursor, from_dt: str, to_dt: str):
    return repo.get_receipts_between(cursor, from_dt, to_dt)


def cancel_receipt(conn, cursor, fis_id: str) -> None:
    """Mark receipt canceled and restore products stock."""
    # get lines to restore stock
    cursor.execute("SELECT product_name, quantity, warehouse_id FROM sales WHERE fis_id=? AND (canceled IS NULL OR canceled=0)", (fis_id,))
    rows = cursor.fetchall()
    for name, qty, wh_id in rows:
        try:
            product_svc.increment_stock(conn, cursor, name, float(qty), warehouse_id=wh_id)
        except Exception:
            # even if a product is missing, try to proceed
            pass
    repo.cancel_receipt(conn, cursor, fis_id)


def get_profit_loss_stats(cursor, from_dt: str, to_dt: str):
    return repo.get_profit_stats(cursor, from_dt, to_dt)
