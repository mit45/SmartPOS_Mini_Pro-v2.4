from datetime import datetime

def get_cash_movements(cursor, start_date=None, end_date=None):
    # Combine Sales (Cash), Cari Tahsilat/Odeme, Expenses
    movements = []
    
    # 1. Sales (Cash)
    query = "SELECT id, created_at, 'Satış', total, 'Giriş', fis_id FROM sales WHERE payment_method='cash' AND (canceled=0 OR canceled IS NULL)"
    params = []
    if start_date:
        query += " AND date(created_at) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date(created_at) <= ?"
        params.append(end_date)
    
    cursor.execute(query, params)
    for r in cursor.fetchall():
        movements.append({
            'id': r[0], 'date': r[1], 'type': r[2], 'amount': r[3], 'direction': r[4], 'desc': r[5]
        })

    # 2. Cari Hareketler
    # islem_type: 'tahsilat' (Giriş), 'odeme' (Çıkış)
    query = """
        SELECT ch.id, ch.created_at, 
               CASE WHEN ch.islem_type='tahsilat' THEN 'Cari Tahsilat' ELSE 'Cari Ödeme' END,
               ch.tutar,
               CASE WHEN ch.islem_type='tahsilat' THEN 'Giriş' ELSE 'Çıkış' END,
               c.name || ' - ' || COALESCE(ch.aciklama, '')
        FROM cari_hareketler ch
        JOIN cariler c ON ch.cari_id = c.id
        WHERE ch.islem_type IN ('tahsilat', 'odeme')
    """
    params = []
    if start_date:
        query += " AND date(ch.created_at) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date(ch.created_at) <= ?"
        params.append(end_date)
        
    cursor.execute(query, params)
    for r in cursor.fetchall():
        movements.append({
            'id': r[0], 'date': r[1], 'type': r[2], 'amount': r[3], 'direction': r[4], 'desc': r[5]
        })

    # 3. Expenses
    query = "SELECT id, created_at, 'Masraf', amount, 'Çıkış', title || ' - ' || COALESCE(description,'') FROM expenses WHERE 1=1"
    params = []
    if start_date:
        query += " AND date(created_at) >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date(created_at) <= ?"
        params.append(end_date)
        
    cursor.execute(query, params)
    for r in cursor.fetchall():
        movements.append({
            'id': r[0], 'date': r[1], 'type': r[2], 'amount': r[3], 'direction': r[4], 'desc': r[5]
        })
        
    # Sort by date desc
    movements.sort(key=lambda x: x['date'], reverse=True)
    return movements

def get_cash_summary(cursor, date=None):
    # Calculate total In/Out for a specific date (or today if None)
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
        
    summary = {'in': 0.0, 'out': 0.0, 'balance': 0.0}
    
    # Sales
    cursor.execute("SELECT SUM(total) FROM sales WHERE payment_method='cash' AND (canceled=0 OR canceled IS NULL) AND date(created_at)=?", (date,))
    res = cursor.fetchone()
    summary['in'] += res[0] if res and res[0] else 0.0
    
    # Cari Tahsilat
    cursor.execute("SELECT SUM(tutar) FROM cari_hareketler WHERE islem_type='tahsilat' AND date(created_at)=?", (date,))
    res = cursor.fetchone()
    summary['in'] += res[0] if res and res[0] else 0.0
    
    # Cari Ödeme
    cursor.execute("SELECT SUM(tutar) FROM cari_hareketler WHERE islem_type='odeme' AND date(created_at)=?", (date,))
    res = cursor.fetchone()
    summary['out'] += res[0] if res and res[0] else 0.0
    
    # Expenses
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE date(created_at)=?", (date,))
    res = cursor.fetchone()
    summary['out'] += res[0] if res and res[0] else 0.0
    
    summary['balance'] = summary['in'] - summary['out']
    return summary
