"""Purchase Service"""
from repositories import purchase_repository as repo
from repositories import product_repository as prod_repo
from repositories import cari_repository as cari_repo

def create_purchase(conn, cursor, supplier_id, doc_type, doc_number, doc_date, items, description=""):
    """
    Satın alma işlemini kaydeder.
    items: list of dict {'product_id': int, 'name': str, 'qty': float, 'price': float}
    """
    # 1. Belgeyi oluştur
    total_amount = sum(item['qty'] * item['price'] for item in items)
    doc_id = repo.add_document(conn, cursor, supplier_id, doc_type, doc_number, doc_date, total_amount, description)
    
    # 2. Kalemleri ekle ve stok güncelle
    for item in items:
        total = item['qty'] * item['price']
        repo.add_item(conn, cursor, doc_id, item.get('product_id'), item['name'], item['qty'], item['price'], total)
        
        # Stok artır
        if item.get('product_id'):
            # Mevcut stok bilgisini al
            prod = prod_repo.get_by_id(cursor, item['product_id'])
            if prod:
                current_stock = prod[4]
                new_stock = current_stock + item['qty']
                prod_repo.update_stock(conn, cursor, item['product_id'], new_stock)
                
                # Alış fiyatını güncelle (isteğe bağlı, son alış fiyatı)
                if item['price'] > 0:
                    prod_repo.update_buy_price(conn, cursor, item['product_id'], item['price'])

    # 3. Cari hareket işle (Eğer fatura ise borçlanma/alacaklanma durumu)
    # İrsaliye stok etkiler, cariyi etkilemez (genelde). Fatura cariyi etkiler.
    if doc_type == 'fatura' and supplier_id:
        # Tedarikçiye borçlanıyoruz (Alacak ekle)
        # Cari bakiyesi: Alacaklı (+) ise biz borçluyuz.
        cari_repo.add_hareket(conn, cursor, supplier_id, "alacak", total_amount, f"Alış Faturası: {doc_number}")
        
        # Bakiyeyi güncelle
        cari = cari_repo.get_by_id(cursor, supplier_id)
        if cari:
            current_balance = cari[4]
            new_balance = current_balance + total_amount # Alacak artıyor
            cari_repo.update_balance(conn, cursor, supplier_id, new_balance)

    return doc_id

def list_documents(cursor, doc_type=None):
    return repo.list_documents(cursor, doc_type)

def get_document_items(cursor, doc_id):
    return repo.get_document_items(cursor, doc_id)

def get_document(cursor, doc_id):
    return repo.get_document(cursor, doc_id)

def _revert_purchase_effects(conn, cursor, doc_id):
    """Belgenin stok ve cari etkilerini geri alır."""
    doc = repo.get_document(cursor, doc_id)
    if not doc: return
    
    supplier_id = doc[1]
    doc_type = doc[2]
    doc_number = doc[3]
    total_amount = doc[5]
    
    # Stoktan düş
    items = repo.get_document_items(cursor, doc_id)
    for item in items:
        product_id = item[4]
        qty = item[1]
        if product_id:
            prod = prod_repo.get_by_id(cursor, product_id)
            if prod:
                current_stock = prod[4]
                new_stock = current_stock - qty
                prod_repo.update_stock(conn, cursor, product_id, new_stock)

    # Cariyi düzelt (Fatura ise)
    if doc_type == 'fatura' and supplier_id:
        cari_repo.add_hareket(conn, cursor, supplier_id, "borc", total_amount, f"DÜZELTME/İPTAL - Fatura: {doc_number}")
        cari = cari_repo.get_by_id(cursor, supplier_id)
        if cari:
            current_balance = cari[4]
            new_balance = current_balance - total_amount
            cari_repo.update_balance(conn, cursor, supplier_id, new_balance)

def delete_purchase(conn, cursor, doc_id):
    """Satın alma işlemini siler ve stok/cari etkilerini geri alır."""
    _revert_purchase_effects(conn, cursor, doc_id)
    repo.delete_document(conn, cursor, doc_id)

def update_purchase(conn, cursor, doc_id, supplier_id, doc_number, doc_date, items, description=""):
    """Satın alma işlemini günceller."""
    # 1. Eski etkileri geri al
    _revert_purchase_effects(conn, cursor, doc_id)
    
    # 2. Belge başlığını güncelle
    doc = repo.get_document(cursor, doc_id)
    doc_type = doc[2]
    total_amount = sum(item['qty'] * item['price'] for item in items)
    
    repo.update_document(conn, cursor, doc_id, supplier_id, doc_number, doc_date, total_amount, description)
    
    # 3. Eski kalemleri sil
    repo.delete_items(conn, cursor, doc_id)
    
    # 4. Yeni kalemleri ekle ve etkilerini uygula
    for item in items:
        total = item['qty'] * item['price']
        repo.add_item(conn, cursor, doc_id, item.get('product_id'), item['name'], item['qty'], item['price'], total)
        
        # Stok artır
        if item.get('product_id'):
            prod = prod_repo.get_by_id(cursor, item['product_id'])
            if prod:
                current_stock = prod[4]
                new_stock = current_stock + item['qty']
                prod_repo.update_stock(conn, cursor, item['product_id'], new_stock)
                if item['price'] > 0:
                    prod_repo.update_buy_price(conn, cursor, item['product_id'], item['price'])

    # 5. Yeni cari etkisini uygula (Fatura ise)
    if doc_type == 'fatura' and supplier_id:
        cari_repo.add_hareket(conn, cursor, supplier_id, "alacak", total_amount, f"GÜNCELLEME - Fatura: {doc_number}")
        cari = cari_repo.get_by_id(cursor, supplier_id)
        if cari:
            current_balance = cari[4]
            new_balance = current_balance + total_amount
            cari_repo.update_balance(conn, cursor, supplier_id, new_balance)
