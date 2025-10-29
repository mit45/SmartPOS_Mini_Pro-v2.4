"""Sales repository: raw DB operations for sales table."""
from typing import Optional, List, Tuple

def insert_line(conn, cursor,
                fis_id: str,
                product_name: str,
                quantity: int,
                price: float,
                total: float,
                payment_method: str = 'cash',
                canceled: int = 0) -> None:
    cursor.execute(
        """
        INSERT INTO sales(fis_id,product_name,quantity,price,total,payment_method,canceled,created_at)
        VALUES(?,?,?,?,?,?,?,datetime('now','localtime'))
        """,
        (fis_id, product_name, int(quantity), float(price), float(total), payment_method, int(canceled))
    )
    conn.commit()


def get_sales_between(cursor, from_dt: str, to_dt: str) -> List[Tuple[str, str, str, int, float, float]]:
    cursor.execute(
        """
          SELECT fis_id, created_at, product_name, quantity, price, total
          FROM sales
          WHERE (canceled IS NULL OR canceled=0)
            AND datetime(created_at) BETWEEN datetime(?) AND datetime(?)
          ORDER BY datetime(created_at) DESC
        """,
        (from_dt, to_dt)
    )
    rows = cursor.fetchall()
    return [
        (str(r[0]), str(r[1]), str(r[2]), int(r[3]), float(r[4]), float(r[5]))
        for r in rows
    ]


def list_recent_receipts(cursor, limit: int = 200) -> List[Tuple[str, str, float, str]]:
    """Return recent unique receipts (fis_id) with date, total sum and payment method.
    Note: uses MIN(payment_method) as a proxy when mixed lines exist; in practice lines share same method.
    """
    cursor.execute(
        f"""
        SELECT fis_id,
               MAX(created_at) as ts,
               SUM(total) as sum_total,
               MIN(COALESCE(payment_method,'cash')) as pay
        FROM sales
        WHERE (canceled IS NULL OR canceled=0)
        GROUP BY fis_id
        ORDER BY ts DESC
        LIMIT ?
        """,
        (int(limit),)
    )
    rows = cursor.fetchall()
    return [
        (str(r[0]), str(r[1]), float(r[2]), str(r[3]))
        for r in rows
    ]


def cancel_receipt(conn, cursor, fis_id: str) -> None:
    cursor.execute("UPDATE sales SET canceled=1 WHERE fis_id=? AND (canceled IS NULL OR canceled=0)", (fis_id,))
    conn.commit()
