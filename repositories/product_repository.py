"""Product repository: raw DB operations for products table.
Functions accept (conn, cursor) so callers can control transactions.
"""
from typing import List, Tuple, Optional

# list all products ordered by ID (ascending)

def list_all(cursor) -> List[Tuple[int, str, str, float, float, float, str, str]]:
    cursor.execute("""
        SELECT p.id, p.name, COALESCE(p.barcode,''), COALESCE(p.sale_price,p.price) AS sale_price, 
               p.stock, COALESCE(p.buy_price,0) AS buy_price, COALESCE(p.unit,'adet'),
               COALESCE(c.name,'-') AS category_name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        ORDER BY p.id ASC
    """)
    return [(
        int(r[0]), str(r[1]), str(r[2]), float(r[3]), float(r[4]), float(r[5]), str(r[6]), str(r[7])
    ) for r in cursor.fetchall()]

# search products by partial name

def search_by_name(cursor, q: str) -> List[Tuple[int, str, str, float, float, float, str, str]]:
    cursor.execute("""
        SELECT p.id, p.name, COALESCE(p.barcode,''), COALESCE(p.sale_price,p.price), 
               p.stock, COALESCE(p.buy_price,0), COALESCE(p.unit,'adet'),
               COALESCE(c.name,'-') AS category_name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.name LIKE ? 
        ORDER BY p.id ASC
    """, (f"%{q}%",))
    return [(
        int(r[0]), str(r[1]), str(r[2]), float(r[3]), float(r[4]), float(r[5]), str(r[6]), str(r[7])
    ) for r in cursor.fetchall()]

# get product by barcode

def get_by_barcode(cursor, barcode: str) -> Optional[Tuple[int, str, float, float, str]]:
    cursor.execute(
        "SELECT id,name,COALESCE(sale_price,price),stock,COALESCE(unit,'adet') FROM products WHERE barcode=?",
        (barcode,)
    )
    r = cursor.fetchone()
    return (int(r[0]), str(r[1]), float(r[2]), float(r[3]), str(r[4])) if r else None

# get price and stock by name

def get_price_stock_by_name(cursor, name: str) -> Optional[Tuple[float, float, str]]:
    cursor.execute("SELECT COALESCE(sale_price,price),stock,COALESCE(unit,'adet') FROM products WHERE name=?", (name,))
    r = cursor.fetchone()
    return (float(r[0]), float(r[1]), str(r[2])) if r else None


def get_category_name_by_product_name(cursor, name: str) -> Optional[str]:
    cursor.execute(
        """
        SELECT c.name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.name=?
        """,
        (name,)
    )
    r = cursor.fetchone()
    return str(r[0]) if r and r[0] is not None else None

# insert, update, delete

def insert(conn, cursor, name: str, barcode: str, sale_price: float, stock: float, buy_price: float, unit: str = 'adet', category_id: Optional[int] = None) -> int:
    cursor.execute(
        "INSERT INTO products(name,barcode,price,stock,buy_price,sale_price,unit,category_id) VALUES(?,?,?,?,?,?,?,?)",
        (name, barcode, float(sale_price), float(stock), float(buy_price), float(sale_price), unit, category_id)
    )
    conn.commit()
    return int(cursor.lastrowid)


def update(conn, cursor, pid: int, name: str, barcode: str, sale_price: float, stock: float, buy_price: float, unit: str = 'adet', category_id: Optional[int] = None) -> None:
    cursor.execute(
        "UPDATE products SET name=?,barcode=?,price=?,stock=?,buy_price=?,sale_price=?,unit=?,category_id=? WHERE id=?",
        (name, barcode, float(sale_price), float(stock), float(buy_price), float(sale_price), unit, category_id, int(pid))
    )
    conn.commit()


def delete(conn, cursor, pid: int) -> None:
    cursor.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()


def decrement_stock(conn, cursor, name: str, qty: float) -> None:
    cursor.execute("UPDATE products SET stock=stock-? WHERE name=?", (float(qty), name))
    conn.commit()


def increment_stock(conn, cursor, name: str, qty: float) -> None:
    cursor.execute("UPDATE products SET stock=stock+? WHERE name=?", (float(qty), name))
    conn.commit()
 
