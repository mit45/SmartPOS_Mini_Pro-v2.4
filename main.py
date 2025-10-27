import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3
import os, sys, csv, subprocess
from datetime import datetime, date
from PIL import Image, ImageTk  # pip install pillow
import time
from tkinter import simpledialog
from reportlab.lib.styles import ParagraphStyle




# ==========================
# Tema & Genel Ayarlar
# ==========================
FG_COLOR = "#ffffff"
BG_COLOR = "#1e1e2e"   # Arka plan (VSCode tarzı koyu)
CARD_COLOR = "#2c2c3a" # Kart/panel
ACCENT = "#00aaff"     # Vurgu
TEXT_LIGHT = "#ffffff"
TEXT_GRAY = "#b8b8b8"

APP_TITLE = "SmartPOS Mini Pro"
APP_VERSION = "v2.1"


def set_theme(window):
    style = ttk.Style()
    window.configure(bg=BG_COLOR)
    try:
        style.theme_use("clam")
    except:
        pass

    style.configure("TFrame", background=BG_COLOR)
    style.configure("TLabel", background=BG_COLOR, foreground=TEXT_LIGHT, font=("Segoe UI", 10))
    style.configure("Header.TLabel", background=BG_COLOR, foreground=ACCENT, font=("Segoe UI", 16, "bold"))
    style.configure("Sub.TLabel", background=BG_COLOR, foreground=TEXT_GRAY, font=("Segoe UI", 9))
    style.configure("Card.TFrame", background=CARD_COLOR, relief="flat", borderwidth=0)

    style.configure("TButton",
                    background=ACCENT,
                    foreground="white",
                    font=("Segoe UI", 10, "bold"),
                    padding=8,
                    borderwidth=0)
    style.map("TButton",
              background=[("active", "#0088cc")],
              relief=[("pressed", "flat")])

    style.configure("Treeview",
                    background="#232332",
                    fieldbackground="#232332",
                    foreground=TEXT_LIGHT,
                    rowheight=26,
                    bordercolor="#000000",
                    borderwidth=0)
    style.configure("Treeview.Heading",
                    background="#303045",
                    foreground=TEXT_LIGHT,
                    font=("Segoe UI", 10, "bold"))
    style.map("Treeview", background=[("selected", "#004e75")])

