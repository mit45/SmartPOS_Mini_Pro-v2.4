from repositories import warehouse_repository as repo

def list_warehouses(cursor):
    return repo.list_warehouses(cursor)

def add_warehouse(conn, cursor, name, location):
    repo.add_warehouse(cursor, name, location)
    conn.commit()

def update_warehouse(conn, cursor, warehouse_id, name, location):
    repo.update_warehouse(cursor, warehouse_id, name, location)
    conn.commit()

def delete_warehouse(conn, cursor, warehouse_id):
    repo.delete_warehouse(cursor, warehouse_id)
    conn.commit()

def list_warehouse_stocks(cursor, warehouse_id):
    return repo.list_warehouse_stocks(cursor, warehouse_id)

def list_all_stocks(cursor):
    return repo.list_all_stocks(cursor)

def transfer_stock(conn, cursor, source_id, target_id, product_id, quantity, desc, user_id):
    # 1. Check source stock
    current_source = repo.get_stock(cursor, source_id, product_id)
    if current_source < quantity:
        raise ValueError("Yetersiz stok!")
    
    # 2. Decrement source
    repo.update_stock(cursor, source_id, product_id, current_source - quantity)
    
    # 3. Increment target
    current_target = repo.get_stock(cursor, target_id, product_id)
    repo.update_stock(cursor, target_id, product_id, current_target + quantity)
    
    # 4. Record movement
    repo.add_movement(cursor, source_id, target_id, product_id, quantity, desc, user_id)
    conn.commit()

def list_movements(cursor):
    return repo.list_movements(cursor)
