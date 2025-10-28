import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3, os, sys, csv, subprocess, time, glob, tempfile
from datetime import datetime, date
from PIL import Image, ImageTk

# ==========================
# Tema & Genel Ayarlar (v2.4)
# ==========================
FG_COLOR   = "#ffffff"
BG_COLOR   = "#18181c"
CARD_COLOR = "#23232a"
ACCENT     = "#00b0ff"
TEXT_LIGHT = "#ffffff"
TEXT_GRAY  = "#b0b0b0"

APP_TITLE   = "SmartPOS Mini Pro"
APP_VERSION = "v2.4"

def set_theme(window):
    style = ttk.Style()
    window.configure(bg=BG_COLOR)
    try: style.theme_use("clam")
    except: pass

    style.configure("TFrame", background=BG_COLOR)
    style.configure("Card.TFrame", background=CARD_COLOR, relief="flat", borderwidth=0)
    style.configure("TLabel", background=BG_COLOR, foreground=TEXT_LIGHT, font=("Segoe UI", 10))
    style.configure("Header.TLabel", background=BG_COLOR, foreground=ACCENT, font=("Segoe UI", 16, "bold"))
    style.configure("Sub.TLabel", background=BG_COLOR, foreground=TEXT_GRAY,  font=("Segoe UI", 9))

    style.configure("TButton",
        background=ACCENT, foreground="white", font=("Segoe UI", 10, "bold"),
        padding=8, borderwidth=0)
    style.map("TButton", background=[("active", "#0090dd")])

    style.configure("Treeview",
        background="#1f1f25", fieldbackground="#1f1f25",
        foreground=TEXT_LIGHT, rowheight=26, bordercolor="#000000", borderwidth=0)
    style.configure("Treeview.Heading",
        background="#2a2a35", foreground=TEXT_LIGHT, font=("Segoe UI", 10, "bold"))
    style.map("Treeview", background=[("selected", "#004e75")])

