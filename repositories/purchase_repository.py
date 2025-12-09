"""Purchase Repository"""

def add_document(conn, cursor, supplier_id, doc_type, doc_number, doc_date, total_amount, description):
    cursor.execute("""
        INSERT INTO purchase_documents(supplier_id, doc_type, doc_number, doc_date, total_amount, description)
        VALUES(?,?,?,?,?,?)
    """, (supplier_id, doc_type, doc_number, doc_date, total_amount, description))
    conn.commit()
    return cursor.lastrowid

def add_item(conn, cursor, doc_id, product_id, product_name, quantity, price, total):
    cursor.execute("""
        INSERT INTO purchase_items(doc_id, product_id, product_name, quantity, price, total)
        VALUES(?,?,?,?,?,?)
    """, (doc_id, product_id, product_name, quantity, price, total))
    conn.commit()

def list_documents(cursor, doc_type=None):
    sql = """
        SELECT d.id, c.name, d.doc_type, d.doc_number, d.doc_date, d.total_amount, d.description
        FROM purchase_documents d
        LEFT JOIN cariler c ON d.supplier_id = c.id
    """
    params = []
    if doc_type:
        sql += " WHERE d.doc_type = ?"
        params.append(doc_type)
    
    sql += " ORDER BY d.created_at DESC"
    cursor.execute(sql, tuple(params))
    return cursor.fetchall()

def get_document_items(cursor, doc_id):
    cursor.execute("SELECT product_name, quantity, price, total, product_id FROM purchase_items WHERE doc_id=?", (doc_id,))
    return cursor.fetchall()

def get_document(cursor, doc_id):
    cursor.execute("SELECT * FROM purchase_documents WHERE id=?", (doc_id,))
    return cursor.fetchone()

def delete_document(conn, cursor, doc_id):
    cursor.execute("DELETE FROM purchase_items WHERE doc_id=?", (doc_id,))
    cursor.execute("DELETE FROM purchase_documents WHERE id=?", (doc_id,))
    conn.commit()

def update_document(conn, cursor, doc_id, supplier_id, doc_number, doc_date, total_amount, description):
    cursor.execute("""
        UPDATE purchase_documents 
        SET supplier_id=?, doc_number=?, doc_date=?, total_amount=?, description=?
        WHERE id=?
    """, (supplier_id, doc_number, doc_date, total_amount, description, doc_id))
    conn.commit()

def delete_items(conn, cursor, doc_id):
    cursor.execute("DELETE FROM purchase_items WHERE doc_id=?", (doc_id,))
    conn.commit()