def center_window(win, width=600, height=500):
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()

    # Ekrana göre otomatik küçültme (örneğin 1366x768 ekranlarda)
    width = min(width, int(screen_w * 0.9))
    height = min(height, int(screen_h * 0.9))

    x = (screen_w // 2) - (width // 2)
    y = (screen_h // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")
    
    
def show_logo(parent):
    try:
        if os.path.exists("smartpos_logo.png"):
            img = Image.open("smartpos_logo.png")
            img = img.resize((96, 96))
            logo_img = ImageTk.PhotoImage(img)
            lbl = tk.Label(parent, image=logo_img, bg=BG_COLOR)
            lbl.image = logo_img  # type: ignore
            lbl.pack(pady=(10, 6))
    except Exception as e:
        # Logo opsiyonel, hata göstermeyelim
        pass

# ==========================
# Veritabanı
# ==========================
DB_PATH = "database.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

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
    name TEXT UNIQUE,
    price REAL,
    stock INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT,
    quantity INTEGER,
    total REAL,
    created_at TEXT DEFAULT (datetime('now'))
)
""")

# Eski tabloda created_at yoksa ekle
try:
    cursor.execute("PRAGMA table_info(sales)")
    cols = [c[1] for c in cursor.fetchall()]
    if "created_at" not in cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN created_at TEXT DEFAULT (datetime('now'))")
        conn.commit()
except:
    pass

# Varsayılan kullanıcılar
cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", "1234", "admin"))
cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", ("kasiyer", "1234", "cashier"))
conn.commit()

# ==========================
# Gelişmiş Yardımcılar
# ==========================
def parse_float_safe(val, default=None):
    try:
        return float(str(val).replace(",", "."))
    except:
        return default

def parse_int_safe(val, default=None):
    try:
        return int(str(val))
    except:
        return default

def refresh_product_values_for_combo():
    cursor.execute("SELECT name FROM products ORDER BY name ASC")
    return [p[0] for p in cursor.fetchall()]

# ==========================
# Login
# ==========================
def login_action():
    username = entry_username.get().strip()
    password = entry_password.get().strip()
    cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()
    if user:
        role = user[0]
        open_main_window(role)
        login_window.withdraw()
    else:
        messagebox.showerror("Hata", "Kullanıcı adı veya şifre hatalı!")

def toggle_password():
    if entry_password.cget("show") == "*":
        entry_password.config(show="")
        btn_toggle_pw.config(text="🙈 Gizle")
    else:
        entry_password.config(show="*")
        btn_toggle_pw.config(text="👁 Göster")

# ==========================
# Ürün Yönetimi (Liste/Arama/Ekle/Düzenle/Sil)
# ==========================
def product_management_window():
    win = tk.Toplevel()
    win.title("Ürün Yönetimi")
    set_theme(win)
    center_window(win, 560, 660)

    header = ttk.Frame(win, style="Card.TFrame")
    header.pack(fill="x", padx=14, pady=(14, 8))

    ttk.Label(header, text="Ürünler", style="Header.TLabel").pack(side="left", padx=10, pady=10)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(header, textvariable=search_var)
    search_entry.pack(side="right", padx=10, pady=10)
    ttk.Label(header, text="Ara:", style="TLabel").pack(side="right", pady=10)

    body = ttk.Frame(win, style="Card.TFrame")
    body.pack(fill="both", expand=True, padx=14, pady=8)

    cols = ("ID", "Ad", "Fiyat", "Stok")
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
    tree.column("ID", width=60, anchor="center")
    tree.column("Ad", anchor="w", width=220)
    tree.column("Fiyat", anchor="e", width=100)
    tree.column("Stok", anchor="center", width=80)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    btns = ttk.Frame(win, style="Card.TFrame")
    btns.pack(fill="x", padx=14, pady=(0, 14))

    def load_products(filter_text=""):
        for r in tree.get_children():
            tree.delete(r)
        if filter_text:
            q = f"%{filter_text.strip()}%"
            cursor.execute("SELECT id, name, price, stock FROM products WHERE name LIKE ? ORDER BY name ASC", (q,))
        else:
            cursor.execute("SELECT id, name, price, stock FROM products ORDER BY name ASC")
        for row in cursor.fetchall():
            pid, name, price, stock = row
            tree.insert("", "end", values=(pid, name, f"{price:.2f}", stock))

    def add_product_dialog():
        dlg = tk.Toplevel(win)
        dlg.title("Ürün Ekle")
        set_theme(dlg)
        center_window(dlg, 360, 480)

        frm = ttk.Frame(dlg, style="Card.TFrame")
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(frm, text="Ürün Adı:").pack(anchor="w", pady=(6, 2))
        e_name = ttk.Entry(frm)
        e_name.pack(fill="x")

        ttk.Label(frm, text="Fiyat:").pack(anchor="w", pady=(10, 2))
        e_price = ttk.Entry(frm)
        e_price.pack(fill="x")

        ttk.Label(frm, text="Stok:").pack(anchor="w", pady=(10, 2))
        e_stock = ttk.Entry(frm)
        e_stock.pack(fill="x")

        def save():
            name = e_name.get().strip()
            price = parse_float_safe(e_price.get(), None)
            stock = parse_int_safe(e_stock.get(), None)
            if not name or price is None or stock is None:
                messagebox.showwarning("Uyarı", "Lütfen geçerli ad/fiyat/stok girin.")
                return
            try:
                cursor.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", (name, price, stock))
                conn.commit()
                messagebox.showinfo("Başarılı", "Ürün eklendi.")
                dlg.destroy()
                load_products(search_var.get())
            except sqlite3.IntegrityError:
                messagebox.showerror("Hata", "Bu ürün adı zaten mevcut!")

        ttk.Button(frm, text="Kaydet", command=save).pack(pady=14)

    def edit_selected_product():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Uyarı", "Lütfen düzenlenecek ürünü seçin.")
            return
        values = tree.item(sel[0])["values"]
        pid, name_cur, price_cur, stock_cur = values

        dlg = tk.Toplevel(win)
        dlg.title("Ürün Düzenle")
        set_theme(dlg)
        center_window(dlg, 360, 500)

        frm = ttk.Frame(dlg, style="Card.TFrame")
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(frm, text=f"Ürün ID: {pid}", style="Sub.TLabel").pack(anchor="w", pady=(0, 6))

        ttk.Label(frm, text="Ürün Adı:").pack(anchor="w", pady=(6, 2))
        e_name = ttk.Entry(frm)
        e_name.insert(0, name_cur)
        e_name.pack(fill="x")

        ttk.Label(frm, text="Fiyat:").pack(anchor="w", pady=(10, 2))
        e_price = ttk.Entry(frm)
        e_price.insert(0, price_cur)
        e_price.pack(fill="x")

        ttk.Label(frm, text="Stok:").pack(anchor="w", pady=(10, 2))
        e_stock = ttk.Entry(frm)
        e_stock.insert(0, stock_cur)
        e_stock.pack(fill="x")

        def save():
            name = e_name.get().strip()
            price = parse_float_safe(e_price.get(), None)
            stock = parse_int_safe(e_stock.get(), None)
            if not name or price is None or stock is None:
                messagebox.showwarning("Uyarı", "Lütfen geçerli ad/fiyat/stok girin.")
                return
            try:
                cursor.execute("UPDATE products SET name=?, price=?, stock=? WHERE id=?", (name, price, stock, pid))
                conn.commit()
                messagebox.showinfo("Başarılı", "Ürün güncellendi.")
                dlg.destroy()
                load_products(search_var.get())
            except sqlite3.IntegrityError:
                messagebox.showerror("Hata", "Bu ürün adı zaten mevcut!")

        ttk.Button(frm, text="Kaydet", command=save).pack(pady=14)

    def delete_selected_product():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Uyarı", "Lütfen silinecek ürünü seçin.")
            return
        values = tree.item(sel[0])["values"]
        pid, name = values[0], values[1]
        if messagebox.askyesno("Onay", f"'{name}' adlı ürünü silmek istiyor musun?"):
            cursor.execute("DELETE FROM products WHERE id=?", (pid,))
            conn.commit()
            load_products(search_var.get())
            messagebox.showinfo("Silindi", f"{name} silindi.")

    ttk.Button(btns, text="➕ Ürün Ekle", command=add_product_dialog).pack(side="left", padx=6, pady=10)
    ttk.Button(btns, text="✏️ Düzenle", command=edit_selected_product).pack(side="left", padx=6, pady=10)
    ttk.Button(btns, text="🗑 Sil", command=delete_selected_product).pack(side="left", padx=6, pady=10)
    ttk.Button(btns, text="🔄 Yenile", command=lambda: load_products(search_var.get())).pack(side="right", padx=6, pady=10)

    def on_search(*_):
        load_products(search_var.get())

    search_var.trace_add("write", on_search)
    load_products()

# ==========================
# Kullanıcı Yönetimi
# ==========================
def add_user_window(parent=None):
    win = tk.Toplevel(parent)
    win.title("Yeni Kullanıcı Oluştur")
    set_theme(win)
    center_window(win, 360, 520)

    frm = ttk.Frame(win, style="Card.TFrame")
    frm.pack(fill="both", expand=True, padx=16, pady=16)

    ttk.Label(frm, text="Kullanıcı Adı:").pack(anchor="w", pady=(6, 2))
    e_username = ttk.Entry(frm)
    e_username.pack(fill="x")

    ttk.Label(frm, text="Şifre:").pack(anchor="w", pady=(10, 2))
    e_password = ttk.Entry(frm, show="*")
    e_password.pack(fill="x")

    ttk.Label(frm, text="Rol:").pack(anchor="w", pady=(10, 2))
    cb_role = ttk.Combobox(frm, values=["admin", "cashier"], state="readonly")
    cb_role.set("cashier")
    cb_role.pack(fill="x")

    def save():
        u = e_username.get().strip()
        p = e_password.get().strip()
        r = cb_role.get().strip()
        if not u or not p:
            messagebox.showwarning("Uyarı", "Kullanıcı adı ve şifre zorunlu.")
            return
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (u, p, r))
            conn.commit()
            messagebox.showinfo("Başarılı", "Kullanıcı eklendi.")
            win.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Hata", "Bu kullanıcı adı zaten mevcut!")

    ttk.Button(frm, text="Kaydet", command=save).pack(pady=14)

def manage_users_window():
    win = tk.Toplevel()
    win.title("Kullanıcı Yönetimi")
    set_theme(win)
    center_window(win, 520, 620)

    ttk.Label(win, text="Kayıtlı Kullanıcılar", style="Header.TLabel").pack(pady=(14, 6))

    body = ttk.Frame(win, style="Card.TFrame")
    body.pack(fill="both", expand=True, padx=14, pady=8)

    tree = ttk.Treeview(body, columns=("ID", "Kullanıcı", "Rol"), show="headings")
    for c in ("ID", "Kullanıcı", "Rol"):
        tree.heading(c, text=c)
    tree.column("ID", width=60, anchor="center")
    tree.column("Kullanıcı", anchor="w", width=240)
    tree.column("Rol", anchor="center", width=100)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    def load_users():
        for r in tree.get_children():
            tree.delete(r)
        cursor.execute("SELECT id, username, role FROM users ORDER BY username ASC")
        for u in cursor.fetchall():
            tree.insert("", "end", values=u)

    def add_user():
        add_user_window(win)
        win.after(300, load_users)

    def edit_user():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Uyarı", "Lütfen düzenlenecek kullanıcıyı seçin.")
            return
        uid, uname, role = tree.item(sel[0])["values"]

        dlg = tk.Toplevel(win)
        dlg.title("Kullanıcı Düzenle")
        set_theme(dlg)
        center_window(dlg, 360, 500)

        frm = ttk.Frame(dlg, style="Card.TFrame")
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(frm, text=f"Kullanıcı ID: {uid}", style="Sub.TLabel").pack(anchor="w")
        ttk.Label(frm, text="Kullanıcı Adı:").pack(anchor="w", pady=(10, 2))
        e_username = ttk.Entry(frm)
        e_username.insert(0, uname)
        e_username.pack(fill="x")

        ttk.Label(frm, text="Yeni Şifre (opsiyonel):").pack(anchor="w", pady=(10, 2))
        e_password = ttk.Entry(frm, show="*")
        e_password.pack(fill="x")

        ttk.Label(frm, text="Rol:").pack(anchor="w", pady=(10, 2))
        cb_role = ttk.Combobox(frm, values=["admin", "cashier"], state="readonly")
        cb_role.set(role)
        cb_role.pack(fill="x")

        def save():
            new_u = e_username.get().strip()
            new_p = e_password.get().strip()
            new_r = cb_role.get().strip()

            if not new_u:
                messagebox.showwarning("Uyarı", "Kullanıcı adı zorunlu.")
                return
            try:
                if new_p:
                    cursor.execute("UPDATE users SET username=?, password=?, role=? WHERE id=?",
                                   (new_u, new_p, new_r, uid))
                else:
                    cursor.execute("UPDATE users SET username=?, role=? WHERE id=?",
                                   (new_u, new_r, uid))
                conn.commit()
                messagebox.showinfo("Başarılı", "Kullanıcı güncellendi.")
                dlg.destroy()
                load_users()
            except sqlite3.IntegrityError:
                messagebox.showerror("Hata", "Bu kullanıcı adı zaten mevcut!")

        ttk.Button(frm, text="Kaydet", command=save).pack(pady=14)

    def delete_user():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Uyarı", "Lütfen silinecek kullanıcıyı seçin.")
            return
        uid, uname, _ = tree.item(sel[0])["values"]
        if uname == "admin":
            messagebox.showwarning("Uyarı", "Admin kullanıcısı silinemez!")
            return
        if messagebox.askyesno("Onay", f"{uname} adlı kullanıcı silinsin mi?"):
            cursor.execute("DELETE FROM users WHERE id=?", (uid,))
            conn.commit()
            messagebox.showinfo("Silindi", f"{uname} silindi.")
            load_users()

    btns = ttk.Frame(win, style="Card.TFrame")
    btns.pack(fill="x", padx=14, pady=(0, 14))
    ttk.Button(btns, text="➕ Ekle", command=add_user).pack(side="left", padx=6, pady=10)
    ttk.Button(btns, text="✏️ Düzenle", command=edit_user).pack(side="left", padx=6, pady=10)
    ttk.Button(btns, text="🗑 Sil", command=delete_user).pack(side="left", padx=6, pady=10)
    ttk.Button(btns, text="🔄 Yenile", command=load_users).pack(side="right", padx=6, pady=10)

    load_users()

# ==========================
# Satış
# ==========================
def sell_product_window():
    import uuid
    win = tk.Toplevel()
    win.title("Toplu Satış (KDV / İndirimli)")
    set_theme(win)
    center_window(win, 640, 760)

    ttk.Label(win, text="🧾 Toplu Satış Ekranı", style="Header.TLabel").pack(pady=(10, 5))
    ttk.Label(win, text="Ürünleri sepete ekle, müşteri bilgisi gir, KDV ve indirim uygula.", style="Sub.TLabel").pack(pady=(0, 10))

    # ------------------ ÜST BİLGİLER ------------------
    top_info = ttk.Frame(win, style="Card.TFrame")
    top_info.pack(fill="x", padx=16, pady=(4, 10))

    ttk.Label(top_info, text="Müşteri Adı:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
    customer_entry = ttk.Entry(top_info, width=30)
    customer_entry.grid(row=0, column=1, padx=6, pady=6)

    ttk.Label(top_info, text="KDV Oranı:").grid(row=0, column=2, padx=6, pady=6, sticky="e")
    vat_cb = ttk.Combobox(top_info, values=["%8", "%18", "Özel"], state="readonly", width=6)
    vat_cb.set("%18")
    vat_cb.grid(row=0, column=3, padx=6, pady=6)

    ttk.Label(top_info, text="İndirim (%):").grid(row=1, column=2, padx=6, pady=6, sticky="e")
    discount_entry = ttk.Entry(top_info, width=6)
    discount_entry.insert(0, "0")
    discount_entry.grid(row=1, column=3, padx=6, pady=6)

    # ------------------ ÜRÜN SEÇİMİ ------------------
    frame_top = ttk.Frame(win, style="Card.TFrame")
    frame_top.pack(fill="x", padx=16, pady=(4, 10))

    ttk.Label(frame_top, text="Ürün:").grid(row=0, column=0, padx=6, pady=6)
    products = refresh_product_values_for_combo()
    cb_product = ttk.Combobox(frame_top, values=products, state="readonly", width=25)
    cb_product.grid(row=0, column=1, padx=6, pady=6)

    ttk.Label(frame_top, text="Adet:").grid(row=0, column=2, padx=6, pady=6)
    e_qty = ttk.Entry(frame_top, width=6)
    e_qty.insert(0, "1")
    e_qty.grid(row=0, column=3, padx=6, pady=6)

    ttk.Label(frame_top, text="Fiyat:").grid(row=1, column=0, padx=6, pady=6)
    lbl_price = ttk.Label(frame_top, text="-", style="Sub.TLabel")
    lbl_price.grid(row=1, column=1, sticky="w", padx=6, pady=6)

    ttk.Label(frame_top, text="Stok:").grid(row=1, column=2, padx=6, pady=6)
    lbl_stock = ttk.Label(frame_top, text="-", style="Sub.TLabel")
    lbl_stock.grid(row=1, column=3, sticky="w", padx=6, pady=6)

    def update_info(*_):
        pname = cb_product.get()
        cursor.execute("SELECT price, stock FROM products WHERE name=?", (pname,))
        r = cursor.fetchone()
        if r:
            price, stock = r
            lbl_price.config(text=f"{price:.2f} ₺")
            lbl_stock.config(text=str(stock))
        else:
            lbl_price.config(text="-")
            lbl_stock.config(text="-")
    cb_product.bind("<<ComboboxSelected>>", update_info)

    # ------------------ SEPET TABLOSU ------------------
    frame_mid = ttk.Frame(win, style="Card.TFrame")
    frame_mid.pack(fill="both", expand=True, padx=16, pady=10)

    cols = ("Ürün", "Adet", "Fiyat", "Toplam")
    tree = ttk.Treeview(frame_mid, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
    tree.column("Ürün", width=240)
    tree.column("Adet", width=80, anchor="center")
    tree.column("Fiyat", width=100, anchor="e")
    tree.column("Toplam", width=100, anchor="e")
    tree.pack(fill="both", expand=True)

    total_label = ttk.Label(win, text="Toplam: 0.00 ₺", style="Header.TLabel")
    total_label.pack(pady=8)

    def update_total_label():
        total_sum = sum([float(tree.item(row)["values"][3]) for row in tree.get_children()])
        total_label.config(text=f"Ara Toplam: {total_sum:.2f} ₺")

    def add_to_cart():
        pname = cb_product.get().strip()
        qty = parse_int_safe(e_qty.get(), None)
        if not pname or qty is None or qty <= 0:
            messagebox.showwarning("Uyarı", "Geçerli ürün ve adet girin.")
            return

        cursor.execute("SELECT price, stock FROM products WHERE name=?", (pname,))
        r = cursor.fetchone()
        if not r:
            messagebox.showerror("Hata", "Ürün bulunamadı.")
            return
        price, stock = r
        if qty > stock:
            messagebox.showerror("Hata", f"Yetersiz stok! (Mevcut: {stock})")
            return

        total = qty * price
        tree.insert("", "end", values=(pname, qty, f"{price:.2f}", f"{total:.2f}"))
        update_total_label()

    def remove_selected():
        for s in tree.selection():
            tree.delete(s)
        update_total_label()

    # ------------------ BUTONLAR ------------------
    frame_btns = ttk.Frame(win, style="Card.TFrame")
    frame_btns.pack(fill="x", padx=16, pady=(0, 10))

    ttk.Button(frame_btns, text="➕ Sepete Ekle", command=add_to_cart).pack(side="left", padx=6, pady=6)
    ttk.Button(frame_btns, text="🗑 Seçiliyi Kaldır", command=remove_selected).pack(side="left", padx=6, pady=6)

    # ------------------ SATIŞ ONAY ------------------
    def confirm_sale():
        rows = tree.get_children()
        if not rows:
            messagebox.showwarning("Uyarı", "Sepet boş.")
            return

        customer_name = customer_entry.get().strip() or "Müşteri"
        kdv_text = vat_cb.get()
        discount_val = parse_float_safe(discount_entry.get(), 0.0)

        # Fiş numarası üret
        fis_id = f"FIS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"

        sales_list = []
        subtotal = 0.0
        for row in rows:
            pname, qty, price, total = tree.item(row)["values"]
            qty = int(qty)
            price = float(price)
            total = float(total)
            cursor.execute("UPDATE products SET stock = stock - ? WHERE name=?", (qty, pname))
            cursor.execute("""
                INSERT INTO sales (product_name, quantity, total, fis_id)
                VALUES (?, ?, ?, ?)
            """, (pname, qty, total, fis_id))
            sales_list.append((pname, qty, price, total))
            subtotal += total

        # İndirim ve KDV hesapla
        discount_amount = subtotal * (discount_val / 100)
        subtotal_after_discount = subtotal - discount_amount
        vat_rate = 8 if kdv_text == "%8" else 18 if kdv_text == "%18" else parse_float_safe(simpledialog.askstring("Özel KDV", "KDV oranını gir (%):"), 0)
        vat_amount = subtotal_after_discount * (vat_rate / 100)
        grand_total = subtotal_after_discount + vat_amount

        conn.commit()

        # PDF fatura yazdır
        print_receipt(sales_list, grand_total, fis_id, customer_name, vat_rate, discount_val)

        messagebox.showinfo("Satış Tamamlandı",
                            f"Satış başarıyla kaydedildi.\nMüşteri: {customer_name}\nFiş No: {fis_id}\nToplam: {grand_total:.2f} ₺")
        win.destroy()

    ttk.Button(win, text="✅ Satışı Onayla", command=confirm_sale).pack(pady=(0, 12))




# ==========================
# Raporlar (Tarih Filtreli)
# ==========================
def show_report_window():
    win = tk.Toplevel()
    win.title("Satış Raporu")
    set_theme(win)
    center_window(win, 740, 680)

    header = ttk.Frame(win, style="Card.TFrame")
    header.pack(fill="x", padx=14, pady=(14, 8))
    ttk.Label(header, text="Satış Raporu", style="Header.TLabel").pack(side="left", padx=10, pady=10)

    filt = ttk.Frame(win, style="Card.TFrame")
    filt.pack(fill="x", padx=14, pady=8)

    ttk.Label(filt, text="Başlangıç (YYYY-MM-DD):").pack(side="left", padx=(10, 6))
    sv_from = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    e_from = ttk.Entry(filt, textvariable=sv_from, width=14)
    e_from.pack(side="left", padx=(0, 12))

    ttk.Label(filt, text="Bitiş (YYYY-MM-DD):").pack(side="left", padx=(10, 6))
    sv_to = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    e_to = ttk.Entry(filt, textvariable=sv_to, width=14)
    e_to.pack(side="left", padx=(0, 12))

    def valid_date(s):
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return True
        except:
            return False

    body = ttk.Frame(win, style="Card.TFrame")
    body.pack(fill="both", expand=True, padx=14, pady=8)

    cols = ("Fiş No", "Tarih", "Ürün", "Adet", "Toplam ₺")
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
    tree.column("Fiş No", width=130, anchor="center")
    tree.column("Tarih", width=120, anchor="center")
    tree.column("Ürün", width=200, anchor="w")
    tree.column("Adet", width=80, anchor="center")
    tree.column("Toplam ₺", width=100, anchor="e")
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    footer = ttk.Frame(win, style="Card.TFrame")
    footer.pack(fill="x", padx=14, pady=(0,14))
    lbl_sum = ttk.Label(footer, text="Toplam Adet: 0 | Toplam Ciro: 0.00 ₺", style="TLabel")
    lbl_sum.pack(side="left", padx=10)

    # -------------------- Raporu Listele --------------------
    def load_report():
        frm = sv_from.get().strip()
        to = sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            messagebox.showwarning("Uyarı", "Lütfen geçerli tarih formatı girin (YYYY-MM-DD).")
            return

        to_dt = datetime.strptime(to, "%Y-%m-%d")
        to_plus = (to_dt.replace(hour=23, minute=59, second=59)).strftime("%Y-%m-%d %H:%M:%S")

        for r in tree.get_children():
            tree.delete(r)

        cursor.execute("""
            SELECT fis_id, created_at, product_name, quantity, total
            FROM sales
            WHERE datetime(created_at) BETWEEN datetime(?) AND datetime(?)
            ORDER BY datetime(created_at) DESC
        """, (f"{frm} 00:00:00", to_plus))
        rows = cursor.fetchall()

        total_qty = 0
        total_sum = 0.0
        for (fis_id, ts, pname, qty, total) in rows:
            ts_disp = ts.replace("T", " ") if ts else ""
            tree.insert("", "end", values=(fis_id, ts_disp, pname, qty, f"{total:.2f}"))
            total_qty += int(qty)
            total_sum += float(total)
        lbl_sum.config(text=f"Toplam Adet: {total_qty} | Toplam Ciro: {total_sum:.2f} ₺")

    # -------------------- CSV Dışa Aktar --------------------
    def export_filtered_csv():
        frm = sv_from.get().strip()
        to = sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            messagebox.showwarning("Uyarı", "Lütfen geçerli tarih formatı girin (YYYY-MM-DD).")
            return

        to_dt = datetime.strptime(to, "%Y-%m-%d")
        to_plus = (to_dt.replace(hour=23, minute=59, second=59)).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            SELECT fis_id, created_at, product_name, quantity, total
            FROM sales
            WHERE datetime(created_at) BETWEEN datetime(?) AND datetime(?)
            ORDER BY datetime(created_at) DESC
        """, (f"{frm} 00:00:00", to_plus))
        rows = cursor.fetchall()

        if not rows:
            messagebox.showinfo("Bilgi", "Bu tarih aralığında satış bulunamadı.")
            return

        report_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(report_dir, exist_ok=True)
        filename = os.path.join(report_dir, f"rapor_{frm}_to_{to}.csv")

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Fiş No", "Tarih", "Ürün", "Adet", "Toplam ₺"])
                for fis_id, ts, pname, qty, total in rows:
                    writer.writerow([fis_id, ts, pname, qty, f"{float(total):.2f}"])
        except Exception as e:
            messagebox.showerror("Yazma Hatası", f"CSV dosyası oluşturulamadı:\n{e}")
            return

        if os.path.exists(filename):
            messagebox.showinfo("Başarılı", f"Rapor kaydedildi:\n{filename}")
            try:
                if os.name == "nt":
                    os.startfile(filename)
                else:
                    subprocess.call(('open', filename))
            except Exception as e:
                messagebox.showwarning("Uyarı", f"Rapor oluşturuldu ancak açılamadı:\n{e}")
        else:
            messagebox.showerror("Hata", f"Dosya bulunamadı:\n{filename}")

    # -------------------- Fiş Aç / Yazdır --------------------
    def open_selected_receipt():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Uyarı", "Lütfen bir satış seçin.")
            return
        vals = tree.item(sel[0])["values"]
        fis_id = vals[0] if len(vals) > 0 else None
        if not fis_id:
            messagebox.showwarning("Uyarı", "Seçilen satışa ait fiş bulunamadı.")
            return

        cursor.execute("SELECT product_name, quantity, total FROM sales WHERE fis_id=?", (fis_id,))
        rows = cursor.fetchall()
        if not rows:
            messagebox.showerror("Hata", "Bu fiş bulunamadı veya silinmiş.")
            return

        # PDF olarak yeniden yazdır
        sales_list = [(r[0], r[1], r[2]/r[1], r[2]) for r in rows]
        total_sum = sum([r[3] for r in sales_list])
        print_receipt(sales_list, total_sum, fis_id)

    # -------------------- Butonlar --------------------
    btns = ttk.Frame(win, style="Card.TFrame")
    btns.pack(fill="x", padx=14, pady=(0,14))
    ttk.Button(btns, text="🔍 Listele", command=load_report).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="📤 CSV Dışa Aktar", command=export_filtered_csv).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="🧾 Fiş Aç / Yazdır", command=open_selected_receipt).pack(side="left", padx=6, pady=8)

    # Varsayılan olarak bugünün satışlarını yükle
    load_report()


