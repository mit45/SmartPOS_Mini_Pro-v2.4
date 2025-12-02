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
CURRENT_USER = ""

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
    for w in parent.winfo_children():
        w.destroy()
    # Header
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="🏷️ " + t('barcode_mgmt'), style="Header.TLabel").pack(side="left", padx=8)

    # Body
    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    body.grid_columnconfigure(1, weight=1)

    from services import product_service as ps

    ttk.Label(body, text=t('product')+":", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=8, pady=8, sticky="e")
    products = ps.list_products(cursor)
    product_names = [p[1] for p in products]
    cb = ttk.Combobox(body, values=product_names, width=40, state="readonly", font=("Segoe UI", 10))
    cb.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

    ttk.Label(body, text=t('current_barcode'), font=("Segoe UI", 10)).grid(row=1, column=0, padx=8, pady=6, sticky="e")
    lbl_current = ttk.Label(body, text="-", font=("Segoe UI", 10, "bold"))
    lbl_current.grid(row=1, column=1, padx=8, pady=6, sticky="w")

    ttk.Label(body, text=t('new_barcode'), font=("Segoe UI", 10, "bold")).grid(row=2, column=0, padx=8, pady=6, sticky="e")
    e_new = ttk.Entry(body, width=30, font=("Segoe UI", 10)); e_new.grid(row=2, column=1, padx=8, pady=6, sticky="w")

    def refresh():
        name = cb.get()
        if not name:
            lbl_current.config(text="-"); return
        rows = ps.list_products(cursor, name)
        # find exact match
        row = next((r for r in rows if r[1]==name), None)
        if row:
            _, _name, barcode, _sale, _stock, _buy, _unit, _cat = row
            lbl_current.config(text=str(barcode or "-"))
            e_new.delete(0, tk.END)
            e_new.insert(0, str(barcode or ""))

    cb.bind("<<ComboboxSelected>>", lambda *_: refresh())

    btns = ttk.Frame(body, style="Card.TFrame"); btns.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(10,4))
    def save_barcode():
        name = cb.get().strip()
        if not name:
            return messagebox.showwarning(t('warning'), t('select_item'))
        # find product entry
        rows = ps.list_products(cursor, name)
        row = next((r for r in rows if r[1]==name), None)
        if not row:
            return messagebox.showerror(t('error'), t('product_not_found'))
        pid, _name, _barcode, sale_price, stock, buy_price, unit, _cat = row
        try:
            ps.update_product(conn, cursor, pid, _name, e_new.get().strip(), float(sale_price), float(stock), float(buy_price), unit=unit)
            messagebox.showinfo(t('success'), t('updated'))
            refresh()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))

    tk.Button(btns, text="💾 "+t('save'), command=save_barcode,
              bg="#10b981", fg="white", font=("Segoe UI", 9, "bold"),
              activebackground="#059669", relief="flat", padx=14, pady=8, borderwidth=0).pack(side="left", padx=4)

    if product_names:
        cb.set(product_names[0]); refresh()

def mount_kategori(parent):
    """Kategori Yönetimi"""
    for w in parent.winfo_children():
        w.destroy()

    # Header
    header = ttk.Frame(parent, style="Card.TFrame")
    header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="🗂️ " + t('category_mgmt'), style="Header.TLabel",
              font=("Segoe UI", 16, "bold")).pack(side="left", padx=8)

    # Body
    body = ttk.Frame(parent, style="Card.TFrame")
    body.pack(fill="both", expand=True, padx=12, pady=8)

    # Modern table
    cols = (t('id'), t('category_name'), t('category_color'), t('product_count'))
    tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
    for c in cols:
        tree.heading(c, text=c)
    tree.column(t('id'), width=60, anchor="center")
    tree.column(t('category_name'), width=300, anchor="w")
    tree.column(t('category_color'), width=150, anchor="center")
    tree.column(t('product_count'), width=120, anchor="center")
    tree.pack(fill="both", expand=True, padx=0, pady=0)

    def load_categories():
        for item in tree.get_children():
            tree.delete(item)
        from repositories import category_repository
        categories = category_repository.list_all(cursor)
        if not categories:
            # Boş mesajı
            tree.insert("", "end", values=("", t('no_categories'), "", ""))
        for cid, cname, color in categories:
            cnt = category_repository.count_products(cursor, cid)
            tree.insert("", "end", values=(cid, cname, color or "-", cnt))

    # Action buttons
    btn_frame = ttk.Frame(parent, style="Card.TFrame")
    btn_frame.pack(fill="x", padx=12, pady=(0, 12))

    def add_category():
        dialog = tk.Toplevel(parent)
        dialog.title(t('add_category'))
        set_theme(dialog)
        center_window(dialog, 400, 200)

        tk.Label(dialog, text=t('category_name') + ":", bg=CARD_COLOR, fg="white").pack(pady=(16,4), padx=16, anchor="w")
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=4, padx=16, fill="x")

        tk.Label(dialog, text=t('category_color') + " (hex):", bg=CARD_COLOR, fg="white").pack(pady=(8,4), padx=16, anchor="w")
        color_entry = ttk.Entry(dialog, width=40)
        color_entry.pack(pady=4, padx=16, fill="x")
        color_entry.insert(0, "#00b0ff")

        def save():
            cname = name_entry.get().strip()
            if not cname:
                messagebox.showwarning(t('warning'), t('enter_valid'))
                return
            from repositories import category_repository
            try:
                category_repository.insert(conn, cursor, cname, color_entry.get().strip())
                messagebox.showinfo(t('success'), t('done'))
                load_categories()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(t('error'), str(e))

        tk.Button(dialog, text="✅ " + t('save'), command=save,
                  bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=20, pady=10, cursor="hand2", borderwidth=0).pack(pady=16)

    def edit_category():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning(t('warning'), t('select_record'))
            return
        vals = tree.item(sel[0])['values']
        if not vals or not vals[0]:
            return
        cid = int(vals[0])
        cname = str(vals[1])
        color = str(vals[2]) if vals[2] != "-" else ""

        dialog = tk.Toplevel(parent)
        dialog.title(t('edit_category'))
        set_theme(dialog)
        center_window(dialog, 400, 200)

        tk.Label(dialog, text=t('category_name') + ":", bg=CARD_COLOR, fg="white").pack(pady=(16,4), padx=16, anchor="w")
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=4, padx=16, fill="x")
        name_entry.insert(0, cname)

        tk.Label(dialog, text=t('category_color') + " (hex):", bg=CARD_COLOR, fg="white").pack(pady=(8,4), padx=16, anchor="w")
        color_entry = ttk.Entry(dialog, width=40)
        color_entry.pack(pady=4, padx=16, fill="x")
        color_entry.insert(0, color)

        def save():
            new_name = name_entry.get().strip()
            if not new_name:
                messagebox.showwarning(t('warning'), t('enter_valid'))
                return
            from repositories import category_repository
            try:
                category_repository.update(conn, cursor, cid, new_name, color_entry.get().strip())
                messagebox.showinfo(t('success'), t('done'))
                load_categories()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(t('error'), str(e))

        tk.Button(dialog, text="✅ " + t('save'), command=save,
                  bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=20, pady=10, cursor="hand2", borderwidth=0).pack(pady=16)

    def delete_category():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning(t('warning'), t('select_record'))
            return
        vals = tree.item(sel[0])['values']
        if not vals or not vals[0]:
            return
        cid = int(vals[0])
        cname = str(vals[1])
        cnt = int(vals[3]) if vals[3] else 0
        if cnt > 0:
            if not messagebox.askyesno(t('warning'), f"{cname} kategorisinde {cnt} adet ürün var. Silmek istediğinize emin misiniz?"):
                return
        else:
            if not messagebox.askyesno(t('delete_category'), f"{cname} kategorisini silmek istediğinize emin misiniz?"):
                return
        from repositories import category_repository
        try:
            category_repository.delete(conn, cursor, cid)
            messagebox.showinfo(t('success'), t('done'))
            load_categories()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))

    tk.Button(btn_frame, text="➕ " + t('add'), command=add_category,
              bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"),
              relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0).pack(side="left", padx=4)
    tk.Button(btn_frame, text="✏️ " + t('edit'), command=edit_category,
              bg="#f59e0b", fg="white", font=("Segoe UI", 10, "bold"),
              relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0).pack(side="left", padx=4)
    tk.Button(btn_frame, text="🗑 " + t('delete'), command=delete_category,
              bg="#ef4444", fg="white", font=("Segoe UI", 10, "bold"),
              relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0).pack(side="left", padx=4)

    load_categories()


def mount_stok_giris(parent):
    _mount_stok_islem(parent, mode="in")

def mount_stok_cikis(parent):
    _mount_stok_islem(parent, mode="out")

def mount_envanter_sayim(parent):
    _mount_stok_islem(parent, mode="count")

def _mount_stok_islem(parent, mode: str = "in"):
    for w in parent.winfo_children():
        w.destroy()
    title = t('stock_in') if mode=="in" else (t('stock_out') if mode=="out" else t('inventory_count'))
    icon = "⬆️" if mode=="in" else ("⬇️" if mode=="out" else "📦")
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text=f"{icon} {title}", style="Header.TLabel").pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="x", padx=12, pady=8)
    body.grid_columnconfigure(1, weight=1)

    from services import product_service as ps
    products = ps.list_products(cursor)
    names = [p[1] for p in products]

    ttk.Label(body, text=t('product')+":", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=8, pady=8, sticky="e")
    cb = ttk.Combobox(body, values=names, width=40, state="readonly", font=("Segoe UI", 10))
    cb.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

    ttk.Label(body, text=t('stock')+":", font=("Segoe UI", 10)).grid(row=1, column=0, padx=8, pady=6, sticky="e")
    lbl_stock = ttk.Label(body, text="-", font=("Segoe UI", 10, "bold")); lbl_stock.grid(row=1, column=1, padx=8, pady=6, sticky="w")
    ttk.Label(body, text=t('unit')+":", font=("Segoe UI", 10)).grid(row=1, column=2, padx=8, pady=6, sticky="e")
    lbl_unit = ttk.Label(body, text="-", font=("Segoe UI", 10)); lbl_unit.grid(row=1, column=3, padx=8, pady=6, sticky="w")

    qty_label = t('quantity') if mode!="count" else t('stock')
    ttk.Label(body, text=qty_label+":", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, padx=8, pady=6, sticky="e")
    e_qty = ttk.Entry(body, width=12, font=("Segoe UI", 10)); e_qty.grid(row=2, column=1, padx=8, pady=6, sticky="w")

    def refresh():
        name = cb.get()
        if not name:
            lbl_stock.config(text="-"); lbl_unit.config(text="-"); return
        info = ps.get_price_stock_by_name(cursor, name)
        if info:
            _price, stock, unit = info
            lbl_unit.config(text=str(unit))
            if str(unit).lower()=="kg":
                lbl_stock.config(text=f"{float(stock):.3f}")
            else:
                lbl_stock.config(text=str(int(float(stock))))

    cb.bind("<<ComboboxSelected>>", lambda *_: refresh())

    def apply_change():
        name = cb.get().strip()
        if not name:
            return messagebox.showwarning(t('warning'), t('select_item'))
        qty = parse_float_safe(e_qty.get(), None)
        if qty is None or qty < 0:
            return messagebox.showwarning(t('warning'), t('enter_valid'))
        info2 = ps.get_price_stock_by_name(cursor, name)
        if not info2:
            return messagebox.showerror(t('error'), t('product_not_found'))
        price, stock, unit = info2
        if mode=="in":
            ps.increment_stock(conn, cursor, name, float(qty))
        elif mode=="out":
            if float(qty) > float(stock):
                return messagebox.showwarning(t('warning'), t('insufficient_stock').format(stock=stock))
            ps.decrement_stock(conn, cursor, name, float(qty))
        else:  # count
            # set stock to target by adjusting delta
            target = float(qty)
            delta = target - float(stock)
            if abs(delta) > 1e-9:
                if delta > 0:
                    ps.increment_stock(conn, cursor, name, delta)
                else:
                    ps.decrement_stock(conn, cursor, name, -delta)
        refresh(); messagebox.showinfo(t('success'), t('done'))

    btn_text = t('save') if mode=="count" else t('apply') if t('apply')!= 'apply' else t('save')
    tk.Button(body, text="✅ "+btn_text, command=apply_change,
              bg="#00b0ff", fg="white", font=("Segoe UI", 10, "bold"),
              activebackground="#0ea5e9", relief="flat", padx=14, pady=8, borderwidth=0).grid(row=3, column=1, padx=8, pady=10, sticky="w")

    if names:
        cb.set(names[0]); refresh()

def mount_tahsilat(parent):
    _mount_cari_islem(parent, mode="tahsilat")

def mount_odeme(parent):
    _mount_cari_islem(parent, mode="odeme")

def mount_cari_hareketler(parent):
    _mount_cari_islem(parent, mode="hareket")

