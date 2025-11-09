import sqlite3

DB='database.db'

CATEGORIES = [
    'Temel Gıda','İçecekler','Şarküteri','Kahvaltılık','Makarna & Pirinç','Bakliyat','Yağ',
    'Temizlik','Kişisel Bakım','Konserve','Atıştırmalık','Dondurulmuş','Baharat','Çay & Kahve',
    'Meyve','Kuru Meyve','Un & Kepek','Yumurta Ürünleri','Et Ürünleri','Fırın Ürünleri','Tatlı','Diğer'
]

# Ürün -> Kategori eşlemesi (add_products.py ile eklenen isimlere göre)
MAP = {
    # Temel Gıda
    'Ekmek':'Temel Gıda','Süt 1L':'Temel Gıda','Yumurta 10lu':'Temel Gıda','Beyaz Peynir Kg':'Temel Gıda','Kaşar Peynir Kg':'Temel Gıda',
    'Zeytin 500g':'Temel Gıda','Domates Kg':'Temel Gıda','Salatalık Kg':'Temel Gıda','Patates Kg':'Temel Gıda','Soğan Kg':'Temel Gıda',
    # İçecekler
    'Coca Cola 1L':'İçecekler','Coca Cola 2.5L':'İçecekler','Fanta 1L':'İçecekler','Sprite 1L':'İçecekler','Ayran 1L':'İçecekler',
    'Maden Suyu 1L':'İçecekler','Şalgam 1L':'İçecekler','Limonata 1L':'İçecekler','Portakal Suyu 1L':'İçecekler','Elma Suyu 1L':'İçecekler',
    # Şarküteri
    'Salam Dana 150g':'Şarküteri','Sosis 500g':'Şarküteri','Sucuk Kg':'Şarküteri','Pastırma 100g':'Şarküteri','Kavurma 250g':'Şarküteri',
    # Kahvaltılık
    'Bal 500g':'Kahvaltılık','Reçel 380g':'Kahvaltılık','Tahin 350g':'Kahvaltılık','Pekmez 700g':'Kahvaltılık','Tereyağı 500g':'Kahvaltılık',
    # Makarna & Pirinç
    'Makarna 500g':'Makarna & Pirinç','Spagetti 500g':'Makarna & Pirinç','Pirinç Kg':'Makarna & Pirinç','Bulgur Kg':'Makarna & Pirinç','Mercimek Kg':'Makarna & Pirinç',
    # Bakliyat
    'Nohut Kg':'Bakliyat','Fasulye Kg':'Bakliyat','Barbunya Kg':'Bakliyat',
    # Yağ
    'Ayçiçek Yağı 1L':'Yağ','Zeytinyağı 1L':'Yağ',
    # Temizlik
    'Çamaşır Deterjanı':'Temizlik','Bulaşık Deterjanı':'Temizlik','Tuvalet Kağıdı 16lı':'Temizlik','Peçete 100lü':'Temizlik','Çöp Poşeti 10lu':'Temizlik',
    # Kişisel Bakım
    'Şampuan 500ml':'Kişisel Bakım','Sabun 6lı':'Kişisel Bakım','Diş Macunu':'Kişisel Bakım','Traş Köpüğü':'Kişisel Bakım',
    # Konserve
    'Ton Balığı 160g':'Konserve','Domates Salçası 720g':'Konserve','Biber Salçası 720g':'Konserve','Konserve Bezelye':'Konserve','Konserve Mısır':'Konserve',
    # Atıştırmalık
    'Cips 150g':'Atıştırmalık','Bisküvi 200g':'Atıştırmalık','Çikolata 80g':'Atıştırmalık','Gofret 40g':'Atıştırmalık','Kuruyemiş Karışık 200g':'Atıştırmalık',
    # Dondurulmuş
    'Dondurma 1L':'Dondurulmuş','Patates Kızartması 1Kg':'Dondurulmuş','Pizza 350g':'Dondurulmuş',
    # Baharat
    'Tuz 1Kg':'Baharat','Şeker 1Kg':'Baharat','Karabiber 50g':'Baharat','Kırmızı Biber 50g':'Baharat','Kimyon 50g':'Baharat',
    # Çay & Kahve
    'Çay 1Kg':'Çay & Kahve','Türk Kahvesi 250g':'Çay & Kahve','Hazır Kahve 200g':'Çay & Kahve',
    # Meyve
    'Elma Kg':'Meyve','Muz Kg':'Meyve','Portakal Kg':'Meyve','Mandalina Kg':'Meyve','Üzüm Kg':'Meyve',
    # Kuru Meyve
    'Kuru İncir 250g':'Kuru Meyve','Kuru Kayısı 250g':'Kuru Meyve','Kuru Üzüm 250g':'Kuru Meyve','Ceviz Kg':'Kuru Meyve','Fındık Kg':'Kuru Meyve',
    # Un & Kepek
    'Un 1Kg':'Un & Kepek','Mısır Unu 1Kg':'Un & Kepek',
    # Yumurta Ürünleri
    'Köy Yumurtası 10lu':'Yumurta Ürünleri',
    # Et Ürünleri
    'Dana Kıyma Kg':'Et Ürünleri','Kuzu Pirzola Kg':'Et Ürünleri','Tavuk But Kg':'Et Ürünleri','Tavuk Göğüs Kg':'Et Ürünleri',
    # Fırın Ürünleri
    'Simit':'Fırın Ürünleri','Açma':'Fırın Ürünleri','Poğaça':'Fırın Ürünleri','Börek Dilim':'Fırın Ürünleri',
    # Tatlı
    'Baklava Kg':'Tatlı','Künefe Porsiyon':'Tatlı','Tulumba':'Tatlı',
    # Diğer
    'Kağıt Havlu':'Diğer','Alüminyum Folyo':'Diğer','Streç Film':'Diğer','Kibrit':'Diğer','Çakmak':'Diğer','Pil AA 4lü':'Diğer',
}

def main():
    conn=sqlite3.connect(DB)
    cur=conn.cursor()

    # Kategorileri ekle (varsa yok say)
    for cat in CATEGORIES:
        cur.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (cat,))
    conn.commit()

    # İsim->id haritası
    cur.execute("SELECT id,name FROM categories")
    rows = cur.fetchall()
    cat_map = { name: cid for (cid, name) in rows }  # name->id

    updated=0; missing=[]
    for pname, cat_name in MAP.items():
        cid = cat_map.get(cat_name)
        if not cid:
            missing.append((pname, cat_name)); continue
        cur.execute("UPDATE products SET category_id=? WHERE name=?", (cid, pname))
        updated += cur.rowcount

    conn.commit()

    # Rapor
    cur.execute("SELECT c.name, COUNT(1) FROM products p LEFT JOIN categories c ON c.id=p.category_id GROUP BY c.name ORDER BY c.name")
    counts = cur.fetchall()
    print("Kategori dağılımı:")
    for name, cnt in counts:
        print(f" - {name or 'Bilinmiyor'}: {cnt}")
    if missing:
        print("Eşleşmeyen ürünler:")
        for pname, cat_name in missing:
            print(f" - {pname} -> {cat_name} (kategori bulunamadı)")
    print(f"Güncellenen ürün sayısı: {updated}")

    conn.close()

if __name__=='__main__':
    main()
