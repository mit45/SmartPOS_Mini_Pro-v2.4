import sqlite3

def list_by_code(cursor, list_code):
    cursor.execute("SELECT id, list_code, name, price, sort_order FROM quick_products WHERE list_code=? ORDER BY sort_order, id", (list_code,))
    return cursor.fetchall()

def get_by_id(cursor, pid):
    cursor.execute("SELECT id, list_code, name, price, sort_order FROM quick_products WHERE id=?", (pid,))
    return cursor.fetchone()

def insert(cursor, list_code, name, price, sort_order=0):
    cursor.execute("INSERT INTO quick_products(list_code, name, price, sort_order) VALUES(?,?,?,?)", (list_code, name, price, sort_order))
    return cursor.lastrowid

def update(cursor, pid, list_code, name, price, sort_order):
    cursor.execute("UPDATE quick_products SET list_code=?, name=?, price=?, sort_order=? WHERE id=?", (list_code, name, price, sort_order, pid))

def delete(cursor, pid):
    cursor.execute("DELETE FROM quick_products WHERE id=?", (pid,))
