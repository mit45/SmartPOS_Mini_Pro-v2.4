import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM settings WHERE key='language'")
conn.commit()
conn.close()
print("Dil ayari silindi - program yeniden baslatildiginda dil secimi sorulacak")
