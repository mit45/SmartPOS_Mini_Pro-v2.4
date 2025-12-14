"""Sales repository: raw DB operations for sales table."""
from typing import List, Tuple

def insert_line(conn, cursor,
                fis_id: str,
                product_name: str,
                quantity: float,
                price: float,
                total: float,
                payment_method: str = 'cash',
                canceled: int = 0,
                warehouse_id: int = None) -> None:
    cursor.execute(
        """
        INSERT INTO sales(fis_id,product_name,quantity,price,total,payment_method,canceled,warehouse_id,created_at)
        VALUES(?,?,?,?,?,?,?,?,datetime('now','localtime'))
        """,
    (fis_id, product_name, float(quantity), float(price), float(total), payment_method, int(canceled), warehouse_id)
    )
    conn.commit()


def get_sales_between(cursor, from_dt: str, to_dt: str) -> List[Tuple[str, str, str, float, float, float]]:
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
        (str(r[0]), str(r[1]), str(r[2]), float(r[3]), float(r[4]), float(r[5]))
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


def get_receipts_between(cursor, from_dt: str, to_dt: str) -> List[Tuple[str, str, float, str]]:
    """Return unique receipts (fis_id) with date, total sum and payment method within a date range."""
    cursor.execute(
        """
        SELECT fis_id,
               MAX(created_at) as ts,
               SUM(total) as sum_total,
               MIN(COALESCE(payment_method,'cash')) as pay
        FROM sales
        WHERE (canceled IS NULL OR canceled=0)
          AND datetime(created_at) BETWEEN datetime(?) AND datetime(?)
        GROUP BY fis_id
        ORDER BY ts DESC
        """,
        (from_dt, to_dt)
    )
    rows = cursor.fetchall()
    return [
        (str(r[0]), str(r[1]), float(r[2]), str(r[3]))
        for r in rows
    ]


def cancel_receipt(conn, cursor, fis_id: str) -> None:
    cursor.execute("UPDATE sales SET canceled=1 WHERE fis_id=? AND (canceled IS NULL OR canceled=0)", (fis_id,))
    conn.commit()


def get_profit_stats(cursor, from_dt: str, to_dt: str) -> Tuple[float, float]:
    """
    Returns (total_revenue, total_cost_of_goods_sold).
    COGS is calculated based on current product buy_price.
    """
    cursor.execute(
        """
        SELECT
            SUM(s.total) as total_revenue,
            SUM(s.quantity * COALESCE(p.buy_price, 0)) as total_cost
        FROM sales s
        LEFT JOIN products p ON s.product_name = p.name
        WHERE (s.canceled IS NULL OR s.canceled=0)
          AND datetime(s.created_at) BETWEEN datetime(?) AND datetime(?)
        """,
        (from_dt, to_dt)
    )
    row = cursor.fetchone()
    if row:
        return (row[0] or 0.0, row[1] or 0.0)
    return (0.0, 0.0)
