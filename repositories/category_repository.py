"""Category repository: CRUD for categories table and helpers."""
from typing import List, Tuple, Optional


def list_all(cursor) -> List[Tuple[int, str, str]]:
    cursor.execute("SELECT id, name, COALESCE(color,'') FROM categories ORDER BY name")
    return [(int(r[0]), str(r[1]), str(r[2])) for r in cursor.fetchall()]


def insert(conn, cursor, name: str, color: str = "") -> int:
    cursor.execute("INSERT INTO categories(name,color) VALUES(?,?)", (name.strip(), color.strip()))
    conn.commit()
    return int(cursor.lastrowid)


def update(conn, cursor, cid: int, name: str, color: str = "") -> None:
    cursor.execute("UPDATE categories SET name=?, color=? WHERE id=?", (name.strip(), color.strip(), int(cid)))
    conn.commit()


def delete(conn, cursor, cid: int) -> None:
    cursor.execute("DELETE FROM categories WHERE id=?", (int(cid),))
    conn.commit()


def get_by_name(cursor, name: str) -> Optional[Tuple[int, str, str]]:
    cursor.execute("SELECT id, name, COALESCE(color,'') FROM categories WHERE name=?", (name.strip(),))
    r = cursor.fetchone()
    return (int(r[0]), str(r[1]), str(r[2])) if r else None


def count_products(cursor, cid: int) -> int:
    cursor.execute("SELECT COUNT(1) FROM products WHERE category_id=?", (int(cid),))
    r = cursor.fetchone()
    return int(r[0]) if r and r[0] is not None else 0


def get_name_by_product_name(cursor, product_name: str) -> Optional[str]:
    cursor.execute(
        """
        SELECT c.name
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.name = ?
        """,
        (product_name.strip(),)
    )
    r = cursor.fetchone()
    return str(r[0]) if r and r[0] is not None else None
