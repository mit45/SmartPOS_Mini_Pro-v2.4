"""Product repository: raw DB operations for products table.
Functions accept (conn, cursor) so callers can control transactions.
"""
from typing import List, Tuple, Optional

# list all products ordered by name

def list_all(cursor) -> List[Tuple[int, str, str, float, int]]:
    cursor.execute("SELECT id,name,COALESCE(barcode,''),price,stock FROM products ORDER BY name")
    return [(int(r[0]), str(r[1]), str(r[2]), float(r[3]), int(r[4])) for r in cursor.fetchall()]

# search products by partial name

def search_by_name(cursor, q: str) -> List[Tuple[int, str, str, float, int]]:
    cursor.execute("SELECT id,name,COALESCE(barcode,''),price,stock FROM products WHERE name LIKE ? ORDER BY name", (f"%{q}%",))
    return [(int(r[0]), str(r[1]), str(r[2]), float(r[3]), int(r[4])) for r in cursor.fetchall()]

# get product by barcode

def get_by_barcode(cursor, barcode: str) -> Optional[Tuple[int, str, float, int]]:
    cursor.execute("SELECT id,name,price,stock FROM products WHERE barcode=?", (barcode,))
    r = cursor.fetchone()
    return (int(r[0]), str(r[1]), float(r[2]), int(r[3])) if r else None

# get price and stock by name

def get_price_stock_by_name(cursor, name: str) -> Optional[Tuple[float, int]]:
    cursor.execute("SELECT price,stock FROM products WHERE name=?", (name,))
    r = cursor.fetchone()
    return (float(r[0]), int(r[1])) if r else None

# insert, update, delete

def insert(conn, cursor, name: str, barcode: str, price: float, stock: int) -> int:
    cursor.execute("INSERT INTO products(name,barcode,price,stock) VALUES(?,?,?,?)", (name, barcode, price, stock))
    conn.commit()
    return int(cursor.lastrowid)


def update(conn, cursor, pid: int, name: str, barcode: str, price: float, stock: int) -> None:
    cursor.execute("UPDATE products SET name=?,barcode=?,price=?,stock=? WHERE id=?", (name, barcode, price, stock, pid))
    conn.commit()


def delete(conn, cursor, pid: int) -> None:
    cursor.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()


def decrement_stock(conn, cursor, name: str, qty: int) -> None:
    cursor.execute("UPDATE products SET stock=stock-? WHERE name=?", (qty, name))
    conn.commit()

def increment_stock(conn, cursor, name: str, qty: int) -> None:
    cursor.execute("UPDATE products SET stock=stock+? WHERE name=?", (qty, name))
    conn.commit()
