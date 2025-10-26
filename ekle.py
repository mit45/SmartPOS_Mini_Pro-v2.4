import sqlite3
DB_PATH = "database.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


cursor.execute("ALTER TABLE sales ADD COLUMN fis_id TEXT")
conn.commit()
