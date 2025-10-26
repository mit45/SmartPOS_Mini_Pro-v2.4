import tkinter as tk
from tkinter import messagebox, ttk, Label, Tk
import sqlite3
import os, sys

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from PIL import Image, ImageTk   # Logo için

# Tema ayarları
BG_COLOR = "#2b2b2b"
FG_COLOR = "#ffffff"
ACCENT = "#0078D7"

def set_theme(window):
    window.configure(bg=BG_COLOR)
    style = ttk.Style()
    style.theme_use("clam")

    style.configure("TButton",
                    background=ACCENT,
                    foreground="white",
                    font=("Arial", 11, "bold"),
                    padding=6)
    style.map("TButton",
              background=[("active", "#005a9e")])

    style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR, font=("Arial", 10))
    style.configure("Header.TLabel", background=BG_COLOR, foreground=ACCENT, font=("Arial", 16, "bold"))

def show_logo(window):
    try:
        img = Image.open("smartpos_logo.png")
        img = img.resize((100, 100))
        logo_img = ImageTk.PhotoImage(img)
        label = tk.Label(window, image=logo_img, bg=BG_COLOR)
        label.image = logo_img # type: ignore
        label.pack(pady=5)
    except:
        pass  # logo yoksa hata verme


# ==========================
# Veritabanı Başlangıcı
# ==========================
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Kullanıcı tablosuna role sütunu ekle
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
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

# Varsayılan kullanıcılar
cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", "1234", "admin"))
cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", ("kasiyer", "1234", "cashier"))
conn.commit()


# ==========================
# Giriş Ekranı
# ==========================
def login():
    username = entry_username.get()
    password = entry_password.get()
    cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()

    if user:
        role = user[0]
        open_main_window(role)
    else:
        messagebox.showerror("Hata", "Kullanıcı adı veya şifre hatalı!")



def open_main_window(role):
    login_window.destroy()

    main_window = tk.Tk()
    main_window.title(f"SmartPOS Mini - {role.upper()}")
    main_window.geometry("400x550")
    set_theme(main_window)

    tk.Label(main_window, text="SmartPOS Mini", font=("Arial", 16, "bold")).pack(pady=10)

    if role == "admin":
        ttk.Button(main_window, text="🛒 Ürün Ekle", command=add_product_window).pack(pady=5)
        ttk.Button(main_window, text="👤 Kullanıcı Oluştur", command=add_user_window).pack(pady=5)
        ttk.Button(main_window, text="📋 Kullanıcı Yönetimi", command=manage_users_window).pack(pady=5)


    ttk.Button(main_window, text="💰 Satış Yap", command=sell_product_window).pack(pady=5)
    ttk.Button(main_window, text="📊 Rapor Gör", command=show_report).pack(pady=5)
    ttk.Button(main_window, text="💾 Günlük Raporu Kaydet", command=export_daily_report).pack(pady=5)
    
    
    ttk.Button(main_window, text="🔓 Çıkış Yap", command=lambda: logout(main_window)).pack(pady=15)

    main_window.mainloop()



# ==========================
# Ürün Ekleme
# ==========================
def add_product_window():
    win = tk.Toplevel()
    win.title("Ürün Ekle")
    win.geometry("300x250")
    set_theme(win)

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

def add_user_window():
    win = tk.Toplevel()
    win.title("Yeni Kullanıcı Oluştur")
    win.geometry("300x550")
    set_theme(win)

    tk.Label(win, text="Kullanıcı Adı:").pack()
    username = tk.Entry(win)
    username.pack(pady=5)

    tk.Label(win, text="Şifre:").pack()
    password = tk.Entry(win, show="*")
    password.pack(pady=5)

    tk.Label(win, text="Rol Seç:").pack()
    role = ttk.Combobox(win, values=["admin", "cashier"])
    role.set("cashier")
    role.pack(pady=5)

    def save_user():
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           (username.get(), password.get(), role.get()))
            conn.commit()
            messagebox.showinfo("Başarılı", "Yeni kullanıcı eklendi!")
            win.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Hata", "Bu kullanıcı adı zaten mevcut!")

    ttk.Button(win, text="Kaydet", command=save_user).pack(pady=10)

def manage_users_window():
    win = tk.Toplevel()
    win.title("Kullanıcı Yönetimi")
    win.geometry("400x300")
    set_theme(win)

    tk.Label(win, text="Kayıtlı Kullanıcılar", font=("Arial", 12, "bold"), bg=BG_COLOR, fg=ACCENT).pack(pady=5)

    # Kullanıcı tablosu
    tree = ttk.Treeview(win, columns=("ID", "Kullanıcı", "Rol"), show="headings")
    tree.heading("ID", text="ID")
    tree.heading("Kullanıcı", text="Kullanıcı Adı")
    tree.heading("Rol", text="Rol")
    tree.pack(fill="both", expand=True, pady=5)

    # Kullanıcıları getir
    def load_users():
        for row in tree.get_children():
            tree.delete(row)
        cursor.execute("SELECT id, username, role FROM users")
        for user in cursor.fetchall():
            tree.insert("", "end", values=user)

    load_users()

    # Seçili kullanıcıyı sil
    def delete_user():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen silinecek kullanıcıyı seçin.")
            return
        user_id = tree.item(selected[0])["values"][0]
        username = tree.item(selected[0])["values"][1]

        if username == "admin":
            messagebox.showwarning("Uyarı", "Admin kullanıcısı silinemez!")
            return

        if messagebox.askyesno("Onay", f"{username} adlı kullanıcıyı silmek istediğine emin misin?"):
            cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
            conn.commit()
            messagebox.showinfo("Silindi", f"{username} kullanıcısı silindi.")
            load_users()

    ttk.Button(win, text="❌ Seçili Kullanıcıyı Sil", command=delete_user).pack(pady=8)
    ttk.Button(win, text="🔄 Yenile", command=load_users).pack(pady=3)

# ==========================
# Satış Yapma
# ==========================
def sell_product_window():
    win = tk.Toplevel()
    win.title("Satış Yap")
    win.geometry("350x300")
    set_theme(win)

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

def logout(window):
    window.destroy()
    os.execl(sys.executable, sys.executable, *sys.argv)

# ==========================
# Rapor Görüntüleme
# ==========================
def show_report():
    win = tk.Toplevel()
    win.title("Satış Raporu")
    win.geometry("400x300")
    set_theme(win)

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
login_window.title("SmartPOS Mini Giriş")
login_window.geometry("320x350")
set_theme(login_window)

show_logo(login_window)

ttk.Label(login_window, text="SmartPOS Mini Giriş", style="Header.TLabel").pack(pady=10)
ttk.Label(login_window, text="Kullanıcı Adı:").pack()
entry_username = ttk.Entry(login_window)
entry_username.pack(pady=5)
ttk.Label(login_window, text="Şifre:").pack()
entry_password = ttk.Entry(login_window, show="*")
entry_password.pack(pady=5)

ttk.Button(login_window, text="Giriş Yap", command=login).pack(pady=15)

login_window.mainloop()
