"""Product service: business logic for products, using product_repository."""
from typing import List, Tuple, Optional
from repositories import product_repository as repo


def list_products(cursor, filter_text: str = "") -> List[Tuple[int, str, str, float, float, float, str, str]]:
    q = (filter_text or "").strip()
    if q:
        return repo.search_by_name(cursor, q)
    return repo.list_all(cursor)


def add_product(conn, cursor, name: str, barcode: str, sale_price: float, stock: float, buy_price: float, unit: str = 'adet', category_id: Optional[int] = None) -> int:
    name = (name or "").strip()
    barcode = (barcode or "").strip()
    if not name:
        raise ValueError("name_required")
    if sale_price is None or stock is None:
        raise ValueError("invalid_values")
    unit = (unit or 'adet').strip().lower()
    if unit not in ('adet', 'kg'):
        unit = 'adet'
    return repo.insert(conn, cursor, name, barcode, float(sale_price), float(stock), float(buy_price), unit, category_id)


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


def get_price_stock_by_name(cursor, name: str) -> Optional[Tuple[float, float, str]]:
    return repo.get_price_stock_by_name(cursor, name)


def get_by_barcode(cursor, barcode: str) -> Optional[Tuple[int, str, float, float, str]]:
    return repo.get_by_barcode(cursor, barcode)

def get_by_id(cursor, pid: int):
    return repo.get_by_id(cursor, pid)

def decrement_stock(conn, cursor, name: str, qty: float) -> None:
    repo.decrement_stock(conn, cursor, name, qty)


def decrement_stock(conn, cursor, name: str, qty: float) -> None:
    repo.decrement_stock(conn, cursor, name, float(qty))

def increment_stock(conn, cursor, name: str, qty: float) -> None:
    repo.increment_stock(conn, cursor, name, float(qty))