# ==========================
# Günlük Satış Raporu (Hızlı)
# ==========================
def export_daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"reports/rapor_{today}.csv"

    if not os.path.exists("reports"):
        os.makedirs("reports")

    cursor.execute("""
        SELECT product_name, quantity, total
        FROM sales
        WHERE date(created_at) = date('now', 'localtime')
    """)
    sales_data = cursor.fetchall()

    if not sales_data:
        messagebox.showinfo("Bilgi", "Bugün için kayıtlı satış yok.")
        return

    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Ürün Adı", "Adet", "Toplam ₺"])
        for row in sales_data:
            pname, qty, total = row
            writer.writerow([pname, qty, f"{float(total):.2f}"])

    messagebox.showinfo("Başarılı", f"Günlük rapor kaydedildi:\n{filename}")
    try:
        if os.name == 'nt':
            os.startfile(filename)
        else:
            subprocess.call(('open', filename))
    except Exception as e:
        messagebox.showerror("Hata", f"Rapor açılırken hata oluştu:\n{e}")

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import tempfile
import platform
import subprocess
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet

# Türkçe karakter desteği
pdfmetrics.registerFont(TTFont('DejaVu', 'fonts/DejaVuSans.ttf'))


def print_receipt(sales_list, total_amount, fis_id="", customer_name="Müşteri", kdv_rate: float = 18.0, discount_rate: float = 0.0):
    import tempfile, time
    today = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    temp_dir = os.path.join(tempfile.gettempdir(), "SmartPOS_Receipts")
    os.makedirs(temp_dir, exist_ok=True)
    filename = os.path.join(temp_dir, f"{fis_id or 'fis'}_{today}.pdf")

    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    y = height - 40*mm

    c.setFont("DejaVu", 14)
    c.drawString(25*mm, y, "SMARTPOS MINI PRO - SATIŞ FİŞİ")
    y -= 8*mm
    c.setFont("DejaVu", 10)
    c.drawString(25*mm, y, f"Fiş No: {fis_id}")
    y -= 6*mm
    c.drawString(25*mm, y, f"Müşteri: {customer_name}")
    y -= 6*mm
    c.drawString(25*mm, y, f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    y -= 8*mm
    c.drawString(25*mm, y, "-"*75)
    y -= 6*mm

    c.setFont("DejaVu", 10)
    c.drawString(25*mm, y, "Ürün")
    c.drawString(90*mm, y, "Adet")
    c.drawString(110*mm, y, "Fiyat")
    c.drawString(135*mm, y, "Tutar")
    y -= 5*mm
    c.setFont("DejaVu", 10)
    c.drawString(25*mm, y, "-"*75)
    y -= 6*mm

    subtotal = 0
    for pname, qty, price, subtotal_item in sales_list:
        c.drawString(25*mm, y, str(pname)[:25])
        c.drawRightString(102*mm, y, str(qty))
        c.drawRightString(128*mm, y, f"{price:.2f}")
        c.drawRightString(155*mm, y, f"{subtotal_item:.2f}")
        y -= 6*mm
        subtotal += subtotal_item
        if y < 50*mm:
            c.showPage()
            y = height - 40*mm

    discount_amt = subtotal * (discount_rate / 100)
    after_discount = subtotal - discount_amt
    kdv_amt = after_discount * (kdv_rate / 100)
    grand_total = after_discount + kdv_amt

    y -= 10*mm
    c.drawString(25*mm, y, "-"*75)
    y -= 10*mm
    c.setFont("DejaVu", 10)
    c.drawRightString(155*mm, y, f"Ara Toplam: {subtotal:.2f} ₺")
    y -= 6*mm
    c.drawRightString(155*mm, y, f"İndirim ({discount_rate:.1f}%): -{discount_amt:.2f} ₺")
    y -= 6*mm
    c.drawRightString(155*mm, y, f"KDV ({kdv_rate:.1f}%): +{kdv_amt:.2f} ₺")
    y -= 10*mm
    c.setFont("DejaVu", 12)
    c.drawRightString(155*mm, y, f"Genel Toplam: {grand_total:.2f} ₺")
    y -= 10*mm
    c.setFont("DejaVu", 10)
    c.drawString(25*mm, y, "Teşekkür ederiz - SmartPOS Mini Pro")
    c.save()

    time.sleep(0.5)
    if os.path.exists(filename):
        try:
            os.startfile(filename)
        except Exception:
            pass
    messagebox.showinfo("Fiş Oluşturuldu", f"Fatura kaydedildi:\n{filename}")



# ==========================
# Ana Pencere
# ==========================
def open_main_window(role):
    main = tk.Toplevel()
    main.title(f"{APP_TITLE} - {role.upper()}")
    set_theme(main)
    center_window(main, 520, 720)

    ttk.Label(main, text=f"{APP_TITLE} — {role.title()} Paneli", style="Header.TLabel").pack(pady=(16, 6))
    ttk.Label(main, text="Küçük işletmeler için satış & stok sistemi", style="Sub.TLabel").pack(pady=(0, 14))

    btn_frame = ttk.Frame(main, style="Card.TFrame")
    btn_frame.pack(padx=24, pady=10, fill="x")

    # Admin butonları
    if role == "admin":
        ttk.Button(btn_frame, text="🧾 Ürün Yönetimi", command=product_management_window).pack(pady=8, ipadx=20, fill="x", padx=20)
        ttk.Button(btn_frame, text="👥 Kullanıcı Yönetimi", command=manage_users_window).pack(pady=8, ipadx=20, fill="x", padx=20)
        ttk.Separator(btn_frame).pack(fill="x", padx=20, pady=6)

    ttk.Button(btn_frame, text="💰 Satış Yap", command=sell_product_window).pack(pady=8, ipadx=20, fill="x", padx=20)
    ttk.Button(btn_frame, text="🧾 Fişleri Görüntüle / Yazdır", command=show_receipts_window).pack(pady=8, ipadx=20, fill="x", padx=20)
    ttk.Button(btn_frame, text="📊 Raporlar (Tarih Filtresi)", command=show_report_window).pack(pady=8, ipadx=20, fill="x", padx=20)
    ttk.Button(btn_frame, text="💾 Günlük Raporu Kaydet", command=export_daily_report).pack(pady=8, ipadx=20, fill="x", padx=20)

    ttk.Button(main, text="🔓 Çıkış Yap", command=lambda: logout_and_restart(main)).pack(pady=16)

    ttk.Label(main, text=f"{APP_TITLE} {APP_VERSION} © Ümit Topuz", style="Sub.TLabel").pack(side="bottom", pady=10)

# ==========================
# Logout
# ==========================
def logout_and_restart(window):
    try:
        window.destroy()
    except:
        pass
    try:
        login_window.destroy()
    except:
        pass
    os.execl(sys.executable, sys.executable, *sys.argv)

def show_receipts_window():
    win = tk.Toplevel()
    win.title("Fişleri Görüntüle / Yazdır")
    set_theme(win)
    center_window(win, 600, 600)

    ttk.Label(win, text="Kaydedilmiş Fişler", style="Header.TLabel").pack(pady=(10, 5))

    frm = ttk.Frame(win, style="Card.TFrame")
    frm.pack(fill="both", expand=True, padx=16, pady=10)

    tree = ttk.Treeview(frm, columns=("Dosya", "Tarih"), show="headings")
    tree.heading("Dosya", text="Fiş Adı")
    tree.heading("Tarih", text="Oluşturulma Tarihi")
    tree.column("Dosya", width=400)
    tree.column("Tarih", width=150)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    # Fişleri listele
    import tempfile, glob
    temp_dir = os.path.join(tempfile.gettempdir(), "SmartPOS_Receipts")
    os.makedirs(temp_dir, exist_ok=True)

    files = sorted(glob.glob(os.path.join(temp_dir, "*.pdf")), reverse=True)
    for f in files:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(f)))
        tree.insert("", "end", values=(os.path.basename(f), ts))

    def open_selected_receipt():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Uyarı", "Lütfen bir fiş seçin.")
            return
        fname = tree.item(sel[0])["values"][0]
        full_path = os.path.join(temp_dir, fname)
        if os.path.exists(full_path):
            try:
                os.startfile(full_path)
            except Exception as e:
                messagebox.showerror("Hata", f"Fiş açılamadı:\n{e}")
        else:
            messagebox.showerror("Hata", "Dosya bulunamadı.")

    ttk.Button(win, text="🖨 Fişi Aç / Yazdır", command=open_selected_receipt).pack(pady=8)

