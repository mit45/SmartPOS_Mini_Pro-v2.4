"""Expense & Service Repository"""

# --- SERVICES ---
def list_services(cursor):
    cursor.execute("SELECT id, name, price, description FROM services ORDER BY name")
    return cursor.fetchall()

def add_service(conn, cursor, name, price, description):
    cursor.execute("INSERT INTO services(name, price, description) VALUES(?,?,?)", (name, price, description))
    conn.commit()

def update_service(conn, cursor, service_id, name, price, description):
    cursor.execute("UPDATE services SET name=?, price=?, description=? WHERE id=?", (name, price, description, service_id))
    conn.commit()

def delete_service(conn, cursor, service_id):
    cursor.execute("DELETE FROM services WHERE id=?", (service_id,))
    conn.commit()

# --- EXPENSES ---
def list_expenses(cursor):
    cursor.execute("SELECT id, title, amount, category, description, created_at FROM expenses ORDER BY created_at DESC")
    return cursor.fetchall()

def add_expense(conn, cursor, title, amount, category, description):
    cursor.execute("INSERT INTO expenses(title, amount, category, description) VALUES(?,?,?,?)", (title, amount, category, description))
    conn.commit()

def delete_expense(conn, cursor, expense_id):
    cursor.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()

def get_total_expenses(cursor, start_date=None, end_date=None):
    if start_date and end_date:
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE date(created_at) BETWEEN ? AND ?", (start_date, end_date))
    else:
        cursor.execute("SELECT SUM(amount) FROM expenses")
    result = cursor.fetchone()
    return result[0] if result and result[0] else 0.0