def center_window(win, width=1080, height=720):
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    width  = min(width,  int(screen_w * 0.92))
    height = min(height, int(screen_h * 0.92))
    x = (screen_w // 2) - (width // 2)
    y = (screen_h // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")

# ==========================
# Veritabanı
# ==========================
DB_PATH = "database.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE,
  password TEXT,
  role TEXT
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE,
  price REAL DEFAULT 0,
  stock INTEGER DEFAULT 0
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fis_id TEXT,
  product_name TEXT,
  quantity INTEGER,
  price REAL,
  total REAL,
  created_at TEXT DEFAULT (datetime('now','localtime'))
)""")

# Eski tabloda eksik kolonlar varsa tamamla
cursor.execute("PRAGMA table_info(sales)")
existing_cols = {c[1] for c in cursor.fetchall()}
for need in ("fis_id", "price"):
    if need not in existing_cols:
        cursor.execute(f"ALTER TABLE sales ADD COLUMN {need} {'TEXT' if need=='fis_id' else 'REAL'}")
        conn.commit()

cursor.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES (?,?,?)", ("admin","1234","admin"))
cursor.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES (?,?,?)", ("kasiyer","1234","cashier"))
conn.commit()

# ==========================
# Yardımcılar
# ==========================
def parse_float_safe(v, default=None):
    try: return float(str(v).replace(",", "."))
    except: return default

def parse_int_safe(v, default=None):
    try: return int(str(v))
    except: return default

def refresh_product_values_for_combo():
    cursor.execute("SELECT name FROM products ORDER BY name ASC")
    return [r[0] for r in cursor.fetchall()]

# ==========================
# PDF Fiş
# ==========================
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_READY = False
try:
    font_path = os.path.join("fonts","DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
        FONT_READY = True
except: pass

def print_receipt(sales_list, fis_id="", customer_name="Müşteri", kdv_rate=18.0, discount_rate=0.0):
    """
    sales_list: [(pname, qty, price, subtotal), ...]
    """
    today = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    temp_dir = os.path.join(tempfile.gettempdir(), "SmartPOS_Receipts")
    os.makedirs(temp_dir, exist_ok=True)
    filename = os.path.join(temp_dir, f"{fis_id or 'fis'}_{today}.pdf")

    c = pdfcanvas.Canvas(filename, pagesize=A4)
    face = "DejaVu" if FONT_READY else "Helvetica"
    width, height = A4
    y = height - 40*mm

    c.setFont(face, 14)
    c.drawString(25*mm, y, "SMARTPOS MINI PRO - SATIŞ FİŞİ")
    y -= 8*mm
    c.setFont(face, 10)
    c.drawString(25*mm, y, f"Fiş No: {fis_id}")
    y -= 6*mm
    c.drawString(25*mm, y, f"Müşteri: {customer_name}")
    y -= 6*mm
    c.drawString(25*mm, y, f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    y -= 8*mm
    c.drawString(25*mm, y, "-"*75); y -= 6*mm

    c.setFont(face, 10)
    c.drawString(25*mm, y, "Ürün")
    c.drawString(90*mm, y, "Adet")
    c.drawString(110*mm, y, "Fiyat")
    c.drawString(135*mm, y, "Tutar")
    y -= 5*mm
    c.drawString(25*mm, y, "-"*75); y -= 6*mm

    subtotal = 0.0
    for pname, qty, price, line_total in sales_list:
        c.drawString(25*mm, y, str(pname)[:40])
        c.drawRightString(102*mm, y, f"{qty}")
        c.drawRightString(128*mm, y, f"{price:.2f}")
        c.drawRightString(155*mm, y, f"{line_total:.2f}")
        y -= 6*mm
        subtotal += float(line_total)
        if y < 40*mm:
            c.showPage()
            c.setFont(face, 10)
            y = height - 40*mm

    discount_amt = subtotal * (float(discount_rate)/100.0)
    after_discount = subtotal - discount_amt
    kdv_amt = after_discount * (float(kdv_rate)/100.0)
    grand_total = after_discount + kdv_amt

    y -= 8*mm; c.drawString(25*mm, y, "-"*75); y -= 8*mm
    c.drawRightString(155*mm, y, f"Ara Toplam: {subtotal:.2f} ₺"); y -= 6*mm
    c.drawRightString(155*mm, y, f"İndirim ({discount_rate:.1f}%): -{discount_amt:.2f} ₺"); y -= 6*mm
    c.drawRightString(155*mm, y, f"KDV ({kdv_rate:.1f}%): +{kdv_amt:.2f} ₺"); y -= 8*mm
    c.setFont(face, 12)
    c.drawRightString(155*mm, y, f"Genel Toplam: {grand_total:.2f} ₺"); y -= 10*mm
    c.setFont(face, 10)
    c.drawString(25*mm, y, "Teşekkür ederiz - SmartPOS Mini Pro")

    c.save()

    # Windows'ta aç
    try:
        if os.name == "nt":
            os.startfile(filename)  # type: ignore
        else:
            subprocess.call(("open", filename))
    except Exception:
        pass

    messagebox.showinfo("Fiş Oluşturuldu", f"Fatura kaydedildi:\n{filename}")

# ==========================
# Gömülü Modüller (tek pencere)
# ==========================
def mount_products(parent):
    for w in parent.winfo_children(): w.destroy()

    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="📦 Ürün Yönetimi", style="Header.TLabel").pack(side="left", padx=8)
    search_var = tk.StringVar()
    ttk.Entry(header, textvariable=search_var).pack(side="right", padx=8)
    ttk.Label(header, text="Ara:", style="TLabel").pack(side="right")

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)

    cols = ("ID","Ad","Fiyat","Stok")
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for c in cols: tree.heading(c, text=c)
    tree.column("ID", width=60, anchor="center")
    tree.column("Ad", anchor="w", width=240)
    tree.column("Fiyat", anchor="e", width=100)
    tree.column("Stok", anchor="center", width=90)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))

    def load(filter_text=""):
        for r in tree.get_children(): tree.delete(r)
        if filter_text:
            q=f"%{filter_text.strip()}%"
            cursor.execute("SELECT id,name,price,stock FROM products WHERE name LIKE ? ORDER BY name",(q,))
        else:
            cursor.execute("SELECT id,name,price,stock FROM products ORDER BY name")
        for pid,name,price,stock in cursor.fetchall():
            tree.insert("", "end", values=(pid, name, f"{float(price):.2f}", stock))

    def add_product():
        name = simpledialog.askstring("Ürün Ekle", "Ürün adı:")
        if not name: return
        price = parse_float_safe(simpledialog.askstring("Ürün Ekle","Fiyat (örn 99.90):"), 0.0)
        stock = parse_int_safe(simpledialog.askstring("Ürün Ekle","Stok (örn 10):"), 0)
        try:
            cursor.execute("INSERT INTO products(name,price,stock) VALUES(?,?,?)",(name,price,stock))
            conn.commit(); load(search_var.get())
        except sqlite3.IntegrityError:
            messagebox.showerror("Hata","Bu ürün adı zaten mevcut!")

    def edit_product():
        sel = tree.selection()
        if not sel: return messagebox.showwarning("Uyarı","Bir ürün seçin.")
        pid, name_cur, price_cur, stock_cur = tree.item(sel[0])["values"]

        name  = simpledialog.askstring("Düzenle","Ürün adı:", initialvalue=name_cur)
        if name is None: return
        price = parse_float_safe(simpledialog.askstring("Düzenle","Fiyat:", initialvalue=price_cur), None)
        stock = parse_int_safe(simpledialog.askstring("Düzenle","Stok:", initialvalue=stock_cur), None)
        if price is None or stock is None:
            return messagebox.showwarning("Uyarı","Geçerli fiyat/stok girin.")
        try:
            cursor.execute("UPDATE products SET name=?,price=?,stock=? WHERE id=?",(name,price,stock,pid))
            conn.commit(); load(search_var.get())
        except sqlite3.IntegrityError:
            messagebox.showerror("Hata","Bu ürün adı zaten mevcut!")

    def delete_product():
        sel = tree.selection()
        if not sel: return messagebox.showwarning("Uyarı","Bir ürün seçin.")
        pid, name = tree.item(sel[0])["values"][:2]
        if messagebox.askyesno("Onay", f"{name} silinsin mi?"):
            cursor.execute("DELETE FROM products WHERE id=?", (pid,))
            conn.commit(); load(search_var.get())

    ttk.Button(btns, text="➕ Ekle", command=add_product).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="✏️ Düzenle", command=edit_product).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="🗑 Sil", command=delete_product).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="🔄 Yenile", command=lambda: load(search_var.get())).pack(side="right", padx=6, pady=8)

    search_var.trace_add("write", lambda *_: load(search_var.get()))
    load()

def mount_users(parent):
    for w in parent.winfo_children(): w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="👥 Kullanıcı Yönetimi", style="Header.TLabel").pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    cols = ("ID","Kullanıcı","Rol")
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for c in cols: tree.heading(c, text=c); tree.column(c, anchor="center", width=160)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))

    def load():
        for r in tree.get_children(): tree.delete(r)
        cursor.execute("SELECT id,username,role FROM users ORDER BY username")
        for row in cursor.fetchall(): tree.insert("", "end", values=row)

    def add_user():
        u = simpledialog.askstring("Yeni Kullanıcı","Kullanıcı adı:")
        if not u: return
        p = simpledialog.askstring("Yeni Kullanıcı","Şifre:")
        if not p: return
        r = simpledialog.askstring("Yeni Kullanıcı","Rol (admin/cashier):", initialvalue="cashier") or "cashier"
        try:
            cursor.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",(u,p,r))
            conn.commit(); load()
        except sqlite3.IntegrityError:
            messagebox.showerror("Hata","Bu kullanıcı adı zaten mevcut!")

    def edit_user():
        sel = tree.selection()
        if not sel: return messagebox.showwarning("Uyarı","Bir kullanıcı seçin.")
        uid, uname, role = tree.item(sel[0])["values"]
        new_u = simpledialog.askstring("Düzenle","Kullanıcı adı:", initialvalue=uname); 
        if new_u is None: return
        new_p = simpledialog.askstring("Düzenle","Yeni şifre (boş bırak=değişmesin):")
        new_r = simpledialog.askstring("Düzenle","Rol:", initialvalue=role) or role
        if new_p:
            cursor.execute("UPDATE users SET username=?,password=?,role=? WHERE id=?",(new_u,new_p,new_r,uid))
        else:
            cursor.execute("UPDATE users SET username=?,role=? WHERE id=?",(new_u,new_r,uid))
        conn.commit(); load()

    def delete_user():
        sel = tree.selection()
        if not sel: return messagebox.showwarning("Uyarı","Bir kullanıcı seçin.")
        uid, uname, _ = tree.item(sel[0])["values"]
        if uname=="admin": return messagebox.showwarning("Uyarı","admin kullanıcısı silinemez!")
        if messagebox.askyesno("Onay", f"{uname} silinsin mi?"):
            cursor.execute("DELETE FROM users WHERE id=?", (uid,))
            conn.commit(); load()

    ttk.Button(btns, text="➕ Ekle", command=add_user).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="✏️ Düzenle", command=edit_user).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="🗑 Sil", command=delete_user).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="🔄 Yenile", command=load).pack(side="right", padx=6, pady=8)
    load()

def mount_receipts(parent):
    for w in parent.winfo_children(): w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="🧾 Kayıtlı Fişler (PDF)", style="Header.TLabel").pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    tree = ttk.Treeview(body, columns=("Dosya","Tarih"), show="headings")
    tree.heading("Dosya", text="Fiş Adı"); tree.heading("Tarih", text="Oluşturulma")
    tree.column("Dosya", width=420); tree.column("Tarih", width=180, anchor="center")
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    temp_dir = os.path.join(tempfile.gettempdir(), "SmartPOS_Receipts")
    os.makedirs(temp_dir, exist_ok=True)

    def load():
        for r in tree.get_children(): tree.delete(r)
        files = sorted(glob.glob(os.path.join(temp_dir, "*.pdf")), reverse=True)
        for f in files:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(f)))
            tree.insert("", "end", values=(os.path.basename(f), ts))

    def open_selected():
        sel = tree.selection()
        if not sel: return messagebox.showwarning("Uyarı","Bir fiş seçin.")
        fname = tree.item(sel[0])["values"][0]
        full = os.path.join(temp_dir, fname)
        if os.path.exists(full):
            try:
                if os.name=="nt": os.startfile(full)  # type: ignore
                else: subprocess.call(("open", full))
            except Exception as e:
                messagebox.showerror("Hata", f"Açılamadı:\n{e}")

    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))
    ttk.Button(btns, text="🖨 Aç / Yazdır", command=open_selected).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="🔄 Yenile", command=load).pack(side="right", padx=6, pady=8)
    load()

def mount_reports(parent):
    for w in parent.winfo_children(): w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="📊 Satış Raporu", style="Header.TLabel").pack(side="left", padx=8)

    filt = ttk.Frame(parent, style="Card.TFrame"); filt.pack(fill="x", padx=12, pady=8)
    sv_from = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    sv_to   = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    ttk.Label(filt, text="Başlangıç (YYYY-MM-DD):").pack(side="left", padx=(10,6))
    ttk.Entry(filt, textvariable=sv_from, width=14).pack(side="left", padx=(0,12))
    ttk.Label(filt, text="Bitiş (YYYY-MM-DD):").pack(side="left", padx=(10,6))
    ttk.Entry(filt, textvariable=sv_to, width=14).pack(side="left", padx=(0,12))

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    cols = ("Fiş No","Tarih","Ürün","Adet","Fiyat","Toplam ₺")
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for c in cols: tree.heading(c, text=c)
    tree.column("Fiş No", width=140, anchor="center")
    tree.column("Tarih",  width=140, anchor="center")
    tree.column("Ürün",   width=220, anchor="w")
    tree.column("Adet",   width=80,  anchor="center")
    tree.column("Fiyat",  width=100, anchor="e")
    tree.column("Toplam ₺",width=110,anchor="e")
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    footer = ttk.Frame(parent, style="Card.TFrame"); footer.pack(fill="x", padx=12, pady=(0,12))
    lbl_sum = ttk.Label(footer, text="Toplam Adet: 0 | Toplam Ciro: 0.00 ₺", style="TLabel")
    lbl_sum.pack(side="left", padx=10)

    def valid_date(s):
        try: datetime.strptime(s, "%Y-%m-%d"); return True
        except: return False

    def load_report():
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            return messagebox.showwarning("Uyarı","Tarih formatı YYYY-MM-DD olmalı.")
        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        for r in tree.get_children(): tree.delete(r)

        cursor.execute("""
          SELECT fis_id, created_at, product_name, quantity, price, total
          FROM sales
          WHERE datetime(created_at) BETWEEN datetime(?) AND datetime(?)
          ORDER BY datetime(created_at) DESC
        """, (f"{frm} 00:00:00", to_plus))
        rows = cursor.fetchall()

        t_qty=0; t_sum=0.0
        for fis_id, ts, pname, qty, price, total in rows:
            ts_disp = (ts or "").replace("T"," ")
            tree.insert("", "end", values=(fis_id, ts_disp, pname, qty, f"{float(price):.2f}", f"{float(total):.2f}"))
            t_qty += int(qty); t_sum += float(total)
        lbl_sum.config(text=f"Toplam Adet: {t_qty} | Toplam Ciro: {t_sum:.2f} ₺")

    def export_csv():
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            return messagebox.showwarning("Uyarı","Tarih formatı YYYY-MM-DD olmalı.")
        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
          SELECT fis_id, created_at, product_name, quantity, price, total
          FROM sales
          WHERE datetime(created_at) BETWEEN datetime(?) AND datetime(?)
          ORDER BY datetime(created_at) DESC
        """, (f"{frm} 00:00:00", to_plus))
        rows = cursor.fetchall()
        if not rows: return messagebox.showinfo("Bilgi","Bu aralıkta satış yok.")
        os.makedirs("reports", exist_ok=True)
        fname = os.path.join("reports", f"rapor_{frm}_to_{to}.csv")
        with open(fname, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Fiş No","Tarih","Ürün","Adet","Fiyat","Toplam ₺"])
            for r in rows: w.writerow([r[0],r[1],r[2],r[3],f"{float(r[4]):.2f}",f"{float(r[5]):.2f}"])
        messagebox.showinfo("Başarılı", f"Rapor kaydedildi:\n{fname}")
        try:
            if os.name=="nt": os.startfile(fname)  # type: ignore
            else: subprocess.call(("open", fname))
        except: pass

    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))
    ttk.Button(btns, text="🔍 Listele", command=load_report).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text="📤 CSV Dışa Aktar", command=export_csv).pack(side="left", padx=6, pady=8)

    load_report()

