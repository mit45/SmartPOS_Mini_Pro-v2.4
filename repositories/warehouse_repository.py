import sqlite3
from datetime import datetime

def list_warehouses(cursor):
    cursor.execute("SELECT id, name, location, created_at FROM warehouses ORDER BY id DESC")
    return cursor.fetchall()

def add_warehouse(cursor, name, location):
    cursor.execute("INSERT INTO warehouses (name, location) VALUES (?, ?)", (name, location))
    return cursor.lastrowid

def update_warehouse(cursor, warehouse_id, name, location):
    cursor.execute("UPDATE warehouses SET name = ?, location = ? WHERE id = ?", (name, location, warehouse_id))

def delete_warehouse(cursor, warehouse_id):
    cursor.execute("DELETE FROM warehouses WHERE id = ?", (warehouse_id,))

def get_stock(cursor, warehouse_id, product_id):
    cursor.execute("SELECT quantity FROM warehouse_stocks WHERE warehouse_id = ? AND product_id = ?", (warehouse_id, product_id))
    res = cursor.fetchone()
    return res[0] if res else 0.0

def update_stock(cursor, warehouse_id, product_id, quantity):
    # Check if exists
    cursor.execute("SELECT id FROM warehouse_stocks WHERE warehouse_id = ? AND product_id = ?", (warehouse_id, product_id))
    if cursor.fetchone():
        cursor.execute("UPDATE warehouse_stocks SET quantity = ?, updated_at = datetime('now','localtime') WHERE warehouse_id = ? AND product_id = ?", (quantity, warehouse_id, product_id))
    else:
        cursor.execute("INSERT INTO warehouse_stocks (warehouse_id, product_id, quantity) VALUES (?, ?, ?)", (warehouse_id, product_id, quantity))

def add_movement(cursor, source_id, target_id, product_id, quantity, desc, user_id):
    cursor.execute("""
        INSERT INTO warehouse_movements (source_warehouse_id, target_warehouse_id, product_id, quantity, description, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (source_id, target_id, product_id, quantity, desc, user_id))
    return cursor.lastrowid

def list_movements(cursor, limit=50):
    cursor.execute("""
        SELECT m.id, 
               ws.name as source, 
               wt.name as target, 
               p.name as product, 
               m.quantity, 
               m.movement_date, 
               m.description,
               u.username
        FROM warehouse_movements m
        LEFT JOIN warehouses ws ON m.source_warehouse_id = ws.id
        LEFT JOIN warehouses wt ON m.target_warehouse_id = wt.id
        JOIN products p ON m.product_id = p.id
        LEFT JOIN users u ON m.user_id = u.id
        ORDER BY m.movement_date DESC LIMIT ?
    """, (limit,))
    return cursor.fetchall()

def list_warehouse_stocks(cursor, warehouse_id):
    cursor.execute("""
        SELECT p.name, ws.quantity, p.unit
        FROM warehouse_stocks ws
        JOIN products p ON ws.product_id = p.id
        WHERE ws.warehouse_id = ?
    """, (warehouse_id,))
    return cursor.fetchall()

def list_all_stocks(cursor):
    cursor.execute("""
        SELECT w.name, p.name, ws.quantity, p.unit
        FROM warehouse_stocks ws
        JOIN warehouses w ON ws.warehouse_id = w.id
        JOIN products p ON ws.product_id = p.id
        ORDER BY w.name, p.name
    """)
    return cursor.fetchall()
