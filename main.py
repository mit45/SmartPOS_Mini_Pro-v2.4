import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3, os, sys, csv, subprocess, time, glob, tempfile
from datetime import datetime, date
from PIL import Image, ImageTk # type: ignore
from languages import LANGUAGES
from pos.db_handler import get_connection, init_schema
from services import product_service as product_svc
from receipts import print_receipt, print_thermal_receipt

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

# ==========================
# Dil Sistemi (Yeni)
# ==========================
CURRENT_LANGUAGE = "tr"

def t(key: str) -> str:
    """Çeviri fonksiyonu - Translation function"""
    result = LANGUAGES.get(CURRENT_LANGUAGE, LANGUAGES["tr"]).get(key, key)
    return result if result is not None else key

def set_language(lang_code: str):
    """Dili değiştir ve ayarı veritabanına yaz."""
    global CURRENT_LANGUAGE
    CURRENT_LANGUAGE = lang_code
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('language', ?)", (lang_code,))
        conn.commit()
    except Exception:
        pass

def load_language_preference():
    """Kaydedilmiş dil tercihini yükle - Load saved language preference"""
    global CURRENT_LANGUAGE
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("SELECT value FROM settings WHERE key='language'")
        result = cursor.fetchone()
        if result:
            CURRENT_LANGUAGE = result[0]
    except Exception:
        pass

def set_theme(window):
    style = ttk.Style(window)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    window.configure(bg=BG_COLOR)
    style.configure("TFrame", background=BG_COLOR)
    style.configure("TLabel", background=BG_COLOR, foreground=TEXT_LIGHT, font=("Segoe UI", 10))
    style.configure("Header.TLabel", background=BG_COLOR, foreground=ACCENT, font=("Segoe UI", 16, "bold"))
    style.configure("Sub.TLabel", background=BG_COLOR, foreground=TEXT_GRAY,  font=("Segoe UI", 9))
    style.configure("Card.TFrame", background=CARD_COLOR)
    style.configure("Treeview", background="#1f1f25", fieldbackground="#1f1f25", foreground=TEXT_LIGHT)
    style.configure("Treeview.Heading", background="#30303a", foreground=TEXT_LIGHT)
    style.map("Treeview", background=[("selected", "#004e75")])
    # Menü scrollbari opak görünsün
    try:
        style.configure("Menu.Vertical.TScrollbar",
                        background="#3a3a45",
                        troughcolor="#2a2a35",
                        bordercolor="#3a3a45",
                        arrowcolor="#ffffff")
        style.map("Menu.Vertical.TScrollbar",
                   background=[("active", "#4a4a55"), ("pressed", "#5a5a66")])
    except Exception:
        pass

def center_window(win, width: int, height: int):
    """Pencereyi ekranda ortala ve görünür olmasını garanti et."""
    try:
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        width  = min(width,  int(screen_w * 0.92))
        height = min(height, int(screen_h * 0.92))
        x = int((screen_w / 2) - (width / 2))
        y = int((screen_h / 2) - (height / 2))
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.lift()
        win.attributes('-topmost', True)
        win.after(200, lambda: win.attributes('-topmost', False))
    except Exception:
        pass

# ==========================
# Veritabanı bağlantısı ve şema kurulumu
# ==========================
conn, cursor = get_connection()
init_schema(conn, cursor)
load_language_preference()

# Yardımcı dönüştürücüler ve yardımcı fonksiyonlar
def parse_float_safe(val, default: float | None = 0.0):
    try:
        if val is None:
            return default
        s = str(val).strip().replace(",", ".")
        return float(s)
    except Exception:
        return default

def parse_int_safe(val, default: int | None = 0):
    try:
        if val is None:
            return default
        s = str(val).strip()
        return int(float(s)) if s else default
    except Exception:
        return default

def refresh_product_values_for_combo():
    try:
        rows = product_svc.list_products(cursor)
        return [r[1] for r in rows]  # name column
    except Exception:
        return []

# moved to receipts.thermal_printer

# ==========================
# Gömülü Modüller (tek pencere)
# ==========================
def mount_products(parent):
    from ui.products_view import mount_products as _mount_products_view
    return _mount_products_view(parent, conn, cursor, t, FG_COLOR, BG_COLOR, CARD_COLOR, ACCENT)

def mount_irsaliye(parent):
    for w in parent.winfo_children():
        w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="📥 " + t('dispatch_entry'), style="Header.TLabel").pack(side="left", padx=8)
    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    ttk.Label(body, text=t('dispatch_entry_coming'), font=("Segoe UI", 12), background=CARD_COLOR).pack(expand=True, padx=16, pady=16)


def mount_fatura(parent):
    for w in parent.winfo_children():
        w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="🧾 " + t('invoice_entry'), style="Header.TLabel").pack(side="left", padx=8)
    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    ttk.Label(body, text=t('invoice_entry_coming'), font=("Segoe UI", 12), background=CARD_COLOR).pack(expand=True, padx=16, pady=16)


def mount_placeholder(parent, icon, title_text, body_text):
    for w in parent.winfo_children():
        w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text=f"{icon} {title_text}", style="Header.TLabel").pack(side="left", padx=8)
    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    ttk.Label(body, text=body_text, font=("Segoe UI", 12), background=CARD_COLOR).pack(expand=True, padx=16, pady=16)


# Generic placeholder pages for new submenus
def mount_barkod(parent):
    mount_placeholder(parent, "🏷️", t('barcode_mgmt'), t('coming_soon'))

def mount_kategori(parent):
    mount_placeholder(parent, "🗂️", t('category_mgmt'), t('coming_soon'))

def mount_stok_giris(parent):
    mount_placeholder(parent, "⬆️", t('stock_in'), t('coming_soon'))

def mount_stok_cikis(parent):
    mount_placeholder(parent, "⬇️", t('stock_out'), t('coming_soon'))

def mount_envanter_sayim(parent):
    mount_placeholder(parent, "📦", t('inventory_count'), t('coming_soon'))

def mount_tahsilat(parent):
    mount_placeholder(parent, "💰", t('collection_entry'), t('coming_soon'))

def mount_odeme(parent):
    mount_placeholder(parent, "💸", t('payment_entry'), t('coming_soon'))

def mount_cari_hareketler(parent):
    mount_placeholder(parent, "🔁", t('transactions'), t('coming_soon'))

def mount_hizmet_listesi(parent):
    mount_placeholder(parent, "🛠️", t('service_list'), t('coming_soon'))

def mount_masraf_ekle(parent):
    mount_placeholder(parent, "➕", t('add_expense'), t('coming_soon'))

def mount_masraf_raporu(parent):
    mount_placeholder(parent, "📑", t('expense_report'), t('coming_soon'))

def mount_tedarikci_listesi(parent):
    mount_placeholder(parent, "🚚", t('supplier_list'), t('coming_soon'))

def mount_personel_vardiya(parent):
    mount_placeholder(parent, "🕒", t('shift_mgmt'), t('coming_soon'))

def mount_personel_maas(parent):
    mount_placeholder(parent, "💳", t('salary_advance'), t('coming_soon'))

def mount_depo_listesi(parent):
    mount_placeholder(parent, "🏬", t('warehouse_list'), t('coming_soon'))

def mount_depo_transfer(parent):
    mount_placeholder(parent, "🔄", t('transfer'), t('coming_soon'))

def mount_depo_hareket(parent):
    mount_placeholder(parent, "📦", t('warehouse_movements'), t('coming_soon'))

def mount_kasa_hareket(parent):
    mount_placeholder(parent, "💵", t('cash_movements'), t('coming_soon'))

def mount_kasa_devir(parent):
    mount_placeholder(parent, "🔁", t('cash_closure'), t('coming_soon'))

def mount_kasa_rapor(parent):
    mount_placeholder(parent, "📈", t('cash_report'), t('coming_soon'))

def mount_stok_raporu(parent):
    mount_placeholder(parent, "📊", t('stock_report_menu'), t('coming_soon'))

def mount_cari_raporu(parent):
    mount_placeholder(parent, "📊", t('account_report_menu'), t('coming_soon'))

def mount_kasa_raporu(parent):
    mount_placeholder(parent, "📊", t('cash_report_menu'), t('coming_soon'))