def mount_sales(parent):
    for w in parent.winfo_children(): w.destroy()

    ttk.Label(parent, text="🧾 Toplu Satış Ekranı", style="Header.TLabel").pack(pady=(10,5))
    ttk.Label(parent, text="Ürünleri sepete ekle, müşteri bilgisi gir, KDV ve indirim uygula.", style="Sub.TLabel").pack()

    top_info = ttk.Frame(parent, style="Card.TFrame"); top_info.pack(fill="x", padx=12, pady=10)
    ttk.Label(top_info, text="Müşteri Adı:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
    customer_entry = ttk.Entry(top_info, width=30); customer_entry.grid(row=0, column=1, padx=6, pady=6)

    ttk.Label(top_info, text="KDV Oranı:").grid(row=0, column=2, padx=6, pady=6, sticky="e")
    vat_cb = ttk.Combobox(top_info, values=["%8","%18","Özel"], state="readonly", width=6)
    vat_cb.set("%18"); vat_cb.grid(row=0, column=3, padx=6, pady=6)

    ttk.Label(top_info, text="İndirim (%):").grid(row=1, column=2, padx=6, pady=6, sticky="e")
    discount_entry = ttk.Entry(top_info, width=6); discount_entry.insert(0,"0")
    discount_entry.grid(row=1, column=3, padx=6, pady=6)

    pick = ttk.Frame(parent, style="Card.TFrame"); pick.pack(fill="x", padx=12, pady=8)
    ttk.Label(pick, text="Ürün:").grid(row=0, column=0, padx=6, pady=6)
    cb_product = ttk.Combobox(pick, values=refresh_product_values_for_combo(), state="readonly", width=28)
    cb_product.grid(row=0, column=1, padx=6, pady=6)

    ttk.Label(pick, text="Adet:").grid(row=0, column=2, padx=6, pady=6)
    e_qty = ttk.Entry(pick, width=6); e_qty.insert(0,"1"); e_qty.grid(row=0, column=3, padx=6, pady=6)

    ttk.Label(pick, text="Fiyat:").grid(row=1, column=0, padx=6, pady=6)
    lbl_price = ttk.Label(pick, text="-", style="Sub.TLabel"); lbl_price.grid(row=1, column=1, sticky="w", padx=6, pady=6)

    ttk.Label(pick, text="Stok:").grid(row=1, column=2, padx=6, pady=6)
    lbl_stock = ttk.Label(pick, text="-", style="Sub.TLabel"); lbl_stock.grid(row=1, column=3, sticky="w", padx=6, pady=6)

    def update_info(*_):
        pname = cb_product.get()
        cursor.execute("SELECT price,stock FROM products WHERE name=?", (pname,))
        r = cursor.fetchone()
        if r: lbl_price.config(text=f"{float(r[0]):.2f} ₺"); lbl_stock.config(text=str(r[1]))
        else: lbl_price.config(text="-"); lbl_stock.config(text="-")
    cb_product.bind("<<ComboboxSelected>>", update_info)

    mid = ttk.Frame(parent, style="Card.TFrame"); mid.pack(fill="both", expand=True, padx=12, pady=10)
    cols = ("Ürün","Adet","Fiyat","Toplam")
    tree = ttk.Treeview(mid, columns=cols, show="headings")
    for c in cols: tree.heading(c, text=c)
    tree.column("Ürün", width=280); tree.column("Adet", width=80, anchor="center")
    tree.column("Fiyat", width=100, anchor="e"); tree.column("Toplam", width=110, anchor="e")
    tree.pack(fill="both", expand=True)

    total_label = ttk.Label(parent, text="Ara Toplam: 0.00 ₺", style="Header.TLabel"); total_label.pack(pady=8)

    def update_total_label():
        total_sum = 0.0
        for row in tree.get_children():
            total_sum += float(tree.item(row)["values"][3])
        total_label.config(text=f"Ara Toplam: {total_sum:.2f} ₺")

    def add_to_cart():
        pname = cb_product.get().strip(); qty = parse_int_safe(e_qty.get(), None)
        if not pname or qty is None or qty <= 0:
            return messagebox.showwarning("Uyarı","Geçerli ürün ve adet girin.")
        cursor.execute("SELECT price,stock FROM products WHERE name=?", (pname,))
        r = cursor.fetchone()
        if not r: return messagebox.showerror("Hata","Ürün bulunamadı.")
        price, stock = float(r[0]), int(r[1])
        if qty > stock: return messagebox.showerror("Hata", f"Yetersiz stok! (Mevcut: {stock})")
        line = qty * price
        tree.insert("", "end", values=(pname, qty, f"{price:.2f}", f"{line:.2f}"))
        update_total_label()

    def remove_selected():
        for s in tree.selection(): tree.delete(s)
        update_total_label()

    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,10))
    ttk.Button(btns, text="➕ Sepete Ekle", command=add_to_cart).pack(side="left", padx=6, pady=6)
    ttk.Button(btns, text="🗑 Seçiliyi Kaldır", command=remove_selected).pack(side="left", padx=6, pady=6)

    def confirm_sale():
        rows = tree.get_children()
        if not rows: return messagebox.showwarning("Uyarı","Sepet boş.")
        customer_name = (customer_entry.get().strip() or "Müşteri")
        kdv_text = vat_cb.get()
        discount_val = parse_float_safe(discount_entry.get(), 0.0) or 0.0
        # KDV
        if kdv_text == "%8": vat_rate = 8.0
        elif kdv_text == "%18": vat_rate = 18.0
        else:
            vat_rate = parse_float_safe(simpledialog.askstring("Özel KDV","KDV oranını gir (%):"), 0.0) or 0.0

        fis_id = f"FIS-{datetime.now().strftime('%Y%m%d')}-{os.urandom(3).hex().upper()}"

        sales_list = []
        subtotal = 0.0
        for row in rows:
            pname, qty, price, total = tree.item(row)["values"]
            qty = int(qty); price = float(price); total = float(total)
            # Stok düş
            cursor.execute("UPDATE products SET stock=stock-? WHERE name=?", (qty, pname))
            # Satırı kaydet
            cursor.execute("""
               INSERT INTO sales(fis_id,product_name,quantity,price,total,created_at)
               VALUES(?,?,?,?,?,datetime('now','localtime'))
            """, (fis_id, pname, qty, price, total))
            sales_list.append((pname, qty, price, total))
            subtotal += total

        conn.commit()

        # PDF
        print_receipt(sales_list, fis_id=fis_id, customer_name=customer_name,
                      kdv_rate=vat_rate, discount_rate=discount_val)

        # Bilgi
        # Genel toplam hesaplamak için:
        discount_amount = subtotal * (discount_val/100.0)
        after_discount = subtotal - discount_amount
        vat_amount = after_discount * (vat_rate/100.0)
        grand_total = after_discount + vat_amount

        messagebox.showinfo("Satış Tamamlandı",
            f"Müşteri: {customer_name}\nFiş No: {fis_id}\nToplam: {grand_total:.2f} ₺")

        # Paneli sıfırla
        for r in tree.get_children(): tree.delete(r)
        update_total_label()
        cb_product.set(""); lbl_price.config(text="-"); lbl_stock.config(text="-")

    ttk.Button(parent, text="✅ Satışı Onayla", command=confirm_sale).pack(pady=(0,12))

