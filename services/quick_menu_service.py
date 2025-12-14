from repositories import quick_menu_repository as repo

def list_quick_products(cursor, list_code):
    return repo.list_by_code(cursor, list_code)

def get_quick_product(cursor, pid):
    return repo.get_by_id(cursor, pid)

def add_quick_product(conn, cursor, list_code, name, price, sort_order=0):
    pid = repo.insert(cursor, list_code, name, price, sort_order)
    conn.commit()
    return pid

def update_quick_product(conn, cursor, pid, list_code, name, price, sort_order=0):
    repo.update(cursor, pid, list_code, name, price, sort_order)
    conn.commit()

def delete_quick_product(conn, cursor, pid):
    repo.delete(cursor, pid)
    conn.commit()
