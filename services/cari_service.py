"""Cari Service - Business logic for accounts"""
from repositories import cari_repository as repo

def list_all(cursor):
    """Tüm carileri listele"""
    return repo.list_all(cursor)

def search_by_name(cursor, name):
    """İsme göre cari ara"""
    if not name or not name.strip():
        return repo.list_all(cursor)
    return repo.search_by_name(cursor, name.strip())

def get_by_id(cursor, cari_id):
    """ID'ye göre cari getir"""
    return repo.get_by_id(cursor, cari_id)

def get_by_name(cursor, name):
    """İsme göre cari getir"""
    return repo.get_by_name(cursor, name)

def add_cari(conn, cursor, name, phone, address, balance, cari_type):
    """Yeni cari ekle"""
    if not name or not name.strip():
        raise ValueError("Cari adı boş olamaz")
    
    name = name.strip()
    phone = phone.strip() if phone else ""
    address = address.strip() if address else ""
    
    try:
        balance = float(balance) if balance else 0.0
    except ValueError:
        raise ValueError("Geçersiz bakiye değeri")
    
    if cari_type not in ['alacakli', 'borclu']:
        cari_type = 'alacakli'
    
    repo.add(conn, cursor, name, phone, address, balance, cari_type)

def update_cari(conn, cursor, cari_id, name, phone, address, cari_type):
    """Cari bilgilerini güncelle"""
    if not name or not name.strip():
        raise ValueError("Cari adı boş olamaz")
    
    name = name.strip()
    phone = phone.strip() if phone else ""
    address = address.strip() if address else ""
    
    if cari_type not in ['alacakli', 'borclu']:
        cari_type = 'alacakli'
    
    repo.update(conn, cursor, cari_id, name, phone, address, cari_type)

def delete_cari(conn, cursor, cari_id):
    """Cari sil"""
    repo.delete(conn, cursor, cari_id)

def add_tahsilat(conn, cursor, cari_id, tutar, aciklama="Tahsilat"):
    """Tahsilat ekle (alacak azalır)"""
    if tutar <= 0:
        raise ValueError("Tahsilat tutarı pozitif olmalıdır")
    
    # Mevcut bakiyeyi al
    cari = repo.get_by_id(cursor, cari_id)
    if not cari:
        raise ValueError("Cari bulunamadı")
    
    current_balance = float(cari[4])
    new_balance = current_balance - tutar
    
    # Bakiyeyi güncelle
    repo.update_balance(conn, cursor, cari_id, new_balance)
    
    # Hareketi kaydet
    repo.add_hareket(conn, cursor, cari_id, "tahsilat", tutar, aciklama)

def add_odeme(conn, cursor, cari_id, tutar, aciklama="Ödeme"):
    """Ödeme ekle (borç azalır)"""
    if tutar <= 0:
        raise ValueError("Ödeme tutarı pozitif olmalıdır")
    
    # Mevcut bakiyeyi al
    cari = repo.get_by_id(cursor, cari_id)
    if not cari:
        raise ValueError("Cari bulunamadı")
    
    current_balance = float(cari[4])
    new_balance = current_balance + tutar
    
    # Bakiyeyi güncelle
    repo.update_balance(conn, cursor, cari_id, new_balance)
    
    # Hareketi kaydet
    repo.add_hareket(conn, cursor, cari_id, "odeme", tutar, aciklama)

def add_borc(conn, cursor, cari_id, tutar, aciklama="Borç"):
    """Borç ekle"""
    if tutar <= 0:
        raise ValueError("Borç tutarı pozitif olmalıdır")
    
    # Mevcut bakiyeyi al
    cari = repo.get_by_id(cursor, cari_id)
    if not cari:
        raise ValueError("Cari bulunamadı")
    
    current_balance = float(cari[4])
    new_balance = current_balance - tutar
    
    # Bakiyeyi güncelle
    repo.update_balance(conn, cursor, cari_id, new_balance)
    
    # Hareketi kaydet
    repo.add_hareket(conn, cursor, cari_id, "borc", tutar, aciklama)

def add_alacak(conn, cursor, cari_id, tutar, aciklama="Alacak"):
    """Alacak ekle"""
    if tutar <= 0:
        raise ValueError("Alacak tutarı pozitif olmalıdır")
    
    # Mevcut bakiyeyi al
    cari = repo.get_by_id(cursor, cari_id)
    if not cari:
        raise ValueError("Cari bulunamadı")
    
    current_balance = float(cari[4])
    new_balance = current_balance + tutar
    
    # Bakiyeyi güncelle
    repo.update_balance(conn, cursor, cari_id, new_balance)
    
    # Hareketi kaydet
    repo.add_hareket(conn, cursor, cari_id, "alacak", tutar, aciklama)

def list_hareketler(cursor, cari_id):
    """Carinin hareketlerini listele"""
    return repo.list_hareketler(cursor, cari_id)

def get_total_alacak(cursor):
    """Toplam alacak"""
    return repo.get_total_alacak(cursor)

def get_total_borc(cursor):
    """Toplam borç"""
    return repo.get_total_borc(cursor)
