"""Product service: business logic for products, using product_repository."""
from typing import List, Tuple, Optional
from repositories import product_repository as repo


def list_products(cursor, filter_text: str = "") -> List[Tuple[int, str, float, int]]:
    q = (filter_text or "").strip()
    if q:
        return repo.search_by_name(cursor, q)
    return repo.list_all(cursor)


def add_product(conn, cursor, name: str, price: float, stock: int) -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("name_required")
    if price is None or stock is None:
        raise ValueError("invalid_values")
    return repo.insert(conn, cursor, name, float(price), int(stock))


def update_product(conn, cursor, pid: int, name: str, price: float, stock: int) -> None:
    name = (name or "").strip()
    if not pid:
        raise ValueError("id_required")
    if not name:
        raise ValueError("name_required")
    repo.update(conn, cursor, int(pid), name, float(price), int(stock))


def delete_product(conn, cursor, pid: int) -> None:
    if not pid:
        raise ValueError("id_required")
    repo.delete(conn, cursor, int(pid))


def get_price_stock_by_name(cursor, name: str) -> Optional[Tuple[float, int]]:
    return repo.get_price_stock_by_name(cursor, name)


def decrement_stock(conn, cursor, name: str, qty: int) -> None:
    repo.decrement_stock(conn, cursor, name, int(qty))

def increment_stock(conn, cursor, name: str, qty: int) -> None:
    repo.increment_stock(conn, cursor, name, int(qty))