def export_daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("reports", exist_ok=True)
    filename = os.path.join("reports", f"rapor_{today}.csv")
    cursor.execute("""
      SELECT fis_id, product_name, quantity, price, total, created_at
      FROM sales WHERE date(created_at) = date('now','localtime')
      ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    if not rows: return messagebox.showinfo("Bilgi","Bugün için satış yok.")
    with open(filename, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["Fiş No","Ürün","Adet","Fiyat","Toplam","Tarih"])
        for r in rows: w.writerow([r[0],r[1],r[2],f"{float(r[3]):.2f}",f"{float(r[4]):.2f}",r[5]])
    messagebox.showinfo("Başarılı", f"Günlük rapor kaydedildi:\n{filename}")
    try:
        if os.name=="nt": os.startfile(filename)  # type: ignore
        else: subprocess.call(("open", filename))
    except: pass

# ==========================
# Ana Pencere (tek pencere navigasyon)
# ==========================
def open_main_window(role):
    main = tk.Toplevel()
    main.title(f"{APP_TITLE} - {role.upper()}")
    set_theme(main); center_window(main, 1080, 720)

    top_bar = ttk.Frame(main, style="Card.TFrame"); top_bar.pack(fill="x", padx=10, pady=(8,4))
    ttk.Label(top_bar, text=f"{APP_TITLE} {APP_VERSION}", style="Header.TLabel").pack(side="left", padx=10)
    ttk.Label(top_bar, text=f"Oturum: {role.title()}", style="Sub.TLabel").pack(side="left", padx=8)
    ttk.Button(top_bar, text="🚪 Çıkış Yap", command=lambda: logout_action(main)).pack(side="right", padx=6)

    body = ttk.Frame(main); body.pack(fill="both", expand=True, padx=10, pady=10)

    # Sol Menü
    menu = ttk.Frame(body, style="Card.TFrame", width=260); menu.pack(side="left", fill="y", padx=(10,6), pady=10)
    menu.pack_propagate(False)
    ttk.Label(menu, text="📂 İşlem Menüsü", style="Header.TLabel").pack(pady=(12,10))

    # Sağ Panel (dinamik)
    global right_panel
    right_panel = ttk.Frame(body, style="Card.TFrame"); right_panel.pack(side="right", fill="both", expand=True, padx=(0,10), pady=10)
    ttk.Label(right_panel, text="Sol menüden bir işlem seçiniz 👈", font=("Segoe UI", 12, "italic"),
              background=CARD_COLOR, foreground=TEXT_GRAY).pack(expand=True)

    def mbtn(parent, text, cmd):
        b = tk.Button(parent, text=text, bg=CARD_COLOR, fg="white",
                      font=("Segoe UI",10,"bold"), activebackground="#003c66",
                      activeforeground="white", relief="flat", padx=10, pady=10,
                      anchor="w", borderwidth=0, command=cmd)
        b.pack(fill="x", pady=4, padx=14)
        return b

    if role == "admin":
        mbtn(menu, "🛒 Satış Yap", lambda: mount_sales(right_panel))
        mbtn(menu, "📦 Ürün Yönetimi", lambda: mount_products(right_panel))
        mbtn(menu, "👥 Kullanıcı Yönetimi", lambda: mount_users(right_panel))
        mbtn(menu, "🧾 Fişleri Görüntüle / Yazdır", lambda: mount_receipts(right_panel))
        mbtn(menu, "📊 Raporlar", lambda: mount_reports(right_panel))
        mbtn(menu, "💾 Günlük Raporu Kaydet", export_daily_report)
    else:
        mbtn(menu, "🛒 Satış Yap", lambda: mount_sales(right_panel))
        mbtn(menu, "🧾 Fişleri Görüntüle / Yazdır", lambda: mount_receipts(right_panel))

    footer = ttk.Frame(main, style="Card.TFrame"); footer.pack(fill="x", padx=10, pady=(0,8))
    ttk.Label(footer, text="SmartPOS Mini Pro © 2025", style="Sub.TLabel").pack(side="left", padx=10)
    ttk.Label(footer, text="Zaman damgası: "+datetime.now().strftime("%d.%m.%Y %H:%M"), style="Sub.TLabel").pack(side="right", padx=10)

def logout_action(window):
    window.destroy()
    login_window.deiconify()

# ==========================
# Login
# ==========================
def login_action():
    username = entry_username.get().strip()
    password = entry_password.get().strip()
    cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username,password))
    r = cursor.fetchone()
    if r:
        role = r[0]
        open_main_window(role)
        login_window.withdraw()
    else:
        messagebox.showerror("Hata","Kullanıcı adı veya şifre hatalı!")

def toggle_password():
    if entry_password.cget("show") == "*":
        entry_password.config(show=""); btn_toggle_pw.config(text="🙈 Gizle")
    else:
        entry_password.config(show="*"); btn_toggle_pw.config(text="👁 Göster")

def start_login_screen():
    global login_window, entry_username, entry_password, btn_toggle_pw
    login_window = tk.Tk()
    login_window.title(f"{APP_TITLE} Giriş")
    set_theme(login_window); center_window(login_window, 420, 720)

    ttk.Label(login_window, text=APP_TITLE, style="Header.TLabel").pack(pady=(10, 4))
    ttk.Label(login_window, text="Küçük işletmeler için satış sistemi", style="Sub.TLabel").pack(pady=(0, 12))

    frame = ttk.Frame(login_window, style="Card.TFrame"); frame.pack(pady=10, padx=24, fill="x")
    ttk.Label(frame, text="Kullanıcı Adı:").pack(pady=(16,4), anchor="w")
    entry_username = ttk.Entry(frame, font=("Segoe UI",10)); entry_username.pack(pady=(0,8), ipady=3, fill="x", padx=16)

    ttk.Label(frame, text="Şifre:").pack(pady=(8,4), anchor="w")
    pw_row = ttk.Frame(frame, style="Card.TFrame"); pw_row.pack(fill="x", padx=16)
    entry_password = ttk.Entry(pw_row, show="*", font=("Segoe UI",10)); entry_password.pack(side="left", fill="x", expand=True)
    btn_toggle_pw = ttk.Button(pw_row, text="👁 Göster", command=toggle_password); btn_toggle_pw.pack(side="left", padx=(8,0))

    ttk.Button(frame, text="Giriş Yap", command=login_action).pack(pady=20, ipadx=20)
    login_window.bind("<Return>", lambda e: login_action())
    ttk.Label(login_window, text=f"{APP_VERSION}", style="Sub.TLabel").pack(side="bottom", pady=10)
    login_window.mainloop()

# ==========================
# Çalıştır
# ==========================
if __name__ == "__main__":
    start_login_screen()
