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

    # Backfill missing columns
    cursor.execute("PRAGMA table_info(sales)")
    existing_cols = {c[1] for c in cursor.fetchall()}
    for need in ("fis_id", "price", "payment_method", "canceled"):
        if need not in existing_cols:
            sql_type = 'TEXT' if need in ('fis_id', 'payment_method') else ('INTEGER' if need=='canceled' else 'REAL')
            cursor.execute(f"ALTER TABLE sales ADD COLUMN {need} {sql_type}")
            conn.commit()

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
