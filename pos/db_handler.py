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
      stock INTEGER DEFAULT 0,
      buy_price REAL DEFAULT 0,
      sale_price REAL
    )""")

    # sales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      fis_id TEXT,
      product_name TEXT,
      quantity INTEGER,
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

    # Seeds
    cursor.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES (?,?,?)", ("admin","1234","admin"))
    cursor.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES (?,?,?)", ("kasiyer","1234","cashier"))
    cursor.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES (?,?,?)", ("cashier","1234","cashier"))
    conn.commit()