def mount_users(parent):
    for w in parent.winfo_children(): w.destroy()
    
    # Modern header
    header = ttk.Frame(parent, style="Card.TFrame")
    header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="👥 " + t('user_management'), style="Header.TLabel", 
              font=("Segoe UI", 16, "bold")).pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame")
    body.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Modern table
    cols = (t('id'), t('user'), t('role'))
    tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
    for c in cols: 
        tree.heading(c, text=c)
        tree.column(c, anchor="center", width=200)
    
    # Zebrastripe
    tree.tag_configure('oddrow', background='#1f1f25')
    tree.tag_configure('evenrow', background='#252530')
    
    original_insert = tree.insert
    def insert_with_tags(*args, **kwargs):
        item = original_insert(*args, **kwargs)
        idx = tree.index(item)
        tree.item(item, tags=('evenrow',) if idx % 2 == 0 else ('oddrow',))
        return item
    tree.insert = insert_with_tags
    
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    btns = ttk.Frame(parent, style="Card.TFrame")
    btns.pack(fill="x", padx=12, pady=(0,12))

    from services import users_service as users_svc

    def load():
        for r in tree.get_children(): tree.delete(r)
        for row in users_svc.list_users(cursor):
            tree.insert("", "end", values=row)

    def add_user():
        u = simpledialog.askstring(t('new_user'), t('username'))
        if not u: return
        p = simpledialog.askstring(t('new_user'), t('password'))
        if not p: return
        r = simpledialog.askstring(t('new_user'), t('role_input'), initialvalue="cashier") or "cashier"
        try:
            users_svc.add_user(conn, cursor, u, p, r)
            load()
        except sqlite3.IntegrityError:
            messagebox.showerror(t('error'), t('duplicate_user_error'))
        except ValueError as ve:
            messagebox.showwarning(t('warning'), str(ve))

    def edit_user():
        sel = tree.selection()
        if not sel: return messagebox.showwarning(t('warning'), t('select_item'))
        uid, uname, role = tree.item(sel[0])["values"]
        new_u = simpledialog.askstring(t('edit'), t('username'), initialvalue=uname)
        if new_u is None: return
        new_p = simpledialog.askstring(t('edit'), t('new_password'))
        new_r = simpledialog.askstring(t('edit'), t('role'), initialvalue=role) or role
        users_svc.update_user(conn, cursor, int(uid), new_u, new_r, new_p)
        load()

    def delete_user():
        sel = tree.selection()
        if not sel: return messagebox.showwarning(t('warning'), t('select_item'))
        uid, uname, _ = tree.item(sel[0])["values"]
        if uname=="admin": return messagebox.showwarning(t('warning'), t('admin_delete_error'))
        if messagebox.askyesno(t('confirm'), f"{uname} {t('delete_confirm')}"):
            try:
                users_svc.delete_user(conn, cursor, int(uid), uname)
                load()
            except PermissionError:
                messagebox.showwarning(t('warning'), t('admin_delete_error'))

    # Modern butonlar
    def create_user_button(parent, text, command, bg_color):
        btn = tk.Button(parent, text=text, command=command,
                       bg=bg_color, fg="white", font=("Segoe UI", 10, "bold"),
                       activebackground=bg_color, activeforeground="white",
                       relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0)
        
        def on_enter(e):
            factor = 1.15 if bg_color in ["#10b981", "#00b0ff"] else 0.85
            new_color = adjust_user_brightness(bg_color, factor)
            btn.config(bg=new_color)
        
        def on_leave(e):
            btn.config(bg=bg_color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.pack(side="left", padx=4, pady=8)
    
    def adjust_user_brightness(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(min(255, max(0, r * factor)))
        g = int(min(255, max(0, g * factor)))
        b = int(min(255, max(0, b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    create_user_button(btns, "➕ " + t('add'), add_user, "#10b981")
    create_user_button(btns, "✏️ " + t('edit'), edit_user, "#00b0ff")
    create_user_button(btns, "🗑 " + t('delete'), delete_user, "#ef4444")
    
    refresh_btn = tk.Button(btns, text="🔄 " + t('refresh'), command=load,
                           bg="#8b5cf6", fg="white", font=("Segoe UI", 10, "bold"),
                           activebackground="#7c3aed", activeforeground="white",
                           relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0)
    refresh_btn.pack(side="right", padx=4, pady=8)
    
    def refresh_hover_in(e): refresh_btn.config(bg="#7c3aed")
    def refresh_hover_out(e): refresh_btn.config(bg="#8b5cf6")
    refresh_btn.bind("<Enter>", refresh_hover_in)
    refresh_btn.bind("<Leave>", refresh_hover_out)
    load()

def mount_receipts(parent):
    for w in parent.winfo_children(): w.destroy()
    
    # Modern header
    header = ttk.Frame(parent, style="Card.TFrame")
    header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="🧾 " + t('receipts_title'), style="Header.TLabel",
              font=("Segoe UI", 16, "bold")).pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame")
    body.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Modern table
    tree = ttk.Treeview(body, columns=(t('file'), t('date')), show="headings", height=14)
    tree.heading(t('file'), text=t('file'))
    tree.heading(t('date'), text=t('date'))
    tree.column(t('file'), width=480)
    tree.column(t('date'), width=200, anchor="center")
    
    # Zebrastripe
    tree.tag_configure('oddrow', background='#1f1f25')
    tree.tag_configure('evenrow', background='#252530')
    
    original_insert = tree.insert
    def insert_with_tags(*args, **kwargs):
        item = original_insert(*args, **kwargs)
        idx = tree.index(item)
        tree.item(item, tags=('evenrow',) if idx % 2 == 0 else ('oddrow',))
        return item
    tree.insert = insert_with_tags
    
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
        if not sel: return messagebox.showwarning(t('warning'), t('select_item'))
        fname = tree.item(sel[0])["values"][0]
        full = os.path.join(temp_dir, fname)
        if os.path.exists(full):
            try:
                if os.name=="nt": os.startfile(full)  # type: ignore
                else: subprocess.call(("open", full))
            except Exception as e:
                messagebox.showerror(t('error'), f"{t('open_failed')}\n{e}")

    # Modern butonlar
    btns = ttk.Frame(parent, style="Card.TFrame")
    btns.pack(fill="x", padx=12, pady=(0,12))
    
    def create_receipt_button(parent, text, command, bg_color):
        btn = tk.Button(parent, text=text, command=command,
                       bg=bg_color, fg="white", font=("Segoe UI", 10, "bold"),
                       activebackground=bg_color, activeforeground="white",
                       relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0)
        
        def on_enter(e):
            factor = 1.15
            new_color = adjust_receipt_brightness(bg_color, factor)
            btn.config(bg=new_color)
        
        def on_leave(e):
            btn.config(bg=bg_color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn
    
    def adjust_receipt_brightness(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(min(255, max(0, r * factor)))
        g = int(min(255, max(0, g * factor)))
        b = int(min(255, max(0, b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    create_receipt_button(btns, "🖨 " + t('open_print'), open_selected, "#00b0ff").pack(side="left", padx=4, pady=8)
    create_receipt_button(btns, "🔄 " + t('refresh'), load, "#8b5cf6").pack(side="right", padx=4, pady=8)
    load()

def mount_reports(parent):
    for w in parent.winfo_children(): w.destroy()
    
    # Modern header
    header = ttk.Frame(parent, style="Card.TFrame")
    header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="📊 " + t('reports_title'), style="Header.TLabel",
              font=("Segoe UI", 16, "bold")).pack(side="left", padx=8)

    # Modern tarih filtreleri
    filt = tk.Frame(parent, bg=CARD_COLOR)
    filt.pack(fill="x", padx=12, pady=12)
    
    sv_from = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    sv_to = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    
    tk.Label(filt, text="📅 " + t('start_date'), bg=CARD_COLOR, fg=TEXT_LIGHT,
             font=("Segoe UI", 10, "bold")).pack(side="left", padx=(10,6))
    from_entry = ttk.Entry(filt, textvariable=sv_from, width=16, font=("Segoe UI", 11))
    from_entry.pack(side="left", padx=(0,16), ipady=4)
    
    tk.Label(filt, text="📅 " + t('end_date'), bg=CARD_COLOR, fg=TEXT_LIGHT,
             font=("Segoe UI", 10, "bold")).pack(side="left", padx=(10,6))
    to_entry = ttk.Entry(filt, textvariable=sv_to, width=16, font=("Segoe UI", 11))
    to_entry.pack(side="left", padx=(0,12), ipady=4)

    # Butonlar (tarih seçici alanının hemen altında, tablo üstünde)
    btns = ttk.Frame(parent, style="Card.TFrame")
    btns.pack(fill="x", padx=12, pady=(6,8))
    
    def create_report_button(parent, text, command, bg_color):
        btn = tk.Button(parent, text=text, command=command,
                       bg=bg_color, fg="white", font=("Segoe UI", 10, "bold"),
                       activebackground=bg_color, activeforeground="white",
                       relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0)
        
        def on_enter(e):
            new_color = adjust_report_brightness(bg_color, 1.15)
            btn.config(bg=new_color)
        
        def on_leave(e):
            btn.config(bg=bg_color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.pack(side="left", padx=4, pady=4)
        return btn
    
    def adjust_report_brightness(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(min(255, max(0, r * factor)))
        g = int(min(255, max(0, g * factor)))
        b = int(min(255, max(0, b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    body = ttk.Frame(parent, style="Card.TFrame")
    body.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Modern table
    cols = (t('receipt_no'), t('date'), t('product'), t('quantity'), t('price'), t('total'))
    tree = ttk.Treeview(body, columns=cols, show="headings", height=12)
    for c in cols: tree.heading(c, text=c)
    tree.column(t('receipt_no'), width=140, anchor="center")
    tree.column(t('date'), width=140, anchor="center")
    tree.column(t('product'), width=220, anchor="w")
    tree.column(t('quantity'), width=80, anchor="center")
    tree.column(t('price'), width=100, anchor="e")
    tree.column(t('total'), width=110, anchor="e")
    
    # Zebrastripe
    tree.tag_configure('oddrow', background='#1f1f25')
    tree.tag_configure('evenrow', background='#252530')
    
    original_insert = tree.insert
    def insert_with_tags(*args, **kwargs):
        item = original_insert(*args, **kwargs)
        idx = tree.index(item)
        tree.item(item, tags=('evenrow',) if idx % 2 == 0 else ('oddrow',))
        return item
    tree.insert = insert_with_tags
    
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    # Modern footer - toplam bilgisi
    footer = tk.Frame(parent, bg=CARD_COLOR)
    footer.pack(fill="x", padx=12, pady=(0,12))
    lbl_sum = tk.Label(footer, text=f"{t('quantity')}: 0 | {t('total')}: 0.00 ₺",
                      bg=CARD_COLOR, fg=ACCENT, font=("Segoe UI", 12, "bold"))
    lbl_sum.pack(side="left", padx=10)

    def valid_date(s):
        try: datetime.strptime(s, "%Y-%m-%d"); return True
        except: return False

    from services import sales_service as sales_svc

    def load_report():
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            return messagebox.showwarning(t('warning'), t('date_format_warning'))
        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        for r in tree.get_children(): tree.delete(r)
        rows = sales_svc.list_sales_between(cursor, f"{frm} 00:00:00", to_plus)

        t_qty=0; t_sum=0.0
        for fis_id, ts, pname, qty, price, total in rows:
            ts_disp = (ts or "").replace("T"," ")
            tree.insert("", "end", values=(fis_id, ts_disp, pname, qty, f"{float(price):.2f}", f"{float(total):.2f}"))
            t_qty += int(qty); t_sum += float(total)
        lbl_sum.config(text=f"{t('quantity')}: {t_qty} | {t('total')}: {t_sum:.2f} ₺")

    def export_csv():
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            return messagebox.showwarning(t('warning'), t('date_format_warning'))
        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        rows = sales_svc.list_sales_between(cursor, f"{frm} 00:00:00", to_plus)
        if not rows: return messagebox.showinfo(t('info'), t('no_sales_in_range'))
        os.makedirs("reports", exist_ok=True)
        fname = os.path.join("reports", f"rapor_{frm}_to_{to}.csv")
        with open(fname, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([t('receipt_no'), t('date'), t('product'), t('quantity'), t('price'), t('total')])
            for r in rows: w.writerow([r[0],r[1],r[2],r[3],f"{float(r[4]):.2f}",f"{float(r[5]):.2f}"])
        messagebox.showinfo(t('success'), f"{t('report_saved')}\n{fname}")
        try:
            if os.name=="nt": os.startfile(fname)  # type: ignore
            else: subprocess.call(("open", fname))
        except: pass

    def export_pdf():
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            return messagebox.showwarning(t('warning'), t('date_format_warning'))
        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        rows = sales_svc.list_sales_between(cursor, f"{frm} 00:00:00", to_plus)
        if not rows: return messagebox.showinfo(t('info'), t('no_sales_in_range'))
        
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            os.makedirs("reports", exist_ok=True)
            fname = os.path.join("reports", f"rapor_{frm}_to_{to}.pdf")
            
            # Türkçe karakter desteği
            try:
                pdfmetrics.registerFont(TTFont('DejaVu', 'fonts/DejaVuSans.ttf'))
                default_font = 'DejaVu'
            except:
                default_font = 'Helvetica'
            
            doc = SimpleDocTemplate(fname, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            # Başlık
            title_style = styles['Title']
            title_style.fontName = default_font
            elements.append(Paragraph(t('reports_title'), title_style))
            elements.append(Spacer(1, 12))
            
            # Tarih aralığı
            info = [[t('start_date'), frm], [t('end_date'), to]]
            info_table = Table(info, colWidths=[80*mm, 100*mm])
            info_table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), default_font),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ]))
            elements.append(info_table)
            elements.append(Spacer(1, 12))
            
            # Tablo verileri
            data = [[t('receipt_no'), t('date'), t('product'), t('quantity'), t('price'), t('total')]]
            t_qty = 0
            t_sum = 0.0
            for fis_id, ts, pname, qty, price, total in rows:
                ts_disp = (ts or "").replace("T", " ")
                data.append([str(fis_id), ts_disp, str(pname), str(qty), f"{float(price):.2f}", f"{float(total):.2f}"])
                t_qty += int(qty)
                t_sum += float(total)
            
            # Toplam satırı
            data.append(['', '', t('total'), str(t_qty), '', f"{t_sum:.2f} ₺"])
            
            product_table = Table(data, colWidths=[45*mm, 40*mm, 50*mm, 20*mm, 25*mm, 30*mm])
            product_table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), default_font),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('ALIGN', (2,1), (2,-1), 'LEFT'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),
                ('FONTSIZE', (0,-1), (-1,-1), 10),
                ('TEXTCOLOR', (0,-1), (-1,-1), colors.blue),
            ]))
            elements.append(product_table)
            
            doc.build(elements)
            messagebox.showinfo(t('success'), f"{t('report_saved')}\n{fname}")
            try:
                if os.name=="nt": os.startfile(fname)  # type: ignore
                else: subprocess.call(("open", fname))
            except: pass
        except ImportError:
            messagebox.showerror(t('error'), "ReportLab kütüphanesi gerekli!\n\nTerminalden şu komutu çalıştırın:\npip install reportlab")
        except Exception as e:
            messagebox.showerror(t('error'), f"PDF oluşturma hatası:\n\n{str(e)}")

    # Butonları oluştur (yukarıda tanımlandı)
    create_report_button(btns, "🔍 " + t('list'), load_report, "#00b0ff")
    create_report_button(btns, "� PDF", export_pdf, "#9333ea")
    create_report_button(btns, "📥 CSV", export_csv, "#10b981")

    load_report()

    # Satır çift tıklanınca ilgili fişi PDF olarak aç
    def open_receipt_pdf_from_row(event=None):
        try:
            sel = tree.selection()
            if not sel: return
            values = tree.item(sel[0]).get("values", [])
            if not values: return
            fis_id = str(values[0])

            # Fiş satırlarını DB'den çek
            cursor.execute("""
                SELECT product_name, quantity, price, total
                FROM sales
                WHERE fis_id=? AND (canceled IS NULL OR canceled=0)
                ORDER BY created_at ASC
            """, (fis_id,))
            rows = cursor.fetchall()
            if not rows:
                return messagebox.showinfo(t('info'), t('no_sales_in_range'))

            # Satış listesi: (pname, qty, base_price_for_display, line_gross)
            # PDF'te fiyatı KDV dahil göstermek için base_price olarak brüt birim fiyatı geçiyoruz
            sales_list = []
            for pname, qty, unit_net, line_gross in rows:
                q = float(qty) if qty else 1.0
                unit_gross = float(line_gross) / q if q else float(unit_net)
                sales_list.append((str(pname), int(qty), float(unit_gross), float(line_gross)))

            # Etkin KDV oranını yaklaşık hesapla (bilgi amaçlı)
            try:
                ratios = []
                for _, qty, unit_net, line_gross in rows:
                    q = float(qty) if qty else 1.0
                    unit_net_f = float(unit_net)
                    unit_gross_f = float(line_gross) / q if q else unit_net_f
                    if unit_net_f > 0:
                        ratios.append(max(0.0, (unit_gross_f/unit_net_f - 1.0)*100.0))
                kdv_rate_guess = round(sum(ratios)/len(ratios), 2) if ratios else 0.0
            except Exception:
                kdv_rate_guess = 0.0

            # Fişi PDF olarak üret ve aç (fiyatları KDV dahil göster)
            print_receipt(
                sales_list,
                fis_id=fis_id,
                customer_name=t('customer'),
                kdv_rate=kdv_rate_guess,
                discount_rate=0.0,
                vat_included=True,
                open_after=True,
                show_message=False,
                language_code=CURRENT_LANGUAGE
            )
        except Exception as e:
            messagebox.showerror(t('error'), str(e))

    tree.bind("<Double-1>", open_receipt_pdf_from_row)

def mount_cariler(parent):
    for w in parent.winfo_children(): w.destroy()

    # Modern header
    header = ttk.Frame(parent, style="Card.TFrame")
    header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="💼 " + t('cari_management'), style="Header.TLabel",
              font=("Segoe UI", 16, "bold")).pack(side="left", padx=8)
    
    search_var = tk.StringVar()
    ttk.Entry(header, textvariable=search_var, font=("Segoe UI", 10)).pack(side="right", padx=8)
    ttk.Label(header, text=t('search'), style="TLabel").pack(side="right")

    # Özet bilgiler
    summary = ttk.Frame(parent, style="Card.TFrame")
    summary.pack(fill="x", padx=12, pady=8)
    
    from services import cari_service
    
    total_alacak_label = ttk.Label(summary, text="", style="Sub.TLabel", font=("Segoe UI", 11, "bold"))
    total_alacak_label.pack(side="left", padx=12)
    
    total_borc_label = ttk.Label(summary, text="", style="Sub.TLabel", font=("Segoe UI", 11, "bold"))
    total_borc_label.pack(side="left", padx=12)
    
    def update_summary():
        alacak = cari_service.get_total_alacak(cursor)
        borc = cari_service.get_total_borc(cursor)
        total_alacak_label.config(text=f"✅ {t('total_alacak')} {alacak:.2f} ₺", foreground="#10b981")
        total_borc_label.config(text=f"❌ {t('total_borc')} {borc:.2f} ₺", foreground="#ef4444")

    # Ana gövde: sol tarafta liste, sağ tarafta form
    body = ttk.Frame(parent, style="Card.TFrame")
    body.pack(fill="both", expand=True, padx=12, pady=8)
    left = ttk.Frame(body, style="Card.TFrame")
    left.pack(side="left", fill="both", expand=True, padx=(8,4), pady=8)
    right = ttk.Frame(body, style="Card.TFrame")
    right.pack(side="left", fill="y", padx=(4,8), pady=8)

    # Modern table
    cols = (t('id'), t('name'), t('phone'), t('balance'), t('cari_type'))
    tree = ttk.Treeview(left, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
    tree.column(t('id'), width=60, anchor="center")
    tree.column(t('name'), anchor="w", width=200)
    tree.column(t('phone'), anchor="w", width=120)
    tree.column(t('balance'), anchor="e", width=120)
    tree.column(t('cari_type'), anchor="center", width=100)
    
    # Zebrastripe
    tree.tag_configure('oddrow', background='#1f1f25')
    tree.tag_configure('evenrow', background='#252530')
    tree.tag_configure('positive', foreground='#10b981')
    tree.tag_configure('negative', foreground='#ef4444')
    
    tree.pack(fill="both", expand=True)

    # Form bölümü
    form_header = tk.Label(right, text="📝 " + t('cari_info'), bg=CARD_COLOR, fg=ACCENT,
                          font=("Segoe UI", 12, "bold"))
    form_header.pack(pady=(8,12), padx=8)

    def lbl(parent, text):
        ttk.Label(parent, text=text, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(8,2))
    
    def ent():
        e = ttk.Entry(right, width=30, font=("Segoe UI", 10))
        e.pack(padx=8, pady=(0,8), ipady=4)
        return e

    lbl(right, t('cari_name'))
    entry_name = ent()
    
    lbl(right, t('phone'))
    entry_phone = ent()
    
    lbl(right, t('address'))
    entry_address = ent()
    
    lbl(right, t('balance'))
    entry_balance = ent()
    entry_balance.insert(0, "0")
    
    lbl(right, t('cari_type'))
    cari_type_var = tk.StringVar(value='alacakli')
    type_frame = ttk.Frame(right)
    type_frame.pack(padx=8, pady=(0,12))
    ttk.Radiobutton(type_frame, text=t('alacakli'), variable=cari_type_var, value='alacakli').pack(side="left", padx=4)
    ttk.Radiobutton(type_frame, text=t('borclu'), variable=cari_type_var, value='borclu').pack(side="left", padx=4)

    def load(search=""):
        for r in tree.get_children():
            tree.delete(r)
        results = cari_service.search_by_name(cursor, search) if search else cari_service.list_all(cursor)
        for idx, row in enumerate(results):
            cari_id, name, phone, address, balance, ctype = row
            balance_str = f"{float(balance):.2f} ₺"
            type_str = t('alacakli') if ctype == 'alacakli' else t('borclu')
            
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            color_tag = 'positive' if float(balance) >= 0 else 'negative'
            
            item = tree.insert("", "end", values=(cari_id, name, phone, balance_str, type_str), tags=(tag, color_tag))
        
        update_summary()

    def add_cari():
        try:
            cari_service.add_cari(
                conn, cursor,
                entry_name.get(),
                entry_phone.get(),
                entry_address.get(),
                entry_balance.get(),
                cari_type_var.get()
            )
            messagebox.showinfo(t('success'), t('cari_added'))
            clear_form()
            load()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))

    def edit_cari():
        sel = tree.selection()
        if not sel:
            return messagebox.showwarning(t('warning'), t('select_item'))
        
        cari_id = tree.item(sel[0])["values"][0]
        try:
            cari_service.update_cari(
                conn, cursor, cari_id,
                entry_name.get(),
                entry_phone.get(),
                entry_address.get(),
                cari_type_var.get()
            )
            messagebox.showinfo(t('success'), t('cari_updated'))
            clear_form()
            load()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))

    def delete_cari():
        sel = tree.selection()
        if not sel:
            return messagebox.showwarning(t('warning'), t('select_item'))
        
        if not messagebox.askyesno(t('confirm'), t('delete_confirm')):
            return
        
        cari_id = tree.item(sel[0])["values"][0]
        try:
            cari_service.delete_cari(conn, cursor, cari_id)
            messagebox.showinfo(t('success'), t('cari_deleted'))
            clear_form()
            load()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))

    def clear_form():
        entry_name.delete(0, tk.END)
        entry_phone.delete(0, tk.END)
        entry_address.delete(0, tk.END)
        entry_balance.delete(0, tk.END)
        entry_balance.insert(0, "0")
        cari_type_var.set('alacakli')

    def on_select(e):
        sel = tree.selection()
        if not sel:
            return
        cari_id = tree.item(sel[0])["values"][0]
        cari = cari_service.get_by_id(cursor, cari_id)
        if cari:
            entry_name.delete(0, tk.END)
            entry_name.insert(0, cari[1])
            entry_phone.delete(0, tk.END)
            entry_phone.insert(0, cari[2] or "")
            entry_address.delete(0, tk.END)
            entry_address.insert(0, cari[3] or "")
            entry_balance.delete(0, tk.END)
            entry_balance.insert(0, str(cari[4]))
            cari_type_var.set(cari[5])

    tree.bind("<<TreeviewSelect>>", on_select)
    search_var.trace_add("write", lambda *args: load(search_var.get()))

    # Butonlar
    btns = ttk.Frame(right)
    btns.pack(fill="x", padx=8, pady=12)
    
    def create_cari_button(parent, text, command, bg_color):
        btn = tk.Button(parent, text=text, command=command,
                       bg=bg_color, fg="white", font=("Segoe UI", 9, "bold"),
                       activebackground=bg_color, activeforeground="white",
                       relief="flat", padx=14, pady=8, cursor="hand2", borderwidth=0)
        
        def on_enter(e):
            factor = 1.15 if bg_color in ["#10b981", "#00b0ff"] else 0.85
            new_color = adjust_cari_brightness(bg_color, factor)
            btn.config(bg=new_color)
        
        def on_leave(e):
            btn.config(bg=bg_color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.pack(side="left", padx=4, pady=8)
    
    def adjust_cari_brightness(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(min(255, max(0, r * factor)))
        g = int(min(255, max(0, g * factor)))
        b = int(min(255, max(0, b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    create_cari_button(btns, "💾 " + t('save'), add_cari, "#10b981")
    create_cari_button(btns, "🔁 " + t('update_btn'), edit_cari, "#00b0ff")
    create_cari_button(btns, "🗑 " + t('delete'), delete_cari, "#ef4444")
    create_cari_button(btns, "🧹 " + t('clear_form'), clear_form, "#6b7280")
    
    refresh_btn = tk.Button(btns, text="🔄 " + t('refresh'), command=lambda: load(search_var.get()),
                           bg="#8b5cf6", fg="white", font=("Segoe UI", 9, "bold"),
                           activebackground="#7c3aed", activeforeground="white",
                           relief="flat", padx=14, pady=8, cursor="hand2", borderwidth=0)
    refresh_btn.pack(side="right", padx=4, pady=8)
    
    def refresh_hover_in(e): refresh_btn.config(bg="#7c3aed")
    def refresh_hover_out(e): refresh_btn.config(bg="#8b5cf6")
    refresh_btn.bind("<Enter>", refresh_hover_in)
    refresh_btn.bind("<Leave>", refresh_hover_out)
    
    load()

def mount_sales(parent):
    for w in parent.winfo_children():
        w.destroy()

    # Başlık
    ttk.Label(parent, text="🛒 " + t('sales_screen'), style="Header.TLabel", font=("Segoe UI", 14, "bold")).pack(pady=(6,2))

    # Üst Bilgi Bloğu
    top = ttk.Frame(parent, style="Card.TFrame"); top.pack(fill="x", padx=12, pady=6)
    # Combobox yüksekliği için büyük stil
    try:
        style = ttk.Style(top)
        style.configure('Large.TCombobox', padding=(8, 8))
        style.configure('LargeValue.TLabel', padding=(4, 6))
    except Exception:
        pass
    top.grid_columnconfigure(1, weight=1)
    top.grid_columnconfigure(7, weight=0)

    from services import cari_service

    # Cari seçimi
    ttk.Label(top, text=t('customer_name'), font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=6, pady=6, sticky="w")
    def get_cari_names():
        cariler = cari_service.list_all(cursor)
        return [c[1] for c in cariler]
    # Müşteri seçimi ve ekleme butonunu aynı kutuda toplayalım (ikon yakına gelsin)
    cari_box = tk.Frame(top, bg=BG_COLOR)
    cari_box.grid(row=0, column=1, padx=(6,2), pady=6, sticky="ew")
    cari_box.grid_columnconfigure(0, weight=1)
    customer_cb = ttk.Combobox(cari_box, values=get_cari_names(), width=36, font=("Segoe UI", 11), style='Large.TCombobox', state="readonly")
    customer_cb.grid(row=0, column=0, padx=(0,4), pady=0, sticky="ew")

    def add_new_cari_from_sales():
        from tkinter import simpledialog
        name = simpledialog.askstring(t('add'), t('cari_name'))
        if not name or not name.strip():
            return
        phone = simpledialog.askstring(t('phone'), t('phone'), initialvalue="")
        try:
            cari_service.add_cari(conn, cursor, name.strip(), phone or "", "", 0, 'alacakli')
            messagebox.showinfo(t('success'), t('cari_added_name').format(name=name))
            customer_cb.config(values=get_cari_names())
            customer_cb.set(name.strip())
        except Exception as e:
            messagebox.showerror(t('error'), str(e))
    add_cari_btn = tk.Button(cari_box, text="➕", command=add_new_cari_from_sales,
                             bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"),
                             activebackground="#059669", activeforeground="white",
                             relief="flat", padx=8, pady=4, cursor="hand2", borderwidth=0)
    add_cari_btn.grid(row=0, column=1, padx=(2, 0), pady=0, sticky="e")

    def add_cari_hover_in(e): add_cari_btn.config(bg="#059669")
    def add_cari_hover_out(e): add_cari_btn.config(bg="#10b981")
    add_cari_btn.bind("<Enter>", add_cari_hover_in)
    add_cari_btn.bind("<Leave>", add_cari_hover_out)

    # KDV ve KDV Dahil
    ttk.Label(top, text=t('vat'), font=("Segoe UI", 10, "bold")).grid(row=0, column=3, padx=6, pady=6, sticky="e")
    vat_cb = ttk.Combobox(top, values=["%8","%18", t('special_vat')], state="readonly", width=8, font=("Segoe UI", 10))
    vat_cb.set("%18")
    vat_cb.grid(row=0, column=4, padx=(6,0), pady=6)
    vat_included_var = tk.BooleanVar(value=False)
    vat_included_cb = tk.Checkbutton(top, text=t('vat_included'), variable=vat_included_var,
                                     font=("Segoe UI", 9), bg=BG_COLOR, fg=TEXT_GRAY,
                                     activebackground=BG_COLOR, activeforeground="#00b0ff",
                                     selectcolor="#1a1a20", cursor="hand2")
    vat_included_cb.grid(row=0, column=5, padx=(6,6), pady=6, sticky="w")

    # Ödeme yöntemi
    ttk.Label(top, text=t('payment_method'), font=("Segoe UI", 10, "bold")).grid(row=1, column=0, padx=6, pady=6, sticky="w")
    payment_var = tk.StringVar(value='cash')
    pm_box = tk.Frame(top, bg=BG_COLOR); pm_box.grid(row=1, column=1, columnspan=2, padx=6, pady=6, sticky="w")
    def set_hover(btn, base, hover):
        try:
            btn.unbind("<Enter>"); btn.unbind("<Leave>")
        except Exception:
            pass
        def on_enter(_): btn.config(bg=hover)
        def on_leave(_): btn.config(bg=base)
        btn.bind("<Enter>", on_enter); btn.bind("<Leave>", on_leave)

    def create_payment_button(parent, text, value):
        def toggle():
            payment_var.set(value)
            update_payment_buttons()
        b = tk.Button(parent, text=text, command=toggle, font=("Segoe UI", 10, "bold"), relief="flat",
                      padx=18, pady=10, cursor="hand2", borderwidth=0, width=14)
        b.pack(side="left", padx=4)
        return b

    cash_btn = create_payment_button(pm_box, "💵 " + t('cash'), 'cash')
    card_btn = create_payment_button(pm_box, "💳 " + t('credit_card'), 'card')

    def update_payment_buttons():
        if payment_var.get() == 'cash':
            cash_btn.config(bg=ACCENT, fg="white", activebackground="#0090dd")
            card_btn.config(bg="#2a2a35", fg=TEXT_GRAY, activebackground="#3a3a45")
            set_hover(cash_btn, ACCENT, "#0090dd")
            set_hover(card_btn, "#2a2a35", "#3a3a45")
        else:
            card_btn.config(bg=ACCENT, fg="white", activebackground="#0090dd")
            cash_btn.config(bg="#2a2a35", fg=TEXT_GRAY, activebackground="#3a3a45")
            set_hover(card_btn, ACCENT, "#0090dd")
            set_hover(cash_btn, "#2a2a35", "#3a3a45")

    update_payment_buttons()

    # İndirim
    ttk.Label(top, text=t('discount'), font=("Segoe UI", 10, "bold")).grid(row=1, column=3, padx=6, pady=6, sticky="e")
    discount_entry = ttk.Entry(top, width=8, font=("Segoe UI", 10)); discount_entry.insert(0, "0")
    discount_entry.grid(row=1, column=4, padx=6, pady=6, sticky="w")

    # Barkod alanı (ürün ekleme satırında, sağda aksiyonların solunda)
    # Ürün seçimi ve aksiyonlar

    # Ürün seçimi ve aksiyonlar
    pick = ttk.Frame(parent, style="Card.TFrame"); pick.pack(fill="x", padx=12, pady=6)
    ttk.Label(pick, text=t('product')+":", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=4, pady=4, sticky="w")
    # Ürün seçimini genişlet ve satırda esnet
    pick.grid_columnconfigure(1, weight=1)
    all_products = refresh_product_values_for_combo()
    cb_product = ttk.Combobox(pick, values=all_products, state="normal", width=40, font=("Segoe UI", 11), style='Large.TCombobox')
    cb_product.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
    ttk.Label(pick, text=t('quantity')+":", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=4, pady=4, sticky="e")
    e_qty = ttk.Entry(pick, width=6, font=("Segoe UI", 10, "bold")); e_qty.insert(0, "1")
    e_qty.grid(row=0, column=3, padx=4, pady=4, sticky="w")

    # Fiyat etiketi dinamik (KDV Dahil/Hariç)
    lbl_price_header = ttk.Label(pick, text=t('price')+":", font=("Segoe UI", 10))
    lbl_price_header.grid(row=1, column=0, padx=4, pady=(6,6), sticky="w")
    lbl_price = ttk.Label(pick, text="-", style="LargeValue.TLabel", font=("Segoe UI", 11, "bold")); lbl_price.grid(row=1, column=1, sticky="w", padx=4, pady=(6,6), ipady=3)
    ttk.Label(pick, text=t('stock')+":", font=("Segoe UI", 10)).grid(row=1, column=2, padx=4, pady=(6,6), sticky="e")
    lbl_stock = ttk.Label(pick, text="-", style="LargeValue.TLabel", font=("Segoe UI", 11, "bold")); lbl_stock.grid(row=1, column=3, sticky="w", padx=4, pady=(6,6), ipady=3)
    
    def update_price_label_text():
        """KDV Dahil açıksa 'Fiyat (KDV Dahil)', değilse 'Fiyat (KDV Hariç)' göster"""
        if vat_included_var.get():
            lbl_price_header.config(text=t('price')+" (KDV Dahil):")
        else:
            lbl_price_header.config(text=t('price')+" (KDV Hariç):")

    # Sağ panel: üstte barkod, altında aksiyon butonları
    pick.grid_columnconfigure(4, weight=1)
    right_panel = tk.Frame(pick, bg=BG_COLOR); right_panel.grid(row=0, column=5, rowspan=2, padx=(6,0), pady=2, sticky="ne")
    barcode_frame = tk.Frame(right_panel, bg=CARD_COLOR)
    barcode_frame.pack(fill="x", padx=0, pady=(0,6))
    tk.Label(barcode_frame, text="📷", font=("Segoe UI", 12), bg=CARD_COLOR, fg="white").pack(side="left", padx=(6,6))
    barcode_entry = tk.Entry(barcode_frame, font=("Segoe UI", 11), bg="#ffffff", fg="#000000",
                             insertbackground="#000000", relief="flat")
    barcode_entry.pack(side="left", fill="x", expand=True, padx=(0,8), pady=6, ipady=4)
    barcode_entry.insert(0, "🔍 " + t('scan_barcode'))

    # Aksiyon butonları sağda, her koşulda görünür
    actions_frame = tk.Frame(right_panel, bg=BG_COLOR)
    actions_frame.pack(fill="x")
    def create_action_button(parent, text, command, bg_color):
        btn = tk.Button(parent, text=text, command=command, bg=bg_color, fg="white", font=("Segoe UI", 10, "bold"),
                        activebackground=bg_color, activeforeground="white", relief="flat", padx=18, pady=10,
                        cursor="hand2", borderwidth=0, width=16)
        # Tutarlı hover renkleri
        hover = "#0ea5e9" if bg_color == "#00b0ff" else ("#059669" if bg_color == "#10b981" else "#ef233c")
        def on_enter(_): btn.config(bg=hover)
        def on_leave(_): btn.config(bg=bg_color)
        btn.bind("<Enter>", on_enter); btn.bind("<Leave>", on_leave)
        btn.pack(side="right", padx=(0,6))
        return btn

    from services import product_service as product_svc
    from services import sales_service as sales_svc

    def update_info(*_):
        pname = cb_product.get(); r = product_svc.get_price_stock_by_name(cursor, pname)
        if r:
            price, stock = r; lbl_price.config(text=f"{float(price):.2f} ₺"); lbl_stock.config(text=str(int(stock)))
        else:
            lbl_price.config(text="-"); lbl_stock.config(text="-")
    cb_product.bind("<<ComboboxSelected>>", update_info)

    # Ürün adı yazarak filtreleme
    # Ürün adı yazarak filtreleme (debounce ile akıcı)
    _filter_job = {"id": None}
    def _apply_filter():
        try:
            text = (cb_product.get() or "").strip().lower()
            matches = [p for p in all_products if text in p.lower()] if text else list(all_products)
            cb_product.configure(values=matches)
        finally:
            _filter_job["id"] = None

    def on_product_type(event=None):
        # Önceki işi iptal et, 120ms erteli uygula
        if _filter_job["id"] is not None:
            try:
                parent.after_cancel(_filter_job["id"])  # type: ignore
            except Exception:
                pass
        _filter_job["id"] = parent.after(120, _apply_filter)

    cb_product.bind("<KeyRelease>", on_product_type)

    def on_product_return(event=None):
        text = (cb_product.get() or "").strip().lower()
        matches = [p for p in all_products if text in p.lower()] if text else list(all_products)
        if matches:
            cb_product.set(matches[0])
            update_info()
    cb_product.bind("<Return>", on_product_return)

    def get_current_vat_rate():
        k = vat_cb.get()
        if k == "%8": return 8.0
        if k == "%18": return 18.0
        if not hasattr(get_current_vat_rate, "_custom"):
            try:
                from tkinter import simpledialog
                val = parse_float_safe(simpledialog.askstring(t('special_vat'), t('enter_vat_percent')), 0.0) or 0.0
            except Exception:
                val = 0.0
            setattr(get_current_vat_rate, "_custom", float(val))
        return float(getattr(get_current_vat_rate, "_custom", 0.0))

    # Sepet tablosu
    mid = ttk.Frame(parent, style="Card.TFrame"); mid.pack(fill="both", expand=True, padx=12, pady=6)
    cols = (t('seq'), t('product'), t('quantity'), t('price'), t('vat_short'), t('total'))
    tree = ttk.Treeview(mid, columns=cols, show="headings", height=10)
    for c in cols: tree.heading(c, text=c)
    tree.column(t('seq'), width=60, anchor="center")
    tree.column(t('product'), width=280)
    tree.column(t('quantity'), width=80, anchor="center")
    tree.column(t('price'), width=110, anchor="e")
    tree.column(t('vat_short'), width=100, anchor="e")
    tree.column(t('total'), width=120, anchor="e")
    tree.tag_configure('oddrow', background='#1f1f25'); tree.tag_configure('evenrow', background='#252530')
    orig_insert = tree.insert
    def insert_with_tags(*args, **kwargs):
        item = orig_insert(*args, **kwargs); idx = tree.index(item)
        tree.item(item, tags=('evenrow',) if idx % 2 == 0 else ('oddrow',)); return item
    tree.insert = insert_with_tags
    tree.pack(fill="both", expand=True)

    # Alt bar: ara toplam
    total_frame = tk.Frame(parent, bg=CARD_COLOR); total_frame.pack(side="bottom", pady=6, fill="x", padx=12)
    total_label = tk.Label(total_frame, text=f"{t('subtotal')} 0.00 ₺", font=("Segoe UI", 14, "bold"), bg=CARD_COLOR, fg=ACCENT); total_label.pack()

    def rebuild_cart_rows():
        rows = list(tree.get_children()); rate = get_current_vat_rate(); inc = bool(vat_included_var.get())
        items = []
        for r in rows:
            vals = list(tree.item(r)["values"]) if tree.item(r) else []
            if not vals: continue
            if len(vals) >= 3 and (str(vals[0]).isdigit() or isinstance(vals[0], int)):
                pname = vals[1]; qty = int(vals[2])
            else:
                pname = vals[0]; qty = int(vals[1]) if len(vals) > 1 else 1
            items.append((pname, qty))
        for r in rows: tree.delete(r)
        seq = 1
        for pname, qty in items:
            pr = product_svc.get_price_stock_by_name(cursor, pname)
            base_price = float(pr[0]) if pr else 0.0
            if inc:
                # Fiyat KDV dahil: neti düş, toplam satış tutarı base_price olsun
                unit_gross = base_price
                unit_net = unit_gross / (1.0 + rate/100.0) if rate else unit_gross
            else:
                # Fiyat KDV hariç: brütü ekle
                unit_net = base_price
                unit_gross = unit_net * (1.0 + rate/100.0)
            unit_disp = unit_gross if inc else unit_net
            line_vat = qty * (unit_gross - unit_net)
            line_gross = qty * unit_gross
            tree.insert("", "end", values=(seq, pname, qty, f"{unit_disp:.2f}", f"{line_vat:.2f}", f"{line_gross:.2f}")); seq += 1
        update_total_label()

    def update_total_label():
        total_sum = 0.0
        for r in tree.get_children():
            v = tree.item(r)["values"]
            if len(v) >= 6:
                total_sum += float(v[5])
            elif len(v) >= 4:
                total_sum += float(v[-1])
        total_label.config(text=f"{t('subtotal')} {total_sum:.2f} ₺")

    try:
        vat_cb.bind('<<ComboboxSelected>>', lambda e: rebuild_cart_rows())
        vat_included_cb.config(command=lambda: [rebuild_cart_rows(), update_price_label_text()])
    except Exception:
        pass

    def add_to_cart():
        pname = cb_product.get().strip(); qty = parse_int_safe(e_qty.get(), None)
        if not pname or qty is None or qty <= 0:
            return messagebox.showwarning(t('warning'), t('valid_product_qty'))
        r = product_svc.get_price_stock_by_name(cursor, pname)
        if not r:
            return messagebox.showerror(t('error'), t('product_not_found'))
        unit_net, stock = float(r[0]), int(r[1])
        if qty > stock:
            return messagebox.showerror(t('error'), t('insufficient_stock').format(stock=stock))
        seq = len(tree.get_children()) + 1
        tree.insert("", "end", values=(seq, pname, qty, f"{unit_net:.2f}", f"0.00", f"0.00"))
        rebuild_cart_rows()

    def remove_selected():
        for s in tree.selection(): tree.delete(s)
        rebuild_cart_rows()

    # Aksiyon butonları, confirm_sale tanımından sonra oluşturulacak

    # Barkod olayları
    def barcode_focus_in(event):
        cur = barcode_entry.get()
        if "🔍" in cur or cur == t('scan_barcode'):
            barcode_entry.delete(0, tk.END); barcode_entry.config(foreground="#000000")
    def barcode_focus_out(event):
        if not barcode_entry.get().strip():
            barcode_entry.insert(0, "🔍 " + t('scan_barcode')); barcode_entry.config(foreground="#999999")
    def scan_barcode(event):
        barcode = barcode_entry.get().strip().replace("🔍", "").strip()
        if not barcode or barcode == t('scan_barcode'): return
        result = product_svc.get_by_barcode(cursor, barcode)
        if not result:
            messagebox.showwarning(t('warning'), t('barcode_not_found').format(barcode=barcode))
            barcode_entry.delete(0, tk.END); barcode_entry.insert(0, "🔍 " + t('scan_barcode')); barcode_entry.config(foreground="#999999"); return
        pid, pname, price, stock = result
        qty = parse_int_safe(e_qty.get(), 1) or 1
        if qty > int(stock):
            messagebox.showerror(t('error'), t('insufficient_stock').format(stock=stock))
            barcode_entry.delete(0, tk.END); barcode_entry.insert(0, "🔍 " + t('scan_barcode')); barcode_entry.config(foreground="#999999"); return
        seq = len(tree.get_children()) + 1
        tree.insert("", "end", values=(seq, pname, qty, f"{float(price):.2f}", f"0.00", f"0.00"))
        rebuild_cart_rows()
        barcode_entry.delete(0, tk.END); barcode_entry.insert(0, "🔍 " + t('scan_barcode')); barcode_entry.config(foreground="#999999"); barcode_entry.focus_set()
    barcode_entry.bind("<FocusIn>", barcode_focus_in)
    barcode_entry.bind("<FocusOut>", barcode_focus_out)
    barcode_entry.bind("<Return>", scan_barcode)

    # Satışı tamamla
    def confirm_sale():
        rows = tree.get_children()
        if not rows: return messagebox.showwarning(t('warning'), t('cart_empty'))
        customer_name = (customer_cb.get().strip() or t('customer'))
        kdv_text = vat_cb.get()
        discount_val = parse_float_safe(discount_entry.get(), 0.0) or 0.0
        if kdv_text == "%8": vat_rate = 8.0
        elif kdv_text == "%18": vat_rate = 18.0
        else:
            vat_rate = parse_float_safe(simpledialog.askstring(t('special_vat'), t('enter_vat_percent')), 0.0) or 0.0
        payment_method = payment_var.get() or 'cash'
        vat_included_flag = bool(vat_included_var.get())

        fis_id = f"FIS-{datetime.now().strftime('%Y%m%d')}-{os.urandom(3).hex().upper()}"
        sales_list = []
        subtotal_gross = 0.0
        for r in rows:
            vals = tree.item(r)["values"]
            pname = vals[1]; qty = int(vals[2]); line_gross = float(vals[5]) if len(vals) >= 6 else float(vals[-1])
            # DB'ye birim NET fiyatı yazalım
            pr = product_svc.get_price_stock_by_name(cursor, pname)
            unit_net = float(pr[0]) if pr else 0.0
            product_svc.decrement_stock(conn, cursor, pname, qty)
            sales_svc.insert_sale_line(conn, cursor, fis_id, pname, qty, unit_net, line_gross, payment_method=payment_method)
            sales_list.append((pname, qty, unit_net, line_gross))
            subtotal_gross += line_gross
        conn.commit()

        # Yazdırma seçimi
        print_choice = messagebox.askyesnocancel(
            t('print_receipt'),
            f"{t('receipt_created')}\n\n{t('print_options')}\n\n" +
            f"Evet = {t('thermal_printer')}\n" +
            f"Hayır = PDF\n" +
            f"İptal = {t('no_print')}"
        )
        if print_choice is True:
            print_thermal_receipt(sales_list, fis_id=fis_id, customer_name=customer_name,
                                  kdv_rate=vat_rate, discount_rate=discount_val, vat_included=vat_included_flag,
                                  language_code=CURRENT_LANGUAGE)
            print_receipt(sales_list, fis_id=fis_id, customer_name=customer_name,
                          kdv_rate=vat_rate, discount_rate=discount_val, vat_included=vat_included_flag,
                          open_after=False, show_message=False, language_code=CURRENT_LANGUAGE)
        elif print_choice is False:
            print_receipt(sales_list, fis_id=fis_id, customer_name=customer_name,
                          kdv_rate=vat_rate, discount_rate=discount_val, vat_included=vat_included_flag,
                          language_code=CURRENT_LANGUAGE)

        # Ekran bildirimi (brüt tutar üzerinden indirim uygula)
        discount_amount = subtotal_gross * (discount_val/100.0)
        grand_total = subtotal_gross - discount_amount
        messagebox.showinfo(t('success'), f"{t('customer')}: {customer_name}\n{t('receipt_no')} {fis_id}\n{t('total')}: {grand_total:.2f} ₺")

        # Temizle
        for r in tree.get_children(): tree.delete(r)
        update_total_label(); cb_product.set(""); lbl_price.config(text="-"); lbl_stock.config(text="-")
        customer_cb.set(""); discount_entry.delete(0, tk.END); discount_entry.insert(0, "0")

    # Aksiyon butonlarını şimdi oluştur (sağdan sola sırala)
    complete_btn = tk.Button(actions_frame, text="✅ " + t('complete_sale').upper(), command=confirm_sale, bg="#10b981", fg="white",
                             font=("Segoe UI", 10, "bold"), relief="flat", padx=18, pady=10,
                             cursor="hand2", borderwidth=0, activebackground="#059669", activeforeground="white", width=18)
    complete_btn.pack(side="right", padx=(6,4))
    remove_btn = create_action_button(actions_frame, "❌ " + t('remove_selected'), remove_selected, "#ef4444")
    add_btn = create_action_button(actions_frame, "➕ " + t('add_to_cart'), add_to_cart, "#10b981")

    # Satışı Tamamla butonu artık actions_frame içinde

def mount_cancel_sales(parent):
    for w in parent.winfo_children(): w.destroy()

    # Modern header
    header = ttk.Frame(parent, style="Card.TFrame")
    header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="🛑 " + t('cancel_sale'), style="Header.TLabel",
              font=("Segoe UI", 16, "bold")).pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame")
    body.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Modern table
    cols = (t('receipt_no'), t('date'), t('total'), t('payment_method'))
    tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
    for c in cols: tree.heading(c, text=c)
    tree.column(t('receipt_no'), width=180, anchor="center")
    tree.column(t('date'), width=180, anchor="center")
    tree.column(t('total'), width=140, anchor="e")
    tree.column(t('payment_method'), width=150, anchor="center")
    
    # Zebrastripe
    tree.tag_configure('oddrow', background='#1f1f25')
    tree.tag_configure('evenrow', background='#252530')
    
    original_insert = tree.insert
    def insert_with_tags(*args, **kwargs):
        item = original_insert(*args, **kwargs)
        idx = tree.index(item)
        tree.item(item, tags=('evenrow',) if idx % 2 == 0 else ('oddrow',))
        return item
    tree.insert = insert_with_tags
    
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    from services import sales_service as sales_svc

    def load():
        for r in tree.get_children(): tree.delete(r)
        for fis_id, ts, sum_total, pay in sales_svc.list_recent_receipts(cursor, 200):
            ts_disp = (ts or "").replace("T"," ")
            # Ödeme yöntemi ikonlu
            pay_display = ("💵 " + t('cash')) if pay == 'cash' else ("💳 " + t('credit_card'))
            tree.insert("", "end", values=(fis_id, ts_disp, f"{float(sum_total):.2f} ₺", pay_display))

    def cancel_selected():
        sel = tree.selection()
        if not sel: return messagebox.showwarning(t('warning'), t('select_item'))
        fis_id = tree.item(sel[0])["values"][0]
        if not messagebox.askyesno(t('confirm'), t('confirm_cancel_receipt')):
            return
        try:
            sales_svc.cancel_receipt(conn, cursor, fis_id)
            messagebox.showinfo(t('success'), t('cancel_success'))
            load()
        except Exception as e:
            messagebox.showerror(t('error'), f"{t('cancel_error')}\n{e}")

    # Modern butonlar
    btns = ttk.Frame(parent, style="Card.TFrame")
    btns.pack(fill="x", padx=12, pady=(0,12))
    
    def create_cancel_button(parent, text, command, bg_color):
        btn = tk.Button(parent, text=text, command=command,
                       bg=bg_color, fg="white", font=("Segoe UI", 10, "bold"),
                       activebackground=bg_color, activeforeground="white",
                       relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0)
        
        def on_enter(e):
            factor = 1.15 if bg_color in ["#10b981", "#00b0ff"] else 0.85
            new_color = adjust_cancel_brightness(bg_color, factor)
            btn.config(bg=new_color)
        
        def on_leave(e):
            btn.config(bg=bg_color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.pack(side="left", padx=4, pady=8)
    
    def adjust_cancel_brightness(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(min(255, max(0, r * factor)))
        g = int(min(255, max(0, g * factor)))
        b = int(min(255, max(0, b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    create_cancel_button(btns, "🛑 " + t('cancel_receipt'), cancel_selected, "#ef4444")
    
    refresh_btn = tk.Button(btns, text="🔄 " + t('refresh'), command=load,
                           bg="#8b5cf6", fg="white", font=("Segoe UI", 10, "bold"),
                           activebackground="#7c3aed", activeforeground="white",
                           relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0)
    refresh_btn.pack(side="right", padx=4, pady=8)
    
    def refresh_hover_in(e): refresh_btn.config(bg="#7c3aed")
    def refresh_hover_out(e): refresh_btn.config(bg="#8b5cf6")
    refresh_btn.bind("<Enter>", refresh_hover_in)
    refresh_btn.bind("<Leave>", refresh_hover_out)
    
    load()

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
    if not rows: return messagebox.showinfo(t('info'), t('no_sales_today'))
    with open(filename, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow([t('csv_receipt_no'), t('csv_product'), t('csv_qty'), t('csv_price'), t('csv_total'), t('csv_date')])
        for r in rows: w.writerow([r[0],r[1],r[2],f"{float(r[3]):.2f}",f"{float(r[4]):.2f}",r[5]])
    messagebox.showinfo(t('success'), f"{t('daily_report_saved')}\n{filename}")
    try:
        if os.name=="nt": os.startfile(filename)  # type: ignore
        else: subprocess.call(("open", filename))
    except: pass

# ==========================
# Ana Pencere (tek pencere navigasyon)
# ==========================
def open_main_window(role):
    main = tk.Toplevel()
    main.title(f"{t('app_title')} - {role.upper()}")
    set_theme(main)
    
    # Tam ekran yap
    main.state('zoomed')  # Windows için maximize
    
    top_bar = ttk.Frame(main, style="Card.TFrame"); top_bar.pack(fill="x", padx=10, pady=(8,4))
    ttk.Label(top_bar, text=f"{t('app_title')} {APP_VERSION}", style="Header.TLabel").pack(side="left", padx=10)
    ttk.Label(top_bar, text=f"{t('session')}: {role.title()}", style="Sub.TLabel").pack(side="left", padx=8)
    
    # Dil değiştirici - İyileştirilmiş Tasarım
    lang_container = tk.Frame(top_bar, bg=CARD_COLOR)
    lang_container.pack(side="right", padx=(0, 6))
    
    ttk.Label(lang_container, text="🌐", style="Sub.TLabel", font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
    
    def create_lang_button_main(code, emoji):
        def select_lang():
            if CURRENT_LANGUAGE != code:
                set_language(code)
                main.destroy()
                open_main_window(role)
        
        is_active = (CURRENT_LANGUAGE == code)
        bg_color = ACCENT if is_active else "#2a2a35"
        
        btn = tk.Button(lang_container, text=emoji, 
                       bg=bg_color, fg="white",
                       font=("Segoe UI", 10, "bold" if is_active else "normal"),
                       activebackground="#0090dd" if is_active else "#3a3a45",
                       activeforeground="white",
                       relief="flat", padx=8, pady=4,
                       borderwidth=0, cursor="hand2",
                       command=select_lang)
        btn.pack(side="left", padx=1)
        
        # Hover efekti
        def on_enter(e):
            if not is_active:
                btn.config(bg="#3a3a45")
        def on_leave(e):
            if not is_active:
                btn.config(bg="#2a2a35")
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn
    
    create_lang_button_main("tr", "🇹🇷")
    create_lang_button_main("en", "🇬🇧")
    
    ttk.Button(top_bar, text=f"🚪 {t('logout')}", command=lambda: logout_action(main)).pack(side="right", padx=6)

    body = ttk.Frame(main); body.pack(fill="both", expand=True, padx=10, pady=10)

    # Sol Menü (Scroll'lu)
    menu_container = ttk.Frame(body, style="Card.TFrame", width=280)
    menu_container.pack(side="left", fill="y", padx=(10,6), pady=10)
    menu_container.pack_propagate(False)

    # Sabit başlık
    ttk.Label(menu_container, text="📂 " + t('action_menu'), style="Header.TLabel").pack(pady=(12,6), fill="x")
    # ttk.Separator(menu_container, orient="horizontal").pack(fill="x", padx=10, pady=(0,6))  # kullanıcı isteğiyle kaldırıldı

    # Scroll alanı (başlığın altında kalsın)
    scroll_area = ttk.Frame(menu_container, style="Card.TFrame")
    scroll_area.pack(fill="both", expand=True)

    menu_canvas = tk.Canvas(scroll_area, bg=CARD_COLOR, highlightthickness=0)
    menu_scrollbar = ttk.Scrollbar(scroll_area, orient="vertical", command=menu_canvas.yview, style="Menu.Vertical.TScrollbar")
    menu_canvas.configure(yscrollcommand=menu_scrollbar.set)
    menu_scrollbar.pack(side="right", fill="y")
    menu_canvas.pack(side="left", fill="both", expand=True)

    # İçerik çerçevesi (scrollable frame)
    menu = ttk.Frame(menu_canvas, style="Card.TFrame")
    menu_window = menu_canvas.create_window((0, 0), window=menu, anchor="nw")

    # Scroll bölgesini ve genişliği dinamik ayarla
    def _on_menu_configure(event=None):
        try:
            menu_canvas.configure(scrollregion=menu_canvas.bbox("all"))
            # İç çerçeveyi kanvas genişliğine eşitle
            menu_canvas.itemconfigure(menu_window, width=menu_canvas.winfo_width())
        except Exception:
            pass
    menu.bind("<Configure>", _on_menu_configure)
    menu_canvas.bind("<Configure>", _on_menu_configure)

    # Mouse tekeri ile kaydırma (Windows)
    def _on_mousewheel(event):
        try:
            delta = -1 * int(event.delta / 120)
            menu_canvas.yview_scroll(delta, "units")
        except Exception:
            pass
    menu_canvas.bind("<MouseWheel>", _on_mousewheel)
    menu.bind("<MouseWheel>", _on_mousewheel)

    # Hover ile focus ver, böylece mouse menü üzerindeyken tekerlek çalışır
    def _focus_canvas(_):
        try:
            menu_canvas.focus_set()
        except Exception:
            pass
    menu_container.bind("<Enter>", _focus_canvas)
    scroll_area.bind("<Enter>", _focus_canvas)
    menu_canvas.bind("<Enter>", _focus_canvas)
    menu.bind("<Enter>", _focus_canvas)

    # Bölüm yönetimi (accordion mantığı)
    all_sections = []  # {header, sub, visible}
    def register_section(header, sub, visible):
        all_sections.append({"header": header, "sub": sub, "visible": visible})

    def close_others(current_sub):
        for s in all_sections:
            if s["sub"] is not current_sub and s["visible"]["v"]:
                try:
                    s["sub"].pack_forget()
                except Exception:
                    pass
                s["visible"]["v"] = False

    def open_section(header, sub, visible):
        close_others(sub)
        sub.pack(fill="x", padx=0, after=header)
        visible["v"] = True

    def close_all_sections():
        close_others(None)

    # Arama kutusu kaldırıldı (istenen sade görünüm ve opak scroll)

    # Sağ Panel (dinamik)
    global right_panel
    right_panel = ttk.Frame(body, style="Card.TFrame"); right_panel.pack(side="right", fill="both", expand=True, padx=(0,10), pady=10)
    ttk.Label(right_panel, text=t('menu_hint'), font=("Segoe UI", 12, "italic"),
              background=CARD_COLOR, foreground=TEXT_GRAY).pack(expand=True)

    def mbtn(parent, text, cmd):
        b = tk.Button(parent, text=text, bg=CARD_COLOR, fg="white",
                      font=("Segoe UI",10,"bold"), activebackground="#003c66",
                      activeforeground="white", relief="flat", padx=10, pady=10,
                      anchor="w", borderwidth=0, command=cmd)
        b.pack(fill="x", pady=4, padx=14)
        # Menü üzerindeyken tekerlekle kaydırma için hover ve wheel bağları
        try:
            b.bind("<Enter>", _focus_canvas)
            b.bind("<MouseWheel>", _on_mousewheel)
        except Exception:
            pass
        return b

    # Alt menü butonu (daha küçük ve içeriden)
    def msub(parent, text, cmd):
        b = tk.Button(parent, text="   • " + text, bg=CARD_COLOR, fg="white",
                      font=("Segoe UI",9), activebackground="#003c66",
                      activeforeground="white", relief="flat", padx=10, pady=8,
                      anchor="w", borderwidth=0, command=cmd)
        b.pack(fill="x", pady=2, padx=30)
        try:
            b.bind("<Enter>", _focus_canvas)
            b.bind("<MouseWheel>", _on_mousewheel)
        except Exception:
            pass
        return b

    if role == "admin":
        mbtn(menu, "🛒 " + t('sales'), lambda: mount_sales(right_panel))
        mbtn(menu, "🛑 " + t('cancel_sale'), lambda: mount_cancel_sales(right_panel))

        # Ürün Yönetimi
        products_header = mbtn(menu, "📦 " + t('product_mgmt'), lambda: None)
        products_sub = ttk.Frame(menu, style="Card.TFrame")
        products_visible = {"v": False}
        def toggle_products():
            if products_visible["v"]:
                products_sub.pack_forget(); products_visible["v"] = False
            else:
                open_section(products_header, products_sub, products_visible)
        products_header.config(command=toggle_products)
        register_section(products_header, products_sub, products_visible)
        msub(products_sub, t('product_list'), lambda: mount_products(right_panel))
        msub(products_sub, t('barcode_mgmt'), lambda: mount_barkod(right_panel))
        msub(products_sub, t('category_mgmt'), lambda: mount_kategori(right_panel))

        # Stok Yönetimi
        stock_header = mbtn(menu, "📦 " + t('stock_mgmt'), lambda: None)
        stock_sub = ttk.Frame(menu, style="Card.TFrame")
        stock_visible = {"v": False}
        def toggle_stock():
            if stock_visible["v"]:
                stock_sub.pack_forget(); stock_visible["v"] = False
            else:
                open_section(stock_header, stock_sub, stock_visible)
        stock_header.config(command=toggle_stock)
        register_section(stock_header, stock_sub, stock_visible)
        msub(stock_sub, t('stock_list'), lambda: mount_products(right_panel))
        msub(stock_sub, t('stock_in'), lambda: mount_stok_giris(right_panel))
        msub(stock_sub, t('stock_out'), lambda: mount_stok_cikis(right_panel))
        msub(stock_sub, t('inventory_count'), lambda: mount_envanter_sayim(right_panel))

        # Cari Yönetim
        account_header = mbtn(menu, "💼 " + t('account_mgmt_menu'), lambda: None)
        account_sub = ttk.Frame(menu, style="Card.TFrame")
        account_visible = {"v": False}
        def toggle_account():
            if account_visible["v"]:
                account_sub.pack_forget(); account_visible["v"] = False
            else:
                open_section(account_header, account_sub, account_visible)
        account_header.config(command=toggle_account)
        register_section(account_header, account_sub, account_visible)
        msub(account_sub, t('cari_list'), lambda: mount_cariler(right_panel))
        msub(account_sub, t('collection_entry'), lambda: mount_tahsilat(right_panel))
        msub(account_sub, t('payment_entry'), lambda: mount_odeme(right_panel))
        msub(account_sub, t('transactions'), lambda: mount_cari_hareketler(right_panel))

        # Hizmet/Masraf Yönetimi (emoji varyasyonunu sadeleştir – boşluk hissini azalt)
        svc_header = mbtn(menu, "🛠 " + t('service_expense_mgmt'), lambda: None)
        svc_sub = ttk.Frame(menu, style="Card.TFrame")
        svc_visible = {"v": False}
        def toggle_svc():
            if svc_visible["v"]:
                svc_sub.pack_forget(); svc_visible["v"] = False
            else:
                open_section(svc_header, svc_sub, svc_visible)
        svc_header.config(command=toggle_svc)
        register_section(svc_header, svc_sub, svc_visible)
        msub(svc_sub, t('service_list'), lambda: mount_hizmet_listesi(right_panel))
        msub(svc_sub, t('add_expense'), lambda: mount_masraf_ekle(right_panel))
        msub(svc_sub, t('expense_report'), lambda: mount_masraf_raporu(right_panel))

        # Satın Alma Yönetimi
        purchase_header = mbtn(menu, "🧾 " + t('purchase_mgmt'), lambda: None)
        purchase_sub = ttk.Frame(menu, style="Card.TFrame")
        purchase_visible = {"v": False}
        def toggle_purchase():
            if purchase_visible["v"]:
                purchase_sub.pack_forget(); purchase_visible["v"] = False
            else:
                open_section(purchase_header, purchase_sub, purchase_visible)
        purchase_header.config(command=toggle_purchase)
        register_section(purchase_header, purchase_sub, purchase_visible)
        msub(purchase_sub, t('dispatch_entry'), lambda: mount_irsaliye(right_panel))
        msub(purchase_sub, t('invoice_entry'), lambda: mount_fatura(right_panel))
        msub(purchase_sub, t('supplier_list'), lambda: mount_tedarikci_listesi(right_panel))

        # Personel Yönetimi
        personnel_header = mbtn(menu, "👥 " + t('personnel_mgmt'), lambda: None)
        personnel_sub = ttk.Frame(menu, style="Card.TFrame")
        personnel_visible = {"v": False}
        def toggle_personnel():
            if personnel_visible["v"]:
                personnel_sub.pack_forget(); personnel_visible["v"] = False
            else:
                open_section(personnel_header, personnel_sub, personnel_visible)
        personnel_header.config(command=toggle_personnel)
        register_section(personnel_header, personnel_sub, personnel_visible)
        msub(personnel_sub, t('personnel_list'), lambda: mount_users(right_panel))
        msub(personnel_sub, t('shift_mgmt'), lambda: mount_personel_vardiya(right_panel))
        msub(personnel_sub, t('salary_advance'), lambda: mount_personel_maas(right_panel))

        # Depo Yönetimi
        warehouse_header = mbtn(menu, "🏬 " + t('warehouse_mgmt'), lambda: None)
        warehouse_sub = ttk.Frame(menu, style="Card.TFrame")
        warehouse_visible = {"v": False}
        def toggle_warehouse():
            if warehouse_visible["v"]:
                warehouse_sub.pack_forget(); warehouse_visible["v"] = False
            else:
                open_section(warehouse_header, warehouse_sub, warehouse_visible)
        warehouse_header.config(command=toggle_warehouse)
        register_section(warehouse_header, warehouse_sub, warehouse_visible)
        msub(warehouse_sub, t('warehouse_list'), lambda: mount_depo_listesi(right_panel))
        msub(warehouse_sub, t('transfer'), lambda: mount_depo_transfer(right_panel))
        msub(warehouse_sub, t('warehouse_movements'), lambda: mount_depo_hareket(right_panel))

        # Kasa Yönetimi
        cash_header = mbtn(menu, "💵 " + t('cash_mgmt'), lambda: None)
        cash_sub = ttk.Frame(menu, style="Card.TFrame")
        cash_visible = {"v": False}
        def toggle_cash():
            if cash_visible["v"]:
                cash_sub.pack_forget(); cash_visible["v"] = False
            else:
                open_section(cash_header, cash_sub, cash_visible)
        cash_header.config(command=toggle_cash)
        register_section(cash_header, cash_sub, cash_visible)
        msub(cash_sub, t('cash_movements'), lambda: mount_kasa_hareket(right_panel))
        msub(cash_sub, t('cash_closure'), lambda: mount_kasa_devir(right_panel))
        msub(cash_sub, t('cash_report'), lambda: mount_kasa_rapor(right_panel))

        # Raporlar
        reports_header = mbtn(menu, "📊 " + t('reports'), lambda: None)
        reports_sub = ttk.Frame(menu, style="Card.TFrame")
        reports_visible = {"v": False}
        def toggle_reports():
            if reports_visible["v"]:
                reports_sub.pack_forget(); reports_visible["v"] = False
            else:
                open_section(reports_header, reports_sub, reports_visible)
        reports_header.config(command=toggle_reports)
        register_section(reports_header, reports_sub, reports_visible)
        msub(reports_sub, t('sales_report_menu'), lambda: mount_reports(right_panel))
        msub(reports_sub, t('stock_report_menu'), lambda: mount_stok_raporu(right_panel))
        msub(reports_sub, t('account_report_menu'), lambda: mount_cari_raporu(right_panel))
        msub(reports_sub, t('cash_report_menu'), lambda: mount_kasa_raporu(right_panel))

        # Diğer menüler
        mbtn(menu, "🧾 " + t('receipts'), lambda: mount_receipts(right_panel))
        mbtn(menu, "💾 " + t('daily_report'), export_daily_report)
    else:
        mbtn(menu, "🛒 " + t('sales'), lambda: mount_sales(right_panel))
        mbtn(menu, "🛑 " + t('cancel_sale'), lambda: mount_cancel_sales(right_panel))
        mbtn(menu, "🧾 " + t('receipts'), lambda: mount_receipts(right_panel))

    footer = ttk.Frame(main, style="Card.TFrame"); footer.pack(fill="x", padx=10, pady=(0,8))
    ttk.Label(footer, text=t('copyright'), style="Sub.TLabel").pack(side="left", padx=10)
    ttk.Label(footer, text=t('timestamp')+" "+datetime.now().strftime("%d.%m.%Y %H:%M"), style="Sub.TLabel").pack(side="right", padx=10)

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
        messagebox.showerror(t('error'), t('login_error'))

def toggle_password():
    if entry_password.cget("show") == "*":
        entry_password.config(show=""); btn_toggle_pw.config(text=f"🙈 {t('hide')}")
    else:
        entry_password.config(show="*"); btn_toggle_pw.config(text=f"👁 {t('show')}")

def start_login_screen():
    global login_window, entry_username, entry_password, btn_toggle_pw
    login_window = tk.Tk()
    login_window.title(f"{t('app_title')} - {t('login')}")
    set_theme(login_window); center_window(login_window, 440, 740)

    # Modern Dil Seçici
    lang_container = ttk.Frame(login_window, style="Card.TFrame")
    lang_container.pack(pady=(16, 0), padx=24, fill="x")
    
    lang_frame = tk.Frame(lang_container, bg=CARD_COLOR)
    lang_frame.pack(side="right")
    
    ttk.Label(lang_frame, text="🌐", style="TLabel", font=("Segoe UI", 13, "bold")).pack(side="left", padx=(0, 8))
    
    lang_var = tk.StringVar(value=CURRENT_LANGUAGE)
    
    def create_lang_button(code, label, emoji):
        def select_lang():
            if lang_var.get() != code:
                set_language(code)
                login_window.destroy()
                start_login_screen()
        
        is_active = (CURRENT_LANGUAGE == code)
        bg_color = ACCENT if is_active else "#2a2a35"
        fg_color = "white"
        
        btn = tk.Button(lang_frame, text=f"{emoji} {label}", 
                       bg=bg_color, fg=fg_color,
                       font=("Segoe UI", 10, "bold"),
                       activebackground="#0090dd" if is_active else "#3a3a45",
                       activeforeground="white",
                       relief="flat", padx=14, pady=8,
                       borderwidth=0, cursor="hand2",
                       command=select_lang)
        btn.pack(side="left", padx=3)
        
        def on_enter(e):
            if not is_active:
                btn.config(bg="#3a3a45")
        def on_leave(e):
            if not is_active:
                btn.config(bg="#2a2a35")
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn
    
    create_lang_button("tr", "TR", "🇹🇷")
    create_lang_button("en", "EN", "🇬🇧")

    # Modern Header
    ttk.Label(login_window, text=t('app_title'), 
              font=("Segoe UI", 22, "bold"),
              foreground="#00b0ff").pack(pady=(20, 4))
    ttk.Label(login_window, text=t('subtitle'), 
              style="Sub.TLabel",
              font=("Segoe UI", 11)).pack(pady=(0, 16))

    # Modern Form
    frame = ttk.Frame(login_window, style="Card.TFrame")
    frame.pack(pady=12, padx=28, fill="x")
    
    ttk.Label(frame, text=t('username'), 
              font=("Segoe UI", 11, "bold")).pack(pady=(20,6), anchor="w", padx=4)
    entry_username = ttk.Entry(frame, font=("Segoe UI", 11))
    entry_username.pack(pady=(0, 12), ipady=6, fill="x", padx=4)

    ttk.Label(frame, text=t('password'),
              font=("Segoe UI", 11, "bold")).pack(pady=(12,6), anchor="w", padx=4)
    pw_row = ttk.Frame(frame, style="Card.TFrame")
    pw_row.pack(fill="x", padx=4, pady=(0, 20))
    entry_password = ttk.Entry(pw_row, show="*", font=("Segoe UI", 11))
    entry_password.pack(side="left", fill="x", expand=True, ipady=6)
    
    btn_toggle_pw = tk.Button(pw_row, text=f"👁 {t('show')}", command=toggle_password,
                             bg="#3a3a45", fg="white", font=("Segoe UI", 9, "bold"),
                             activebackground="#4a4a55", activeforeground="white",
                             relief="flat", padx=12, pady=8, cursor="hand2", borderwidth=0)
    btn_toggle_pw.pack(side="left", padx=(8, 0))
    
    def toggle_hover_in(e): btn_toggle_pw.config(bg="#4a4a55")
    def toggle_hover_out(e): btn_toggle_pw.config(bg="#3a3a45")
    btn_toggle_pw.bind("<Enter>", toggle_hover_in)
    btn_toggle_pw.bind("<Leave>", toggle_hover_out)

    # Modern Login Butonu
    login_btn = tk.Button(frame, text="🔐 " + t('login'), command=login_action,
                         bg="#10b981", fg="white", font=("Segoe UI", 12, "bold"),
                         activebackground="#059669", activeforeground="white",
                         relief="flat", padx=24, pady=14, cursor="hand2", borderwidth=0)
    login_btn.pack(pady=(8, 24), fill="x", padx=4)
    
    def login_hover_in(e): login_btn.config(bg="#059669")
    def login_hover_out(e): login_btn.config(bg="#10b981")
    login_btn.bind("<Enter>", login_hover_in)
    login_btn.bind("<Leave>", login_hover_out)
    
    login_window.bind("<Return>", lambda e: login_action())
    
    ttk.Label(login_window, text=f"📦 {APP_VERSION}", 
              style="Sub.TLabel",
              font=("Segoe UI", 9)).pack(side="bottom", pady=14)
    login_window.mainloop()

# ==========================
# ==========================
# İlk Kurulum Ekranı
# ==========================
def show_language_setup():
    """İlk açılışta dil seçim ekranı göster"""
    global CURRENT_LANGUAGE
    
    setup_window = tk.Tk()
    setup_window.title("SmartPOS Mini Pro - Setup")
    
    # Pencereyi görünür ve en üstte yap
    setup_window.lift()
    setup_window.attributes('-topmost', True)
    setup_window.after_idle(setup_window.attributes, '-topmost', False)
    
    set_theme(setup_window)
    center_window(setup_window, 600, 600)
    
    # Ana container
    main_container = tk.Frame(setup_window, bg=BG_COLOR)
    main_container.pack(fill="both", expand=True, padx=20, pady=20)
    
    # Başlık
    ttk.Label(main_container, text="🌍", font=("Segoe UI", 48)).pack(pady=(20, 10))
    ttk.Label(main_container, text=t('app_title'), style="Header.TLabel").pack(pady=(0, 5))
    ttk.Label(main_container, text=t('select_language'), 
              style="TLabel", font=("Segoe UI", 11)).pack(pady=(5, 30))
    
    # Dil seçenekleri
    lang_frame = tk.Frame(main_container, bg=BG_COLOR)
    lang_frame.pack(pady=20, fill="x")
    
    def create_setup_lang_button(code, label, emoji, description):
        container = tk.Frame(lang_frame, bg=BG_COLOR)
        container.pack(pady=8, padx=20, fill="x")
        
        def select():
            # Dil seçilince otomatik devam et
            set_language(code)
            setup_window.destroy()  # Önce setup penceresini kapat
            setup_window.quit()     # mainloop'u durdur
            # start_login_screen() buradan çağırılmayacak, main'den çağrılacak
        
        btn = tk.Button(container, 
                       text=f"{emoji}  {label}",
                       bg=CARD_COLOR,
                       fg="white",
                       font=("Segoe UI", 12),
                       activebackground=ACCENT,
                       activeforeground="white",
                       relief="flat",
                       padx=30, pady=15,
                       borderwidth=0,
                       cursor="hand2",
                       command=select,
                       anchor="w")
        btn.pack(fill="x")
        
        ttk.Label(container, text=description, style="Sub.TLabel").pack(pady=(5, 0))
        
        # Hover efekti
        def on_enter(e):
            btn.config(bg=ACCENT)
        def on_leave(e):
            btn.config(bg=CARD_COLOR)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn
    
    create_setup_lang_button("tr", "Türkçe", "🇹🇷", "Turkish - Türkiye")
    create_setup_lang_button("en", "English", "🇬🇧", "English - International")
    
    setup_window.mainloop()

def check_first_run():
    """İlk çalıştırma kontrolü - dil ayarı var mı?"""
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        cursor.execute("SELECT value FROM settings WHERE key='language'")
        result = cursor.fetchone()
        return result is None
    except Exception as e:
        return True

# ==========================
# Çalıştır
# ==========================
if __name__ == "__main__":
    # Veritabanı tablolarını oluştur
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
    except Exception as e:
        pass
    
    # İlk çalıştırma kontrolü yap
    if check_first_run():
        show_language_setup()
        # Dil seçildikten sonra mainloop sona erdi, dili yükle ve giriş ekranını aç
        load_language_preference()
    
    # Giriş ekranını aç
    start_login_screen()