def _mount_cari_islem(parent, mode: str):
    for w in parent.winfo_children():
        w.destroy()
    from services import cari_service as cs
    title = t('collection_entry') if mode=="tahsilat" else (t('payment_entry') if mode=="odeme" else t('transactions'))
    icon = "💰" if mode=="tahsilat" else ("💸" if mode=="odeme" else "🔁")
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text=f"{icon} {title}", style="Header.TLabel").pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)

    # Cari seçimi
    ttk.Label(body, text=t('cari_name'), font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=8, pady=8, sticky="e")
    cariler = cs.list_all(cursor)
    cari_names = [c[1] for c in cariler]
    cb = ttk.Combobox(body, values=cari_names, width=36, state="readonly", font=("Segoe UI", 10))
    cb.grid(row=0, column=1, padx=8, pady=8, sticky="w")

    if mode in ("tahsilat","odeme"):
        ttk.Label(body, text=t('tutar'), font=("Segoe UI", 10, "bold")).grid(row=1, column=0, padx=8, pady=6, sticky="e")
        e_amount = ttk.Entry(body, width=14, font=("Segoe UI", 10)); e_amount.grid(row=1, column=1, padx=8, pady=6, sticky="w")
        ttk.Label(body, text=t('aciklama'), font=("Segoe UI", 10)).grid(row=2, column=0, padx=8, pady=6, sticky="e")
        e_desc = ttk.Entry(body, width=28, font=("Segoe UI", 10)); e_desc.grid(row=2, column=1, padx=8, pady=6, sticky="w")

        def apply_tx():
            name = cb.get().strip()
            if not name:
                return messagebox.showwarning(t('warning'), t('select_item'))
            row = next((c for c in cariler if c[1]==name), None)
            if not row:
                return messagebox.showerror(t('error'), t('product_not_found'))
            cari_id = row[0]
            amt = parse_float_safe(e_amount.get(), None)
            if amt is None or amt <= 0:
                return messagebox.showwarning(t('warning'), t('enter_valid'))
            desc = e_desc.get().strip() or (t('collection_entry') if mode=="tahsilat" else t('payment_entry'))
            try:
                if mode=="tahsilat":
                    cs.add_tahsilat(conn, cursor, cari_id, amt, desc)
                else:
                    cs.add_odeme(conn, cursor, cari_id, amt, desc)
                messagebox.showinfo(t('success'), t('done'))
                load_moves()
            except Exception as e:
                messagebox.showerror(t('error'), str(e))

        tk.Button(body, text="✅ "+t('save'), command=apply_tx,
                  bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"),
                  activebackground="#059669", relief="flat", padx=14, pady=8, borderwidth=0).grid(row=3, column=1, padx=8, pady=8, sticky="w")

    # Hareket listesi
    frame = ttk.Frame(body, style="Card.TFrame"); frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=8, pady=12)
    body.grid_rowconfigure(4, weight=1)
    body.grid_columnconfigure(1, weight=1)
    cols = (t('date'), t('islem_type'), t('tutar'), t('aciklama'))
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
    for c in cols:
        tree.heading(c, text=c)
        anchor = "e" if c in (t('tutar'),) else ("w" if c in (t('aciklama'),) else "center")
        tree.column(c, anchor=anchor, width=140)
    tree.pack(fill="both", expand=True)

    def load_moves():
        for r in tree.get_children():
            tree.delete(r)
        name = cb.get().strip()
        if not name:
            return
        row = next((c for c in cariler if c[1]==name), None)
        if not row:
            return
        for mid, typ, tutar, acik, created in cs.list_hareketler(cursor, row[0]):
            tree.insert("", "end", values=(str(created), str(typ), f"{float(tutar):.2f}", str(acik or "")))

    cb.bind("<<ComboboxSelected>>", lambda *_: load_moves())
    if cari_names:
        cb.set(cari_names[0]); load_moves()

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
            # miktarı virgüllü göstermek için
            qty_disp = f"{float(qty):.3f}" if abs(float(qty) - round(float(qty))) > 1e-6 else str(int(round(float(qty))))
            tree.insert("", "end", values=(fis_id, ts_disp, pname, qty_disp, f"{float(price):.2f}", f"{float(total):.2f}"))
            t_qty += float(qty); t_sum += float(total)
        qty_total_disp = f"{t_qty:.3f}" if abs(t_qty - round(t_qty)) > 1e-6 else str(int(round(t_qty)))
        lbl_sum.config(text=f"{t('quantity')}: {qty_total_disp} | {t('total')}: {t_sum:.2f} ₺")

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
            t_qty = 0.0
            t_sum = 0.0
            for fis_id, ts, pname, qty, price, total in rows:
                ts_disp = (ts or "").replace("T", " ")
                qty_disp = f"{float(qty):.3f}" if abs(float(qty) - round(float(qty))) > 1e-6 else str(int(round(float(qty))))
                data.append([str(fis_id), ts_disp, str(pname), qty_disp, f"{float(price):.2f}", f"{float(total):.2f}"])
                t_qty += float(qty)
                t_sum += float(total)
            
            # Toplam satırı
            qty_total_disp = f"{t_qty:.3f}" if abs(t_qty - round(t_qty)) > 1e-6 else str(int(round(t_qty)))
            data.append(['', '', t('total'), qty_total_disp, '', f"{t_sum:.2f} ₺"])
            
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
                sales_list.append((str(pname), float(q), float(unit_gross), float(line_gross)))

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
    """Modern POS Arayüzü - Resimdeki tasarıma göre"""
    for w in parent.winfo_children():
        w.destroy()
    
    from services import product_service as product_svc
    from services import sales_service as sales_svc
    from services import cari_service
    
    # Ana konteynır (sol menü için)
    main_container = tk.Frame(parent, bg=BG_COLOR)
    main_container.pack(fill="both", expand=True, padx=0, pady=0)
    
    # === SOL MEN��: AÇILIR KAPANIR ===
    menu_state = {"open": False}
    
    # Menü butonu (hamburger)
    menu_btn_container = tk.Frame(main_container, bg="#1a1a20", width=60, height=60)
    menu_btn_container.place(x=0, y=0)
    
    menu_btn = tk.Button(menu_btn_container, text="☰", font=("Segoe UI", 24),
                        bg="#20c997", fg="white", relief="flat", padx=8, pady=4,
                        cursor="hand2", borderwidth=0, activebackground="#17a589")
    menu_btn.pack(fill="both", expand=True)
    
    # Menü paneli (başlangıçta gizli)
    menu_panel = tk.Frame(main_container, bg="#1a1a20", width=250)
    
    def toggle_menu():
        if menu_state["open"]:
            # Kapat
            menu_panel.place_forget()
            menu_state["open"] = False
            menu_btn.config(text="☰")
        else:
            # Aç
            menu_panel.place(x=0, y=0, relheight=1.0)
            menu_state["open"] = True
            menu_btn.config(text="✕")
        
        # Hızlı ürünler yerleşimini güncelle (menü genişliği değiştiğinde)
        # Birden fazla tetikleme ile güvenilirliği artır
        try:
            if hasattr(parent, '_relayout_quick_products'):
                parent.update_idletasks()  # Layout güncellemesini zorla
                parent.after(10, parent._relayout_quick_products)
                parent.after(100, parent._relayout_quick_products)
                parent.after(200, parent._relayout_quick_products)
        except Exception:
            pass
    
    menu_btn.config(command=toggle_menu)
    
    # Menü içeriği
    menu_header = tk.Frame(menu_panel, bg="#20c997", height=60)
    menu_header.pack(fill="x")
    tk.Label(menu_header, text="📋 İşlem Menüsü", font=("Segoe UI", 14, "bold"),
             bg="#20c997", fg="white").pack(side="left", padx=15, pady=15)
    
    menu_close_btn = tk.Button(menu_header, text="✕", font=("Segoe UI", 18),
                               bg="#20c997", fg="white", relief="flat", padx=8,
                               cursor="hand2", borderwidth=0, command=toggle_menu)
    menu_close_btn.pack(side="right", padx=10)
    
    menu_content = tk.Frame(menu_panel, bg="#1a1a20")
    menu_content.pack(fill="both", expand=True, padx=0, pady=0)
    
    # Menü öğeleri
    def create_menu_item(parent, icon, text, command):
        btn = tk.Button(parent, text=f"{icon}  {text}", font=("Segoe UI", 11),
                       bg="#1a1a20", fg="white", relief="flat", anchor="w",
                       padx=20, pady=12, cursor="hand2", borderwidth=0,
                       activebackground="#2a2a35", activeforeground="white",
                       command=command)
        btn.pack(fill="x", pady=1)
        
        def on_enter(e):
            btn.config(bg="#2a2a35")
        def on_leave(e):
            btn.config(bg="#1a1a20")
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn
    
    # Menü öğelerini ekle
    create_menu_item(menu_content, "📦", t('product_mgmt'), lambda: [toggle_menu(), mount_products(parent)])
    create_menu_item(menu_content, "📊", t('stock_mgmt'), lambda: [toggle_menu(), mount_stok_giris(parent)])
    create_menu_item(menu_content, "💼", t('account_mgmt_menu'), lambda: [toggle_menu(), mount_cariler(parent)])
    create_menu_item(menu_content, "👥", t('users'), lambda: [toggle_menu(), mount_users(parent)])
    create_menu_item(menu_content, "🛑", t('cancel_sale'), lambda: [toggle_menu(), mount_cancel_sales(parent)])
    create_menu_item(menu_content, "🧾", t('receipts'), lambda: [toggle_menu(), mount_receipts(parent)])
    create_menu_item(menu_content, "📈", t('reports'), lambda: [toggle_menu(), mount_reports(parent)])
    
    # Ana içerik (menü kapalıyken tam ekran)
    content_container = tk.Frame(main_container, bg=BG_COLOR)
    content_container.place(x=0, y=0, relwidth=1.0, relheight=1.0)
    
    # Ana içerik (menü kapalıyken tam ekran)
    content_container = tk.Frame(main_container, bg=BG_COLOR)
    content_container.place(x=0, y=0, relwidth=1.0, relheight=1.0)
    
    # === ÜST BÖLÜM: BARKOD OKUMA VE FİYAT GÖR ===
    top_section = tk.Frame(content_container, bg=BG_COLOR)
    top_section.pack(fill="x", padx=12, pady=(8,4))
    
    # Barkod giriş alanı (sol)
    barcode_frame = tk.Frame(top_section, bg=CARD_COLOR, relief="flat", bd=1)
    barcode_frame.pack(side="left", fill="x", expand=True, padx=(0,8))
    
    tk.Label(barcode_frame, text="📷", font=("Segoe UI", 16), bg=CARD_COLOR, fg="white").pack(side="left", padx=10)
    barcode_entry = tk.Entry(barcode_frame, font=("Segoe UI", 14), bg="#ffffff", fg="#333333",
                             insertbackground="#000000", relief="flat", bd=0)
    barcode_entry.pack(side="left", fill="both", expand=True, padx=0, pady=8, ipady=6)
    barcode_entry.insert(0, "Ürün Barkodunu Okutunuz...")
    barcode_entry.config(fg="#999999")
    
    # FONKSİYONLARI ÖNCE TANIMLA (butonlardan önce)
    def show_product_list():
        """Ürün listesini göster (ara butonuna basıldığında)"""
        search_text = barcode_entry.get().strip()
        if "Okutunuz" in search_text:
            search_text = ""
        
        # Ürün arama penceresi
        search_win = tk.Toplevel(parent)
        search_win.title(t('search'))
        set_theme(search_win)
        center_window(search_win, 800, 600)
        
        ttk.Label(search_win, text="🔍 " + t('product_list'), style="Header.TLabel").pack(pady=12)
        
        # Arama kutusu
        search_frame = tk.Frame(search_win, bg=CARD_COLOR)
        search_frame.pack(fill="x", padx=12, pady=8)
        search_entry = ttk.Entry(search_frame, font=("Segoe UI", 11), width=40)
        search_entry.pack(side="left", padx=8, pady=8, fill="x", expand=True)
        search_entry.insert(0, search_text)
        
        # Liste
        list_frame = tk.Frame(search_win, bg=CARD_COLOR)
        list_frame.pack(fill="both", expand=True, padx=12, pady=8)
        
        cols = (t('name'), t('barcode'), t('price'), t('stock'), t('unit'))
        search_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=15)
        for c in cols:
            search_tree.heading(c, text=c)
        search_tree.column(t('name'), width=300)
        search_tree.column(t('barcode'), width=150)
        search_tree.column(t('price'), width=100, anchor="e")
        search_tree.column(t('stock'), width=100, anchor="e")
        search_tree.column(t('unit'), width=80, anchor="center")
        search_tree.pack(fill="both", expand=True)
        
        def load_products(filter_text=""):
            for item in search_tree.get_children():
                search_tree.delete(item)
            from repositories import product_repository
            products = product_repository.list_all(cursor)
            for p in products:
                pid, name, barcode, price, stock, buy_price, unit, category = p
                if filter_text.lower() in name.lower() or filter_text in (barcode or ""):
                    search_tree.insert("", "end", values=(name, barcode or "", f"{float(price):.2f}", 
                                                          f"{float(stock):.2f}", unit or "adet"))
        
        def on_search(e=None):
            load_products(search_entry.get().strip())
        
        search_entry.bind("<KeyRelease>", on_search)
        
        def on_select(e=None):
            sel = search_tree.selection()
            # Eğer seçim yoksa ama liste doluysa (örn: Enter'a basıldı), ilkini seç
            if not sel:
                children = search_tree.get_children()
                if children:
                    sel = (children[0],)
            
            if sel:
                pname = search_tree.item(sel[0])["values"][0]
                add_product_to_cart(pname, 1)
                
                # Ana ekrandaki arama kutusunu temizle
                try:
                    barcode_entry.delete(0, tk.END)
                    barcode_entry.insert(0, "Ürün Barkodunu Okutunuz...")
                    barcode_entry.config(fg="#999999")
                    # Odağı geri ver
                    barcode_entry.focus_set()
                    barcode_entry.icursor(0)
                except:
                    pass

                search_win.destroy()
        
        def focus_tree(e):
            """Arama kutusundan aşağı oka basınca listeye odaklan"""
            children = search_tree.get_children()
            if children:
                search_tree.focus_set()
                # İlk elemanı seçili hale getir
                search_tree.selection_set(children[0])
                search_tree.focus(children[0])
                search_tree.see(children[0])
                return "break"

        search_tree.bind("<Double-1>", on_select)
        search_tree.bind("<Return>", on_select)
        
        # Arama kutusu eventleri
        search_entry.bind("<Return>", on_select)
        search_entry.bind("<Down>", focus_tree)
        
        load_products(search_text)
        search_entry.focus_set()
    
    def show_price():
        """Barkod ile fiyat sorgulama"""
        barcode = barcode_entry.get().strip()
        if "Okutunuz" in barcode or not barcode:
            messagebox.showwarning(t('warning'), "Lütfen barkod okutun veya girin!")
            return
        result = product_svc.get_by_barcode(cursor, barcode)
        if result:
            pid, pname, price, stock, unit = result
            messagebox.showinfo(t('price'), f"{pname}\n\n{t('price')}: {price:.2f} ₺\n{t('stock')}: {stock:.2f} {unit}")
        else:
            messagebox.showerror(t('error'), t('product_not_found'))
    
    def reprint_last():
        """Son fişi yeniden yazdır veya sepet doluysa sepeti yazdır"""
        # Sepet kontrolü
        try:
            items = product_tree.get_children()
        except NameError:
            items = []

        if items:
            # Sepet doluysa MEVCUT sepeti yazdır (Önizleme)
            current_sales_list = []
            for item in items:
                vals = product_tree.item(item)["values"]
                # vals: [DeleteBtn, Barcode, Name, Category, Qty, Price, Total]
                pname = vals[2]
                def num(v):
                    try:
                        return float(str(v).replace(".", ".").replace(",", "."))
                    except:
                        return 0.0
                qty = num(vals[4])
                price = num(vals[5])
                line_total = num(vals[6])
                current_sales_list.append((pname, qty, price, line_total))
            
            # Müşteri adı
            cust_name = t('customer')
            try:
                if customer_entry.get().strip():
                    cust_name = customer_entry.get().strip()
            except:
                pass

            # Yazdır (Önizleme)
            print_receipt(current_sales_list, fis_id="ONIZLEME", customer_name=cust_name,
                         kdv_rate=18.0, discount_rate=0.0, vat_included=False,
                         language_code=CURRENT_LANGUAGE)
            
            messagebox.showinfo(t('info'), "Sepetteki ürünler önizleme olarak yazdırıldı.\n(Satış henüz kaydedilmedi)")
            return

        # Sepet boşsa son fişi yazdır
        if not messagebox.askyesno(t('reprint'), "Sepet boş. Son kesilen fişi tekrar yazdırmak ister misiniz?"):
            return

        cursor.execute("SELECT fis_id FROM sales ORDER BY id DESC LIMIT 1")
        r = cursor.fetchone()
        if not r:
            messagebox.showwarning(t('warning'), "Henüz fiş bulunamadı!")
            return
        fis_id = r[0]
        cursor.execute("SELECT product_name, quantity, price, total FROM sales WHERE fis_id=?", (fis_id,))
        sales_list = [(row[0], row[1], row[2], row[3]) for row in cursor.fetchall()]
        
        if not sales_list:
            return
        
        print_receipt(sales_list, fis_id=fis_id, customer_name=t('customer'),
                     kdv_rate=18.0, discount_rate=0.0, vat_included=False,
                     language_code=CURRENT_LANGUAGE)
    
    # Ara butonu
    search_btn = tk.Button(top_section, text="🔍 " + t('search'), font=("Segoe UI", 12, "bold"),
                          bg="#17a2b8", fg="white", relief="flat", padx=20, pady=12,
                          cursor="hand2", borderwidth=0, activebackground="#138496",
                          command=show_product_list)
    search_btn.pack(side="left", padx=4)
    
    # Fiyat Gör butonu
    price_btn = tk.Button(top_section, text="💰 " + t('see_price'), font=("Segoe UI", 12, "bold"),
                         bg="#28a745", fg="white", relief="flat", padx=20, pady=12,
                         cursor="hand2", borderwidth=0, activebackground="#218838",
                         command=show_price)
    price_btn.pack(side="left", padx=4)
    
    # Yazdır butonu
    print_btn = tk.Button(top_section, text="🖨 " + t('reprint'), font=("Segoe UI", 9),
                         bg="#fd7e14", fg="white", relief="flat", padx=16, pady=8,
                         cursor="hand2", borderwidth=0, activebackground="#e96d0b",
                         command=reprint_last)
    print_btn.pack(side="left", padx=4)
    
    # === ORTA BÖLÜM: 3 SÜTUN LAYOUT ===
    middle_section = tk.Frame(content_container, bg=BG_COLOR)
    middle_section.pack(fill="both", expand=True, padx=12, pady=4)
    
    # SOL PANEL: Ürün Listesi (genişlik artırıldı)
    left_panel = tk.Frame(middle_section, bg=CARD_COLOR, width=750)
    left_panel.pack(side="left", fill="both", expand=True, padx=(0,8), pady=0)
    
    # Ürün başlık ve ekle butonu
    product_header = tk.Frame(left_panel, bg=CARD_COLOR)
    product_header.pack(fill="x", padx=8, pady=8)
    product_count_label = tk.Label(product_header, text=t('products') + " 🗂️ 0", font=("Segoe UI", 12, "bold"),
             bg=CARD_COLOR, fg="white")
    product_count_label.pack(side="left")
    
    tk.Button(product_header, text=t('add'), font=("Segoe UI", 9), bg="#6c757d", fg="white",
             relief="flat", padx=12, pady=4, cursor="hand2", command=show_product_list).pack(side="right")
    
    # Ürün tablosu
    product_frame = tk.Frame(left_panel, bg=CARD_COLOR)
    product_frame.pack(fill="both", expand=True, padx=8, pady=(0,8))
    
    cols = (t('delete'), t('barcode'), t('product'), t('category'), t('quantity'), t('price'), t('total'))
    product_tree = ttk.Treeview(product_frame, columns=cols, show="headings", height=12)
    for c in cols:
        product_tree.heading(c, text=c)
    # Kolon genişliklerini 750px panel için optimize et (sağdaki G.(?) kolonu kaldırıldı)
    product_tree.column(t('delete'), width=40, anchor="center", stretch=False)
    product_tree.column(t('barcode'), width=110, anchor="w", stretch=False)
    product_tree.column(t('product'), width=220, anchor="w", stretch=True)
    product_tree.column(t('category'), width=110, anchor="w", stretch=False)
    product_tree.column(t('quantity'), width=120, anchor="center", stretch=False)
    product_tree.column(t('price'), width=120, anchor="center", stretch=False)
    product_tree.column(t('total'), width=100, anchor="e", stretch=False)
    
    product_tree.tag_configure('oddrow', background='#1f1f25')
    product_tree.tag_configure('evenrow', background='#252530')

    # Miktar hücresi inline editor (Frame) referansı
    qty_editor_frame = None

    # Miktar hücresi için açık editörü kapat
    def destroy_qty_editor():
        nonlocal qty_editor_frame
        if qty_editor_frame is not None:
            try:
                if qty_editor_frame.winfo_exists():
                    qty_editor_frame.destroy()
            except Exception:
                pass
            qty_editor_frame = None

    # Satır silme ve miktar düzenleme
    def on_tree_click(event):
        """Ürün tablosuna tıklandığında - Sil sütununa tıklanırsa sil"""
        # Başka yere tıklandığında açık editör varsa kapat
        destroy_qty_editor()
        region = product_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = product_tree.identify_column(event.x)
            item = product_tree.identify_row(event.y)
            if column == "#1" and item:  # Sil sütunu (#1 = ilk sütun)
                if messagebox.askyesno("Sil", "Bu ürünü sepetten silmek istiyor musunuz?"):
                    destroy_qty_editor()
                    # İlgili miktar ve fiyat frame'lerini de kaldır
                    try:
                        frq = qty_frames.pop(item, None)
                        if frq and frq.winfo_exists():
                            frq.destroy()
                        frp = price_frames.pop(item, None)
                        if frp and frp.winfo_exists():
                            frp.destroy()
                    except Exception:
                        pass
                    product_tree.delete(item)
                    update_totals()
    # Miktar hücresi için inline editör
    # Çoklu miktar ve fiyat editörleri: tüm satırlara kalıcı alanlar
    qty_frames = {}   # item_id -> frame
    price_frames = {} # item_id -> frame

    def build_qty_frame(item_id):
        vals = list(product_tree.item(item_id, "values"))
        if len(vals) < 7:
            return
        bbox = product_tree.bbox(item_id, "#5")  # miktar sütunu
        if not bbox:
            # görünmüyorsa varsa gizle
            fr = qty_frames.get(item_id)
            if fr and fr.winfo_exists():
                fr.place_forget()
            return
        x, y, w, h = bbox
        # Birim ve step
        pname = vals[2]
        unit = "adet"
        step = 1.0
        stock = 999999
        try:
            r = product_svc.get_price_stock_by_name(cursor, pname)
            if r:
                unit = str(r[2]) or "adet"
                stock = float(r[1])
            step = 0.1 if unit.lower().startswith("kg") else 1.0
        except Exception:
            pass
        # Mevcut qty
        try:
            current_qty = float(str(vals[4]).replace(",", "."))
        except Exception:
            current_qty = 1.0

        def format_qty(q):
            return f"{q:.3f}" if step == 0.1 else f"{int(round(q))}"

        # Frame yarat veya kullan
        frame = qty_frames.get(item_id)
        if frame is None or not frame.winfo_exists():
            frame = tk.Frame(product_tree, bg="#f5e4c8", highlightbackground="black", highlightthickness=1)
            qty_frames[item_id] = frame
            qty_var = tk.DoubleVar(value=current_qty)

            def apply_qty(new_q, update_entry=True):
                if new_q < 0:
                    new_q = 0.0
                if new_q > stock:
                    new_q = stock
                if step == 0.1:
                    new_q = round(new_q, 3)
                else:
                    new_q = round(new_q)
                qty_var.set(new_q)
                if update_entry and 'qty_entry' in locals():
                    try:
                        qty_entry.delete(0, tk.END)
                        qty_entry.insert(0, format_qty(new_q))
                    except Exception:
                        pass
                try:
                    price = float(str(vals[5]).replace(",", "."))
                except Exception:
                    price = 0.0
                vals[4] = format_qty(new_q)
                vals[6] = f"{price * float(new_q):.2f}"
                product_tree.item(item_id, values=vals)
                update_totals()

            def read_from_entry():
                try:
                    return float(str(qty_entry.get()).replace(",", ".").strip())
                except Exception:
                    return qty_var.get()

            def inc():
                apply_qty(read_from_entry() + step)
            def dec():
                apply_qty(read_from_entry() - step)

            # GRID yerleşimi: butonlar sabit, orta giriş esner
            frame.grid_propagate(False)
            frame.columnconfigure(1, weight=1)
            btn_minus = tk.Button(frame, text="-", font=("Segoe UI", 10, "bold"), bg="#dc3545", fg="white", bd=0, cursor="hand2", command=dec)
            btn_plus = tk.Button(frame, text="+", font=("Segoe UI", 10, "bold"), bg="#28a745", fg="white", bd=0, cursor="hand2", command=inc)
            qty_entry = tk.Entry(frame, justify="center", font=("Segoe UI", 10, "bold"), bg="#f5e4c8", fg="#000", relief="flat")
            qty_entry.insert(0, format_qty(current_qty))
            btn_minus.grid(row=0, column=0, sticky="nsw", padx=(0,0))
            qty_entry.grid(row=0, column=1, sticky="nsew")
            btn_plus.grid(row=0, column=2, sticky="nse", padx=(0,0))

            def on_qty_keyrelease(e):
                # metinden sayıyı al, geçerliyse satırı güncelle, giriş biçimini bozmadan
                try:
                    val = float(str(qty_entry.get()).replace(",", ".").strip())
                    apply_qty(val, update_entry=False)
                except Exception:
                    pass

            def on_qty_commit(e=None):
                apply_qty(read_from_entry(), update_entry=True)

            qty_entry.bind('<KeyRelease>', on_qty_keyrelease)
            qty_entry.bind('<FocusOut>', on_qty_commit)
            qty_entry.bind('<Return>', lambda e: on_qty_commit())
        else:
            # mevcutsa etiketi güncelle
            try:
                children = frame.winfo_children()
                if len(children) >= 2 and isinstance(children[1], tk.Entry):
                    children[1].delete(0, tk.END)
                    children[1].insert(0, format_qty(current_qty))
            except Exception:
                pass
        frame.place(x=x, y=y, width=w, height=h)

    def build_price_frame(item_id):
        vals = list(product_tree.item(item_id, "values"))
        if len(vals) < 7:
            return
        bbox = product_tree.bbox(item_id, "#6")  # fiyat sütunu
        if not bbox:
            fr = price_frames.get(item_id)
            if fr and fr.winfo_exists():
                fr.place_forget()
            return
        x, y, w, h = bbox

        # Mevcut price ve qty
        try:
            current_price = float(str(vals[5]).replace(",", "."))
        except Exception:
            current_price = 0.0
        try:
            current_qty = float(str(vals[4]).replace(",", "."))
        except Exception:
            current_qty = 1.0

        step = 0.50  # fiyat adımı (TL)

        def format_price(p):
            return f"{p:.2f}"

        frame = price_frames.get(item_id)
        if frame is None or not frame.winfo_exists():
            frame = tk.Frame(product_tree, bg="#f5e4c8", highlightbackground="black", highlightthickness=1)
            price_frames[item_id] = frame
            price_var = tk.DoubleVar(value=current_price)

            def apply_price(new_p, update_entry=True):
                if new_p < 0:
                    new_p = 0.0
                new_p = round(new_p, 2)
                price_var.set(new_p)
                if update_entry and 'price_entry' in locals():
                    try:
                        price_entry.delete(0, tk.END)
                        price_entry.insert(0, format_price(new_p))
                    except Exception:
                        pass
                # Tree güncelle
                vals_local = list(product_tree.item(item_id, "values"))
                vals_local[5] = format_price(new_p)
                try:
                    qty_local = float(str(vals_local[4]).replace(",", "."))
                except Exception:
                    qty_local = current_qty
                vals_local[6] = f"{float(new_p) * float(qty_local):.2f}"
                product_tree.item(item_id, values=vals_local)
                update_totals()

            def read_from_entry():
                try:
                    return float(str(price_entry.get()).replace(",", ".").strip())
                except Exception:
                    return price_var.get()

            def inc():
                apply_price(read_from_entry() + step)
            def dec():
                apply_price(read_from_entry() - step)

            frame.grid_propagate(False)
            frame.columnconfigure(1, weight=1)
            btn_minus = tk.Button(frame, text="-", font=("Segoe UI", 10, "bold"), bg="#dc3545", fg="white", bd=0, cursor="hand2", command=dec)
            btn_plus = tk.Button(frame, text="+", font=("Segoe UI", 10, "bold"), bg="#28a745", fg="white", bd=0, cursor="hand2", command=inc)
            price_entry = tk.Entry(frame, justify="center", font=("Segoe UI", 10, "bold"), bg="#f5e4c8", fg="#000", relief="flat")
            price_entry.insert(0, format_price(current_price))
            btn_minus.grid(row=0, column=0, sticky="nsw")
            price_entry.grid(row=0, column=1, sticky="nsew")
            btn_plus.grid(row=0, column=2, sticky="nse")

            def on_price_keyrelease(e):
                try:
                    val = float(str(price_entry.get()).replace(",", ".").strip())
                    apply_price(val, update_entry=False)
                except Exception:
                    pass

            def on_price_commit(e=None):
                apply_price(read_from_entry(), update_entry=True)

            price_entry.bind('<KeyRelease>', on_price_keyrelease)
            price_entry.bind('<FocusOut>', on_price_commit)
            price_entry.bind('<Return>', lambda e: on_price_commit())
        else:
            try:
                children = frame.winfo_children()
                if len(children) >= 2 and isinstance(children[1], tk.Entry):
                    children[1].delete(0, tk.END)
                    children[1].insert(0, format_price(current_price))
            except Exception:
                pass
        frame.place(x=x, y=y, width=w, height=h)

    def refresh_all_qty_frames():
        # Silinen item'ların frame'lerini temizle
        existing_ids = set(product_tree.get_children())
        for dct in (qty_frames, price_frames):
            for iid in list(dct.keys()):
                if iid not in existing_ids:
                    try:
                        if dct[iid].winfo_exists():
                            dct[iid].destroy()
                    except Exception:
                        pass
                    del dct[iid]
        # Her görünür satır için frame üret/güncelle
        for iid in product_tree.get_children():
            build_qty_frame(iid)
            build_price_frame(iid)

    # Scroll ve yeniden boyutlandıkça konumları güncelle
    def on_tree_configure(event):
        refresh_all_qty_frames()
    product_tree.bind('<Configure>', on_tree_configure)
    product_tree.bind('<MouseWheel>', lambda e: (product_tree.after_idle(refresh_all_qty_frames)))
    # İlk yüklemede çerçeveleri yerleştir
    product_tree.after(120, refresh_all_qty_frames)


    # Seçili satır miktarını +/- ile değiştir
    def adjust_selected_qty(delta):
        sel = product_tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = list(product_tree.item(item, "values"))
        try:
            qty = float(vals[4])
        except Exception:
            qty = 0.0
        pname = vals[2]
        r = None
        try:
            r = product_svc.get_price_stock_by_name(cursor, pname)
        except Exception:
            pass
        unit = str(r[2]) if r else "adet"
        step = 0.1 if unit.lower().startswith("kg") else 1.0
        stock = float(r[1]) if r else 999999
        new_qty = qty + delta * step
        if new_qty < 0:
            new_qty = 0
        if new_qty > stock:
            new_qty = stock
        try:
            price = float(str(vals[5]).replace(",", "."))
        except Exception:
            price = 0.0
        qty_text = f"{new_qty:.3f}" if (unit.lower().startswith("kg")) else f"{int(round(new_qty))}"
        vals[4] = qty_text
        vals[6] = f"{price * float(new_qty):.2f}"
        product_tree.item(item, values=vals)
        # Görsel miktar çerçevesini güncelle
        build_qty_frame(item)
        update_totals()

    # Miktar hücresine gelince imleci "yazı" işaretine çevir (düzenlenebilir olduğu anlaşılsın)
    def on_tree_motion(event):
        region = product_tree.identify_region(event.x, event.y)
        if region == "cell" and product_tree.identify_column(event.x) == "#5":
            product_tree.config(cursor="xterm")
        else:
            product_tree.config(cursor="")

    # Çift tıklamada özel editör açma kaldırıldı; sadece odaklanır
    product_tree.bind("<Double-1>", lambda e: None)
    product_tree.bind("<Motion>", on_tree_motion)
    product_tree.bind("+", lambda e: adjust_selected_qty(+1))
    product_tree.bind("-", lambda e: adjust_selected_qty(-1))
    product_tree.bind("<KP_Add>", lambda e: adjust_selected_qty(+1))
    product_tree.bind("<KP_Subtract>", lambda e: adjust_selected_qty(-1))

    product_tree.bind("<Button-1>", on_tree_click)
    product_tree.bind("<<TreeviewSelect>>", lambda e: destroy_qty_editor())
    
    # Kaydırma çubukları (taşma olduğunda görünür)
    x_scroll = ttk.Scrollbar(product_frame, orient="horizontal", command=product_tree.xview)
    y_scroll = ttk.Scrollbar(product_frame, orient="vertical", command=product_tree.yview)
    # Scroll değişince miktar frame'lerini yeniden konumlandır
    def on_tree_yview_changed(first, last):
        y_scroll.set(first, last)
        refresh_all_qty_frames()
    def on_tree_xview_changed(first, last):
        x_scroll.set(first, last)
        refresh_all_qty_frames()
    product_tree.configure(xscrollcommand=on_tree_xview_changed, yscrollcommand=on_tree_yview_changed)
    y_scroll.pack(side="right", fill="y")
    x_scroll.pack(side="bottom", fill="x")
    product_tree.pack(side="left", fill="both", expand=True)
    
    # ORTA PANEL: Ödeme Bilgileri ve Hızlı İşlemler
    center_panel = tk.Frame(middle_section, bg=BG_COLOR, width=420)
    # Orta panelin dikeyde de genişleyebilmesi için expand=True yapıldı
    center_panel.pack(side="left", fill="both", expand=True, padx=(0,8), pady=0)
    center_panel.pack_propagate(False)
    
    # Ödeme bilgileri kutusu
    payment_box = tk.Frame(center_panel, bg=CARD_COLOR)
    payment_box.pack(fill="x", padx=0, pady=(0,8))
    
    # Ödenen / TUTAR / Para Üstü
    info_grid = tk.Frame(payment_box, bg=CARD_COLOR)
    info_grid.pack(fill="x", padx=12, pady=12)
    
    tk.Label(info_grid, text=t('paid'), font=("Segoe UI", 10), bg=CARD_COLOR, fg=TEXT_GRAY).grid(row=0, column=0, sticky="w", pady=2)
    paid_label = tk.Label(info_grid, text="0", font=("Segoe UI", 18, "bold"), bg=CARD_COLOR, fg="white")
    paid_label.grid(row=1, column=0, sticky="w", pady=2)
    
    tk.Label(info_grid, text=t('total').upper() + " :", font=("Segoe UI", 12), bg=CARD_COLOR, fg=TEXT_GRAY).grid(row=0, column=1, sticky="e", padx=20, pady=2)
    total_label = tk.Label(info_grid, text="0.00", font=("Segoe UI", 28, "bold"), bg=CARD_COLOR, fg="#ff3333")
    total_label.grid(row=1, column=1, sticky="e", padx=20, pady=2)
    
    tk.Label(info_grid, text=t('money_on_account'), font=("Segoe UI", 10), bg=CARD_COLOR, fg=TEXT_GRAY).grid(row=0, column=2, sticky="e", pady=2)
    change_label = tk.Label(info_grid, text="0", font=("Segoe UI", 18, "bold"), bg=CARD_COLOR, fg="#00ff00")
    change_label.grid(row=1, column=2, sticky="e", pady=2)
    
    info_grid.grid_columnconfigure(1, weight=1)
    
    # Hızlı tutar butonları
    # Ödeme takibi için değişkenler
    paid_amount = tk.DoubleVar(value=0.0)
    
    def update_payment_display():
        """Ödenen, toplam ve para üstü bilgilerini günceller"""
        try:
            paid_val = paid_amount.get()
            total_val = 0.0
            
            # Sepetteki ürünlerin toplam tutarını hesapla
            for item in product_tree.get_children():
                values = product_tree.item(item)['values']
                # values: [Sil, No, Ürün Adı, Miktar, Birim, Fiyat, Toplam]
                if len(values) >= 7:
                    try:
                        item_total = float(values[6])
                        total_val += item_total
                    except (ValueError, IndexError):
                        pass
            
            # Etiketleri güncelle
            paid_label.config(text=f"{paid_val:.2f}")
            total_label.config(text=f"{total_val:.2f}")
            
            change = paid_val - total_val
            change_label.config(text=f"{change:.2f}")
            
            # Para üstü rengini ayarla
            if change >= 0:
                change_label.config(fg="#00ff00")
            else:
                change_label.config(fg="#ff3333")
                
        except Exception as e:
            print(f"Ödeme güncelleme hatası: {e}")
    
    def add_to_paid(amount):
        """Ödenen tutara miktar ekler veya ayarlar"""
        try:
            current = paid_amount.get()
            if isinstance(amount, str):
                # +5, -5, +10, -10 gibi değerler
                if amount.startswith("+"):
                    new_amount = current + float(amount[1:])
                elif amount.startswith("-"):
                    new_amount = max(0, current - float(amount[1:]))
                else:
                    new_amount = float(amount)
            else:
                # 5, 10, 20, 50, 100, 200 gibi sabit değerler
                new_amount = float(amount)
            
            paid_amount.set(new_amount)
            update_payment_display()
        except Exception as e:
            print(f"Tutar ekleme hatası: {e}")
    
    quick_amount_label = tk.Label(center_panel, text=t('quick_amounts'), font=("Segoe UI", 10),
                                  bg=BG_COLOR, fg=TEXT_GRAY)
    quick_amount_label.pack(anchor="w", padx=4, pady=(4,2))
    
    quick_btns_frame = tk.Frame(center_panel, bg=BG_COLOR)
    quick_btns_frame.pack(fill="x", padx=0, pady=2)
    
    quick_values = [5, 10, 20, 50, 100, 200, "+5", "-5", "+10", "-10"]
    for val in quick_values:
        btn_text = str(val)
        btn = tk.Button(quick_btns_frame, text=btn_text, font=("Segoe UI", 10, "bold"),
                       bg="#007bff", fg="white", relief="flat", padx=0, pady=8,
                       cursor="hand2", borderwidth=0, activebackground="#0056b3",
                       command=lambda v=val: add_to_paid(v))
        btn.pack(side="left", fill="x", expand=True, padx=2)
    
    # Ödeme yöntemi butonları
    payment_methods_frame = tk.Frame(center_panel, bg=BG_COLOR)
    payment_methods_frame.pack(fill="x", padx=0, pady=8)
    
    payment_var = tk.StringVar(value="NAKİT")
    
    def on_nakit_click():
        payment_var.set("NAKİT")
        complete_sale()

    nakit_btn = tk.Button(payment_methods_frame, text="💵 " + t('cash_register') + "\n(F8)",
                         font=("Segoe UI", 10, "bold"), bg="#28a745", fg="white",
                         relief="flat", padx=0, pady=14, cursor="hand2", borderwidth=0,
                         activebackground="#218838", command=on_nakit_click)
    nakit_btn.pack(side="left", fill="x", expand=True, padx=2)
    
    pos_btn = tk.Button(payment_methods_frame, text="💳 " + t('pos_payment') + "\n(F9)",
                       font=("Segoe UI", 10, "bold"), bg="#17a2b8", fg="white",
                       relief="flat", padx=0, pady=14, cursor="hand2", borderwidth=0,
                       activebackground="#138496", command=lambda: payment_var.set("POS"))
    pos_btn.pack(side="left", fill="x", expand=True, padx=2)
    
    open_acc_btn = tk.Button(payment_methods_frame, text="📋 " + t('open_account') + "\n(F10)",
                            font=("Segoe UI", 10, "bold"), bg="#fd7e14", fg="white",
                            relief="flat", padx=0, pady=14, cursor="hand2", borderwidth=0,
                            activebackground="#e96d0b", command=lambda: payment_var.set("AÇIK HESAP"))
    open_acc_btn.pack(side="left", fill="x", expand=True, padx=2)
    
    fragmented_btn = tk.Button(payment_methods_frame, text="🔀 " + t('fragmented'),
                              font=("Segoe UI", 10, "bold"), bg="#007bff", fg="white",
                              relief="flat", padx=0, pady=14, cursor="hand2", borderwidth=0,
                              activebackground="#0056b3", command=lambda: payment_var.set("PARÇALI"))
    fragmented_btn.pack(side="left", fill="x", expand=True, padx=2)
    
    # HIZLI ÜRÜNLER: Ödeme butonlarının altında (orta panelde)
    quick_panel = tk.Frame(center_panel, bg=BG_COLOR)
    quick_panel.pack(fill="both", expand=True, padx=0, pady=(8,0))
    
    # Liste kodları ve aktif liste
    LISTS = [
        ("main",  t('main_list')),
        ("list_1", t('list_1')),
        ("list_2", t('list_2')),
        ("list_3", t('list_3')),
        ("list_4", t('list_4')),
    ]
    active_list_code = tk.StringVar(value="main")

    # DB yardımcıları
    def db_quick_list(list_code: str):
        try:
            cursor.execute("SELECT id, list_code, name, price, sort_order FROM quick_products WHERE list_code=? ORDER BY sort_order, id", (list_code,))
            return cursor.fetchall()
        except Exception:
            return []

    def db_quick_get(pid: int):
        cursor.execute("SELECT id, list_code, name, price, sort_order FROM quick_products WHERE id=?", (pid,))
        return cursor.fetchone()

    def db_quick_insert(list_code: str, name: str, price: float):
        cursor.execute("INSERT INTO quick_products(list_code, name, price, sort_order) VALUES(?,?,?,?)", (list_code, name, price, 0))
        conn.commit()
        return cursor.lastrowid

    def db_quick_update(pid: int, list_code: str, name: str, price: float):
        cursor.execute("UPDATE quick_products SET list_code=?, name=?, price=? WHERE id=?", (list_code, name, price, pid))
        conn.commit()

    def db_quick_delete(pid: int):
        cursor.execute("DELETE FROM quick_products WHERE id=?", (pid,))
        conn.commit()
    
    def db_get_top_products(limit=10):
        """En çok satılan ürünleri getir"""
        try:
            cursor.execute("""
                SELECT product_name, SUM(quantity) as total_qty, 
                       (SELECT COALESCE(sale_price, price) FROM products WHERE name=sales.product_name LIMIT 1) as price
                FROM sales 
                WHERE (canceled IS NULL OR canceled=0)
                GROUP BY product_name 
                ORDER BY total_qty DESC 
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()
        except Exception:
            return []
    
    def db_get_all_products():
        """Tüm ürünleri getir (ürün ekleme için)"""
        try:
            cursor.execute("SELECT name, COALESCE(sale_price, price) FROM products ORDER BY name")
            return cursor.fetchall()
        except Exception:
            return []

    # Başlık ve sekmeler - aynı satırda yan yana
    header_row = tk.Frame(quick_panel, bg=BG_COLOR)
    header_row.pack(fill="x", padx=4, pady=(0,4))

    tk.Label(header_row, text=t('quick_products'), font=("Segoe UI", 10, "bold"),
             bg=BG_COLOR, fg="white").pack(side="left", padx=(4,8))
    
    def change_list(code: str):
        active_list_code.set(code)
        reload_quick_products()

    for code, title in LISTS:
        btn = tk.Button(header_row, text=title, font=("Segoe UI", 8),
                        bg="#6c757d", fg="white", relief="flat", padx=8, pady=3,
                        cursor="hand2", borderwidth=0, activebackground="#5a6268",
                        command=lambda c=code: change_list(c))
        btn.pack(side="left", padx=1)
    
    # Scrollable container için Canvas + Scrollbar
    scroll_container = tk.Frame(quick_panel, bg=BG_COLOR)
    scroll_container.pack(fill="both", expand=True, padx=0, pady=0)
    
    # Canvas
    canvas = tk.Canvas(scroll_container, bg=BG_COLOR, highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)
    
    # İnce scrollbar
    scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview, width=8)
    scrollbar.pack(side="right", fill="y")
    
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Grid container canvas içinde
    quick_products_grid = tk.Frame(canvas, bg=BG_COLOR)
    canvas_window = canvas.create_window((0, 0), window=quick_products_grid, anchor="nw")
    
    # Canvas scroll bölgesini güncelle
    def update_scroll_region(event=None):
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
    
    quick_products_grid.bind("<Configure>", update_scroll_region)
    
    # Canvas genişliğini ayarla
    def resize_canvas(event=None):
        canvas.update_idletasks()
        canvas_width = canvas.winfo_width()
        canvas.itemconfig(canvas_window, width=canvas_width)
    
    canvas.bind("<Configure>", resize_canvas)
    
    # Mouse wheel scroll desteği - Canvas geçerliyken
    def on_mousewheel(event):
        try:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass
    
    canvas.bind("<MouseWheel>", on_mousewheel)
    
    # Not: Hızlı ürünler artık veritabanından okunuyor (quick_products)
    
    def quick_product_click(product_name):
        """Hızlı ürün kartına tıklandığında ürünü sepete ekler"""
        try:
            # İleride add_product_to_cart fonksiyonu tanımlanacak
            # Şimdilik ürün adını yazdırıyoruz
            add_product_to_cart(product_name, 1)
        except Exception as e:
            messagebox.showerror("Hata", f"Ürün eklenirken hata: {e}")
    
    # Kartları ve meta bilgilerini tut
    quick_product_cards = []
    quick_card_meta: dict[int, dict] = {}
    
    # Hızlı ürün ekleme formu
    def show_add_quick_product_dialog(existing: dict | None = None):
        """Hızlı ürün ekleme popup penceresi"""
        dialog = tk.Toplevel(parent)
        dialog.title("Hızlı Ürün Ekle" if existing is None else "Hızlı Ürün Düzenle")
        dialog.geometry("450x280")
        dialog.resizable(False, False)
        dialog.transient(parent)
        dialog.grab_set()
        
        # Ortala
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (dialog.winfo_screenheight() // 2) - (280 // 2)
        dialog.geometry(f"450x280+{x}+{y}")
        
        set_theme(dialog)
        
        # İçerik frame
        content = tk.Frame(dialog, bg=BG_COLOR)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Başlık
        tk.Label(content, text=("➕ Yeni Hızlı Ürün Ekle" if existing is None else "✏️ Hızlı Ürün Düzenle"), font=("Segoe UI", 14, "bold"),
                 bg=BG_COLOR, fg="white").pack(pady=(0,15))
        
        # Liste seçimi
        list_frame = tk.Frame(content, bg=BG_COLOR)
        list_frame.pack(fill="x", pady=(0,10))
        tk.Label(list_frame, text="Liste:", font=("Segoe UI", 10),
                 bg=BG_COLOR, fg=TEXT_GRAY).pack(side="left", padx=(0,10))

        list_var = tk.StringVar(value="main")
        list_combo = ttk.Combobox(list_frame, textvariable=list_var,
                                  values=[code for code, _ in LISTS],
                                  state="readonly", width=25, font=("Segoe UI", 10))
        list_combo.pack(side="left", fill="x", expand=True)
        
        # Ürün seçimi - arama yapılabilir
        name_frame = tk.Frame(content, bg=BG_COLOR)
        name_frame.pack(fill="x", pady=(0,10))
        tk.Label(name_frame, text="Ürün Seç:", font=("Segoe UI", 10),
                 bg=BG_COLOR, fg=TEXT_GRAY).pack(side="left", padx=(0,10))

        # Ürün listesini çek
        all_products = db_get_all_products()
        product_names = [p[0] for p in all_products]
        product_prices = {p[0]: p[1] for p in all_products}
        
        name_var = tk.StringVar()
        name_combo = ttk.Combobox(name_frame, textvariable=name_var,
                                  values=product_names,
                                  font=("Segoe UI", 10))
        name_combo.pack(side="left", fill="x", expand=True)
        name_combo.focus()
        
        # Arama özelliği - sadece filtrele
        def on_keyup(event):
            # Özel tuşları atla
            if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab', 'Escape'):
                return
            
            # Yazılan metin
            typed = name_var.get().lower()
            
            if typed == '':
                # Boşsa tüm listeyi göster
                name_combo['values'] = product_names
            else:
                # Filtrelenmiş liste
                filtered = [p for p in product_names if typed in p.lower()]
                name_combo['values'] = filtered
        
        name_combo.bind('<KeyRelease>', on_keyup)
        
        def on_product_select(event):
            selected = name_var.get()
            if selected and selected in product_prices:
                # Otomatik fiyat doldur
                price_entry.delete(0, tk.END)
                price_entry.insert(0, f"{product_prices[selected]:.2f}")
                # Listeyi sıfırla
                name_combo['values'] = product_names
        
        name_combo.bind("<<ComboboxSelected>>", on_product_select)
        
        # Fiyat
        price_frame = tk.Frame(content, bg=BG_COLOR)
        price_frame.pack(fill="x", pady=(0,15))
        tk.Label(price_frame, text="Fiyat (₺):", font=("Segoe UI", 10),
                bg=BG_COLOR, fg=TEXT_GRAY).pack(side="left", padx=(0,10))
        
        price_entry = ttk.Entry(price_frame, font=("Segoe UI", 10), width=15)
        price_entry.pack(side="left")
        
        # Butonlar
        btn_frame = tk.Frame(content, bg=BG_COLOR)
        btn_frame.pack(fill="x", pady=(10,0))
        
        if existing is not None:
            # Prefill (düzenleme modunda)
            try:
                name_var.set(existing.get('name',''))
                price_entry.insert(0, f"{existing.get('price',0):.2f}")
                list_var.set(existing.get('list_code','main'))
            except Exception:
                pass

        def save_quick_product():
            """Hızlı ürünü kaydet"""
            name = name_var.get().strip()
            price_str = price_entry.get().strip()
            
            if not name:
                messagebox.showwarning("Uyarı", "Lütfen ürün seçin!", parent=dialog)
                return
            
            # Ürünün listede olup olmadığını kontrol et (düzenleme modunda esnek)
            if existing is None and name not in product_names:
                messagebox.showwarning("Uyarı", "Lütfen listeden geçerli bir ürün seçin!", parent=dialog)
                return
            
            if not price_str:
                messagebox.showwarning("Uyarı", "Lütfen fiyat girin!", parent=dialog)
                return
            
            try:
                price = float(price_str.replace(",", "."))
            except ValueError:
                messagebox.showwarning("Uyarı", "Geçerli bir fiyat girin!", parent=dialog)
                return
            
            list_code = list_var.get()

            if existing is None:
                db_quick_insert(list_code, name, price)
                msg = f"'{name}' eklendi."
            else:
                db_quick_update(existing['id'], list_code, name, price)
                msg = f"'{name}' güncellendi."

            reload_quick_products()
            messagebox.showinfo("Başarılı", msg, parent=dialog)
            dialog.destroy()
        
        save_btn = tk.Button(btn_frame, text="💾 Kaydet", font=("Segoe UI", 10, "bold"),
                            bg="#28a745", fg="white", relief="flat", padx=20, pady=8,
                            cursor="hand2", command=save_quick_product)
        save_btn.pack(side="right", padx=(5,0))
        
        cancel_btn = tk.Button(btn_frame, text="❌ İptal", font=("Segoe UI", 10),
                              bg="#6c757d", fg="white", relief="flat", padx=20, pady=8,
                              cursor="hand2", command=dialog.destroy)
        cancel_btn.pack(side="right")
        
        # Enter tuşu ile kaydet
        dialog.bind("<Return>", lambda e: save_quick_product())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
    
    def make_quick_card(pname, pprice, is_add_button=False, pid: int | None = None, list_code: str | None = None):
        """Her kart için closure oluşturan yardımcı fonksiyon"""
        card = tk.Frame(quick_products_grid, bg="#343a40" if not is_add_button else "#28a745",
                       relief="solid", bd=1, cursor="hand2", highlightthickness=0)
        
        if is_add_button:
            # "+" ekleme butonu - kompakt
            def on_add_click(e):
                show_add_quick_product_dialog()
            
            card.bind("<Button-1>", on_add_click)
            
            icon_label = tk.Label(card, text="➕", font=("Segoe UI", 16, "bold"),
                                 bg="#28a745", fg="white", cursor="hand2")
            icon_label.place(relx=0.5, rely=0.5, anchor="center")
            icon_label.bind("<Button-1>", on_add_click)
            
            return card
        else:
            # Normal ürün kartı - daha kompakt
            def on_click(e):
                quick_product_click(pname)
            
            card.bind("<Button-1>", on_click)

            name_label = tk.Label(card, text=pname, font=("Segoe UI", 7, "bold"),
                                  bg="#343a40", fg="white", cursor="hand2",
                                  wraplength=100, justify="center", anchor="center")
            name_label.place(relx=0.5, rely=0.35, anchor="center")
            name_label.bind("<Button-1>", on_click)

            price_label = tk.Label(card, text=pprice, font=("Segoe UI", 9, "bold"),
                                   bg="#343a40", fg="#ffc107", cursor="hand2", anchor="center")
            price_label.place(relx=0.5, rely=0.70, anchor="center")
            price_label.bind("<Button-1>", on_click)

            # Sağ tık menüsü (Düzenle / Sil)
            if pid is not None:
                def show_ctx(event):
                    menu = None
                    try:
                        menu = tk.Menu(card, tearoff=0)
                        menu.add_command(label="✏️ Düzenle", command=lambda: show_add_quick_product_dialog({
                            'id': pid, 'list_code': list_code or 'main', 'name': pname, 'price': float(str(pprice).replace('₺','').strip())
                        }))
                        def do_delete():
                            if messagebox.askyesno("Sil", f"'{pname}' silinsin mi?"):
                                db_quick_delete(pid); reload_quick_products()
                        menu.add_command(label="🗑 Sil", command=do_delete)
                        menu.tk_popup(event.x_root, event.y_root)
                    finally:
                        if menu is not None:
                            try:
                                menu.grab_release()
                            except Exception:
                                pass
                card.bind("<Button-3>", show_ctx)

            return card
    
    def reload_quick_products():
        # Temizle mevcut kartlar
        for c in quick_product_cards:
            try:
                c.destroy()
            except Exception:
                pass
        quick_product_cards.clear(); quick_card_meta.clear()

        current_list = active_list_code.get()
        
        # ANA sekmesi için en çok satılan ürünleri göster
        if current_list == 'main':
            # Önce veritabanından kayıtlı hızlı ürünleri kontrol et
            rows = db_quick_list('main')
            
            # Eğer yoksa, en çok satılan ürünlerden otomatik ekle
            if not rows:
                top_products = db_get_top_products(limit=10)
                if top_products:
                    try:
                        for product_name, total_qty, price in top_products:
                            if price is not None:
                                db_quick_insert('main', product_name, price)
                        rows = db_quick_list('main')
                    except Exception as e:
                        pass
        else:
            # Diğer listeler için normal yükleme
            rows = db_quick_list(current_list)

        for pid, list_code_val, name, price, sort_order in rows:
            card = make_quick_card(name, f"₺ {price:g}", False, pid=pid, list_code=list_code_val)
            quick_product_cards.append(card)
            quick_card_meta[id(card)] = {'id': pid, 'name': name, 'price': price, 'list_code': list_code_val}

        # Son olarak "+" butonu
        quick_product_cards.append(make_quick_card("", "", is_add_button=True))
        relayout_quick_products()

    def relayout_quick_products(event=None):
        """Dinamik grid yerleşimi - genişliğe göre responsive"""
        try:
            quick_products_grid.update_idletasks()
            width = quick_products_grid.winfo_width()
            if width <= 1:
                width = 420
        except Exception:
            width = 420
        
        # Responsive sütun sayısı (daha kompakt için daha fazla sütun)
        if width >= 360:
            cols = 3
            card_h = 65  # daha küçük
        elif width >= 240:
            cols = 2
            card_h = 60
        else:
            cols = 1
            card_h = 55
        
        # Tüm kartları grid'den kaldır
        for card in quick_product_cards:
            card.grid_forget()

        # Grid sütunlarını yapılandır
        for i in range(4):
            quick_products_grid.grid_columnconfigure(i, weight=0, minsize=0)
        for i in range(cols):
            quick_products_grid.grid_columnconfigure(i, weight=1, uniform="qp")

        # Tüm kartları yerleştir (hiçbirini gizleme)
        row = col = 0
        for card in quick_product_cards:
            card.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")  # padding küçültüldü
            col += 1
            if col >= cols:
                col = 0
                row += 1
        
        # Satır yüksekliklerini ayarla
        for r in range(row + 1):
            quick_products_grid.grid_rowconfigure(r, weight=0, minsize=card_h)
        
        # Canvas scroll bölgesini güncelle
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    # İlk yükleme
    quick_products_grid.after(100, reload_quick_products)
    
    # Boyut değişimlerinde otomatik yeniden yerleşim
    quick_products_grid.bind("<Configure>", relayout_quick_products)
    
    # Global referans: menü toggle'dan tetiklemek için
    parent._relayout_quick_products = relayout_quick_products
    
    # === ALT BÖLÜM: Müşteri Bilgileri ve Satış Yap ===
    bottom_section = tk.Frame(content_container, bg=CARD_COLOR)
    bottom_section.pack(fill="x", padx=12, pady=(4,8))
    
    bottom_left = tk.Frame(bottom_section, bg=CARD_COLOR)
    bottom_left.pack(side="left", fill="both", expand=True, padx=12, pady=12)
    
    # Müşteri İsmi
    tk.Label(bottom_left, text="👤 " + t('customer_name'), font=("Segoe UI", 9),
             bg=CARD_COLOR, fg=TEXT_GRAY).grid(row=0, column=0, sticky="w", pady=2)
    customer_entry = ttk.Entry(bottom_left, font=("Segoe UI", 10), width=25)
    customer_entry.grid(row=1, column=0, sticky="ew", pady=2, padx=(0,8))
    
    # Otomatik cari arama (yazarken açılan öneri penceresi)
    customer_cache_rows = None  # [(id, name, phone, balance), ...]
    customer_popup_win = None   # Toplevel
    customer_popup_list = None  # Listbox
    current_results = []        # filtrelenmiş satırlar

    def hide_customer_popup():
        nonlocal customer_popup_win, customer_popup_list, current_results
        if customer_popup_win is not None:
            try:
                customer_popup_win.destroy()
            except Exception:
                pass
            customer_popup_win = None
            customer_popup_list = None
            current_results = []

    def select_customer(index: int):
        nonlocal current_results
        if index < 0 or index >= len(current_results):
            hide_customer_popup(); return
        _cid, name, phone, _bal = current_results[index]
        customer_entry.delete(0, tk.END); customer_entry.insert(0, str(name))
        phone_entry.delete(0, tk.END); phone_entry.insert(0, str(phone or ""))
        hide_customer_popup()

    def show_customer_popup():
        nonlocal customer_popup_win, customer_popup_list, current_results
        if not current_results:
            hide_customer_popup(); return
        # pencereyi oluştur/konumlandır
        win = customer_popup_win
        lb = customer_popup_list
        if win is None:
            win = tk.Toplevel(parent)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            set_theme(win)
            lb = tk.Listbox(win, height=6)
            lb.pack(fill="both", expand=True)
            def on_double(_=None):
                sel = lb.curselection()
                if sel:
                    select_customer(int(sel[0]))
            lb.bind("<Double-Button-1>", on_double)
            lb.bind("<Return>", on_double)
            customer_popup_win = win
            customer_popup_list = lb
        # konum ve içerik
        try:
            x = customer_entry.winfo_rootx()
            y = customer_entry.winfo_rooty() + customer_entry.winfo_height()
            w = max(260, customer_entry.winfo_width())
            win.geometry(f"{w}x150+{x}+{y}")
        except Exception:
            pass
        if lb is None:
            return
        lb.delete(0, tk.END)
        for _cid, name, phone, bal in current_results[:50]:
            lb.insert(tk.END, f"{name} | {phone or ''}")
        lb.selection_clear(0, tk.END)
        lb.selection_set(0)
        lb.activate(0)

    def on_customer_typed(e=None):
        from services import cari_service as cs
        q = customer_entry.get().strip().lower()
        nonlocal customer_cache_rows, current_results
        if customer_cache_rows is None:
            try:
                customer_cache_rows = cs.list_all(cursor)
            except Exception:
                customer_cache_rows = []
        if not q:
            hide_customer_popup(); return
        res = []
        for cid, name, phone, address, balance, cari_type in customer_cache_rows:
            if q in str(name).lower() or q in str(phone or "").lower():
                res.append((cid, name, phone, balance))
        current_results = res
        show_customer_popup()

    def on_customer_keydown(e):
        nonlocal customer_popup_list
        if customer_popup_list is None:
            return
        lb = customer_popup_list
        if e.keysym in ("Down",):
            try:
                cur = lb.curselection()[0] if lb.curselection() else -1
                nxt = min(cur + 1, lb.size()-1)
                lb.selection_clear(0, tk.END); lb.selection_set(nxt); lb.activate(nxt)
            except Exception:
                pass
            return "break"
        if e.keysym in ("Up",):
            try:
                cur = lb.curselection()[0] if lb.curselection() else 0
                nxt = max(cur - 1, 0)
                lb.selection_clear(0, tk.END); lb.selection_set(nxt); lb.activate(nxt)
            except Exception:
                pass
            return "break"
        if e.keysym in ("Return",):
            try:
                cur = customer_popup_list.curselection()
                if cur:
                    select_customer(int(cur[0]))
                    return "break"
            except Exception:
                pass
        if e.keysym in ("Escape",):
            hide_customer_popup(); return "break"

    customer_entry.bind("<KeyRelease>", lambda e: on_customer_typed())
    customer_entry.bind("<KeyPress>", on_customer_keydown)
    customer_entry.bind("<FocusOut>", lambda e: parent.after(150, hide_customer_popup))
    
    # Satışa dair notlar
    tk.Label(bottom_left, text="📝 " + t('sales_note'), font=("Segoe UI", 9),
             bg=CARD_COLOR, fg=TEXT_GRAY).grid(row=0, column=1, sticky="w", pady=2)
    notes_entry = ttk.Entry(bottom_left, font=("Segoe UI", 10), width=30)
    notes_entry.grid(row=1, column=1, sticky="ew", pady=2, padx=(0,8))
    
    # Telefon (SMS için)
    tk.Label(bottom_left, text="📱 " + t('customer_phone'), font=("Segoe UI", 9),
             bg=CARD_COLOR, fg=TEXT_GRAY).grid(row=0, column=2, sticky="w", pady=2)
    phone_entry = ttk.Entry(bottom_left, font=("Segoe UI", 10), width=20)
    phone_entry.grid(row=1, column=2, sticky="ew", pady=2)
    
    bottom_left.grid_columnconfigure(0, weight=1)
    bottom_left.grid_columnconfigure(1, weight=1)
    bottom_left.grid_columnconfigure(2, weight=1)
    
    # Ödeme seçici ve limit bilgisi
    payment_selector = tk.Frame(bottom_left, bg=CARD_COLOR)
    payment_selector.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8,4))
    
    tk.Checkbutton(payment_selector, text=t('sms_receipt'), font=("Segoe UI", 9),
                  bg=CARD_COLOR, fg=TEXT_GRAY, selectcolor="#1a1a20").pack(side="left", padx=(0,12))
    
    ttk.Combobox(payment_selector, values=[t('cash_register'), t('credit_card'), t('bank_transfer')], 
                state="readonly", width=15, font=("Segoe UI", 9)).pack(side="left")
    
    # Limit bilgisi
    tk.Label(bottom_left, text=t('limit_info'), font=("Segoe UI", 8),
             bg=CARD_COLOR, fg=TEXT_GRAY).grid(row=2, column=2, sticky="e", pady=(8,4))
    
    # SMS notu
    tk.Label(bottom_left, text=t('sms_note'), font=("Segoe UI", 8, "italic"),
             bg=CARD_COLOR, fg="#666").grid(row=3, column=0, columnspan=3, sticky="w", pady=(4,0))
    
    # SATIŞ YAP butonu (sağ)
    complete_sale_btn = tk.Button(bottom_section, text="✅ " + t('complete_sale_btn'),
                                  font=("Segoe UI", 16, "bold"), bg="#28a745", fg="white",
                                  relief="flat", padx=40, pady=24, cursor="hand2",
                                  borderwidth=0, activebackground="#218838")
    complete_sale_btn.pack(side="right", padx=12, pady=12)
    
    # === FONKSİYONLAR ===
    def add_product_to_cart(pname, qty=1):
        """Ürünü sepete ekle"""
        r = product_svc.get_price_stock_by_name(cursor, pname)
        if not r:
            return
        price, stock, unit = float(r[0]), float(r[1]), str(r[2])
        if qty > stock:
            messagebox.showerror(t('error'), t('insufficient_stock').format(stock=stock))
            return
        
        # Tabloya ekle
        seq = len(product_tree.get_children()) + 1
        tags = ('evenrow',) if seq % 2 == 0 else ('oddrow',)
        # Miktarı birime göre uygun formatta yaz
        qty_text = f"{qty:.3f}" if unit.lower().startswith("kg") else f"{int(round(qty))}"
        # Barkod (varsa)
        try:
            cursor.execute("SELECT COALESCE(barcode,'') FROM products WHERE name=? LIMIT 1", (pname,))
            rbc = cursor.fetchone()
            barcode_val = str(rbc[0]) if rbc and rbc[0] is not None else ''
        except Exception:
            barcode_val = ''
        # Kategori adı (varsa)
        try:
            from repositories import category_repository
            cat_name = category_repository.get_name_by_product_name(cursor, pname) or "-"
        except Exception:
            cat_name = "-"
        iid = product_tree.insert("", "end", values=("❌", barcode_val, pname, cat_name, qty_text, f"{price:.2f}", f"{price*float(qty):.2f}"), tags=tags)
        # Satır eklendikten sonra miktar/fiyat çerçevesini oluştur
        product_tree.after(90, lambda: (build_qty_frame(iid), build_price_frame(iid)))
        update_totals()
    
    def update_totals():
        """Toplamları güncelle"""
        total = 0.0
        count = 0
        for item in product_tree.get_children():
            vals = product_tree.item(item)["values"]
            if len(vals) >= 7:
                try:
                    total += float(str(vals[6]).replace(",", "."))
                except Exception:
                    pass
                count += 1
        
        total_label.config(text=f"{total:.2f}")
        # Ürün sayısını güncelle
        for widget in left_panel.winfo_children():
            if isinstance(widget, tk.Frame):
                for label in widget.winfo_children():
                    if isinstance(label, tk.Label) and t('products') in label.cget("text"):
                        label.config(text=t('products') + f" 🗂️ {count}")
        
        # Ödeme bilgilerini güncelle
        update_payment_display()
    
    def barcode_scan(event):
        """Barkod okutulduğunda veya Enter basıldığında"""
        barcode = barcode_entry.get().strip()
        if not barcode or "Okutunuz" in barcode:
            return
        
        result = product_svc.get_by_barcode(cursor, barcode)
        if result:
            pid, pname, price, stock, unit = result
            add_product_to_cart(pname, 1)
            barcode_entry.delete(0, tk.END)
            barcode_entry.insert(0, "Ürün Barkodunu Okutunuz...")
            barcode_entry.config(fg="#999999")
        else:
            # Barkod bulunamazsa Ara penceresini aç
            show_product_list()
    
    def barcode_focus_in(event):
        if "Okutunuz" in barcode_entry.get():
            barcode_entry.delete(0, tk.END)
            barcode_entry.config(fg="#333333")
    
    def barcode_focus_out(event):
        if not barcode_entry.get().strip():
            barcode_entry.insert(0, "Ürün Barkodunu Okutunuz...")
            barcode_entry.config(fg="#999999")
    
    def show_sale_options_dialog(fis_id, sales_list, customer_name, total_amount, on_confirm):
        dialog = tk.Toplevel()
        dialog.title(t('print_receipt'))
        set_theme(dialog)
        center_window(dialog, 500, 450)
        dialog.resizable(False, False)
        try:
            dialog.transient(parent.winfo_toplevel())
            dialog.grab_set()
        except:
            pass
        
        # İçerik
        content = tk.Frame(dialog, bg=BG_COLOR)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        def show_result_ui(message, is_error=False):
            for w in content.winfo_children(): w.destroy()
            
            icon = "❌" if is_error else "✅"
            color = "#dc3545" if is_error else "#28a745"
            
            tk.Label(content, text=icon, font=("Segoe UI", 48), bg=BG_COLOR, fg=color).pack()
            tk.Label(content, text=message, font=("Segoe UI", 11), 
                     bg=BG_COLOR, fg="white", wraplength=450).pack(pady=(20, 20))
            
            tk.Button(content, text="Tamam", font=("Segoe UI", 10, "bold"), 
                      bg="#6c757d", fg="white", relief="flat", padx=30, pady=10, cursor="hand2",
                      activebackground="#5a6268", activeforeground="white", borderwidth=0,
                      command=dialog.destroy).pack()

        def process_action(mode):
            # Butonları devre dışı bırak
            try:
                b1.config(state="disabled")
                b2.config(state="disabled")
                b3.config(state="disabled")
                b4.config(state="disabled")
            except:
                pass
            
            # İşlemi gerçekleştir
            try:
                result_msg = on_confirm(mode)
                show_result_ui(result_msg, is_error=False)
            except Exception as e:
                show_result_ui(f"Hata:\n{e}", is_error=True)

        # İkon ve Başlık
        tk.Label(content, text="❓", font=("Segoe UI", 48), bg=BG_COLOR, fg="#17a2b8").pack()
        tk.Label(content, text=t('confirm'), font=("Segoe UI", 16, "bold"), 
                 bg=BG_COLOR, fg="white").pack(pady=(10, 5))
        
        # Bilgi
        info_frame = tk.Frame(content, bg=BG_COLOR)
        info_frame.pack(pady=(0, 20))
        
        tk.Label(info_frame, text=f"{t('total')}: {total_amount:.2f} ₺", font=("Segoe UI", 12, "bold"), 
                 bg=BG_COLOR, fg="#ffc107").pack(pady=5)
        tk.Label(info_frame, text=f"{t('customer')}: {customer_name}", font=("Segoe UI", 10), 
                 bg=BG_COLOR, fg=TEXT_GRAY).pack()
        
        # Butonlar Container
        btn_container = tk.Frame(content, bg=BG_COLOR)
        btn_container.pack(fill="x", pady=10)

        # Üst Sıra (3 Buton)
        top_row = tk.Frame(btn_container, bg=BG_COLOR)
        top_row.pack(fill="x", pady=(0, 10))
        
        # Termal
        b1 = tk.Button(top_row, text=f"🖨 {t('thermal_printer')}", font=("Segoe UI", 10, "bold"), 
                  bg="#007bff", fg="white", relief="flat", padx=10, pady=12, cursor="hand2",
                  activebackground="#0056b3", activeforeground="white", borderwidth=0,
                  command=lambda: process_action('thermal'))
        b1.pack(side="left", fill="x", expand=True, padx=5)
        
        # PDF
        b2 = tk.Button(top_row, text="📄 PDF", font=("Segoe UI", 10, "bold"), 
                  bg="#17a2b8", fg="white", relief="flat", padx=10, pady=12, cursor="hand2",
                  activebackground="#138496", activeforeground="white", borderwidth=0,
                  command=lambda: process_action('pdf'))
        b2.pack(side="left", fill="x", expand=True, padx=5)
        
        # Kaydet (Yazdırma)
        b3 = tk.Button(top_row, text=f"💾 {t('no_print')}", font=("Segoe UI", 10, "bold"), 
                  bg="#6c757d", fg="white", relief="flat", padx=10, pady=12, cursor="hand2",
                  activebackground="#5a6268", activeforeground="white", borderwidth=0,
                  command=lambda: process_action('none'))
        b3.pack(side="left", fill="x", expand=True, padx=5)

        # Alt Sıra (İptal Butonu) - Tam genişlik
        b4 = tk.Button(btn_container, text=f"❌ {t('cancel_sale')}", font=("Segoe UI", 10, "bold"), 
                  bg="#dc3545", fg="white", relief="flat", padx=10, pady=12, cursor="hand2",
                  activebackground="#c82333", activeforeground="white", borderwidth=0,
                  command=dialog.destroy)
        b4.pack(fill="x", padx=5)
        
        dialog.wait_window()

    def complete_sale():
        """Satışı başlat ve onay iste"""
        items = product_tree.get_children()
        if not items:
            messagebox.showwarning(t('warning'), t('cart_empty'))
            return
        
        customer = customer_entry.get().strip() or t('customer')
        payment_method = payment_var.get()
        
        # Verileri hazırla
        sales_data = []
        total_amount = 0.0
        
        for item in items:
            vals = product_tree.item(item)["values"]
            pname = vals[2]
            def num(v):
                try: return float(str(v).replace(",", "."))
                except: return 0.0
            qty = num(vals[4])
            price = num(vals[5])
            total = num(vals[6])
            sales_data.append({'pname': pname, 'qty': qty, 'price': price, 'total': total})
            total_amount += total
            
        fis_id = f"FIS-{datetime.now().strftime('%Y%m%d')}-{os.urandom(3).hex().upper()}"
        
        def on_confirm_sale(mode):
            # 1. Veritabanı işlemleri
            sales_list_for_print = []
            for d in sales_data:
                product_svc.decrement_stock(conn, cursor, d['pname'], d['qty'])
                sales_svc.insert_sale_line(conn, cursor, fis_id, d['pname'], d['qty'], d['price'], d['total'], payment_method=payment_method.lower())
                sales_list_for_print.append((d['pname'], d['qty'], d['price'], d['total']))
            
            conn.commit()
            
            # 2. UI Temizle
            for item in product_tree.get_children():
                product_tree.delete(item)
            customer_entry.delete(0, tk.END)
            notes_entry.delete(0, tk.END)
            phone_entry.delete(0, tk.END)
            update_totals()
            
            # 3. Yazdırma İşlemleri
            msg = t('receipt_created') + f"\n{t('receipt_no')} {fis_id}"
            
            if mode == 'thermal':
                try:
                    print_thermal_receipt(sales_list_for_print, fis_id=fis_id, customer_name=customer,
                                          kdv_rate=18.0, discount_rate=0.0, vat_included=False,
                                          language_code=CURRENT_LANGUAGE)
                    # PDF yedeği
                    print_receipt(sales_list_for_print, fis_id=fis_id, customer_name=customer,
                                 kdv_rate=18.0, discount_rate=0.0, vat_included=False,
                                 open_after=False, show_message=False, language_code=CURRENT_LANGUAGE)
                    msg += "\n\nFiş termal yazıcıya gönderildi."
                except Exception as e:
                    msg += f"\n\nYazdırma Hatası: {e}"
                    
            elif mode == 'pdf':
                fname = print_receipt(sales_list_for_print, fis_id=fis_id, customer_name=customer,
                                     kdv_rate=18.0, discount_rate=0.0, vat_included=False,
                                     open_after=True, show_message=False, language_code=CURRENT_LANGUAGE)
                if fname:
                    msg += f"\n\nPDF Kaydedildi:\n{fname}"
                else:
                    msg += "\n\nPDF Kaydedilemedi!"
            
            return msg

        show_sale_options_dialog(fis_id, sales_data, customer, total_amount, on_confirm_sale)
    
    # Hızlı ürün butonlarına fonksiyon bağla
    for widget in quick_products_grid.winfo_children():
        if isinstance(widget, tk.Frame):
            for label in widget.winfo_children():
                if isinstance(label, tk.Label) and "₺" not in label.cget("text"):
                    pname = label.cget("text")
                    widget.bind("<Button-1>", lambda e, p=pname: add_product_to_cart(p, 1))
    
    # Event bindings
    barcode_entry.bind("<Return>", barcode_scan)
    barcode_entry.bind("<FocusIn>", barcode_focus_in)
    barcode_entry.bind("<FocusOut>", barcode_focus_out)
    complete_sale_btn.config(command=complete_sale)
    
    # Klavye kısayolları
    def keyboard_shortcuts(event):
        """Klavye kısayollarını yönet"""
        if event.keysym == "F7":
            # F7: Fiyat Gör
            show_price()
        elif event.keysym == "F8":
            # F8: Nakit ödeme
            payment_var.set("NAKİT")
            nakit_btn.config(bg="#1a7c34")
            pos_btn.config(bg="#17a2b8")
            open_acc_btn.config(bg="#fd7e14")
            fragmented_btn.config(bg="#007bff")
        elif event.keysym == "F9":
            # F9: POS ödeme
            payment_var.set("POS")
            nakit_btn.config(bg="#28a745")
            pos_btn.config(bg="#117a8b")
            open_acc_btn.config(bg="#fd7e14")
            fragmented_btn.config(bg="#007bff")
        elif event.keysym == "F10":
            # F10: Açık hesap
            payment_var.set("AÇIK HESAP")
            nakit_btn.config(bg="#28a745")
            pos_btn.config(bg="#17a2b8")
            open_acc_btn.config(bg="#d5620a")
            fragmented_btn.config(bg="#007bff")
    
    main_container.bind_all("<F7>", keyboard_shortcuts)
    main_container.bind_all("<F8>", keyboard_shortcuts)
    main_container.bind_all("<F9>", keyboard_shortcuts)
    main_container.bind_all("<F10>", keyboard_shortcuts)
    
    # İlk odak (Kaldırıldı - Kullanıcı isteği)
    # barcode_entry.focus_set()

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

def show_custom_confirm_dialog(title, message, parent=None):
    """Özel Evet/Hayır onay penceresi"""
    result = {"value": False}
    
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    set_theme(dialog)
    center_window(dialog, 400, 280)
    dialog.resizable(False, False)
    
    try:
        if parent:
            dialog.transient(parent)
        dialog.grab_set()
    except:
        pass
        
    # İçerik
    content = tk.Frame(dialog, bg=BG_COLOR)
    content.pack(fill="both", expand=True, padx=20, pady=20)
    
    # İkon
    tk.Label(content, text="❓", font=("Segoe UI", 48), bg=BG_COLOR, fg="#17a2b8").pack(pady=(10, 10))
    
    # Mesaj
    tk.Label(content, text=message, font=("Segoe UI", 11, "bold"), 
             bg=BG_COLOR, fg="white", wraplength=350).pack(pady=(0, 20))
    
    # Butonlar
    btn_frame = tk.Frame(content, bg=BG_COLOR)
    btn_frame.pack(fill="x", pady=10)
    
    def on_yes():
        result["value"] = True
        dialog.destroy()
        
    def on_no():
        result["value"] = False
        dialog.destroy()
        
    # Evet
    b1 = tk.Button(btn_frame, text=f"✅ {t('yes')}", font=("Segoe UI", 10, "bold"), 
              bg="#28a745", fg="white", relief="flat", padx=20, pady=10, cursor="hand2",
              activebackground="#218838", activeforeground="white", borderwidth=0,
              command=on_yes)
    b1.pack(side="left", fill="x", expand=True, padx=5)
    
    # Hayır
    b2 = tk.Button(btn_frame, text=f"❌ {t('no')}", font=("Segoe UI", 10, "bold"), 
              bg="#dc3545", fg="white", relief="flat", padx=20, pady=10, cursor="hand2",
              activebackground="#c82333", activeforeground="white", borderwidth=0,
              command=on_no)
    b2.pack(side="left", fill="x", expand=True, padx=5)
    
    dialog.wait_window()
    return result["value"]

# ==========================
# Ana Pencere (tek pencere navigasyon)
# ==========================
def open_main_window(role, username):
    main = tk.Toplevel()
    main.title(f"{t('app_title')} - {role.upper()}")
    set_theme(main)
    
    # Çıkış onayı (X tuşu)
    def on_close():
        if show_custom_confirm_dialog(t('exit_title'), t('confirm_exit'), main):
            main.destroy()
            login_window.destroy() # Ana pencereyi de kapat (Uygulamadan çık)
            
    main.protocol("WM_DELETE_WINDOW", on_close)
    
    # Tam ekran yap
    main.state('zoomed')  # Windows için maximize
    main.minsize(1200, 800) # Minimum pencere boyutu
    
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
                open_main_window(role, username)
        
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
    
    # Profil butonu
    def open_profile_window():
        """Profil penceresi: İşletme bilgileri ve şifre değiştirme sekmeli görünümü"""
        prof_win = tk.Toplevel(main)
        prof_win.title(t('profile'))
        set_theme(prof_win)
        center_window(prof_win, 600, 550)
        
        # Üst başlık
        ttk.Label(prof_win, text=f"👤 {t('profile')}", style="Header.TLabel").pack(pady=(16, 12))
        
        # Notebook (Sekmeli)
        notebook = ttk.Notebook(prof_win)
        notebook.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        
        # === TAB 1: İşletme Bilgileri ===
        business_tab = ttk.Frame(notebook, style="Card.TFrame")
        notebook.add(business_tab, text=f"🏢 {t('business_info')}")
        
        biz_frame = ttk.Frame(business_tab, style="Card.TFrame")
        biz_frame.pack(fill="both", expand=True, padx=24, pady=16)
        
        # Mevcut değerleri yükle
        def get_setting(key, default=""):
            cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            r = cursor.fetchone()
            return r[0] if r else default
        
        company_val = get_setting("company_name", "SmartPOS İşletme")
        tax_office_val = get_setting("tax_office", "")
        tax_num_val = get_setting("tax_number", "")
        phone_val = get_setting("company_phone", "")
        addr_val = get_setting("company_address", "")
        footer_val = get_setting("receipt_footer", t('thank_you'))
        
        ttk.Label(biz_frame, text=t('company_name'), style="TLabel").grid(row=0, column=0, sticky="w", pady=8)
        e_company = ttk.Entry(biz_frame, width=40)
        e_company.insert(0, company_val)
        e_company.grid(row=0, column=1, pady=8, padx=(8,0), sticky="ew")
        
        ttk.Label(biz_frame, text=t('tax_office'), style="TLabel").grid(row=1, column=0, sticky="w", pady=8)
        e_tax_office = ttk.Entry(biz_frame, width=40)
        e_tax_office.insert(0, tax_office_val)
        e_tax_office.grid(row=1, column=1, pady=8, padx=(8,0), sticky="ew")
        
        ttk.Label(biz_frame, text=t('tax_number'), style="TLabel").grid(row=2, column=0, sticky="w", pady=8)
        e_tax_num = ttk.Entry(biz_frame, width=40)
        e_tax_num.insert(0, tax_num_val)
        e_tax_num.grid(row=2, column=1, pady=8, padx=(8,0), sticky="ew")
        
        ttk.Label(biz_frame, text=t('phone'), style="TLabel").grid(row=3, column=0, sticky="w", pady=8)
        e_phone = ttk.Entry(biz_frame, width=40)
        e_phone.insert(0, phone_val)
        e_phone.grid(row=3, column=1, pady=8, padx=(8,0), sticky="ew")
        
        ttk.Label(biz_frame, text=t('address'), style="TLabel").grid(row=4, column=0, sticky="w", pady=8)
        e_address = ttk.Entry(biz_frame, width=40)
        e_address.insert(0, addr_val)
        e_address.grid(row=4, column=1, pady=8, padx=(8,0), sticky="ew")
        
        ttk.Label(biz_frame, text=t('receipt_footer'), style="TLabel").grid(row=5, column=0, sticky="w", pady=8)
        e_footer = ttk.Entry(biz_frame, width=40)
        e_footer.insert(0, footer_val)
        e_footer.grid(row=5, column=1, pady=8, padx=(8,0), sticky="ew")
        
        biz_frame.columnconfigure(1, weight=1)
        
        def save_business_info():
            cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('company_name',?)", (e_company.get().strip(),))
            cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('tax_office',?)", (e_tax_office.get().strip(),))
            cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('tax_number',?)", (e_tax_num.get().strip(),))
            cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('company_phone',?)", (e_phone.get().strip(),))
            cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('company_address',?)", (e_address.get().strip(),))
            cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('receipt_footer',?)", (e_footer.get().strip(),))
            conn.commit()
            messagebox.showinfo(t('success'), t('profile_saved'))
        
        btn_save_biz = tk.Button(business_tab, text=f"💾 {t('save')}", command=save_business_info,
                                 bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"),
                                 relief="flat", padx=20, pady=10, cursor="hand2", borderwidth=0,
                                 activebackground="#059669", activeforeground="white")
        btn_save_biz.pack(pady=(6, 16))
        
        # === TAB 2: Şifre Değiştir ===
        pw_tab = ttk.Frame(notebook, style="Card.TFrame")
        notebook.add(pw_tab, text=f"🔒 {t('change_password')}")
        
        pw_frame = ttk.Frame(pw_tab, style="Card.TFrame")
        pw_frame.pack(fill="both", expand=True, padx=24, pady=16)
        
        ttk.Label(pw_frame, text=t('current_password'), style="TLabel").grid(row=0, column=0, sticky="w", pady=8)
        e_curr_pw = ttk.Entry(pw_frame, show="*", width=30)
        e_curr_pw.grid(row=0, column=1, pady=8, padx=(8,0), sticky="ew")
        
        ttk.Label(pw_frame, text=t('new_password2'), style="TLabel").grid(row=1, column=0, sticky="w", pady=8)
        e_new_pw = ttk.Entry(pw_frame, show="*", width=30)
        e_new_pw.grid(row=1, column=1, pady=8, padx=(8,0), sticky="ew")
        
        ttk.Label(pw_frame, text=t('confirm_password'), style="TLabel").grid(row=2, column=0, sticky="w", pady=8)
        e_confirm_pw = ttk.Entry(pw_frame, show="*", width=30)
        e_confirm_pw.grid(row=2, column=1, pady=8, padx=(8,0), sticky="ew")
        
        pw_frame.columnconfigure(1, weight=1)
        
        def change_password():
            curr = e_curr_pw.get().strip()
            new_pw = e_new_pw.get().strip()
            conf_pw = e_confirm_pw.get().strip()
            if not curr or not new_pw or not conf_pw:
                return messagebox.showwarning(t('warning'), t('enter_valid'))
            # Mevcut şifre doğru mu?
            cursor.execute("SELECT password FROM users WHERE username=?", (username,))
            r = cursor.fetchone()
            if not r or r[0] != curr:
                return messagebox.showerror(t('error'), t('wrong_password'))
            if new_pw != conf_pw:
                return messagebox.showerror(t('error'), t('password_mismatch'))
            cursor.execute("UPDATE users SET password=? WHERE username=?", (new_pw, username))
            conn.commit()
            messagebox.showinfo(t('success'), t('password_changed'))
            e_curr_pw.delete(0, tk.END)
            e_new_pw.delete(0, tk.END)
            e_confirm_pw.delete(0, tk.END)
        
        btn_change_pw = tk.Button(pw_tab, text=f"🔑 {t('change_password')}", command=change_password,
                                  bg="#8b5cf6", fg="white", font=("Segoe UI", 10, "bold"),
                                  relief="flat", padx=20, pady=10, cursor="hand2", borderwidth=0,
                                  activebackground="#7c3aed", activeforeground="white")
        btn_change_pw.pack(pady=(6, 16))
    
    btn_profile = tk.Button(top_bar, text=f"👤 {t('profile')}", command=open_profile_window,
                            bg="#8b5cf6", fg="white", font=("Segoe UI", 10),
                            relief="flat", padx=12, pady=6, cursor="hand2", borderwidth=0,
                            activebackground="#7c3aed", activeforeground="white")
    btn_profile.pack(side="right", padx=6)
    
    ttk.Button(top_bar, text=f"🚪 {t('logout')}", command=lambda: logout_action(main)).pack(side="right", padx=6)

    body = ttk.Frame(main); body.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Grid Layout Yapılandırması (Daha stabil görünüm için)
    body.grid_columnconfigure(0, weight=0) # Menü (sabit)
    body.grid_columnconfigure(1, weight=1) # İçerik (esnek)
    body.grid_rowconfigure(0, weight=1)

    # Sol Menü (Scroll'lu)
    menu_container = ttk.Frame(body, style="Card.TFrame", width=280)
    menu_container.grid(row=0, column=0, sticky="ns", padx=(10,6), pady=10)
    menu_container.pack_propagate(False)

    # Sol menü daralt/genişlet durumu
    menu_state = {"collapsed": True}

    # Sabit başlık (ikon + başlık + daralt butonu)
    header_bar = ttk.Frame(menu_container, style="Card.TFrame")
    header_bar.pack(fill="x", padx=0, pady=(12,6))
    header_label = ttk.Label(header_bar, text="📂 " + t('action_menu'), style="Header.TLabel")
    header_label.pack(side="left", padx=(8,0))
    collapse_btn = tk.Button(header_bar, text="◀", bg=CARD_COLOR, fg="white",
                             relief="flat", padx=8, pady=4, cursor="hand2", borderwidth=0)
    collapse_btn.pack(side="right", padx=(0,8))
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
    right_panel = ttk.Frame(body, style="Card.TFrame")
    right_panel.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)

    # Üst menü butonlarını tutalım (ikon ve tam metin için)
    top_buttons = []

    def mbtn(parent, text, cmd):
        b = tk.Button(parent, text=text, bg=CARD_COLOR, fg="white",
                      font=("Segoe UI",10,"bold"), activebackground="#003c66",
                      activeforeground="white", relief="flat", padx=10, pady=10,
                      anchor="w", borderwidth=0, command=cmd)
        b.pack(fill="x", pady=4, padx=14)
        # Tam metni ve ikonunu sakla (ilk boşluğa kadar)
        try:
            icon = text.split(" ")[0]
        except Exception:
            icon = text
        top_buttons.append({"btn": b, "full": text, "icon": icon})
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

    # Menüyü daralt/genişlet
    def apply_menu_collapse():
        collapsed = menu_state["collapsed"]
        if collapsed:
            w = 64
            menu_container.config(width=w)
            body.grid_columnconfigure(0, minsize=w) # Grid sütun genişliğini zorla
            header_label.config(text="📂")
            collapse_btn.config(text="▶")
            # Alt bölümleri kapat
            close_all_sections()
            # Scrollbar'ı gizle (dar alanda yer kaplamasın)
            try:
                menu_scrollbar.pack_forget()
            except Exception:
                pass
            for meta in top_buttons:
                try:
                    meta["btn"].config(text=meta["icon"], anchor="center", padx=0)
                except Exception:
                    pass
        else:
            w = 280
            menu_container.config(width=w)
            body.grid_columnconfigure(0, minsize=w) # Grid sütun genişliğini zorla
            header_label.config(text="📂 " + t('action_menu'))
            collapse_btn.config(text="◀")
            # Scrollbar'ı geri getir
            try:
                menu_scrollbar.pack(side="right", fill="y")
            except Exception:
                pass
            for meta in top_buttons:
                try:
                    meta["btn"].config(text=meta["full"], anchor="w", padx=10)
                except Exception:
                    pass

    def toggle_menu_collapse():
        menu_state["collapsed"] = not menu_state["collapsed"]
        apply_menu_collapse()

    collapse_btn.config(command=toggle_menu_collapse)
    
    # Başlangıçta menü durumunu uygula
    apply_menu_collapse()

    footer = ttk.Frame(main, style="Card.TFrame"); footer.pack(fill="x", padx=10, pady=(0,8))
    ttk.Label(footer, text=t('copyright'), style="Sub.TLabel").pack(side="left", padx=10)
    ttk.Label(footer, text=t('timestamp')+" "+datetime.now().strftime("%d.%m.%Y %H:%M"), style="Sub.TLabel").pack(side="right", padx=10)
    
    # Varsayılan olarak satış ekranını aç
    mount_sales(right_panel)

def logout_action(window):
    if show_custom_confirm_dialog(t('exit_title'), t('confirm_logout'), window):
        window.destroy()
        login_window.deiconify()

# ==========================
# Login
# ==========================
def login_action():
    global CURRENT_USER
    username = entry_username.get().strip()
    password = entry_password.get().strip()
    cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username,password))
    r = cursor.fetchone()
    if r:
        role = r[0]
        CURRENT_USER = username
        
        # Son kullanıcıyı kaydet
        try:
            cursor.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('last_user', ?)", (username,))
            conn.commit()
        except Exception:
            pass

        open_main_window(role, username)
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
    
    # Son kullanıcıyı yükle
    try:
        cursor.execute("SELECT value FROM settings WHERE key='last_user'")
        last_user_row = cursor.fetchone()
        if last_user_row:
            entry_username.insert(0, last_user_row[0])
    except Exception:
        pass

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

    # Akıllı Odaklanma (Kullanıcı adı doluysa şifreye, boşsa kullanıcı adına odaklan)
    if entry_username.get():
        entry_password.focus_set()
    else:
        entry_username.focus_set()

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

