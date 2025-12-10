import sqlite3
from datetime import datetime

def start_shift(cursor, user_id, note=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO personnel_shifts (user_id, start_time, note)
        VALUES (?, ?, ?)
    """, (user_id, now, note))
    return cursor.lastrowid

def end_shift(cursor, shift_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE personnel_shifts
        SET end_time = ?
        WHERE id = ?
    """, (now, shift_id))

def get_active_shift(cursor, user_id):
    cursor.execute("""
        SELECT id, start_time, note FROM personnel_shifts
        WHERE user_id = ? AND end_time IS NULL
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    return cursor.fetchone()

def list_shifts(cursor, user_id=None, limit=50):
    if user_id:
        cursor.execute("""
            SELECT s.id, u.username, s.start_time, s.end_time, s.note
            FROM personnel_shifts s
            JOIN users u ON s.user_id = u.id
            WHERE s.user_id = ?
            ORDER BY s.id DESC LIMIT ?
        """, (user_id, limit))
    else:
        cursor.execute("""
            SELECT s.id, u.username, s.start_time, s.end_time, s.note
            FROM personnel_shifts s
            JOIN users u ON s.user_id = u.id
            ORDER BY s.id DESC LIMIT ?
        """, (limit,))
    return cursor.fetchall()

def add_payment(cursor, user_id, amount, ptype, date, desc):
    cursor.execute("""
        INSERT INTO personnel_payments (user_id, amount, payment_type, payment_date, description)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, amount, ptype, date, desc))
    return cursor.lastrowid

def list_payments(cursor, user_id=None, limit=50):
    if user_id:
        cursor.execute("""
            SELECT p.id, u.username, p.amount, p.payment_type, p.payment_date, p.description
            FROM personnel_payments p
            JOIN users u ON p.user_id = u.id
            WHERE p.user_id = ?
            ORDER BY p.payment_date DESC LIMIT ?
        """, (user_id, limit))
    else:
        cursor.execute("""
            SELECT p.id, u.username, p.amount, p.payment_type, p.payment_date, p.description
            FROM personnel_payments p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.payment_date DESC LIMIT ?
        """, (limit,))
    return cursor.fetchall()