# ==========================
# Giriş Ekranı
# ==========================
def start_login_screen():
    global login_window, entry_username, entry_password, btn_toggle_pw
    login_window = tk.Tk()
    login_window.title(f"{APP_TITLE} Giriş")
    set_theme(login_window)
    center_window(login_window, 420, 720)

    show_logo(login_window)
    ttk.Label(login_window, text=APP_TITLE, style="Header.TLabel").pack(pady=(6, 4))
    ttk.Label(login_window, text="Küçük işletmeler için satış sistemi", style="Sub.TLabel").pack(pady=(0, 12))

    frame = ttk.Frame(login_window, style="Card.TFrame")
    frame.pack(pady=10, padx=24, fill="x")

    ttk.Label(frame, text="Kullanıcı Adı:").pack(pady=(16, 4), anchor="w")
    entry_username = ttk.Entry(frame, font=("Segoe UI", 10))
    entry_username.pack(pady=(0, 8), ipady=3, fill="x", padx=16)

    ttk.Label(frame, text="Şifre:").pack(pady=(8, 4), anchor="w")
    pw_row = ttk.Frame(frame, style="Card.TFrame")
    pw_row.pack(fill="x", padx=16)
    entry_password = ttk.Entry(pw_row, show="*", font=("Segoe UI", 10))
    entry_password.pack(side="left", fill="x", expand=True)
    btn_toggle_pw = ttk.Button(pw_row, text="👁 Göster", command=toggle_password)
    btn_toggle_pw.pack(side="left", padx=(8,0))

    ttk.Button(frame, text="Giriş Yap", command=login_action).pack(pady=20, ipadx=20)

    # Enter ile giriş
    login_window.bind("<Return>", lambda e: login_action())

    ttk.Label(login_window, text=f"{APP_VERSION}", style="Sub.TLabel").pack(side="bottom", pady=10)

    login_window.mainloop()

# ==========================
# Çalıştır
# ==========================
if __name__ == "__main__":
    start_login_screen()
