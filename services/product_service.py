"""Product service: business logic for products, using product_repository."""
from typing import List, Tuple, Optional
from repositories import product_repository as repo


def list_products(cursor, filter_text: str = "") -> List[Tuple[int, str, str, float, float, float, str, str]]:
    q = (filter_text or "").strip()
    if q:
        return repo.search_by_name(cursor, q)
    return repo.list_all(cursor)


from services import warehouse_service as wh_svc

def add_product(conn, cursor, name: str, barcode: str, sale_price: float, stock: float, buy_price: float, unit: str = 'adet', category_id: Optional[int] = None, warehouse_id: Optional[int] = None) -> int:
    name = (name or "").strip()
    barcode = (barcode or "").strip()
    if not name:
        raise ValueError("name_required")
    if sale_price is None or stock is None:
        raise ValueError("invalid_values")
    unit = (unit or 'adet').strip().lower()
    if unit not in ('adet', 'kg'):
        unit = 'adet'
    pid = repo.insert(conn, cursor, name, barcode, float(sale_price), float(stock), float(buy_price), unit, category_id)
    
    if warehouse_id and stock > 0:
        wh_svc.repo.update_stock(cursor, warehouse_id, pid, float(stock))
        wh_svc.repo.add_movement(cursor, None, warehouse_id, pid, float(stock), "Açılış Stoğu", 1)
        
    return pid


def update_product(conn, cursor, pid: int, name: str, barcode: str, sale_price: float, stock: float, buy_price: float, unit: str = 'adet', category_id: Optional[int] = None) -> None:
    name = (name or "").strip()
    barcode = (barcode or "").strip()
    if not pid:
        raise ValueError("id_required")
    if not name:
        raise ValueError("name_required")
    unit = (unit or 'adet').strip().lower()
    if unit not in ('adet', 'kg'):
        unit = 'adet'
    repo.update(conn, cursor, int(pid), name, barcode, float(sale_price), float(stock), float(buy_price), unit, category_id)


def delete_product(conn, cursor, pid: int) -> None:
    if not pid:
        raise ValueError("id_required")
    repo.delete(conn, cursor, int(pid))


def get_price_stock_by_name(cursor, name: str, warehouse_id: Optional[int] = None) -> Optional[Tuple[float, float, str]]:
    return repo.get_price_stock_by_name(cursor, name, warehouse_id)


def get_by_barcode(cursor, barcode: str, warehouse_id: Optional[int] = None) -> Optional[Tuple[int, str, float, float, str]]:
    return repo.get_by_barcode(cursor, barcode, warehouse_id)

def get_by_id(cursor, pid: int):
    return repo.get_by_id(cursor, pid)

def decrement_stock(conn, cursor, name: str, qty: float, warehouse_id: Optional[int] = None) -> None:
    repo.decrement_stock(conn, cursor, name, float(qty))
    
    if warehouse_id:
        cursor.execute("SELECT id FROM products WHERE name=?", (name,))
        row = cursor.fetchone()
        if row:
            pid = row[0]
            current = wh_svc.repo.get_stock(cursor, warehouse_id, pid)
            wh_svc.repo.update_stock(cursor, warehouse_id, pid, current - float(qty))
            # Log movement (Exit)
            wh_svc.repo.add_movement(cursor, warehouse_id, None, pid, float(qty), "Satış", 1)

def increment_stock(conn, cursor, name: str, qty: float, warehouse_id: Optional[int] = None) -> None:
    repo.increment_stock(conn, cursor, name, float(qty))
    
    if warehouse_id:
        cursor.execute("SELECT id FROM products WHERE name=?", (name,))
        row = cursor.fetchone()
        if row:
            pid = row[0]
            current = wh_svc.repo.get_stock(cursor, warehouse_id, pid)
            wh_svc.repo.update_stock(cursor, warehouse_id, pid, current + float(qty))
            # Log movement (Entry)
            wh_svc.repo.add_movement(cursor, None, warehouse_id, pid, float(qty), "Satış İptal/İade", 1)
