import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3

# ==========================
# Veritabanı Başlangıcı
# ==========================
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price REAL,
    stock INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT,
    quantity INTEGER,
    total REAL
)
""")

# Varsayılan kullanıcı
cursor.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("admin", "1234"))
conn.commit()


# ==========================
# Giriş Ekranı
# ==========================
def login():
    username = entry_username.get()
    password = entry_password.get()
    cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()
    if user:
        open_main_window()
    else:
        messagebox.showerror("Hata", "Kullanıcı adı veya şifre hatalı!")


def open_main_window():
    login_window.destroy()

    main_window = tk.Tk()
    main_window.title("SmartPOS Mini")
    main_window.geometry("400x300")

    tk.Label(main_window, text="SmartPOS Mini", font=("Arial", 16, "bold")).pack(pady=10)

    ttk.Button(main_window, text="🛒 Ürün Ekle", command=add_product_window).pack(pady=5)
    ttk.Button(main_window, text="💰 Satış Yap", command=sell_product_window).pack(pady=5)
    ttk.Button(main_window, text="📊 Rapor Gör", command=show_report).pack(pady=5)
    ttk.Button(main_window, text="💾 Günlük Raporu Kaydet", command=export_daily_report).pack(pady=5)

    main_window.mainloop()


# ==========================
# Ürün Ekleme
# ==========================
def add_product_window():
    win = tk.Toplevel()
    win.title("Ürün Ekle")
    win.geometry("300x250")

    tk.Label(win, text="Ürün Adı:").pack()
    name = tk.Entry(win)
    name.pack()

    tk.Label(win, text="Fiyat:").pack()
    price = tk.Entry(win)
    price.pack()

    tk.Label(win, text="Stok:").pack()
    stock = tk.Entry(win)
    stock.pack()

    def save_product():
        cursor.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", 
                       (name.get(), float(price.get()), int(stock.get())))
        conn.commit()
        messagebox.showinfo("Başarılı", "Ürün eklendi!")
        win.destroy()

    ttk.Button(win, text="Kaydet", command=save_product).pack(pady=10)


# ==========================
# Satış Yapma
# ==========================
def sell_product_window():
    win = tk.Toplevel()
    win.title("Satış Yap")
    win.geometry("350x300")

    tk.Label(win, text="Ürün Seç:").pack()
    cursor.execute("SELECT name FROM products")
    products = [p[0] for p in cursor.fetchall()]

    product_cb = ttk.Combobox(win, values=products)
    product_cb.pack()

    tk.Label(win, text="Adet:").pack()
    quantity = tk.Entry(win)
    quantity.pack()

    def make_sale():
        product_name = product_cb.get()
        qty = int(quantity.get())
        cursor.execute("SELECT price, stock FROM products WHERE name=?", (product_name,))
        result = cursor.fetchone()
        if result:
            price, stock = result
            if qty <= stock:
                total = qty * price
                cursor.execute("UPDATE products SET stock = stock - ? WHERE name=?", (qty, product_name))
                cursor.execute("INSERT INTO sales (product_name, quantity, total) VALUES (?, ?, ?)",
                               (product_name, qty, total))
                conn.commit()
                messagebox.showinfo("Satış Başarılı", f"{product_name} - {qty} adet satıldı!\nToplam: {total} ₺")
                win.destroy()
            else:
                messagebox.showerror("Hata", "Yetersiz stok!")
        else:
            messagebox.showerror("Hata", "Ürün bulunamadı!")

    ttk.Button(win, text="Satışı Onayla", command=make_sale).pack(pady=10)


# ==========================
# Rapor Görüntüleme
# ==========================
def show_report():
    win = tk.Toplevel()
    win.title("Satış Raporu")
    win.geometry("400x300")

    tree = ttk.Treeview(win, columns=("Ürün", "Adet", "Toplam"), show="headings")
    tree.heading("Ürün", text="Ürün")
    tree.heading("Adet", text="Adet")
    tree.heading("Toplam", text="Toplam ₺")
    tree.pack(fill="both", expand=True)

    cursor.execute("SELECT product_name, quantity, total FROM sales")
    for row in cursor.fetchall():
        tree.insert("", "end", values=row)

# ==========================
# Günlük Satış Raporu Görüntüleme
# ==========================
import csv
import os
import subprocess
from datetime import datetime
from tkinter import messagebox

def export_daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"reports/rapor_{today}.csv"

    # "reports" klasörü yoksa oluştur
    if not os.path.exists("reports"):
        os.makedirs("reports")

    cursor.execute("SELECT product_name, quantity, total FROM sales")
    sales_data = cursor.fetchall()

    if not sales_data:
        messagebox.showinfo("Bilgi", "Bugün için kayıtlı satış yok.")
        return

    # CSV dosyasını oluştur
    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Ürün Adı", "Adet", "Toplam ₺"])
        writer.writerows(sales_data)

    # Bilgi mesajı
    messagebox.showinfo("Başarılı", f"Günlük rapor kaydedildi:\n{filename}")

    # Varsayılan programda (örneğin Excel) aç
    try:
        if os.name == 'nt':  # Windows
            os.startfile(filename)
        elif os.name == 'posix':  # macOS veya Linux
            subprocess.call(('open', filename))
    except Exception as e:
        messagebox.showerror("Hata", f"Rapor açılırken hata oluştu:\n{e}")



# ==========================
# Giriş Ekranı Başlat
# ==========================
login_window = tk.Tk()
login_window.title("Giriş Yap")
login_window.geometry("300x200")

tk.Label(login_window, text="SmartPOS Mini Giriş", font=("Arial", 12, "bold")).pack(pady=10)
tk.Label(login_window, text="Kullanıcı Adı:").pack()
entry_username = tk.Entry(login_window)
entry_username.pack()
tk.Label(login_window, text="Şifre:").pack()
entry_password = tk.Entry(login_window, show="*")
entry_password.pack()

ttk.Button(login_window, text="Giriş Yap", command=login).pack(pady=10)

login_window.mainloop()
