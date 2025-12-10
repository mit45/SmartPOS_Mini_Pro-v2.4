"""Database handler: centralize connection and schema initialization."""
import sqlite3

DB_PATH_DEFAULT = "database.db"

def get_connection(db_path: str = DB_PATH_DEFAULT):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    return conn, cursor


def init_schema(conn, cursor):
    # settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings(
      key TEXT PRIMARY KEY,
      value TEXT
    )""")

    # users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE,
      password TEXT,
      role TEXT
    )""")

    # products
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE,
      barcode TEXT,
      price REAL DEFAULT 0,
      stock REAL DEFAULT 0,
      buy_price REAL DEFAULT 0,
      sale_price REAL,
      unit TEXT DEFAULT 'adet'
    )""")

    # categories
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE NOT NULL,
      color TEXT
    )""")

    # sales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      fis_id TEXT,
      product_name TEXT,
      quantity REAL,
      price REAL,
      total REAL,
      payment_method TEXT DEFAULT 'cash',
      canceled INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # cariler (accounts receivable/payable)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cariler(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE NOT NULL,
      phone TEXT,
      address TEXT,
      balance REAL DEFAULT 0,
      cari_type TEXT DEFAULT 'alacakli',
      vergi_dairesi TEXT,
      vergi_no TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # cari_hareketler (account transactions)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cari_hareketler(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      cari_id INTEGER NOT NULL,
      islem_type TEXT NOT NULL,
      tutar REAL NOT NULL,
      aciklama TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (cari_id) REFERENCES cariler(id)
    )""")

    # services (hizmetler)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE NOT NULL,
      price REAL DEFAULT 0,
      description TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # expenses (masraflar)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      amount REAL NOT NULL,
      category TEXT,
      description TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # purchase_documents (satın alma belgeleri: irsaliye/fatura)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_documents(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      supplier_id INTEGER,
      doc_type TEXT, -- 'irsaliye' or 'fatura'
      doc_number TEXT,
      doc_date TEXT,
      total_amount REAL DEFAULT 0,
      description TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (supplier_id) REFERENCES cariler(id)
    )""")

    # purchase_items (satın alma kalemleri)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      doc_id INTEGER,
      product_id INTEGER,
      product_name TEXT,
      quantity REAL,
      price REAL,
      total REAL,
      FOREIGN KEY (doc_id) REFERENCES purchase_documents(id)
    )""")

    # personnel_shifts (vardiya)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS personnel_shifts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      start_time TEXT,
      end_time TEXT,
      note TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # personnel_payments (maaş/avans)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS personnel_payments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      amount REAL,
      payment_type TEXT, -- 'maas', 'avans', 'prim'
      payment_date TEXT,
      description TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # warehouses (depolar)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warehouses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE NOT NULL,
      location TEXT,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # warehouse_stocks (depo stokları)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warehouse_stocks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      warehouse_id INTEGER,
      product_id INTEGER,
      quantity REAL DEFAULT 0,
      updated_at TEXT DEFAULT (datetime('now','localtime')),
      FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
      FOREIGN KEY (product_id) REFERENCES products(id),
      UNIQUE(warehouse_id, product_id)
    )""")

    # warehouse_movements (depo hareketleri)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warehouse_movements(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source_warehouse_id INTEGER,
      target_warehouse_id INTEGER,
      product_id INTEGER,
      quantity REAL,
      movement_date TEXT DEFAULT (datetime('now','localtime')),
      description TEXT,
      user_id INTEGER,
      FOREIGN KEY (source_warehouse_id) REFERENCES warehouses(id),
      FOREIGN KEY (target_warehouse_id) REFERENCES warehouses(id),
      FOREIGN KEY (product_id) REFERENCES products(id),
      FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    # Backfill missing columns
    cursor.execute("PRAGMA table_info(sales)")
    existing_cols = {c[1] for c in cursor.fetchall()}
    for need in ("fis_id", "price", "payment_method", "canceled", "warehouse_id"):
        if need not in existing_cols:
            sql_type = 'TEXT' if need in ('fis_id', 'payment_method') else ('INTEGER' if need in ('canceled', 'warehouse_id') else 'REAL')
            cursor.execute(f"ALTER TABLE sales ADD COLUMN {need} {sql_type}")
            conn.commit()
            
    cursor.execute("PRAGMA table_info(purchase_documents)")
    pd_cols = {c[1] for c in cursor.fetchall()}
    if "warehouse_id" not in pd_cols:
        cursor.execute("ALTER TABLE purchase_documents ADD COLUMN warehouse_id INTEGER")
        conn.commit()

    # Ensure default warehouse exists
    cursor.execute("SELECT count(*) FROM warehouses")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO warehouses (name, location) VALUES (?, ?)", ("Merkez Depo", "Merkez"))
        conn.commit()
    
    # Migrate existing product stocks to default warehouse (Merkez Depo)
    # Find default warehouse id
    cursor.execute("SELECT id FROM warehouses ORDER BY id ASC LIMIT 1")
    default_wh = cursor.fetchone()
    if default_wh:
        wh_id = default_wh[0]
        # Find products with stock > 0 but no warehouse_stocks entry
        cursor.execute("""
            SELECT id, stock FROM products 
            WHERE stock > 0 
            AND id NOT IN (SELECT product_id FROM warehouse_stocks)
        """)
        products_to_migrate = cursor.fetchall()
        for pid, qty in products_to_migrate:
            # Insert into warehouse_stocks
            cursor.execute("INSERT INTO warehouse_stocks (warehouse_id, product_id, quantity) VALUES (?, ?, ?)", (wh_id, pid, qty))
            # Log movement
            cursor.execute("""
                INSERT INTO warehouse_movements (source_warehouse_id, target_warehouse_id, product_id, quantity, description, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (None, wh_id, pid, qty, "Stok Migrasyonu", 1))
        if products_to_migrate:
            conn.commit()

    # Backfill products columns

    # Backfill products columns
    cursor.execute("PRAGMA table_info(products)")
    prod_cols = {c[1] for c in cursor.fetchall()}
    if "barcode" not in prod_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN barcode TEXT")
        conn.commit()
    if "buy_price" not in prod_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN buy_price REAL DEFAULT 0")
        conn.commit()
    if "sale_price" not in prod_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN sale_price REAL")
        conn.commit()
        # migrate existing price to sale_price for compatibility
        try:
            cursor.execute("UPDATE products SET sale_price = price WHERE sale_price IS NULL")
            conn.commit()
        except Exception:
            pass
    if "unit" not in prod_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN unit TEXT DEFAULT 'adet'")
        conn.commit()
    if "category_id" not in prod_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN category_id INTEGER")
        conn.commit()

    # Seeds
    cursor.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES (?,?,?)", ("admin","1234","admin"))
    cursor.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES (?,?,?)", ("kasiyer","1234","cashier"))
    cursor.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES (?,?,?)", ("cashier","1234","cashier"))
    conn.commit()

    # quick_products (fast buttons/cards)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS quick_products(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          list_code TEXT NOT NULL,        -- 'main','list_1','list_2','list_3','list_4'
          name TEXT NOT NULL,
          price REAL NOT NULL DEFAULT 0,
          sort_order INTEGER DEFAULT 0,
          created_at TEXT DEFAULT (datetime('now','localtime'))
        )
        """
    )
    conn.commit()
