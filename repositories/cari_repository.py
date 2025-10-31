"""Cari Repository - Database operations for accounts"""

def list_all(cursor):
    """Tüm carileri listele"""
    cursor.execute("SELECT id, name, phone, address, balance, cari_type FROM cariler ORDER BY name")
    return cursor.fetchall()

def search_by_name(cursor, name):
    """İsme göre cari ara"""
    cursor.execute("SELECT id, name, phone, address, balance, cari_type FROM cariler WHERE name LIKE ? ORDER BY name", (f"%{name}%",))
    return cursor.fetchall()

def get_by_id(cursor, cari_id):
    """ID'ye göre cari getir"""
    cursor.execute("SELECT id, name, phone, address, balance, cari_type FROM cariler WHERE id=?", (cari_id,))
    return cursor.fetchone()

def get_by_name(cursor, name):
    """İsme göre cari getir"""
    cursor.execute("SELECT id, name, phone, address, balance, cari_type FROM cariler WHERE name=?", (name,))
    return cursor.fetchone()

def add(conn, cursor, name, phone, address, balance, cari_type):
    """Yeni cari ekle"""
    cursor.execute(
        "INSERT INTO cariler(name, phone, address, balance, cari_type) VALUES(?,?,?,?,?)",
        (name, phone, address, balance, cari_type)
    )
    conn.commit()

def update(conn, cursor, cari_id, name, phone, address, cari_type):
    """Cari bilgilerini güncelle (bakiye hariç)"""
    cursor.execute(
        "UPDATE cariler SET name=?, phone=?, address=?, cari_type=? WHERE id=?",
        (name, phone, address, cari_type, cari_id)
    )
    conn.commit()

def update_balance(conn, cursor, cari_id, new_balance):
    """Cari bakiyesini güncelle"""
    cursor.execute("UPDATE cariler SET balance=? WHERE id=?", (new_balance, cari_id))
    conn.commit()

def delete(conn, cursor, cari_id):
    """Cari sil"""
    cursor.execute("DELETE FROM cariler WHERE id=?", (cari_id,))
    conn.commit()

# Cari Hareketler
def add_hareket(conn, cursor, cari_id, islem_type, tutar, aciklama):
    """Cari hareketi ekle"""
    cursor.execute(
        "INSERT INTO cari_hareketler(cari_id, islem_type, tutar, aciklama) VALUES(?,?,?,?)",
        (cari_id, islem_type, tutar, aciklama)
    )
    conn.commit()

def list_hareketler(cursor, cari_id):
    """Carinin tüm hareketlerini listele"""
    cursor.execute(
        "SELECT id, islem_type, tutar, aciklama, created_at FROM cari_hareketler WHERE cari_id=? ORDER BY created_at DESC",
        (cari_id,)
    )
    return cursor.fetchall()

def get_total_alacak(cursor):
    """Toplam alacak"""
    cursor.execute("SELECT SUM(balance) FROM cariler WHERE cari_type='alacakli' AND balance > 0")
    result = cursor.fetchone()
    return result[0] if result[0] else 0

def get_total_borc(cursor):
    """Toplam borç"""
    cursor.execute("SELECT SUM(ABS(balance)) FROM cariler WHERE cari_type='borclu' AND balance < 0")
    result = cursor.fetchone()
    return result[0] if result[0] else 0
