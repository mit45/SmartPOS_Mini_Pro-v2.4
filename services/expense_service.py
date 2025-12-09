"""Expense & Service Service"""
from repositories import expense_repository as repo

# --- SERVICES ---
def list_services(cursor):
    return repo.list_services(cursor)

def add_service(conn, cursor, name, price, description):
    if not name:
        raise ValueError("Hizmet adı boş olamaz")
    try:
        price = float(price)
    except:
        price = 0.0
    repo.add_service(conn, cursor, name, price, description)

def update_service(conn, cursor, service_id, name, price, description):
    if not name:
        raise ValueError("Hizmet adı boş olamaz")
    try:
        price = float(price)
    except:
        price = 0.0
    repo.update_service(conn, cursor, service_id, name, price, description)

def delete_service(conn, cursor, service_id):
    repo.delete_service(conn, cursor, service_id)

# --- EXPENSES ---
def list_expenses(cursor):
    return repo.list_expenses(cursor)

def add_expense(conn, cursor, title, amount, category, description):
    if not title:
        raise ValueError("Masraf başlığı boş olamaz")
    try:
        amount = float(amount)
    except:
        raise ValueError("Geçersiz tutar")
    
    repo.add_expense(conn, cursor, title, amount, category, description)

def delete_expense(conn, cursor, expense_id):
    repo.delete_expense(conn, cursor, expense_id)

def get_total_expenses(cursor, start_date=None, end_date=None):
    return repo.get_total_expenses(cursor, start_date, end_date)
