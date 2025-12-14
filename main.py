import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3, os, csv, subprocess, time, glob, tempfile
from datetime import datetime, date
from languages import LANGUAGES
from pos.db_handler import get_connection, init_schema
from services import product_service as product_svc
from services import expense_service as expense_svc
from services import purchase_service as purchase_svc
from receipts import print_receipt, print_thermal_receipt

# ==========================
# Tema & Genel Ayarlar (v2.4)
# ==========================
FG_COLOR   = "#ffffff"
BG_COLOR   = "#18181c"
SIDEBAR_COLOR = "#18181c"
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
PARTIAL_PAYMENT_DATA = {}

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

def load_theme_settings():
    """Kaydedilmiş tema ayarlarını yükle"""
    global FG_COLOR, BG_COLOR, SIDEBAR_COLOR, CARD_COLOR, ACCENT, TEXT_LIGHT, TEXT_GRAY
    try:
        cursor.execute("SELECT key, value FROM settings WHERE key LIKE 'theme_%'")
        rows = cursor.fetchall()
        theme_data = {k: v for k, v in rows}
        
        if 'theme_fg' in theme_data: FG_COLOR = theme_data['theme_fg']
        if 'theme_bg' in theme_data: BG_COLOR = theme_data['theme_bg']
        if 'theme_sidebar' in theme_data: SIDEBAR_COLOR = theme_data['theme_sidebar']
        if 'theme_card' in theme_data: CARD_COLOR = theme_data['theme_card']
        if 'theme_accent' in theme_data: ACCENT = theme_data['theme_accent']
        
        # Türetilmiş renkler
        TEXT_LIGHT = FG_COLOR
        # Basitçe okunabilirlik için griyi de ana metin rengi yapalım veya yakın bir ton
        TEXT_GRAY = FG_COLOR 
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
    style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR, font=("Segoe UI", 10))
    style.configure("Header.TLabel", background=BG_COLOR, foreground=ACCENT, font=("Segoe UI", 16, "bold"))
    style.configure("Sub.TLabel", background=BG_COLOR, foreground=FG_COLOR,  font=("Segoe UI", 9))
    style.configure("Card.TFrame", background=CARD_COLOR)
    
    # Treeview dinamik renkler
    style.configure("Treeview", background=CARD_COLOR, fieldbackground=CARD_COLOR, foreground=FG_COLOR)
    style.configure("Treeview.Heading", background=BG_COLOR, foreground=FG_COLOR, relief="flat")
    style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
    
    # Menü scrollbari
    try:
        style.configure("Menu.Vertical.TScrollbar",
                        background=CARD_COLOR,
                        troughcolor=BG_COLOR,
                        bordercolor=CARD_COLOR,
                        arrowcolor=FG_COLOR)
        style.map("Menu.Vertical.TScrollbar",
                   background=[("active", ACCENT), ("pressed", ACCENT)])
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
load_theme_settings()

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

def _mount_purchase_screen(parent, doc_type):
    # doc_type: 'irsaliye' or 'fatura'
    title_key = 'dispatch_entry' if doc_type == 'irsaliye' else 'invoice_entry'
    icon = "📥" if doc_type == 'irsaliye' else "🧾"
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text=f"{icon} {t(title_key)}", style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Üst: Belge Bilgileri
    info_frame = ttk.Frame(content, style="Card.TFrame"); info_frame.pack(fill="x", pady=(0,10))
    
    # Tedarikçi Seçimi
    ttk.Label(info_frame, text=t('supplier_list')).grid(row=0, column=0, padx=10, pady=10)
    from services import cari_service as cs
    suppliers = [c for c in cs.list_all(cursor) if c[5] == 'alacakli']
    supplier_names = [s[1] for s in suppliers]
    cb_supplier = ttk.Combobox(info_frame, values=supplier_names, width=30)
    cb_supplier.grid(row=0, column=1, padx=10, pady=10)

    def filter_suppliers(event):
        text = cb_supplier.get()
        if not text:
            cb_supplier['values'] = supplier_names
        else:
            filtered = [s for s in supplier_names if text.lower() in s.lower()]
            cb_supplier['values'] = filtered
    
    cb_supplier.bind('<KeyRelease>', filter_suppliers)
    
    ttk.Label(info_frame, text="Belge No:").grid(row=0, column=2, padx=10, pady=10)
    e_doc_no = ttk.Entry(info_frame); e_doc_no.grid(row=0, column=3, padx=10, pady=10)
    
    ttk.Label(info_frame, text=t('date')).grid(row=0, column=4, padx=10, pady=10)
    e_date = ttk.Entry(info_frame); e_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
    e_date.grid(row=0, column=5, padx=10, pady=10)
    
    # Depo Seçimi
    ttk.Label(info_frame, text=t('warehouse')).grid(row=0, column=6, padx=10, pady=10)
    from services import warehouse_service as wh_svc
    warehouses = wh_svc.list_warehouses(cursor)
    wh_map = {w[1]: w[0] for w in warehouses}
    wh_names = list(wh_map.keys())
    cb_warehouse = ttk.Combobox(info_frame, values=wh_names, state="readonly", width=20)
    cb_warehouse.grid(row=0, column=7, padx=10, pady=10)
    if wh_names: cb_warehouse.set(wh_names[0])
    
    # Orta: Ürün Ekleme
    add_frame = ttk.Frame(content, style="Card.TFrame"); add_frame.pack(fill="x", pady=(0,10))
    
    ttk.Label(add_frame, text=t('barcode')).pack(side="left", padx=10, pady=10)
    e_barcode = ttk.Entry(add_frame); e_barcode.pack(side="left", padx=10, pady=10)
    e_barcode.focus_set()

    def show_product_selector():
        dialog = tk.Toplevel(parent)
        dialog.title(t('product_search'))
        dialog.geometry("600x400")
        
        # Search
        f_top = ttk.Frame(dialog); f_top.pack(fill="x", padx=10, pady=10)
        ttk.Label(f_top, text=t('search')).pack(side="left")
        sv_search = tk.StringVar()
        e_search = ttk.Entry(f_top, textvariable=sv_search)
        e_search.pack(side="left", fill="x", expand=True, padx=5)
        e_search.focus_set()
        
        # List
        cols = ("no", "name", "stock", "buy_price")
        tree_prod = ttk.Treeview(dialog, columns=cols, show="headings")
        tree_prod.heading("no", text="No"); tree_prod.column("no", width=40, anchor="center")
        tree_prod.heading("name", text=t('product')); tree_prod.column("name", width=200)
        tree_prod.heading("stock", text=t('stock')); tree_prod.column("stock", width=80)
        tree_prod.heading("buy_price", text=t('buy_price')); tree_prod.column("buy_price", width=80)
        tree_prod.pack(fill="both", expand=True, padx=10, pady=10)
        
        def load_prods(*args):
            for i in tree_prod.get_children(): tree_prod.delete(i)
            prods = product_svc.list_products(cursor, sv_search.get())
            for idx, p in enumerate(prods, 1):
                # p: (id, name, barcode, sale_price, stock, buy_price, unit, category_id)
                tree_prod.insert("", "end", text=str(p[0]), values=(idx, p[1], p[4], p[5]))
                
        sv_search.trace("w", load_prods)
        load_prods()
        
        def on_select(event):
            sel = tree_prod.selection()
            if not sel: return
            pid = tree_prod.item(sel[0])["text"]
            dialog.destroy()
            add_item_to_list((pid,))
            
        tree_prod.bind("<Double-1>", on_select)
        tree_prod.bind("<Return>", on_select)

    ttk.Button(add_frame, text="🔍 " + t('find_product'), command=show_product_selector).pack(side="left", padx=10)
    
    def on_barcode_enter(event=None):
        bc = e_barcode.get().strip()
        if not bc: return
        res = product_svc.get_by_barcode(cursor, bc)
        if res:
            add_item_to_list(res)
            e_barcode.delete(0, tk.END)
        else:
            messagebox.showwarning(t('warning'), t('product_not_found'))
            
    e_barcode.bind("<Return>", on_barcode_enter)
    
    # Liste
    list_frame = ttk.Frame(content, style="Card.TFrame"); list_frame.pack(fill="both", expand=True)
    
    columns = ("no", "name", "qty", "price", "total")
    tree = ttk.Treeview(list_frame, columns=columns, show="headings")
    tree.heading("no", text="No"); tree.column("no", width=40, anchor="center")
    tree.heading("name", text=t('product')); tree.column("name", width=200)
    tree.heading("qty", text=t('quantity')); tree.column("qty", width=80)
    tree.heading("price", text=t('buy_price')); tree.column("price", width=100)
    tree.heading("total", text=t('total')); tree.column("total", width=100)
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    items_data = [] # list of dict
    
    def ask_qty_price_custom(title, product_name, initial_price):
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.geometry("350x250")
        dialog.configure(bg=BG_COLOR)
        dialog.transient(parent)
        dialog.grab_set()
        
        # Center
        dialog.update_idletasks()
        w = dialog.winfo_width()
        h = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (w // 2)
        y = (dialog.winfo_screenheight() // 2) - (h // 2)
        dialog.geometry(f"+{x}+{y}")
        
        result = []
        
        ttk.Label(dialog, text=product_name, font=("Segoe UI", 11, "bold"), background=BG_COLOR, foreground=ACCENT).pack(pady=(15, 10))

        # Qty
        f_qty = ttk.Frame(dialog, style="Card.TFrame")
        f_qty.pack(fill="x", padx=20, pady=5)
        ttk.Label(f_qty, text=t('quantity') + ":", width=10, anchor="w").pack(side="left")
        sv_qty = tk.StringVar()
        e_qty = ttk.Entry(f_qty, textvariable=sv_qty)
        e_qty.pack(side="left", fill="x", expand=True)
        
        # Ensure focus after window is ready
        def set_focus():
            e_qty.focus_force()
        dialog.after(200, set_focus)

        # Price
        f_price = ttk.Frame(dialog, style="Card.TFrame")
        f_price.pack(fill="x", padx=20, pady=5)
        ttk.Label(f_price, text=t('buy_price') + ":", width=10, anchor="w").pack(side="left")
        sv_price = tk.StringVar(value=str(initial_price))
        e_price = ttk.Entry(f_price, textvariable=sv_price)
        e_price.pack(side="left", fill="x", expand=True)

        def on_ok(event=None):
            q = sv_qty.get()
            p = sv_price.get()
            if q and p:
                result.append((q, p))
                dialog.destroy()
            
        def on_cancel(event=None):
            dialog.destroy()
            
        btn_frame = ttk.Frame(dialog, style="Card.TFrame")
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="İptal", command=on_cancel).pack(side="left", padx=5)
        
        e_qty.bind("<Return>", lambda e: e_price.focus_set())
        e_price.bind("<Return>", on_ok)
        dialog.bind("<Escape>", on_cancel)
        
        parent.wait_window(dialog)
        return result[0] if result else None

    def add_item_to_list(prod_tuple):
        pid = prod_tuple[0]
        full_prod = product_svc.get_by_id(cursor, pid) # (id, name, barcode, sale_price, stock, buy_price, unit)
        buy_price = full_prod[5]
        
        res = ask_qty_price_custom(t('add_product'), full_prod[1], buy_price)
        if not res: return
        
        qty_str, price_str = res
        try: 
            qty = float(qty_str)
            price = float(price_str)
        except: return
        
        total = qty * price
        items_data.append({
            'product_id': pid,
            'name': full_prod[1],
            'qty': qty,
            'price': price,
            'total': total
        })
        refresh_list()
        
    def refresh_list():
        for i in tree.get_children(): tree.delete(i)
        grand_total = 0
        for idx, item in enumerate(items_data, 1):
            tree.insert("", "end", text=str(item['product_id']), values=(idx, item['name'], item['qty'], item['price'], item['total']))
            grand_total += item['total']
        lbl_total.config(text=f"{t('total')}: {grand_total:.2f} ₺")
        
    lbl_total = ttk.Label(list_frame, text="Total: 0.00 ₺", font=("Segoe UI", 14, "bold"))
    lbl_total.pack(pady=10)
    
    def save_doc():
        supplier_name = cb_supplier.get().strip()
        doc_no = e_doc_no.get().strip()
        doc_date = e_date.get().strip()
        
        if not supplier_name:
            messagebox.showwarning(t('warning'), t('supplier_list') + " seçilmelidir.")
            return
        
        if not doc_no:
            messagebox.showwarning(t('warning'), "Belge numarası girilmelidir.")
            return
            
        if not doc_date:
            messagebox.showwarning(t('warning'), t('date') + " girilmelidir.")
            return

        if not items_data:
            messagebox.showwarning(t('warning'), "En az bir ürün eklenmelidir.")
            return

        supplier_id = None
        if supplier_name:
            for s in suppliers:
                if s[1] == supplier_name:
                    supplier_id = s[0]
                    break
        
        wh_name = cb_warehouse.get()
        wh_id = wh_map.get(wh_name) if wh_name else None
        
        try:
            purchase_svc.create_purchase(conn, cursor, supplier_id, doc_type, doc_no, doc_date, items_data, warehouse_id=wh_id)
            messagebox.showinfo(t('success'), t('saved'))
            items_data.clear()
            refresh_list()
            e_doc_no.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror(t('error'), str(e))
            
    tk.Button(list_frame, text="💾 " + t('save'), command=save_doc, bg=ACCENT, fg="white", relief="flat", padx=20, pady=10).pack(pady=10)

def mount_irsaliye(parent):
    _mount_purchase_screen(parent, 'irsaliye')

def mount_fatura(parent):
    _mount_purchase_screen(parent, 'fatura')

def mount_irsaliye_listesi(parent):
    _mount_purchase_list(parent, 'irsaliye')

def mount_fatura_listesi(parent):
    _mount_purchase_list(parent, 'fatura')

def _mount_purchase_list(parent, doc_type):
    for w in parent.winfo_children(): w.destroy()
    
    title_key = 'dispatch_list' if doc_type == 'irsaliye' else 'invoice_list'
    icon = "🚚" if doc_type == 'irsaliye' else "🧾"
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text=f"{icon} {t(title_key)}", style="Header.TLabel").pack(side="left", padx=8)
    
    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    
    cols = ("no", "supplier", "doc_no", "date", "total", "desc")
    tree = ttk.Treeview(body, columns=cols, show="headings")
    tree.heading("no", text="No"); tree.column("no", width=50, anchor="center")
    tree.heading("supplier", text=t('supplier_list')); tree.column("supplier", width=200)
    tree.heading("doc_no", text="Belge No"); tree.column("doc_no", width=100)
    tree.heading("date", text=t('date')); tree.column("date", width=100)
    tree.heading("total", text=t('total')); tree.column("total", width=100, anchor="e")
    tree.heading("desc", text=t('description')); tree.column("desc", width=200)
    
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Load data
    def load_data():
        for i in tree.get_children(): tree.delete(i)
        docs = purchase_svc.list_documents(cursor, doc_type)
        for idx, d in enumerate(docs, 1):
            # d: (id, supplier_name, doc_type, doc_number, doc_date, total_amount, description)
            tree.insert("", "end", text=str(d[0]), values=(idx, d[1] or "-", d[3], d[4], f"{d[5]:.2f} ₺", d[6] or ""))
    load_data()
        
    # Detail view on double click
    def on_double_click(event):
        sel = tree.selection()
        if not sel: return
        item = tree.item(sel[0])
        doc_id = item['text']
        show_purchase_details(parent, doc_id)
        
    tree.bind("<Double-1>", on_double_click)

    # Buttons
    btn_frame = ttk.Frame(body); btn_frame.pack(fill="x", padx=10, pady=10)
    
    def delete_selected():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning(t('warning'), t('select_record'))
            return
        
        if not messagebox.askyesno(t('confirm'), t('delete_confirm')):
            return
            
        doc_id = tree.item(sel[0])['text']
        try:
            purchase_svc.delete_purchase(conn, cursor, doc_id)
            messagebox.showinfo(t('success'), t('deleted'))
            load_data()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))

    tk.Button(btn_frame, text="🗑 " + t('delete'), command=delete_selected, bg="#dc3545", fg="white", relief="flat", padx=15, pady=8).pack(side="right", padx=5)
    
    # Edit (For now, just delete and re-enter logic or simple info edit? 
    # Since full edit is complex, we will guide user to delete and re-enter for now, 
    # OR implement a basic edit that just opens the details. 
    # User asked for "Edit", let's provide a way to view details which is "Edit" in read-only mode for now, 
    # or we can implement full edit later. 
    # Actually, let's make "Edit" open the details window which we already have.)
    
    tk.Button(btn_frame, text="👁 " + t('details'), command=lambda: on_double_click(None), bg="#17a2b8", fg="white", relief="flat", padx=15, pady=8).pack(side="right", padx=5)

def show_purchase_details(parent, doc_id):
    dialog = tk.Toplevel(parent)
    dialog.title(t('details'))
    dialog.geometry("800x600")
    dialog.configure(bg=BG_COLOR)
    
    # Fetch data
    doc = purchase_svc.get_document(cursor, doc_id)
    if not doc: return
    # doc: (id, supplier_id, doc_type, doc_number, doc_date, total_amount, description, created_at)
    
    items = purchase_svc.get_document_items(cursor, doc_id)
    # items: (name, qty, price, total, product_id)
    
    # Header Info
    header_frame = ttk.Frame(dialog, style="Card.TFrame")
    header_frame.pack(fill="x", padx=10, pady=10)
    
    # Supplier Name
    supplier_name = "-"
    if doc[1]:
        from services import cari_service as cs
        sup = cs.get_by_id(cursor, doc[1])
        if sup: supplier_name = sup[1]
        
    ttk.Label(header_frame, text=f"{t('supplier_list')}: {supplier_name}", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
    ttk.Label(header_frame, text=f"Belge No: {doc[3]}", font=("Segoe UI", 10)).grid(row=0, column=1, padx=10, pady=5, sticky="w")
    ttk.Label(header_frame, text=f"{t('date')}: {doc[4]}", font=("Segoe UI", 10)).grid(row=0, column=2, padx=10, pady=5, sticky="w")
    ttk.Label(header_frame, text=f"{t('total')}: {doc[5]:.2f} ₺", font=("Segoe UI", 12, "bold"), foreground=ACCENT).grid(row=0, column=3, padx=10, pady=5, sticky="w")

    # Items List
    list_frame = ttk.Frame(dialog, style="Card.TFrame")
    list_frame.pack(fill="both", expand=True, padx=10, pady=5)
    
    cols = ("name", "qty", "price", "total")
    tree = ttk.Treeview(list_frame, columns=cols, show="headings")
    tree.heading("name", text=t('product')); tree.column("name", width=250)
    tree.heading("qty", text=t('quantity')); tree.column("qty", width=80, anchor="center")
    tree.heading("price", text=t('price')); tree.column("price", width=100, anchor="e")
    tree.heading("total", text=t('total')); tree.column("total", width=100, anchor="e")
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    for i in items:
        tree.insert("", "end", values=(i[0], i[1], f"{i[2]:.2f}", f"{i[3]:.2f}"))

    # Edit Mode Logic
    def enable_edit():
        dialog.destroy()
        _mount_purchase_edit(parent, doc_id)

    btn_frame = ttk.Frame(dialog, style="Card.TFrame")
    btn_frame.pack(fill="x", padx=10, pady=10)
    
    tk.Button(btn_frame, text="✏️ " + t('edit'), command=enable_edit, bg="#ffc107", fg="black", relief="flat", padx=15, pady=8).pack(side="right", padx=5)
    tk.Button(btn_frame, text=t('close'), command=dialog.destroy, bg="#6c757d", fg="white", relief="flat", padx=15, pady=8).pack(side="right", padx=5)

def _mount_purchase_edit(parent, doc_id):
    # Similar to _mount_purchase_screen but pre-filled and updates instead of creates
    for w in parent.winfo_children(): w.destroy()
    
    doc = purchase_svc.get_document(cursor, doc_id)
    if not doc: return
    
    doc_type = doc[2]
    title_key = 'dispatch_entry' if doc_type == 'irsaliye' else 'invoice_entry'
    icon = "🚚" if doc_type == 'irsaliye' else "🧾"
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text=f"{icon} {t(title_key)} ({t('edit')})", style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Info Frame
    info_frame = ttk.Frame(content, style="Card.TFrame"); info_frame.pack(fill="x", pady=(0,10))
    
    ttk.Label(info_frame, text=t('supplier_list')).grid(row=0, column=0, padx=10, pady=10)
    from services import cari_service as cs
    suppliers = [c for c in cs.list_all(cursor) if c[5] == 'alacakli']
    supplier_names = [s[1] for s in suppliers]
    cb_supplier = ttk.Combobox(info_frame, values=supplier_names, width=30)
    cb_supplier.grid(row=0, column=1, padx=10, pady=10)
    
    # Set current supplier
    current_supplier_name = ""
    if doc[1]:
        sup = cs.get_by_id(cursor, doc[1])
        if sup: 
            current_supplier_name = sup[1]
            cb_supplier.set(current_supplier_name)
            
    ttk.Label(info_frame, text="Belge No:").grid(row=0, column=2, padx=10, pady=10)
    e_doc_no = ttk.Entry(info_frame); e_doc_no.grid(row=0, column=3, padx=10, pady=10)
    e_doc_no.insert(0, doc[3])
    
    ttk.Label(info_frame, text=t('date')).grid(row=0, column=4, padx=10, pady=10)
    e_date = ttk.Entry(info_frame); e_date.grid(row=0, column=5, padx=10, pady=10)
    e_date.insert(0, doc[4])
    
    # Add Item Frame
    add_frame = ttk.Frame(content, style="Card.TFrame"); add_frame.pack(fill="x", pady=(0,10))
    
    ttk.Label(add_frame, text=t('barcode')).pack(side="left", padx=10, pady=10)
    e_barcode = ttk.Entry(add_frame); e_barcode.pack(side="left", padx=10, pady=10)
    e_barcode.focus_set()
    
    # Items Data
    items_data = []
    db_items = purchase_svc.get_document_items(cursor, doc_id)
    for i in db_items:
        # i: (name, qty, price, total, product_id)
        items_data.append({
            'product_id': i[4],
            'name': i[0],
            'qty': i[1],
            'price': i[2],
            'total': i[3]
        })

    # List Frame
    list_frame = ttk.Frame(content, style="Card.TFrame"); list_frame.pack(fill="both", expand=True)
    
    columns = ("no", "name", "qty", "price", "total")
    tree = ttk.Treeview(list_frame, columns=columns, show="headings")
    tree.heading("no", text="No"); tree.column("no", width=40, anchor="center")
    tree.heading("name", text=t('product')); tree.column("name", width=200)
    tree.heading("qty", text=t('quantity')); tree.column("qty", width=80)
    tree.heading("price", text=t('buy_price')); tree.column("price", width=100)
    tree.heading("total", text=t('total')); tree.column("total", width=100)
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    lbl_total = ttk.Label(list_frame, text="Total: 0.00 ₺", font=("Segoe UI", 14, "bold"))
    lbl_total.pack(pady=10)

    def refresh_list():
        for i in tree.get_children(): tree.delete(i)
        grand_total = 0
        for idx, item in enumerate(items_data, 1):
            tree.insert("", "end", text=str(item['product_id']), values=(idx, item['name'], item['qty'], item['price'], item['total']))
            grand_total += item['total']
        lbl_total.config(text=f"{t('total')}: {grand_total:.2f} ₺")

    refresh_list()

    def add_item_to_list(prod_tuple):
        pid = prod_tuple[0]
        full_prod = product_svc.get_by_id(cursor, pid)
        buy_price = full_prod[5]
        
        qty_str = simpledialog.askstring(t('quantity'), f"{full_prod[1]}\n{t('quantity')}:", parent=parent)
        if not qty_str: return
        try: qty = float(qty_str)
        except: return
        
        price_str = simpledialog.askstring(t('price'), f"{t('buy_price')}:", initialvalue=str(buy_price), parent=parent)
        if not price_str: return
        try: price = float(price_str)
        except: return
        
        total = qty * price
        items_data.append({
            'product_id': pid,
            'name': full_prod[1],
            'qty': qty,
            'price': price,
            'total': total
        })
        refresh_list()

    def on_barcode_enter(event=None):
        bc = e_barcode.get().strip()
        if not bc: return
        res = product_svc.get_by_barcode(cursor, bc)
        if res:
            add_item_to_list(res)
            e_barcode.delete(0, tk.END)
        else:
            messagebox.showwarning(t('warning'), t('product_not_found'))
            
    e_barcode.bind("<Return>", on_barcode_enter)

    def show_product_selector():
        dialog = tk.Toplevel(parent)
        dialog.title(t('product_search'))
        dialog.geometry("600x400")
        f_top = ttk.Frame(dialog); f_top.pack(fill="x", padx=10, pady=10)
        ttk.Label(f_top, text=t('search')).pack(side="left")
        sv_search = tk.StringVar()
        e_search = ttk.Entry(f_top, textvariable=sv_search)
        e_search.pack(side="left", fill="x", expand=True, padx=5); e_search.focus_set()
        cols = ("no", "name", "stock", "buy_price")
        tree_prod = ttk.Treeview(dialog, columns=cols, show="headings")
        tree_prod.heading("no", text="No"); tree_prod.column("no", width=40, anchor="center")
        tree_prod.heading("name", text=t('product')); tree_prod.column("name", width=200)
        tree_prod.heading("stock", text=t('stock')); tree_prod.column("stock", width=80)
        tree_prod.heading("buy_price", text=t('buy_price')); tree_prod.column("buy_price", width=80)
        tree_prod.pack(fill="both", expand=True, padx=10, pady=10)
        def load_prods(*args):
            for i in tree_prod.get_children(): tree_prod.delete(i)
            prods = product_svc.list_products(cursor, sv_search.get())
            for idx, p in enumerate(prods, 1): tree_prod.insert("", "end", text=str(p[0]), values=(idx, p[1], p[4], p[5]))
        sv_search.trace("w", load_prods); load_prods()
        def on_select(event):
            sel = tree_prod.selection()
            if not sel: return
            pid = tree_prod.item(sel[0])["text"]
            dialog.destroy()
            add_item_to_list((pid,))
        tree_prod.bind("<Double-1>", on_select); tree_prod.bind("<Return>", on_select)

    ttk.Button(add_frame, text="🔍 " + t('find_product'), command=show_product_selector).pack(side="left", padx=10)
    
    # Remove item on double click
    def remove_item(event):
        sel = tree.selection()
        if not sel: return
        if messagebox.askyesno(t('confirm'), t('delete_confirm')):
            idx = tree.index(sel[0])
            items_data.pop(idx)
            refresh_list()
    tree.bind("<Double-1>", remove_item)
    
    def update_doc():
        if not items_data: return
        supplier_name = cb_supplier.get()
        supplier_id = None
        if supplier_name:
            for s in suppliers:
                if s[1] == supplier_name:
                    supplier_id = s[0]
                    break
        
        doc_no = e_doc_no.get().strip()
        doc_date = e_date.get().strip()
        
        try:
            purchase_svc.update_purchase(conn, cursor, doc_id, supplier_id, doc_no, doc_date, items_data)
            messagebox.showinfo(t('success'), t('updated'))
            # Return to list
            if doc_type == 'irsaliye': mount_irsaliye_listesi(parent)
            else: mount_fatura_listesi(parent)
        except Exception as e:
            messagebox.showerror(t('error'), str(e))
            
    tk.Button(list_frame, text="💾 " + t('update_btn'), command=update_doc, bg=ACCENT, fg="white", relief="flat", padx=20, pady=10).pack(pady=10)
    tk.Button(list_frame, text="❌ " + t('cancel'), command=lambda: mount_fatura_listesi(parent) if doc_type=='fatura' else mount_irsaliye_listesi(parent), bg="#6c757d", fg="white", relief="flat", padx=20, pady=10).pack(pady=10)


def mount_placeholder(parent, icon, title_text, body_text):
    for w in parent.winfo_children():
        w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text=f"{icon} {title_text}", style="Header.TLabel").pack(side="left", padx=8)
    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    ttk.Label(body, text=body_text, font=("Segoe UI", 12), background=CARD_COLOR).pack(expand=True, padx=16, pady=16)


# Generic placeholder pages for new submenus
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

    row_id_map = {}

    def load_categories():
        row_id_map.clear()
        for item in tree.get_children():
            tree.delete(item)
        from repositories import category_repository
        categories = category_repository.list_all(cursor)
        if not categories:
            # Boş mesajı
            tree.insert("", "end", values=("", t('no_categories'), "", ""))
        for i, (cid, cname, color) in enumerate(categories, 1):
            row_id_map[i] = cid
            cnt = category_repository.count_products(cursor, cid)
            tree.insert("", "end", values=(i, cname, color or "-", cnt))

    # Action buttons
    btn_frame = ttk.Frame(parent, style="Card.TFrame")
    btn_frame.pack(fill="x", padx=12, pady=(0, 12))

    def add_category():
        dialog = tk.Toplevel(parent)
        dialog.title(t('add_category'))
        set_theme(dialog)
        center_window(dialog, 400, 200)

        tk.Label(dialog, text=t('category_name') + ":", bg=CARD_COLOR, fg=FG_COLOR).pack(pady=(16,4), padx=16, anchor="w")
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=4, padx=16, fill="x")

        tk.Label(dialog, text=t('category_color') + " (hex):", bg=CARD_COLOR, fg=FG_COLOR).pack(pady=(8,4), padx=16, anchor="w")
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
        
        try:
            display_id = int(vals[0])
            cid = row_id_map.get(display_id)
            if not cid: return
        except: return

        cname = str(vals[1])
        color = str(vals[2]) if vals[2] != "-" else ""

        dialog = tk.Toplevel(parent)
        dialog.title(t('edit_category'))
        set_theme(dialog)
        center_window(dialog, 400, 200)

        tk.Label(dialog, text=t('category_name') + ":", bg=CARD_COLOR, fg=FG_COLOR).pack(pady=(16,4), padx=16, anchor="w")
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(pady=4, padx=16, fill="x")
        name_entry.insert(0, cname)

        tk.Label(dialog, text=t('category_color') + " (hex):", bg=CARD_COLOR, fg=FG_COLOR).pack(pady=(8,4), padx=16, anchor="w")
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
        
        try:
            display_id = int(vals[0])
            cid = row_id_map.get(display_id)
            if not cid: return
        except: return

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

def mount_envanter_sayim(parent):
    from services import product_service as ps
    from services import warehouse_service as wh_svc
    import datetime

    for w in parent.winfo_children(): w.destroy()

    # --- Layout ---
    paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, sashwidth=4, bg=BG_COLOR)
    paned.pack(fill="both", expand=True, padx=12, pady=12)

    # Left Panel: History
    left_frame = ttk.Frame(paned, style="Card.TFrame", width=300)
    paned.add(left_frame, stretch="never")
    
    ttk.Label(left_frame, text="📋 " + t('history'), style="Header.TLabel", font=("Segoe UI", 12, "bold")).pack(fill="x", padx=8, pady=8)
    
    hist_cols = ("id", "date", "desc")
    hist_tree = ttk.Treeview(left_frame, columns=hist_cols, show="headings", height=20)
    hist_tree.heading("id", text="#")
    hist_tree.heading("date", text=t('date'))
    hist_tree.heading("desc", text=t('description'))
    hist_tree.column("id", width=40, anchor="center")
    hist_tree.column("date", width=120)
    hist_tree.column("desc", width=100)
    hist_tree.pack(fill="both", expand=True, padx=4, pady=4)

    # Context Menu for History
    hist_menu = tk.Menu(left_frame, tearoff=0)
    hist_menu.add_command(label="🗑 " + t('delete'), command=lambda: delete_history_record())

    def on_hist_right_click(event):
        item = hist_tree.identify_row(event.y)
        if item:
            hist_tree.selection_set(item)
            hist_menu.post(event.x_root, event.y_root)

    hist_tree.bind("<Button-3>", on_hist_right_click)

    # Right Panel: Details
    right_frame = ttk.Frame(paned, style="Card.TFrame")
    paned.add(right_frame, stretch="always")

    header = ttk.Frame(right_frame, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    lbl_title = ttk.Label(header, text="📦 " + t('inventory_count'), style="Header.TLabel", font=("Segoe UI", 16, "bold"))
    lbl_title.pack(side="left", padx=8)
    
    # --- Form Section ---
    form_frame = ttk.Frame(right_frame, style="Card.TFrame")
    form_frame.pack(fill="x", padx=12, pady=8)
    
    form_frame.columnconfigure(1, weight=1)
    form_frame.columnconfigure(3, weight=1)

    # Data Loading
    products = ps.list_products(cursor)
    product_names = sorted([p[1] for p in products])
    product_map = {p[1]: p[0] for p in products} # Name -> ID
    barcode_map = {str(p[2]): p[1] for p in products if p[2]}

    # Product Selection
    ttk.Label(form_frame, text=t('product')+":", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=8, pady=12, sticky="e")
    cb_product = ttk.Combobox(form_frame, values=product_names, font=("Segoe UI", 10))
    cb_product.grid(row=0, column=1, padx=8, pady=12, sticky="ew")
    
    # Placeholder Logic
    placeholder_text = t('enter_product_or_barcode')
    cb_product.set(placeholder_text)
    
    def on_prod_focus_in(event):
        if cb_product.get() == placeholder_text:
            cb_product.set('')
            cb_product.config(foreground='black') # Normal text color

    def on_prod_focus_out(event):
        if not cb_product.get():
            cb_product.set(placeholder_text)
            # cb_product.config(foreground='grey') # Optional: grey out placeholder

    cb_product.bind("<FocusIn>", on_prod_focus_in)
    cb_product.bind("<FocusOut>", on_prod_focus_out)

    # Warehouse Selection
    ttk.Label(form_frame, text=t('warehouse')+":", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, padx=8, pady=12, sticky="e")
    warehouses = wh_svc.list_warehouses(cursor)
    wh_map = {w[1]: w[0] for w in warehouses}
    wh_names = list(wh_map.keys())
    cb_warehouse = ttk.Combobox(form_frame, values=wh_names, state="readonly", font=("Segoe UI", 10))
    cb_warehouse.grid(row=0, column=3, padx=8, pady=12, sticky="ew")
    if wh_names: cb_warehouse.set(wh_names[0])

    # Current Stock Info
    ttk.Label(form_frame, text=t('stock')+":", font=("Segoe UI", 10)).grid(row=1, column=0, padx=8, pady=8, sticky="e")
    lbl_current_stock = ttk.Label(form_frame, text="-", font=("Segoe UI", 10, "bold"))
    lbl_current_stock.grid(row=1, column=1, padx=8, pady=8, sticky="w")
    
    ttk.Label(form_frame, text=t('unit')+":", font=("Segoe UI", 10)).grid(row=1, column=2, padx=8, pady=8, sticky="e")
    lbl_unit = ttk.Label(form_frame, text="-", font=("Segoe UI", 10))
    lbl_unit.grid(row=1, column=3, padx=8, pady=8, sticky="w")

    # New Count Entry
    ttk.Label(form_frame, text=t('inventory_count')+":", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, padx=8, pady=12, sticky="e")
    entry_count = ttk.Entry(form_frame, font=("Segoe UI", 10))
    entry_count.grid(row=2, column=1, padx=8, pady=12, sticky="w")

    # Add Button
    btn_add = tk.Button(form_frame, text="⬇️ " + t('add'), 
                       bg="#00b0ff", fg="white", font=("Segoe UI", 10, "bold"),
                       relief="flat", padx=20, pady=6, cursor="hand2", borderwidth=0)
    btn_add.grid(row=2, column=3, padx=8, pady=12, sticky="e")

    # --- List Section ---
    list_frame = ttk.Frame(right_frame, style="Card.TFrame")
    list_frame.pack(fill="both", expand=True, padx=12, pady=8)

    cols = ("no", "product", "warehouse", "old_stock", "new_count", "diff")
    tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)
    tree.heading("no", text="#")
    tree.heading("product", text=t('product'))
    tree.heading("warehouse", text=t('warehouse'))
    tree.heading("old_stock", text=t('stock'))
    tree.heading("new_count", text=t('inventory_count'))
    tree.heading("diff", text="Fark")
    
    tree.column("no", width=40, anchor="center")
    tree.column("product", width=200)
    tree.column("warehouse", width=150)
    tree.column("old_stock", width=100, anchor="center")
    tree.column("new_count", width=100, anchor="center")
    tree.column("diff", width=100, anchor="center")

    # Zebrastripe
    tree.tag_configure('oddrow', background=BG_COLOR)
    tree.tag_configure('evenrow', background=CARD_COLOR)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    # State
    # We use a mutable container for current_count_id so inner functions can modify it
    state: dict = {'current_count_id': None, 'editing_item': None} 
    
    pending_items = [] # {'pid', 'product', 'wh_id', 'wh_name', 'old', 'new', 'unit', 'saved_new', 'id'}

    def refresh_info(*args):
        p_name = cb_product.get()
        w_name = cb_warehouse.get()
        wh_id = wh_map.get(w_name)
        
        if not p_name or p_name == placeholder_text:
            lbl_current_stock.config(text="-")
            lbl_unit.config(text="-")
            return
            
        info = ps.get_price_stock_by_name(cursor, p_name, wh_id)
        if info:
            _, stock, unit = info
            lbl_unit.config(text=str(unit))
            if str(unit).lower() == "kg":
                lbl_current_stock.config(text=f"{float(stock):.3f}")
            else:
                lbl_current_stock.config(text=str(int(float(stock))))
        else:
            lbl_current_stock.config(text="0")
            lbl_unit.config(text="-")

    # --- Search & Barcode Logic ---
    def on_product_enter(event=None):
        val = cb_product.get().strip()
        if not val or val == placeholder_text: return
        
        # 1. Barkod kontrolü
        if val in barcode_map:
            found_name = barcode_map[val]
            cb_product.set(found_name)
            cb_product.icursor(tk.END)
            refresh_info()
            entry_count.focus_set()
            return

        # 2. Tam isim kontrolü
        if val in product_names:
            refresh_info()
            entry_count.focus_set()
            return
            
        # 3. Case-insensitive isim kontrolü
        for name in product_names:
            if name.lower() == val.lower():
                cb_product.set(name)
                refresh_info()
                entry_count.focus_set()
                return
        
        # Bulunamadı
        messagebox.showwarning(t('warning'), t('product_not_found'), parent=parent)

    def on_key_release(event):
        if event.keysym in ['Return', 'Up', 'Down', 'Left', 'Right', 'Tab']: return
        val = cb_product.get()
        if val == '':
            cb_product['values'] = product_names
        else:
            filtered = [n for n in product_names if val.lower() in n.lower()]
            cb_product['values'] = filtered

    cb_product.bind("<Return>", on_product_enter)
    cb_product.bind("<KeyRelease>", on_key_release)
    cb_product.bind("<<ComboboxSelected>>", refresh_info)
    cb_warehouse.bind("<<ComboboxSelected>>", refresh_info)

    def add_to_list():
        p_name = cb_product.get().strip()
        w_name = cb_warehouse.get().strip()
        wh_id = wh_map.get(w_name)
        count_str = entry_count.get().strip()
        
        if not p_name or not w_name or p_name == placeholder_text:
            return messagebox.showwarning(t('warning'), t('fill_all_fields'))
        
        try:
            new_count = float(count_str)
            if new_count < 0: raise ValueError
        except:
            return messagebox.showwarning(t('warning'), t('enter_valid'))

        # Check if already in list
        for item in pending_items:
            if item['product'] == p_name and item['wh_id'] == wh_id:
                return messagebox.showwarning(t('warning'), "Bu ürün zaten listede ekli. Lütfen listeden düzenleyin.")

        # Determine old stock and ID
        # If we are editing an item, we should reuse its original 'old' stock and 'id'
        editing_item = state.get('editing_item')
        
        if editing_item and editing_item['product'] == p_name and editing_item['wh_id'] == wh_id:
            # We are re-adding the item we were editing
            old_stock = editing_item['old']
            unit = editing_item.get('unit', '-')
            item_id = editing_item.get('id')
            saved_new = editing_item.get('saved_new')
            state['editing_item'] = None # Clear editing state
        else:
            # New item or changed product
            info = ps.get_price_stock_by_name(cursor, p_name, wh_id)
            old_stock = float(info[1]) if info else 0.0
            unit = info[2] if info else "-"
            item_id = None
            saved_new = None
            # If we were editing but changed product, the original editing_item is effectively discarded (deleted)
            state['editing_item'] = None

        item = {
            'id': item_id,
            'product': p_name,
            'wh_id': wh_id,
            'wh_name': w_name,
            'old': old_stock,
            'new': new_count,
            'unit': unit,
            'saved_new': saved_new
        }
        pending_items.append(item)
        update_tree()
        entry_count.delete(0, tk.END)
        cb_product.set('')
        cb_product.focus_set()
        refresh_info()

    def update_tree():
        for i in tree.get_children(): tree.delete(i)
        for idx, item in enumerate(pending_items):
            diff = item['new'] - item['old']
            diff_str = f"{diff:+.2f}"
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            tree.insert("", "end", values=(idx + 1, item['product'], item['wh_name'], item['old'], item['new'], diff_str), tags=(tag,))

    def delete_selected():
        sel = tree.selection()
        if not sel: return
        idx = tree.index(sel[0])
        del pending_items[idx]
        update_tree()

    def edit_selected():
        sel = tree.selection()
        if not sel: return
        idx = tree.index(sel[0])
        item = pending_items[idx]
        
        # Save to editing state so we can preserve ID and old_stock
        state['editing_item'] = item.copy()
        
        # Load back to form
        cb_product.set(item['product'])
        cb_warehouse.set(item['wh_name'])
        entry_count.delete(0, tk.END)
        entry_count.insert(0, str(item['new']))
        refresh_info()
        
        # Remove from list
        del pending_items[idx]
        update_tree()

    def delete_history_record():
        sel = hist_tree.selection()
        if not sel: return
        item_vals = hist_tree.item(sel[0])['values']
        try:
            c_id = int(item_vals[0])
        except:
            c_id = item_vals[0]
            
        if not messagebox.askyesno(t('confirm'), t('confirm_delete')):
            return
            
        try:
            cursor.execute("DELETE FROM inventory_count_items WHERE count_id=?", (c_id,))
            cursor.execute("DELETE FROM inventory_counts WHERE id=?", (c_id,))
            conn.commit()
            
            if state['current_count_id'] == c_id:
                reset_form()
            
            load_history()
            messagebox.showinfo(t('success'), t('done'))
        except Exception as e:
            conn.rollback()
            messagebox.showerror(t('error'), str(e))

    def load_history():
        for i in hist_tree.get_children(): hist_tree.delete(i)
        try:
            cursor.execute("SELECT id, created_at, description FROM inventory_counts ORDER BY id DESC")
            rows = cursor.fetchall()
            for r in rows:
                hist_tree.insert("", "end", values=(r[0], r[1][:16], r[2] or "-"))
        except Exception as e:
            print("History load error:", e)

    def on_history_select(event):
        sel = hist_tree.selection()
        if not sel: return
        item_vals = hist_tree.item(sel[0])['values']
        try:
            c_id = int(item_vals[0])
        except (ValueError, TypeError):
            c_id = item_vals[0]
        
        # Load items
        try:
            cursor.execute("SELECT id, product_name, warehouse_id, warehouse_name, old_stock, new_stock FROM inventory_count_items WHERE count_id=?", (c_id,))
            rows = cursor.fetchall()
            
            pending_items.clear()
            state['editing_item'] = None
            
            for r in rows:
                pending_items.append({
                    'id': r[0],
                    'product': r[1],
                    'wh_id': r[2],
                    'wh_name': r[3],
                    'old': r[4],
                    'new': r[5],
                    'saved_new': r[5], # Store original saved value for diff calc
                    'unit': '-'
                })
            
            state['current_count_id'] = c_id
            lbl_title.config(text=f"📦 {t('inventory_count')} #{c_id}")
            update_tree()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    hist_tree.bind("<<TreeviewSelect>>", on_history_select)

    def reset_form():
        state['current_count_id'] = None
        state['editing_item'] = None
        pending_items.clear()
        update_tree()
        lbl_title.config(text="📦 " + t('inventory_count'))
        entry_count.delete(0, tk.END)
        cb_product.set(placeholder_text)
        refresh_info()

    def save_all():
        if not pending_items:
            return messagebox.showinfo(t('info'), "Listede ürün yok.")
            
        if not messagebox.askyesno(t('confirm'), f"{len(pending_items)} adet ürün stoğu güncellenecek. Onaylıyor musunuz?"):
            return
            
        try:
            c_id = state['current_count_id']
            
            if c_id is None:
                # INSERT NEW
                cursor.execute("INSERT INTO inventory_counts(description) VALUES (?)", ("Sayım Fişi",))
                c_id = cursor.lastrowid
                
                for item in pending_items:
                    # Insert item
                    cursor.execute("""
                        INSERT INTO inventory_count_items(count_id, product_id, product_name, warehouse_id, warehouse_name, old_stock, new_stock)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (c_id, product_map.get(item['product']), item['product'], item['wh_id'], item['wh_name'], item['old'], item['new']))
                    
                    # Update Stock
                    delta = item['new'] - item['old']
                    if abs(delta) > 1e-9:
                        if delta > 0:
                            ps.increment_stock(conn, cursor, item['product'], delta, warehouse_id=item['wh_id'])
                        else:
                            ps.decrement_stock(conn, cursor, item['product'], -delta, warehouse_id=item['wh_id'])
            else:
                # UPDATE EXISTING
                # 1. Get current DB items to handle updates and deletions
                cursor.execute("SELECT id, product_name, warehouse_id, old_stock, new_stock FROM inventory_count_items WHERE count_id=?", (c_id,))
                db_rows = cursor.fetchall()
                db_items_map = {row[0]: {'product': row[1], 'wh_id': row[2], 'old': row[3], 'new': row[4]} for row in db_rows}
                
                # 2. Process pending items (Updates & Inserts)
                for item in pending_items:
                    item_id = item.get('id')
                    
                    if item_id and item_id in db_items_map:
                        # UPDATE existing item
                        db_item = db_items_map.pop(item_id) # Remove from map, so we know it's handled
                        saved_new = db_item['new']
                        
                        # Calculate adjustment based on difference from PREVIOUSLY SAVED new_stock
                        adjustment = item['new'] - saved_new
                        
                        if abs(adjustment) > 1e-9:
                            # Update stock
                            if adjustment > 0:
                                ps.increment_stock(conn, cursor, item['product'], adjustment, warehouse_id=item['wh_id'])
                            else:
                                ps.decrement_stock(conn, cursor, item['product'], -adjustment, warehouse_id=item['wh_id'])
                            
                            # Update DB
                            cursor.execute("UPDATE inventory_count_items SET new_stock=? WHERE id=?", (item['new'], item_id))
                    else:
                        # INSERT new item into existing count
                        cursor.execute("""
                            INSERT INTO inventory_count_items(count_id, product_id, product_name, warehouse_id, warehouse_name, old_stock, new_stock)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (c_id, product_map.get(item['product']), item['product'], item['wh_id'], item['wh_name'], item['old'], item['new']))
                        
                        delta = item['new'] - item['old']
                        if abs(delta) > 1e-9:
                            if delta > 0:
                                ps.increment_stock(conn, cursor, item['product'], delta, warehouse_id=item['wh_id'])
                            else:
                                ps.decrement_stock(conn, cursor, item['product'], -delta, warehouse_id=item['wh_id'])

                # 3. Handle Deletions (Items remaining in db_items_map)
                for del_id, del_item in db_items_map.items():
                    # Revert the stock change made by this item
                    # Original change was: new - old
                    # To revert, we apply: -(new - old) = old - new
                    revert_amount = del_item['old'] - del_item['new']
                    
                    if abs(revert_amount) > 1e-9:
                        if revert_amount > 0:
                            ps.increment_stock(conn, cursor, del_item['product'], revert_amount, warehouse_id=del_item['wh_id'])
                        else:
                            ps.decrement_stock(conn, cursor, del_item['product'], -revert_amount, warehouse_id=del_item['wh_id'])
                    
                    cursor.execute("DELETE FROM inventory_count_items WHERE id=?", (del_id,))

            conn.commit()
            messagebox.showinfo(t('success'), t('done'))
            reset_form()
            load_history()
            
        except Exception as e:
            conn.rollback()
            messagebox.showerror(t('error'), str(e))

    btn_add.config(command=add_to_list)
    entry_count.bind("<Return>", lambda event: add_to_list())

    # Action Buttons
    action_frame = ttk.Frame(parent, style="Card.TFrame")
    action_frame.pack(fill="x", padx=12, pady=(0,12))
    
    tk.Button(action_frame, text="✏️ " + t('edit'), command=edit_selected,
             bg="#f59e0b", fg="white", font=("Segoe UI", 10, "bold"),
             relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0).pack(side="left", padx=4, pady=8)
             
    tk.Button(action_frame, text="🗑 " + t('delete'), command=delete_selected,
             bg="#ef4444", fg="white", font=("Segoe UI", 10, "bold"),
             relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0).pack(side="left", padx=4, pady=8)

    tk.Button(action_frame, text="💾 " + t('save'), command=save_all,
             bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"),
             relief="flat", padx=20, pady=10, cursor="hand2", borderwidth=0).pack(side="right", padx=4, pady=8)

    if product_names:
        cb_product.set(placeholder_text)
        refresh_info()
    
    load_history()

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
    cols = ("no", t('date'), t('islem_type'), t('tutar'), t('aciklama'))
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
    tree.heading("no", text="No"); tree.column("no", width=50, anchor="center")
    for c in cols[1:]:
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
        for idx, (mid, typ, tutar, acik, created) in enumerate(cs.list_hareketler(cursor, row[0]), 1):
            tree.insert("", "end", text=str(mid), values=(idx, str(created), str(typ), f"{float(tutar):.2f}", str(acik or "")))

    cb.bind("<<ComboboxSelected>>", lambda *_: load_moves())
    if cari_names:
        cb.set(cari_names[0]); load_moves()

def mount_hizmet_listesi(parent):
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="🛠️ " + t('service_list'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Sol: Liste
    left_panel = ttk.Frame(content, style="Card.TFrame"); left_panel.pack(side="left", fill="both", expand=True, padx=(0,8))
    
    columns = ("no", "name", "price", "desc")
    tree = ttk.Treeview(left_panel, columns=columns, show="headings", height=15)
    tree.heading("no", text="No"); tree.column("no", width=50, anchor="center")
    tree.heading("name", text=t('service_name')); tree.column("name", width=200)
    tree.heading("price", text=t('price')); tree.column("price", width=100)
    tree.heading("desc", text=t('description')); tree.column("desc", width=250)
    
    scroll = ttk.Scrollbar(left_panel, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    
    # Sağ: Form
    right_panel = ttk.Frame(content, style="Card.TFrame", width=300); right_panel.pack(side="right", fill="y")
    right_panel.pack_propagate(False)
    
    ttk.Label(right_panel, text=t('new_service'), style="Header.TLabel").pack(pady=10)
    
    ttk.Label(right_panel, text=t('service_name')).pack(anchor="w", padx=10)
    e_name = ttk.Entry(right_panel); e_name.pack(fill="x", padx=10, pady=(0,10))
    
    ttk.Label(right_panel, text=t('price')).pack(anchor="w", padx=10)
    e_price = ttk.Entry(right_panel); e_price.pack(fill="x", padx=10, pady=(0,10))
    
    ttk.Label(right_panel, text=t('description')).pack(anchor="w", padx=10)
    e_desc = ttk.Entry(right_panel); e_desc.pack(fill="x", padx=10, pady=(0,10))
    
    def load_services():
        for i in tree.get_children(): tree.delete(i)
        for idx, s in enumerate(expense_svc.list_services(cursor), 1):
            # s: (id, name, price, desc)
            tree.insert("", "end", text=str(s[0]), values=(idx, s[1], s[2], s[3]))
            
    def save_service():
        name = e_name.get().strip()
        price = e_price.get().strip()
        desc = e_desc.get().strip()
        try:
            expense_svc.add_service(conn, cursor, name, price, desc)
            messagebox.showinfo(t('success'), t('saved'))
            e_name.delete(0, tk.END); e_price.delete(0, tk.END); e_desc.delete(0, tk.END)
            load_services()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))
            
    def delete_service():
        sel = tree.selection()
        if not sel: return
        if messagebox.askyesno(t('confirm'), t('confirm_delete')):
            sid = tree.item(sel[0])["text"]
            expense_svc.delete_service(conn, cursor, sid)
            load_services()

    tk.Button(right_panel, text="💾 " + t('save'), command=save_service, bg=ACCENT, fg="white", relief="flat", padx=10, pady=5).pack(fill="x", padx=10, pady=5)
    tk.Button(right_panel, text="🗑️ " + t('delete'), command=delete_service, bg="#e74c3c", fg="white", relief="flat", padx=10, pady=5).pack(fill="x", padx=10, pady=5)
    
    load_services()

def mount_masraf_ekle(parent):
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="➕ " + t('add_expense'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    form_frame = ttk.Frame(content); form_frame.pack(pady=20)
    
    ttk.Label(form_frame, text=t('expense_title')).grid(row=0, column=0, sticky="w", pady=5)
    e_title = ttk.Entry(form_frame, width=30); e_title.grid(row=0, column=1, pady=5)
    
    ttk.Label(form_frame, text=t('amount')).grid(row=1, column=0, sticky="w", pady=5)
    e_amount = ttk.Entry(form_frame, width=30); e_amount.grid(row=1, column=1, pady=5)
    
    ttk.Label(form_frame, text=t('category')).grid(row=2, column=0, sticky="w", pady=5)
    categories = ["Genel", "Kira", "Fatura", "Personel", "Yemek", "Ulaşım", "Diğer"]
    cb_cat = ttk.Combobox(form_frame, values=categories, width=28); cb_cat.grid(row=2, column=1, pady=5)
    cb_cat.set("Genel")
    
    ttk.Label(form_frame, text=t('description')).grid(row=3, column=0, sticky="w", pady=5)
    e_desc = ttk.Entry(form_frame, width=30); e_desc.grid(row=3, column=1, pady=5)
    
    def save_expense():
        title = e_title.get().strip()
        amount = e_amount.get().strip()
        cat = cb_cat.get()
        desc = e_desc.get().strip()
        try:
            expense_svc.add_expense(conn, cursor, title, amount, cat, desc)
            messagebox.showinfo(t('success'), t('saved'))
            e_title.delete(0, tk.END); e_amount.delete(0, tk.END); e_desc.delete(0, tk.END)
            load_recent_expenses()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))
            
    tk.Button(form_frame, text="💾 " + t('save'), command=save_expense, bg=ACCENT, fg="white", relief="flat", padx=20, pady=10).grid(row=4, column=1, pady=20, sticky="e")
    
    # Son eklenenler listesi
    ttk.Separator(content, orient="horizontal").pack(fill="x", padx=20, pady=10)
    ttk.Label(content, text=t('recent_expenses'), style="Sub.TLabel").pack(anchor="w", padx=20)
    
    columns = ("no", "title", "amount", "cat", "desc", "date")
    tree = ttk.Treeview(content, columns=columns, show="headings", height=8)
    tree.heading("no", text="No"); tree.column("no", width=50, anchor="center")
    tree.heading("title", text=t('expense_title')); tree.column("title", width=150)
    tree.heading("amount", text=t('amount')); tree.column("amount", width=100)
    tree.heading("cat", text=t('category')); tree.column("cat", width=100)
    tree.heading("desc", text=t('description')); tree.column("desc", width=200)
    tree.heading("date", text=t('date')); tree.column("date", width=150)
    tree.pack(fill="both", expand=True, padx=20, pady=10)
    
    def load_recent_expenses():
        for i in tree.get_children(): tree.delete(i)
        for idx, ex in enumerate(expense_svc.list_expenses(cursor), 1):
            # ex: (id, title, amount, cat, desc, date)
            tree.insert("", "end", text=str(ex[0]), values=(idx, ex[1], ex[2], ex[3], ex[4], ex[5]))
            
    load_recent_expenses()

def mount_masraf_raporu(parent):
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="📑 " + t('expense_report'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Filtreler (Basitçe tümünü listele şimdilik)
    
    columns = ("no", "title", "amount", "cat", "desc", "date")
    tree = ttk.Treeview(content, columns=columns, show="headings")
    tree.heading("no", text="No"); tree.column("no", width=50, anchor="center")
    tree.heading("title", text=t('expense_title')); tree.column("title", width=150)
    tree.heading("amount", text=t('amount')); tree.column("amount", width=100)
    tree.heading("cat", text=t('category')); tree.column("cat", width=100)
    tree.heading("desc", text=t('description')); tree.column("desc", width=200)
    tree.heading("date", text=t('date')); tree.column("date", width=150)
    
    scroll = ttk.Scrollbar(content, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    
    total_lbl = ttk.Label(content, text=f"{t('total')}: 0.00", font=("Segoe UI", 12, "bold"))
    total_lbl.pack(pady=10)
    
    def load_data():
        for i in tree.get_children(): tree.delete(i)
        total = 0.0
        for idx, ex in enumerate(expense_svc.list_expenses(cursor), 1):
            # ex: (id, title, amount, cat, desc, date)
            tree.insert("", "end", text=str(ex[0]), values=(idx, ex[1], ex[2], ex[3], ex[4], ex[5]))
            total += float(ex[2])
        total_lbl.config(text=f"{t('total')}: {total:.2f}")
    load_data()

def mount_personel_vardiya(parent):
    from services import personnel_service as ps
    from services import users_service as us
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="🕒 " + t('shift_mgmt'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Sol: Vardiya Listesi
    left_panel = ttk.Frame(content, style="Card.TFrame"); left_panel.pack(side="left", fill="both", expand=True, padx=(0,8))
    
    cols = ("user", "start", "end", "note")
    tree = ttk.Treeview(left_panel, columns=cols, show="headings")
    tree.heading("user", text=t('username')); tree.column("user", width=100)
    tree.heading("start", text=t('start_time')); tree.column("start", width=150)
    tree.heading("end", text=t('end_time')); tree.column("end", width=150)
    tree.heading("note", text=t('note')); tree.column("note", width=150)
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Sağ: İşlemler
    right_panel = ttk.Frame(content, style="Card.TFrame", width=300); right_panel.pack(side="right", fill="y")
    right_panel.pack_propagate(False)
    
    ttk.Label(right_panel, text=t('actions'), style="Header.TLabel").pack(pady=10)
    
    # Kullanıcı Seçimi
    ttk.Label(right_panel, text=t('username')).pack(anchor="w", padx=10)
    users = us.list_users(cursor)
    user_map = {u[1]: u[0] for u in users} # name -> id
    user_names = list(user_map.keys())
    
    cb_user = ttk.Combobox(right_panel, values=user_names, state="readonly")
    cb_user.pack(fill="x", padx=10, pady=(0,10))
    
    ttk.Label(right_panel, text=t('note')).pack(anchor="w", padx=10)
    e_note = ttk.Entry(right_panel); e_note.pack(fill="x", padx=10, pady=(0,10))
    
    lbl_status = ttk.Label(right_panel, text="", font=("Segoe UI", 9, "bold"))
    lbl_status.pack(pady=5)
    
    btn_action = ttk.Button(right_panel, text="-")
    btn_action.pack(fill="x", padx=10, pady=10)
    
    def load_shifts():
        for i in tree.get_children(): tree.delete(i)
        shifts = ps.list_shifts(cursor)
        for s in shifts:
            # s: (id, username, start, end, note)
            tree.insert("", "end", text=str(s[0]), values=(s[1], s[2], s[3] or "-", s[4]))
            
    def check_status(*args):
        uname = cb_user.get()
        if not uname:
            lbl_status.config(text="")
            btn_action.config(state="disabled", text="-")
            return
            
        uid = user_map[uname]
        active = ps.get_active_shift(cursor, uid)
        
        if active:
            # active: (id, start, note)
            lbl_status.config(text=f"🟢 {t('working')}\n{active[1]}", foreground="green")
            btn_action.config(state="normal", text=t('end_shift'), command=lambda: do_end_shift(active[0]))
        else:
            lbl_status.config(text=f"🔴 {t('not_working')}", foreground="red")
            btn_action.config(state="normal", text=t('start_shift'), command=lambda: do_start_shift(uid))
            
    def do_start_shift(uid):
        note = e_note.get().strip()
        ps.start_shift(conn, cursor, uid, note)
        messagebox.showinfo(t('success'), t('shift_started'))
        e_note.delete(0, tk.END)
        load_shifts()
        check_status()
        
    def do_end_shift(sid):
        ps.end_shift(conn, cursor, sid)
        messagebox.showinfo(t('success'), t('shift_ended'))
        load_shifts()
        check_status()
        
    cb_user.bind("<<ComboboxSelected>>", check_status)
    if user_names: cb_user.set(user_names[0]); check_status()
    
    load_shifts()

def mount_personel_maas(parent):
    from services import personnel_service as ps
    from services import users_service as us
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="💳 " + t('salary_advance'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Sol: Liste
    left_panel = ttk.Frame(content, style="Card.TFrame"); left_panel.pack(side="left", fill="both", expand=True, padx=(0,8))
    
    cols = ("user", "amount", "type", "date", "desc")
    tree = ttk.Treeview(left_panel, columns=cols, show="headings")
    tree.heading("user", text=t('username')); tree.column("user", width=100)
    tree.heading("amount", text=t('amount')); tree.column("amount", width=80)
    tree.heading("type", text=t('type')); tree.column("type", width=80)
    tree.heading("date", text=t('date')); tree.column("date", width=120)
    tree.heading("desc", text=t('description')); tree.column("desc", width=150)
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Sağ: Ekleme
    right_panel = ttk.Frame(content, style="Card.TFrame", width=300); right_panel.pack(side="right", fill="y")
    right_panel.pack_propagate(False)
    
    ttk.Label(right_panel, text=t('add_payment'), style="Header.TLabel").pack(pady=10)
    
    ttk.Label(right_panel, text=t('username')).pack(anchor="w", padx=10)
    users = us.list_users(cursor)
    user_map = {u[1]: u[0] for u in users}
    user_names = list(user_map.keys())
    cb_user = ttk.Combobox(right_panel, values=user_names, state="readonly")
    cb_user.pack(fill="x", padx=10, pady=(0,10))
    
    ttk.Label(right_panel, text=t('type')).pack(anchor="w", padx=10)
    cb_type = ttk.Combobox(right_panel, values=[t('salary'), t('advance'), t('bonus')], state="readonly")
    cb_type.set(t('salary'))
    cb_type.pack(fill="x", padx=10, pady=(0,10))
    
    ttk.Label(right_panel, text=t('amount')).pack(anchor="w", padx=10)
    e_amount = ttk.Entry(right_panel); e_amount.pack(fill="x", padx=10, pady=(0,10))
    
    ttk.Label(right_panel, text=t('description')).pack(anchor="w", padx=10)
    e_desc = ttk.Entry(right_panel); e_desc.pack(fill="x", padx=10, pady=(0,10))
    
    def load_payments():
        for i in tree.get_children(): tree.delete(i)
        payments = ps.list_payments(cursor)
        for p in payments:
            # p: (id, username, amount, type, date, desc)
            tree.insert("", "end", text=str(p[0]), values=(p[1], f"{p[2]:.2f}", p[3], p[4], p[5]))
            
    def save_payment():
        uname = cb_user.get()
        if not uname: return
        uid = user_map[uname]
        
        try:
            amt = float(e_amount.get())
        except ValueError:
            messagebox.showerror(t('error'), t('invalid_amount'))
            return
            
        ptype = cb_type.get()
        desc = e_desc.get().strip()
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        ps.add_payment(conn, cursor, uid, amt, ptype, date, desc)
        messagebox.showinfo(t('success'), t('saved'))
        e_amount.delete(0, tk.END); e_desc.delete(0, tk.END)
        load_payments()
        
    tk.Button(right_panel, text="💾 " + t('save'), command=save_payment, bg=ACCENT, fg="white", relief="flat").pack(fill="x", padx=10, pady=10)
    
    load_payments()

def mount_depo_listesi(parent):
    from services import warehouse_service as ws
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="🏬 " + t('warehouse_list'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Sol: Depo Listesi
    left_panel = ttk.Frame(content, style="Card.TFrame"); left_panel.pack(side="left", fill="both", expand=True, padx=(0,8))
    
    cols = ("name", "location")
    tree = ttk.Treeview(left_panel, columns=cols, show="headings")
    tree.heading("name", text=t('name')); tree.column("name", width=150)
    tree.heading("location", text=t('address')); tree.column("location", width=200)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    # Sol Alt: İşlem Butonları
    btn_frame = ttk.Frame(left_panel)
    btn_frame.pack(fill="x", padx=10, pady=(0,10))
    
    # Sağ: Ekleme ve Stok Detayı
    right_panel = ttk.Frame(content, style="Card.TFrame", width=350); right_panel.pack(side="right", fill="y")
    right_panel.pack_propagate(False)
    
    # Ekleme Bölümü
    lbl_form_title = ttk.Label(right_panel, text=t('add'), style="Header.TLabel")
    lbl_form_title.pack(pady=10)
    
    ttk.Label(right_panel, text=t('name')).pack(anchor="w", padx=10)
    e_name = ttk.Entry(right_panel); e_name.pack(fill="x", padx=10, pady=(0,10))
    
    ttk.Label(right_panel, text=t('address')).pack(anchor="w", padx=10)
    e_loc = ttk.Entry(right_panel); e_loc.pack(fill="x", padx=10, pady=(0,10))
    
    editing_id = tk.IntVar(value=0)

    def load_warehouses():
        for i in tree.get_children(): tree.delete(i)
        warehouses = ws.list_warehouses(cursor)
        for w in warehouses:
            # w: (id, name, location, created_at)
            tree.insert("", "end", text=str(w[0]), values=(w[1], w[2]))
            
    def save_warehouse():
        name = e_name.get().strip()
        loc = e_loc.get().strip()
        if not name: return
        
        try:
            if editing_id.get() > 0:
                ws.update_warehouse(conn, cursor, editing_id.get(), name, loc)
                messagebox.showinfo(t('success'), t('updated'))
            else:
                ws.add_warehouse(conn, cursor, name, loc)
                messagebox.showinfo(t('success'), t('saved'))
            
            cancel_edit()
            load_warehouses()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))
            
    def edit_warehouse():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning(t('warning'), t('select_item'))
            return
        
        item = tree.item(sel[0])
        wid = int(item["text"])
        vals = item["values"]
        
        editing_id.set(wid)
        e_name.delete(0, tk.END); e_name.insert(0, vals[0])
        e_loc.delete(0, tk.END); e_loc.insert(0, vals[1])
        
        lbl_form_title.config(text=t('edit'))
        btn_save.config(text="💾 " + t('update_btn'))
        btn_cancel.pack(fill="x", padx=10, pady=5, before=sep_stock)

    def delete_warehouse():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning(t('warning'), t('select_item'))
            return
            
        if messagebox.askyesno(t('confirm'), t('confirm_delete')):
            wid = int(tree.item(sel[0])["text"])
            try:
                ws.delete_warehouse(conn, cursor, wid)
                messagebox.showinfo(t('success'), t('done'))
                load_warehouses()
                # Eğer düzenlenen silindiyse iptal et
                if editing_id.get() == wid:
                    cancel_edit()
            except Exception as e:
                messagebox.showerror(t('error'), str(e))

    def cancel_edit():
        editing_id.set(0)
        e_name.delete(0, tk.END)
        e_loc.delete(0, tk.END)
        lbl_form_title.config(text=t('add'))
        btn_save.config(text="💾 " + t('save'))
        btn_cancel.pack_forget()

    btn_save = tk.Button(right_panel, text="💾 " + t('save'), command=save_warehouse, bg=ACCENT, fg="white", relief="flat")
    btn_save.pack(fill="x", padx=10, pady=10)
    
    sep_stock = ttk.Separator(right_panel, orient="horizontal")
    sep_stock.pack(fill="x", padx=10, pady=10)
    
    btn_cancel = tk.Button(right_panel, text="❌ " + t('cancel_sale'), command=cancel_edit, bg="#e74c3c", fg="white", relief="flat")
    # Başlangıçta gizli
    
    # Sol panel butonları
    tk.Button(btn_frame, text="✏️ " + t('edit'), command=edit_warehouse, bg="#f39c12", fg="white", relief="flat").pack(side="left", fill="x", expand=True, padx=(0,5))
    tk.Button(btn_frame, text="🗑️ " + t('delete'), command=delete_warehouse, bg="#e74c3c", fg="white", relief="flat").pack(side="left", fill="x", expand=True, padx=(5,0))

    # Stok Detayı Bölümü
    ttk.Label(right_panel, text=t('stock_status'), style="Header.TLabel").pack(pady=5)
    
    stock_tree = ttk.Treeview(right_panel, columns=("prod", "qty"), show="headings", height=10)
    stock_tree.heading("prod", text=t('product')); stock_tree.column("prod", width=150)
    stock_tree.heading("qty", text=t('quantity')); stock_tree.column("qty", width=80)
    stock_tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    def on_select(event):
        sel = tree.selection()
        if not sel: return
        wid = tree.item(sel[0])["text"]
        
        for i in stock_tree.get_children(): stock_tree.delete(i)
        stocks = ws.list_warehouse_stocks(cursor, wid)
        for s in stocks:
            # s: (name, quantity, unit)
            stock_tree.insert("", "end", values=(s[0], f"{s[1]} {s[2]}"))
            
    tree.bind("<<TreeviewSelect>>", on_select)
    load_warehouses()

def mount_depo_transfer(parent):
    from services import warehouse_service as ws
    from services import product_service as ps
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="🔄 " + t('transfer'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Form
    f_form = ttk.Frame(content); f_form.pack(padx=20, pady=20)
    
    warehouses = ws.list_warehouses(cursor)
    wh_map = {w[1]: w[0] for w in warehouses}
    wh_names = list(wh_map.keys())
    
    # Kaynak Depo
    ttk.Label(f_form, text=t('source_warehouse')).grid(row=0, column=0, padx=10, pady=10, sticky="e")
    cb_source = ttk.Combobox(f_form, values=wh_names, state="readonly", width=30)
    cb_source.grid(row=0, column=1, padx=10, pady=10)
    
    # Hedef Depo
    ttk.Label(f_form, text=t('target_warehouse')).grid(row=1, column=0, padx=10, pady=10, sticky="e")
    cb_target = ttk.Combobox(f_form, values=wh_names, state="readonly", width=30)
    cb_target.grid(row=1, column=1, padx=10, pady=10)
    
    # Ürün Seçimi
    ttk.Label(f_form, text=t('product')).grid(row=2, column=0, padx=10, pady=10, sticky="e")
    
    # Basit ürün seçimi için combobox (çok ürün varsa yavaş olabilir ama şimdilik yeterli)
    all_prods = ps.list_products(cursor)
    prod_map = {f"{p[1]} ({p[2]})": p[0] for p in all_prods} # Name (Barcode) -> ID
    prod_names = list(prod_map.keys())
    
    cb_prod = ttk.Combobox(f_form, values=prod_names, width=30)
    cb_prod.grid(row=2, column=1, padx=10, pady=10)
    
    # Miktar
    ttk.Label(f_form, text=t('quantity')).grid(row=3, column=0, padx=10, pady=10, sticky="e")
    e_qty = ttk.Entry(f_form, width=32)
    e_qty.grid(row=3, column=1, padx=10, pady=10)
    
    # Açıklama
    ttk.Label(f_form, text=t('description')).grid(row=4, column=0, padx=10, pady=10, sticky="e")
    e_desc = ttk.Entry(f_form, width=32)
    e_desc.grid(row=4, column=1, padx=10, pady=10)
    
    def do_transfer():
        s_name = cb_source.get()
        t_name = cb_target.get()
        p_name = cb_prod.get()
        qty_str = e_qty.get()
        desc = e_desc.get()
        
        if not (s_name and t_name and p_name and qty_str):
            messagebox.showwarning(t('warning'), t('fill_all_fields'))
            return
            
        if s_name == t_name:
            messagebox.showerror(t('error'), "Kaynak ve hedef depo aynı olamaz!")
            return
            
        try:
            qty = float(qty_str)
            sid = wh_map[s_name]
            tid = wh_map[t_name]
            pid = prod_map[p_name]
            
            # User ID şimdilik 1 (admin) varsayalım veya global user'dan alalım
            # main.py'de global 'current_user' var mı? Yoksa 1 gönderelim.
            # Kullanıcı login olduğunda user_id saklanmalı. Şimdilik 1.
            uid = 1 
            
            ws.transfer_stock(conn, cursor, sid, tid, pid, qty, desc, uid)
            messagebox.showinfo(t('success'), t('transfer_success'))
            e_qty.delete(0, tk.END); e_desc.delete(0, tk.END)
            
        except ValueError as ve:
            messagebox.showerror(t('error'), str(ve))
        except Exception as e:
            messagebox.showerror(t('error'), str(e))
            
    tk.Button(f_form, text="🚀 " + t('transfer'), command=do_transfer, bg=ACCENT, fg="white", relief="flat", padx=20, pady=10).grid(row=5, column=1, pady=20)

def mount_depo_hareket(parent):
    from services import warehouse_service as ws
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="📦 " + t('warehouse_movements'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    cols = ("date", "source", "target", "product", "qty", "desc", "user")
    tree = ttk.Treeview(content, columns=cols, show="headings")
    
    tree.heading("date", text=t('date')); tree.column("date", width=120)
    tree.heading("source", text=t('source_warehouse')); tree.column("source", width=120)
    tree.heading("target", text=t('target_warehouse')); tree.column("target", width=120)
    tree.heading("product", text=t('product')); tree.column("product", width=150)
    tree.heading("qty", text=t('quantity')); tree.column("qty", width=80)
    tree.heading("desc", text=t('description')); tree.column("desc", width=150)
    tree.heading("user", text=t('username')); tree.column("user", width=100)
    
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    moves = ws.list_movements(cursor)
    for m in moves:
        # m: (id, source, target, product, qty, date, desc, username)
        tree.insert("", "end", text=str(m[0]), values=(m[5], m[1] or "-", m[2] or "-", m[3], m[4], m[6], m[7]))

def mount_depo_stok_listesi(parent):
    from services import warehouse_service as ws
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="📦 " + t('stock_list'), style="Header.TLabel").pack(side="left", padx=8)
    
    # Filtreler
    filter_frame = ttk.Frame(header); filter_frame.pack(side="right", padx=8)
    
    ttk.Label(filter_frame, text=t('warehouse') + ":").pack(side="left", padx=5)
    
    warehouses = ws.list_warehouses(cursor)
    wh_map = {w[1]: w[0] for w in warehouses}
    wh_names = [t('all')] + list(wh_map.keys())
    
    cb_wh = ttk.Combobox(filter_frame, values=wh_names, state="readonly", width=20)
    cb_wh.set(t('all'))
    cb_wh.pack(side="left", padx=5)
    
    ttk.Label(filter_frame, text=t('search') + ":").pack(side="left", padx=5)
    e_search = ttk.Entry(filter_frame, width=20)
    e_search.pack(side="left", padx=5)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    cols = ("warehouse", "product", "qty", "unit")
    tree = ttk.Treeview(content, columns=cols, show="headings")
    
    tree.heading("warehouse", text=t('warehouse')); tree.column("warehouse", width=150)
    tree.heading("product", text=t('product')); tree.column("product", width=200)
    tree.heading("qty", text=t('quantity')); tree.column("qty", width=100, anchor="center")
    tree.heading("unit", text=t('unit')); tree.column("unit", width=80, anchor="center")
    
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    def load_stocks(event=None):
        for i in tree.get_children(): tree.delete(i)
        
        selected_wh = cb_wh.get()
        search_txt = e_search.get().lower()
        
        if selected_wh == t('all'):
            stocks = ws.list_all_stocks(cursor)
            # stocks: (wh_name, prod_name, qty, unit)
        else:
            wh_id = wh_map.get(selected_wh)
            if not wh_id: return
            raw_stocks = ws.list_warehouse_stocks(cursor, wh_id)
            # raw_stocks: (prod_name, qty, unit)
            stocks = [(selected_wh, s[0], s[1], s[2]) for s in raw_stocks]
            
        for s in stocks:
            wh_name, p_name, qty, unit = s
            if search_txt and search_txt not in p_name.lower():
                continue
            tree.insert("", "end", values=(wh_name, p_name, f"{qty}", unit))
            
    cb_wh.bind("<<ComboboxSelected>>", load_stocks)
    e_search.bind("<KeyRelease>", load_stocks)
    
    load_stocks()


def mount_kasa_hareket(parent):
    from services import cash_service as cs
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="💵 " + t('cash_movements'), style="Header.TLabel").pack(side="left", padx=8)
    
    # Filtreler
    filter_frame = ttk.Frame(header); filter_frame.pack(side="right", padx=8)
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    ttk.Label(filter_frame, text=t('start_date')).pack(side="left", padx=5)
    e_start = ttk.Entry(filter_frame, width=12); e_start.pack(side="left", padx=5)
    e_start.insert(0, today)
    
    ttk.Label(filter_frame, text=t('end_date')).pack(side="left", padx=5)
    e_end = ttk.Entry(filter_frame, width=12); e_end.pack(side="left", padx=5)
    e_end.insert(0, today)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    cols = ("date", "type", "desc", "amount", "direction")
    tree = ttk.Treeview(content, columns=cols, show="headings")
    
    tree.heading("date", text=t('date')); tree.column("date", width=120)
    tree.heading("type", text=t('type')); tree.column("type", width=100)
    tree.heading("desc", text=t('description')); tree.column("desc", width=250)
    tree.heading("amount", text=t('amount')); tree.column("amount", width=100, anchor="e")
    tree.heading("direction", text=t('type')); tree.column("direction", width=80, anchor="center") # Direction header reused 'type' or new key? 'type' is fine or 'direction'
    
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Alt Toplamlar
    footer = ttk.Frame(content); footer.pack(fill="x", padx=10, pady=10)
    lbl_total_in = ttk.Label(footer, text=f"{t('total_in_lbl')}: 0.00", font=("Segoe UI", 10, "bold"), foreground="green")
    lbl_total_in.pack(side="left", padx=10)
    lbl_total_out = ttk.Label(footer, text=f"{t('total_out_lbl')}: 0.00", font=("Segoe UI", 10, "bold"), foreground="red")
    lbl_total_out.pack(side="left", padx=10)
    lbl_balance = ttk.Label(footer, text=f"{t('balance_lbl')}: 0.00", font=("Segoe UI", 10, "bold"))
    lbl_balance.pack(side="right", padx=10)
    
    def load_movements():
        for i in tree.get_children(): tree.delete(i)
        s_date = e_start.get().strip()
        e_date = e_end.get().strip()
        
        moves = cs.get_cash_movements(cursor, s_date, e_date)
        
        t_in = 0.0
        t_out = 0.0
        
        for m in moves:
            # m: {id, date, type, amount, direction, desc}
            tree.insert("", "end", values=(m['date'], m['type'], m['desc'], f"{m['amount']:.2f}", m['direction']))
            if m['direction'] == 'Giriş':
                t_in += m['amount']
            else:
                t_out += m['amount']
                
        lbl_total_in.config(text=f"{t('total_in_lbl')}: {t_in:.2f}")
        lbl_total_out.config(text=f"{t('total_out_lbl')}: {t_out:.2f}")
        lbl_balance.config(text=f"{t('balance_lbl')}: {t_in - t_out:.2f}")
        
    tk.Button(filter_frame, text="🔍 " + t('refresh'), command=load_movements, 
              bg=ACCENT, fg="white", relief="flat").pack(side="left", padx=5)
              
    load_movements()

def mount_kasa_devir(parent):
    from services import cash_service as cs
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="🔁 " + t('cash_closure'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Bugünün Özeti
    today = datetime.now().strftime("%Y-%m-%d")
    summary = cs.get_cash_summary(cursor, today)
    
    f_summary = ttk.Frame(content); f_summary.pack(pady=20)
    
    ttk.Label(f_summary, text=f"{t('date_lbl')}: {today}", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=20)
    
    ttk.Label(f_summary, text=f"{t('total_in_lbl')}:", font=("Segoe UI", 12)).grid(row=1, column=0, padx=20, pady=10, sticky="e")
    ttk.Label(f_summary, text=f"{summary['in']:.2f} ₺", font=("Segoe UI", 12, "bold"), foreground="green").grid(row=1, column=1, padx=20, pady=10, sticky="w")
    
    ttk.Label(f_summary, text=f"{t('total_out_lbl')}:", font=("Segoe UI", 12)).grid(row=2, column=0, padx=20, pady=10, sticky="e")
    ttk.Label(f_summary, text=f"{summary['out']:.2f} ₺", font=("Segoe UI", 12, "bold"), foreground="red").grid(row=2, column=1, padx=20, pady=10, sticky="w")
    
    ttk.Label(f_summary, text=f"{t('end_day_balance')}:", font=("Segoe UI", 14, "bold")).grid(row=3, column=0, padx=20, pady=20, sticky="e")
    ttk.Label(f_summary, text=f"{summary['balance']:.2f} ₺", font=("Segoe UI", 14, "bold"), foreground="#00b0ff").grid(row=3, column=1, padx=20, pady=20, sticky="w")
    
    def close_day():
        # Basitçe bir rapor oluşturup kaydedebiliriz veya sadece mesaj gösterebiliriz
        messagebox.showinfo(t('success'), f"{today} {t('close_day_success')}: {summary['balance']:.2f} ₺")
        
    tk.Button(content, text="✅ " + t('close_day_btn'), command=close_day,
              bg="#28a745", fg="white", font=("Segoe UI", 12, "bold"),
              relief="flat", padx=30, pady=15).pack(pady=20)

def mount_kasa_rapor(parent):
    from services import cash_service as cs
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="📈 " + t('cash_report'), style="Header.TLabel").pack(side="left", padx=8)
    
    # Filtreler
    filter_frame = ttk.Frame(header); filter_frame.pack(side="right", padx=8)
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    ttk.Label(filter_frame, text=t('start_date')).pack(side="left", padx=5)
    e_start = ttk.Entry(filter_frame, width=12); e_start.pack(side="left", padx=5)
    e_start.insert(0, today)
    
    ttk.Label(filter_frame, text=t('end_date')).pack(side="left", padx=5)
    e_end = ttk.Entry(filter_frame, width=12); e_end.pack(side="left", padx=5)
    e_end.insert(0, today)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Rapor Metni
    txt_report = tk.Text(content, font=("Consolas", 10), width=80, height=20)
    txt_report.pack(fill="both", expand=True, padx=10, pady=10)
    
    def generate_report():
        s_date = e_start.get().strip()
        e_date = e_end.get().strip()
        
        moves = cs.get_cash_movements(cursor, s_date, e_date)
        
        # Aggregate
        total_sales = sum(m['amount'] for m in moves if m['type'] == 'Satış')
        total_collection = sum(m['amount'] for m in moves if m['type'] == 'Cari Tahsilat')
        total_payment = sum(m['amount'] for m in moves if m['type'] == 'Cari Ödeme')
        total_expense = sum(m['amount'] for m in moves if m['type'] == 'Masraf')
        
        report = f"{t('cash_report_title')}\n"
        report += f"{t('date_range')}: {s_date} - {e_date}\n"
        report += "-" * 40 + "\n"
        report += f"{t('total_sales_cash')}: {total_sales:10.2f} ₺\n"
        report += f"{t('total_collection')}:      {total_collection:10.2f} ₺\n"
        report += "-" * 40 + "\n"
        report += f"{t('total_inflow')}:         {total_sales + total_collection:10.2f} ₺\n\n"
        
        report += f"{t('total_payment')}:         {total_payment:10.2f} ₺\n"
        report += f"{t('total_expense')}:        {total_expense:10.2f} ₺\n"
        report += "-" * 40 + "\n"
        report += f"{t('total_outflow')}:         {total_payment + total_expense:10.2f} ₺\n\n"
        
        report += "=" * 40 + "\n"
        report += f"{t('net_balance_cap')}:           {(total_sales + total_collection) - (total_payment + total_expense):10.2f} ₺\n"
        
        txt_report.delete("1.0", tk.END)
        txt_report.insert("1.0", report)
        
    tk.Button(filter_frame, text="📊 " + t('report_btn'), command=generate_report, 
              bg=ACCENT, fg="white", relief="flat").pack(side="left", padx=5)
              
    generate_report()

def mount_stok_raporu(parent):
    from services import product_service as ps
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="📊 " + t('stock_report_menu'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Özet Kartları
    summary_frame = ttk.Frame(content); summary_frame.pack(fill="x", padx=10, pady=10)
    
    products = ps.list_products(cursor)
    # p: (id, name, barcode, sale_price, stock, buy_price, unit, category)
    
    total_items = len(products)
    total_qty = sum(p[4] for p in products)
    total_cost = sum(p[5] * p[4] for p in products)
    total_sale = sum(p[3] * p[4] for p in products)
    potential_profit = total_sale - total_cost
    
    def make_card(parent, title, value, color):
        f = tk.Frame(parent, bg=CARD_COLOR, padx=15, pady=10)
        f.pack(side="left", fill="both", expand=True, padx=5)
        tk.Label(f, text=title, font=("Segoe UI", 10), bg=CARD_COLOR, fg="#aaaaaa").pack(anchor="w")
        tk.Label(f, text=value, font=("Segoe UI", 14, "bold"), bg=CARD_COLOR, fg=color).pack(anchor="w")
        return f

    make_card(summary_frame, t('product_count'), str(total_items), "white")
    make_card(summary_frame, t('total_stock'), f"{total_qty:.2f}", "#00b0ff")
    make_card(summary_frame, t('cost_value'), f"{total_cost:.2f} ₺", "#ffc107")
    make_card(summary_frame, t('sales_value'), f"{total_sale:.2f} ₺", "#28a745")
    make_card(summary_frame, t('estimated_profit'), f"{potential_profit:.2f} ₺", "#17a2b8")
    
    # Liste
    cols = ("name", "barcode", "stock", "unit", "buy", "sale", "total_buy", "total_sale")
    tree = ttk.Treeview(content, columns=cols, show="headings")
    
    tree.heading("name", text=t('name')); tree.column("name", width=200)
    tree.heading("barcode", text=t('barcode')); tree.column("barcode", width=120)
    tree.heading("stock", text=t('stock')); tree.column("stock", width=80, anchor="center")
    tree.heading("unit", text=t('unit')); tree.column("unit", width=60, anchor="center")
    tree.heading("buy", text=t('buy_price')); tree.column("buy", width=80, anchor="e")
    tree.heading("sale", text=t('sale_price')); tree.column("sale", width=80, anchor="e")
    tree.heading("total_buy", text=t('total_cost')); tree.column("total_buy", width=100, anchor="e")
    tree.heading("total_sale", text=t('total_sales')); tree.column("total_sale", width=100, anchor="e")
    
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    for p in products:
        t_buy = p[5] * p[4]
        t_sale = p[3] * p[4]
        tree.insert("", "end", values=(p[1], p[2], f"{p[4]:.2f}", p[6], 
                                       f"{p[5]:.2f}", f"{p[3]:.2f}", 
                                       f"{t_buy:.2f}", f"{t_sale:.2f}"))

def mount_cari_raporu(parent):
    from services import cari_service as cs
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="📊 " + t('account_report_menu'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent, style="Card.TFrame"); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    caris = cs.list_all(cursor)
    # c: (id, name, phone, address, balance, cari_type, ...)
    
    # Bakiye < 0: Bize borçlu (Alacağımız var)
    # Bakiye > 0: Biz borçluyuz (Borcumuz var)
    
    total_alacak = sum(abs(c[4]) for c in caris if c[4] < 0)
    total_borc = sum(c[4] for c in caris if c[4] > 0)
    net_balance = sum(c[4] for c in caris) # Pozitifse biz borçluyuz, negatifse alacaklıyız
    
    # Özet
    summary_frame = ttk.Frame(content); summary_frame.pack(fill="x", padx=10, pady=10)
    
    def make_card(parent, title, value, color):
        f = tk.Frame(parent, bg=CARD_COLOR, padx=15, pady=10)
        f.pack(side="left", fill="both", expand=True, padx=5)
        tk.Label(f, text=title, font=("Segoe UI", 10), bg=CARD_COLOR, fg="#aaaaaa").pack(anchor="w")
        tk.Label(f, text=value, font=("Segoe UI", 14, "bold"), bg=CARD_COLOR, fg=color).pack(anchor="w")
        return f
        
    make_card(summary_frame, t('total_receivable_market'), f"{total_alacak:.2f} ₺", "green")
    make_card(summary_frame, t('total_debt_ours'), f"{total_borc:.2f} ₺", "red")
    
    net_text = f"{abs(net_balance):.2f} ₺ " + (t('we_are_creditor') if net_balance < 0 else t('we_are_debtor'))
    net_color = "green" if net_balance < 0 else "red"
    make_card(summary_frame, t('net_status'), net_text, net_color)
    
    # Liste
    cols = ("name", "phone", "type", "balance", "status")
    tree = ttk.Treeview(content, columns=cols, show="headings")
    
    tree.heading("name", text=t('cari_name')); tree.column("name", width=200)
    tree.heading("phone", text=t('phone')); tree.column("phone", width=120)
    tree.heading("type", text=t('cari_type')); tree.column("type", width=100)
    tree.heading("balance", text=t('balance')); tree.column("balance", width=120, anchor="e")
    tree.heading("status", text=t('status')); tree.column("status", width=120, anchor="center")
    
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    for c in caris:
        bal = c[4]
        if bal < 0:
            status = t('debtor_to_us')
            color = "green"
        elif bal > 0:
            status = t('creditor_from_us')
            color = "red"
        else:
            status = "-"
            color = "white"
            
        # Treeview'da satır rengi için tag kullanabiliriz ama şimdilik metin yeterli
        tree.insert("", "end", values=(c[1], c[2], c[5], f"{abs(bal):.2f} ₺", status))

def mount_kasa_raporu(parent):
    mount_kasa_rapor(parent)

def mount_profit_loss_report(parent):
    from services import sales_service as sales_svc
    from services import expense_service as expense_svc
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="📊 " + t('profit_loss_report_menu'), style="Header.TLabel").pack(side="left", padx=8)
    
    # Date Filter
    filt = tk.Frame(parent, bg=CARD_COLOR)
    filt.pack(fill="x", padx=12, pady=(0, 8))
    
    sv_from = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    sv_to = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    
    tk.Label(filt, text="📅 " + t('start_date'), bg=CARD_COLOR, fg=FG_COLOR,
             font=("Segoe UI", 10, "bold")).pack(side="left", padx=(10,6))
    from_entry = ttk.Entry(filt, textvariable=sv_from, width=12, font=("Segoe UI", 11))
    from_entry.pack(side="left", padx=(0,16), ipady=4)
    
    tk.Label(filt, text="📅 " + t('end_date'), bg=CARD_COLOR, fg=FG_COLOR,
             font=("Segoe UI", 10, "bold")).pack(side="left", padx=(10,6))
    to_entry = ttk.Entry(filt, textvariable=sv_to, width=12, font=("Segoe UI", 11))
    to_entry.pack(side="left", padx=(0,12), ipady=4)
    
    content = ttk.Frame(parent, style="Card.TFrame")
    content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Results Container
    results_frame = tk.Frame(content, bg=CARD_COLOR)
    results_frame.pack(fill="both", expand=True, padx=20, pady=20)
    
    def calculate():
        for w in results_frame.winfo_children(): w.destroy()
        
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        try:
            datetime.strptime(frm, "%Y-%m-%d")
            datetime.strptime(to, "%Y-%m-%d")
        except:
            messagebox.showwarning(t('warning'), t('date_format_warning'))
            return
            
        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        
        total_revenue, total_cogs = sales_svc.get_profit_loss_stats(cursor, f"{frm} 00:00:00", to_plus)
        total_expenses = expense_svc.get_total_expenses(cursor, frm, to)
        
        gross_profit = total_revenue - total_cogs
        net_profit = gross_profit - total_expenses
        
        def add_row(label, value, color=FG_COLOR, is_bold=False, size=14):
            row = tk.Frame(results_frame, bg=CARD_COLOR)
            row.pack(fill="x", pady=8)
            font_style = ("Segoe UI", size, "bold") if is_bold else ("Segoe UI", size)
            tk.Label(row, text=label, font=font_style, bg=CARD_COLOR, fg=FG_COLOR).pack(side="left")
            tk.Label(row, text=f"{value:.2f} ₺", font=font_style, bg=CARD_COLOR, fg=color).pack(side="right")
            
        add_row("Toplam Satış (Ciro):", total_revenue, "#10b981", True)
        add_row("Satılan Malın Maliyeti:", total_cogs, "#ef4444")
        
        tk.Frame(results_frame, bg=TEXT_GRAY, height=1).pack(fill="x", pady=10)
        
        add_row("Brüt Kar:", gross_profit, "#00b0ff", True)
        add_row("Toplam Giderler:", total_expenses, "#ef4444")
        
        tk.Frame(results_frame, bg=TEXT_GRAY, height=1).pack(fill="x", pady=10)
        
        net_color = "#10b981" if net_profit >= 0 else "#ef4444"
        add_row("NET KAR/ZARAR:", net_profit, net_color, True, 18)

    # Calculate Button
    btn_calc = tk.Button(filt, text="Hesapla", command=calculate,
                        bg="#00b0ff", fg="white", font=("Segoe UI", 10, "bold"),
                        relief="flat", padx=16, pady=4, cursor="hand2", borderwidth=0)
    btn_calc.pack(side="left", padx=10)
    
    calculate()

def mount_quick_menu_settings(parent):
    from services import quick_menu_service as qms
    from services import product_service as ps
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="⚡ " + t('quick_menu_title'), style="Header.TLabel").pack(side="left", padx=8)
    
    content = ttk.Frame(parent); content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Sol: Liste
    left_panel = ttk.Frame(content, style="Card.TFrame"); left_panel.pack(side="left", fill="both", expand=True, padx=(0,8))
    
    # Liste Filtresi
    filter_frame = ttk.Frame(left_panel); filter_frame.pack(fill="x", padx=10, pady=10)
    ttk.Label(filter_frame, text=t('list_code') + ":").pack(side="left", padx=5)
    
    LISTS = [
        ("main",  t('main_list')),
        ("list_1", t('list_1')),
        ("list_2", t('list_2')),
        ("list_3", t('list_3')),
        ("list_4", t('list_4')),
    ]
    list_map = {l[1]: l[0] for l in LISTS}
    list_names = list(list_map.keys())
    
    cb_list = ttk.Combobox(filter_frame, values=list_names, state="readonly", width=15)
    cb_list.set(list_names[0])
    cb_list.pack(side="left", padx=5)
    
    cols = ("name", "price", "sort")
    tree = ttk.Treeview(left_panel, columns=cols, show="headings", height=15)
    tree.heading("name", text=t('product_name')); tree.column("name", width=150)
    tree.heading("price", text=t('button_price')); tree.column("price", width=80)
    tree.heading("sort", text=t('sort_order')); tree.column("sort", width=50, anchor="center")
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Sağ: Form
    right_panel = ttk.Frame(content, style="Card.TFrame", width=300); right_panel.pack(side="right", fill="y")
    right_panel.pack_propagate(False)
    
    lbl_form_title = ttk.Label(right_panel, text=t('add'), style="Header.TLabel")
    lbl_form_title.pack(pady=10)
    
    # Ürün Arama
    ttk.Label(right_panel, text=t('product_search')).pack(anchor="w", padx=10)
    
    def on_product_search(event):
        if event.keysym in ('Up', 'Down', 'Return', 'Tab'): return
        typed = cb_search.get()
        if len(typed) < 2: return
        results = ps.list_products(cursor, typed)
        cb_search['values'] = [r[1] for r in results]
        
    def on_product_select(event=None):
        name = cb_search.get()
        if not name: return
        results = ps.list_products(cursor, name)
        
        found = None
        # 1. Tam eşleşme ara
        for r in results:
            if r[1] == name:
                found = r
                break
        
        # 2. Bulunamazsa ve sonuç varsa ilkini al (Enter ile seçim için)
        if not found and results:
            found = results[0]
            
        if found:
            cb_search.set(found[1])
            e_name.delete(0, tk.END); e_name.insert(0, found[1])
            e_price.delete(0, tk.END); e_price.insert(0, f"{found[3]:.2f}")

    cb_search = ttk.Combobox(right_panel)
    cb_search.pack(fill="x", padx=10, pady=(0,10))
    cb_search.bind('<KeyRelease>', on_product_search)
    cb_search.bind('<<ComboboxSelected>>', on_product_select)
    cb_search.bind('<Return>', on_product_select)
    
    ttk.Label(right_panel, text=t('product_name')).pack(anchor="w", padx=10)
    e_name = ttk.Entry(right_panel); e_name.pack(fill="x", padx=10, pady=(0,10))
    
    ttk.Label(right_panel, text=t('button_price')).pack(anchor="w", padx=10)
    e_price = ttk.Entry(right_panel); e_price.pack(fill="x", padx=10, pady=(0,10))
    
    ttk.Label(right_panel, text=t('sort_order')).pack(anchor="w", padx=10)
    e_sort = ttk.Entry(right_panel); e_sort.pack(fill="x", padx=10, pady=(0,10))
    e_sort.insert(0, "0")
    
    editing_id = tk.IntVar(value=0)
    
    def load_items(event=None):
        for i in tree.get_children(): tree.delete(i)
        sel_name = cb_list.get()
        if not sel_name: return
        code = list_map[sel_name]
        
        items = qms.list_quick_products(cursor, code)
        for item in items:
            # item: (id, list_code, name, price, sort_order)
            tree.insert("", "end", text=str(item[0]), values=(item[2], f"{item[3]:.2f}", item[4]))
            
    def save_item():
        name = e_name.get().strip()
        try:
            price = float(e_price.get().strip())
            sort = int(e_sort.get().strip())
        except ValueError:
            messagebox.showerror(t('error'), t('invalid_amount'))
            return
            
        if not name: return
        
        sel_name = cb_list.get()
        code = list_map[sel_name]
        
        try:
            if editing_id.get() > 0:
                qms.update_quick_product(conn, cursor, editing_id.get(), code, name, price, sort)
                messagebox.showinfo(t('success'), t('updated'))
            else:
                qms.add_quick_product(conn, cursor, code, name, price, sort)
                messagebox.showinfo(t('success'), t('saved'))
            
            cancel_edit()
            load_items()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))
            
    def edit_item():
        sel = tree.selection()
        if not sel: return
        item = tree.item(sel[0])
        pid = int(item["text"])
        vals = item["values"]
        
        editing_id.set(pid)
        e_name.delete(0, tk.END); e_name.insert(0, vals[0])
        e_price.delete(0, tk.END); e_price.insert(0, vals[1])
        e_sort.delete(0, tk.END); e_sort.insert(0, vals[2])
        
        lbl_form_title.config(text=t('edit'))
        btn_save.config(text="💾 " + t('update_btn'))
        btn_cancel.pack(fill="x", padx=10, pady=5)
        
    def delete_item():
        sel = tree.selection()
        if not sel: return
        if messagebox.askyesno(t('confirm'), t('confirm_delete')):
            pid = int(tree.item(sel[0])["text"])
            qms.delete_quick_product(conn, cursor, pid)
            load_items()
            if editing_id.get() == pid: cancel_edit()
            
    def cancel_edit():
        editing_id.set(0)
        e_name.delete(0, tk.END)
        e_price.delete(0, tk.END)
        e_sort.delete(0, tk.END); e_sort.insert(0, "0")
        lbl_form_title.config(text=t('add'))
        btn_save.config(text="💾 " + t('save'))
        btn_cancel.pack_forget()
        
    btn_save = tk.Button(right_panel, text="💾 " + t('save'), command=save_item, bg=ACCENT, fg="white", relief="flat")
    btn_save.pack(fill="x", padx=10, pady=10)
    
    btn_cancel = tk.Button(right_panel, text="❌ " + t('cancel_sale'), command=cancel_edit, bg="#e74c3c", fg="white", relief="flat")
    
    # Sol panel butonları
    btn_frame = ttk.Frame(left_panel)
    btn_frame.pack(fill="x", padx=10, pady=(0,10))
    tk.Button(btn_frame, text="✏️ " + t('edit'), command=edit_item, bg="#f39c12", fg="white", relief="flat").pack(side="left", fill="x", expand=True, padx=(0,5))
    tk.Button(btn_frame, text="🗑️ " + t('delete'), command=delete_item, bg="#e74c3c", fg="white", relief="flat").pack(side="left", fill="x", expand=True, padx=(5,0))
    
    cb_list.bind("<<ComboboxSelected>>", load_items)
    load_items()


def mount_theme_settings(parent):
    from tkinter import colorchooser
    
    for w in parent.winfo_children(): w.destroy()
    
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12,8))
    ttk.Label(header, text="🎨 " + t('theme_settings'), style="Header.TLabel", font=("Segoe UI", 16, "bold")).pack(side="left", padx=8)
    
    # Main Content Grid
    content = ttk.Frame(parent, style="Card.TFrame")
    content.pack(fill="both", expand=True, padx=12, pady=8)
    
    # Left Panel: Presets
    left_panel = tk.Frame(content, bg=CARD_COLOR)
    left_panel.pack(side="left", fill="both", expand=True, padx=20, pady=20)
    
    tk.Label(left_panel, text=t('theme_select'), font=("Segoe UI", 14, "bold"), bg=CARD_COLOR, fg=FG_COLOR).pack(anchor="w", pady=(0,20))
    
    def apply_preset(bg, fg, sidebar, card, accent):
        save_theme(bg, fg, sidebar, card, accent)
        
    def set_dark():
        apply_preset("#18181c", "#ffffff", "#18181c", "#23232a", "#00b0ff")
        
    def set_light():
        apply_preset("#f5f6fa", "#2c3e50", "#2c3e50", "#ffffff", "#3498db")
    
    # Dark Theme Button
    btn_dark = tk.Button(left_panel, text="🌙 " + t('dark_theme'), command=set_dark, 
              bg="#23232a", fg="white", font=("Segoe UI", 11, "bold"), 
              relief="flat", padx=20, pady=15, cursor="hand2", borderwidth=0)
    btn_dark.pack(fill="x", pady=10)
    
    # Light Theme Button
    btn_light = tk.Button(left_panel, text="☀️ " + t('light_theme'), command=set_light, 
              bg="#f5f6fa", fg="#2c3e50", font=("Segoe UI", 11, "bold"), 
              relief="flat", padx=20, pady=15, cursor="hand2", borderwidth=0)
    btn_light.pack(fill="x", pady=10)
    
    # Separator
    tk.Frame(content, width=1, bg=TEXT_GRAY).pack(side="left", fill="y", pady=20)

    # Right Panel: Custom Colors
    right_panel = tk.Frame(content, bg=CARD_COLOR)
    right_panel.pack(side="right", fill="both", expand=True, padx=20, pady=20)
    
    tk.Label(right_panel, text=t('custom_theme'), font=("Segoe UI", 14, "bold"), bg=CARD_COLOR, fg=FG_COLOR).pack(anchor="w", pady=(0,20))
    
    colors = {
        "theme_bg": {"label": t('bg_color'), "val": BG_COLOR},
        "theme_fg": {"label": t('fg_color'), "val": FG_COLOR},
        "theme_sidebar": {"label": t('sidebar_color'), "val": SIDEBAR_COLOR},
        "theme_card": {"label": t('card_color'), "val": CARD_COLOR},
        "theme_accent": {"label": t('accent_color'), "val": ACCENT},
    }
    
    entries = {}
    
    def pick_color(key):
        curr = entries[key].get()
        color = colorchooser.askcolor(color=curr, title=t('pick_color'))
        if color[1]:
            entries[key].delete(0, tk.END)
            entries[key].insert(0, color[1])
            entries[key].config(bg=color[1], fg="white" if is_dark(color[1]) else "black")
            
    def is_dark(hex_color):
        hex_color = hex_color.lstrip('#')
        try:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return (r*0.299 + g*0.587 + b*0.114) < 128
        except: return True

    for key, data in colors.items():
        row = tk.Frame(right_panel, bg=CARD_COLOR)
        row.pack(fill="x", pady=8)
        
        tk.Label(row, text=data["label"], font=("Segoe UI", 10), bg=CARD_COLOR, fg=FG_COLOR, width=20, anchor="w").pack(side="left")
        
        e = tk.Entry(row, width=12, font=("Consolas", 10))
        e.insert(0, data["val"])
        e.pack(side="left", padx=10, ipady=4)
        try: 
            e.config(bg=data["val"], fg="white" if is_dark(data["val"]) else "black")
        except: pass
        entries[key] = e
        
        tk.Button(row, text="🎨", command=lambda k=key: pick_color(k), 
                 bg=CARD_COLOR, fg=FG_COLOR, relief="flat", cursor="hand2").pack(side="left", padx=5)
        
    def save_custom():
        save_theme(
            entries["theme_bg"].get(),
            entries["theme_fg"].get(),
            entries["theme_sidebar"].get(),
            entries["theme_card"].get(),
            entries["theme_accent"].get()
        )
        
    def save_theme(bg, fg, sidebar, card, accent):
        try:
            cursor.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", ("theme_bg", bg))
            cursor.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", ("theme_fg", fg))
            cursor.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", ("theme_sidebar", sidebar))
            cursor.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", ("theme_card", card))
            cursor.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", ("theme_accent", accent))
            conn.commit()
            messagebox.showinfo(t('success'), t('restart_required'))
        except Exception as e:
            messagebox.showerror(t('error'), str(e))

    tk.Button(right_panel, text="💾 " + t('save'), command=save_custom, 
              bg=ACCENT, fg="white", font=("Segoe UI", 10, "bold"),
              relief="flat", padx=20, pady=12, cursor="hand2", borderwidth=0).pack(fill="x", pady=20)


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
    cols = ("no", t('user'), t('role'))
    tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
    tree.heading("no", text="No"); tree.column("no", anchor="center", width=50)
    tree.heading(t('user'), text=t('user')); tree.column(t('user'), anchor="center", width=200)
    tree.heading(t('role'), text=t('role')); tree.column(t('role'), anchor="center", width=200)
    
    # Zebrastripe
    tree.tag_configure('oddrow', background=BG_COLOR)
    tree.tag_configure('evenrow', background=CARD_COLOR)
    
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
        for idx, row in enumerate(users_svc.list_users(cursor), 1):
            # row: (id, username, role)
            tree.insert("", "end", text=str(row[0]), values=(idx, row[1], row[2]))

    def add_user():
        dialog = tk.Toplevel(parent)
        dialog.title(t('new_user'))
        set_theme(dialog)
        center_window(dialog, 400, 380)
        dialog.resizable(False, False)
        try: dialog.grab_set()
        except: pass

        # Header
        header = tk.Frame(dialog, bg=BG_COLOR)
        header.pack(fill="x", pady=15)
        tk.Label(header, text="👤 " + t('new_user'), font=("Segoe UI", 16, "bold"), bg=BG_COLOR, fg=ACCENT).pack()

        # Form
        form = tk.Frame(dialog, bg=BG_COLOR)
        form.pack(fill="both", expand=True, padx=25)

        # Username
        tk.Label(form, text=t('username'), font=("Segoe UI", 10, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(anchor="w", pady=(5, 2))
        entry_user = ttk.Entry(form, font=("Segoe UI", 11))
        entry_user.pack(fill="x", ipady=4)
        entry_user.focus_set()

        # Password
        tk.Label(form, text=t('password'), font=("Segoe UI", 10, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(anchor="w", pady=(10, 2))
        entry_pass = ttk.Entry(form, font=("Segoe UI", 11), show="*")
        entry_pass.pack(fill="x", ipady=4)

        # Role
        tk.Label(form, text=t('role'), font=("Segoe UI", 10, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(anchor="w", pady=(10, 2))
        combo_role = ttk.Combobox(form, values=["admin", "cashier"], state="readonly", font=("Segoe UI", 11))
        combo_role.set("cashier")
        combo_role.pack(fill="x", ipady=4)

        def save():
            u = entry_user.get().strip()
            p = entry_pass.get().strip()
            r = combo_role.get().strip()

            if not u or not p:
                messagebox.showwarning(t('warning'), t('fill_all_fields'), parent=dialog)
                return

            try:
                users_svc.add_user(conn, cursor, u, p, r)
                load()
                dialog.destroy()
                messagebox.showinfo(t('success'), t('user_added'), parent=parent)
            except sqlite3.IntegrityError:
                messagebox.showerror(t('error'), t('duplicate_user_error'), parent=dialog)
            except ValueError as ve:
                messagebox.showwarning(t('warning'), str(ve), parent=dialog)

        # Buttons
        btn_frame = tk.Frame(dialog, bg=BG_COLOR)
        btn_frame.pack(fill="x", pady=20, padx=25)

        tk.Button(btn_frame, text=t('cancel'), command=dialog.destroy,
                 bg="#ef4444", fg="white", font=("Segoe UI", 10, "bold"),
                 relief="flat", padx=15, pady=8, cursor="hand2", borderwidth=0).pack(side="right", padx=5)
        
        tk.Button(btn_frame, text="✅ " + t('save'), command=save,
                 bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"),
                 relief="flat", padx=15, pady=8, cursor="hand2", borderwidth=0).pack(side="right", padx=5)

    def edit_user():
        sel = tree.selection()
        if not sel: return messagebox.showwarning(t('warning'), t('select_item'))
        item = tree.item(sel[0])
        uid = item["text"]
        uname = item["values"][1]
        role = item["values"][2]
        
        new_u = simpledialog.askstring(t('edit'), t('username'), initialvalue=uname)
        if new_u is None: return
        new_p = simpledialog.askstring(t('edit'), t('new_password'))
        new_r = simpledialog.askstring(t('edit'), t('role'), initialvalue=role) or role
        users_svc.update_user(conn, cursor, int(uid), new_u, new_r, new_p)
        load()

    def delete_user():
        sel = tree.selection()
        if not sel: return messagebox.showwarning(t('warning'), t('select_item'))
        item = tree.item(sel[0])
        uid = item["text"]
        uname = item["values"][1]
        
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
    tree.tag_configure('oddrow', background=BG_COLOR)
    tree.tag_configure('evenrow', background=CARD_COLOR)
    
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
    cols = ("no", t('date'), t('product'), t('quantity'), t('price'), t('total'))
    tree = ttk.Treeview(body, columns=cols, show="headings", height=12)
    tree.heading("no", text="No"); tree.column("no", width=50, anchor="center")
    tree.heading(t('date'), text=t('date')); tree.column(t('date'), width=140, anchor="center")
    tree.heading(t('product'), text=t('product')); tree.column(t('product'), width=220, anchor="w")
    tree.heading(t('quantity'), text=t('quantity')); tree.column(t('quantity'), width=80, anchor="center")
    tree.heading(t('price'), text=t('price')); tree.column(t('price'), width=100, anchor="e")
    tree.heading(t('total'), text=t('total')); tree.column(t('total'), width=110, anchor="e")
    
    # Zebrastripe
    tree.tag_configure('oddrow', background=BG_COLOR)
    tree.tag_configure('evenrow', background=CARD_COLOR)
    
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
    from services import expense_service as expense_svc

    def show_profit_loss():
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            return messagebox.showwarning(t('warning'), t('date_format_warning'))
        
        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        
        # Get data
        total_revenue, total_cogs = sales_svc.get_profit_loss_stats(cursor, f"{frm} 00:00:00", to_plus)
        total_expenses = expense_svc.get_total_expenses(cursor, frm, to)
        
        gross_profit = total_revenue - total_cogs
        net_profit = gross_profit - total_expenses
        
        # Show in a custom dialog
        dialog = tk.Toplevel(parent)
        dialog.title("💰 Kar/Zarar Raporu")
        set_theme(dialog)
        center_window(dialog, 400, 450)
        
        header = tk.Frame(dialog, bg=BG_COLOR)
        header.pack(fill="x", pady=20)
        tk.Label(header, text="Kar/Zarar Analizi", font=("Segoe UI", 18, "bold"), bg=BG_COLOR, fg=ACCENT).pack()
        tk.Label(header, text=f"{frm} - {to}", font=("Segoe UI", 10), bg=BG_COLOR, fg=TEXT_GRAY).pack()
        
        content = tk.Frame(dialog, bg=CARD_COLOR)
        content.pack(fill="both", expand=True, padx=20, pady=(0,20))
        
        def add_row(label, value, color=FG_COLOR, is_bold=False):
            row = tk.Frame(content, bg=CARD_COLOR)
            row.pack(fill="x", pady=8, padx=15)
            font_style = ("Segoe UI", 12, "bold") if is_bold else ("Segoe UI", 12)
            tk.Label(row, text=label, font=font_style, bg=CARD_COLOR, fg=FG_COLOR).pack(side="left")
            tk.Label(row, text=f"{value:.2f} ₺", font=font_style, bg=CARD_COLOR, fg=color).pack(side="right")
            
        add_row("Toplam Satış:", total_revenue, "#10b981")
        add_row("Satılan Malın Maliyeti:", total_cogs, "#ef4444")
        
        tk.Frame(content, bg=TEXT_GRAY, height=1).pack(fill="x", padx=15, pady=5)
        
        add_row("Brüt Kar:", gross_profit, "#00b0ff", True)
        add_row("Toplam Giderler:", total_expenses, "#ef4444")
        
        tk.Frame(content, bg=TEXT_GRAY, height=1).pack(fill="x", padx=15, pady=5)
        
        net_color = "#10b981" if net_profit >= 0 else "#ef4444"
        add_row("NET KAR/ZARAR:", net_profit, net_color, True)
        
        tk.Button(dialog, text="Kapat", command=dialog.destroy,
                 bg=BG_COLOR, fg=FG_COLOR, font=("Segoe UI", 10),
                 relief="flat", padx=20, pady=10).pack(pady=10)

    def load_report():
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            return messagebox.showwarning(t('warning'), t('date_format_warning'))
        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        for r in tree.get_children(): tree.delete(r)
        rows = sales_svc.list_sales_between(cursor, f"{frm} 00:00:00", to_plus)

        t_qty=0; t_sum=0.0
        for idx, (fis_id, ts, pname, qty, price, total) in enumerate(rows, 1):
            ts_disp = (ts or "").replace("T"," ")
            # miktarı virgüllü göstermek için
            qty_disp = f"{float(qty):.3f}" if abs(float(qty) - round(float(qty))) > 1e-6 else str(int(round(float(qty))))
            tree.insert("", "end", text=str(fis_id), values=(idx, ts_disp, pname, qty_disp, f"{float(price):.2f}", f"{float(total):.2f}"))
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
        with open(fname, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=';')
            w.writerow([t('receipt_no'), t('date'), t('product'), t('quantity'), t('price'), t('total')])
            for r in rows: w.writerow([r[0],r[1],r[2],r[3],f"{float(r[4]):.2f}".replace('.', ','),f"{float(r[5]):.2f}".replace('.', ',')])
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
    create_report_button(btns, "💰 Kar/Zarar", show_profit_loss, "#f59e0b")
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
    cols = (t('id'), t('name'), t('phone'), t('tax_office'), t('tax_number'), t('balance'), t('cari_type'))
    tree = ttk.Treeview(left, columns=cols, show="headings", displaycolumns=(t('id'), t('name'), t('phone'), t('tax_office'), t('tax_number'), t('balance'), t('cari_type')))
    
    # Sütun başlıklarını ayarla
    tree.heading(t('id'), text="No") # ID başlığını "No" olarak değiştir
    tree.heading(t('name'), text=t('name'))
    tree.heading(t('phone'), text=t('phone'))
    tree.heading(t('tax_office'), text=t('tax_office'))
    tree.heading(t('tax_number'), text=t('tax_number'))
    tree.heading(t('balance'), text=t('balance'))
    tree.heading(t('cari_type'), text=t('cari_type'))

    tree.column(t('id'), width=40, anchor="center")
    tree.column(t('name'), anchor="w", width=200)
    tree.column(t('phone'), anchor="w", width=120)
    tree.column(t('tax_office'), anchor="w", width=120)
    tree.column(t('tax_number'), anchor="w", width=120)
    tree.column(t('balance'), anchor="e", width=120)
    tree.column(t('cari_type'), anchor="center", width=100)
    
    # Zebrastripe
    tree.tag_configure('oddrow', background=BG_COLOR)
    tree.tag_configure('evenrow', background=CARD_COLOR)
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

    lbl(right, t('tax_office'))
    entry_vergi_dairesi = ent()

    lbl(right, t('tax_number'))
    entry_vergi_no = ent()
    
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
            # Unpack with new columns (8 columns total now)
            if len(row) == 8:
                cari_id, name, phone, address, balance, ctype, vd, vn = row
            else:
                # Fallback for old data if any issue
                cari_id, name, phone, address, balance, ctype = row[:6]
                vd, vn = "", ""

            balance_str = f"{float(balance):.2f} ₺"
            type_str = t('alacakli') if ctype == 'alacakli' else t('borclu')
            
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            color_tag = 'positive' if float(balance) >= 0 else 'negative'
            
            # ID yerine sıra numarası göster (idx + 1)
            # Ancak gerçek ID'yi saklamamız lazım. Treeview'da values listesinde ID'yi tutuyoruz ama
            # ekranda göstermek için values[0]'ı değiştirirsek, seçme işleminde ID'yi alamayız.
            # Bu yüzden values listesine ID'yi en sona ekleyip, displaycolumns ile gizleyebiliriz.
            # Veya daha basiti: values[0] (ID sütunu) içine sıra numarasını yazıp,
            # gerçek ID'yi tree item'ın 'text' özelliğine veya gizli bir sütuna koyabiliriz.
            # Burada en kolayı: ID sütununu "No" olarak kullanmak ve gerçek ID'yi values'un sonuna eklemek.
            # Ancak columns tanımını değiştirmemiz gerekir.
            
            # Mevcut columns: (id, name, phone, tax_office, tax_number, balance, cari_type)
            # Biz values'a şunu vereceğiz: (idx+1, name, phone, vd, vn, balance_str, type_str, cari_id)
            # Ve columns tanımına bir tane daha ekleyeceğiz veya displaycolumns kullanacağız.
            
            # Pratik çözüm:
            # columns listesini değiştirmeden, values[0]'a sıra no yazalım.
            # Gerçek ID'yi tree.insert(..., text=cari_id) ile saklayalım.
            # Seçim yaparken tree.item(sel)['text'] ile ID'yi alalım.
            
            item = tree.insert("", "end", text=str(cari_id), values=(idx+1, name, phone, vd, vn, balance_str, type_str), tags=(tag, color_tag))
        
        update_summary()

    def add_cari():
        try:
            cari_service.add_cari(
                conn, cursor,
                entry_name.get(),
                entry_phone.get(),
                entry_address.get(),
                entry_balance.get(),
                cari_type_var.get(),
                entry_vergi_dairesi.get(),
                entry_vergi_no.get()
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
        
        # ID'yi text özelliğinden al
        cari_id = tree.item(sel[0])["text"]
        try:
            cari_service.update_cari(
                conn, cursor, cari_id,
                entry_name.get(),
                entry_phone.get(),
                entry_address.get(),
                cari_type_var.get(),
                entry_vergi_dairesi.get(),
                entry_vergi_no.get()
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
        
        # ID'yi text özelliğinden al
        cari_id = tree.item(sel[0])["text"]
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
        entry_vergi_dairesi.delete(0, tk.END)
        entry_vergi_no.delete(0, tk.END)
        entry_balance.delete(0, tk.END)
        entry_balance.insert(0, "0")
        cari_type_var.set('alacakli')

    def on_select(e):
        sel = tree.selection()
        if not sel:
            return
        # ID'yi text özelliğinden al
        cari_id = tree.item(sel[0])["text"]
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

            # New fields
            entry_vergi_dairesi.delete(0, tk.END)
            entry_vergi_no.delete(0, tk.END)
            if len(cari) > 6:
                entry_vergi_dairesi.insert(0, cari[6] or "")
                entry_vergi_no.insert(0, cari[7] or "")

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
    from services import warehouse_service as wh_svc
    
    # Ana konteynır (sol menü için)
    main_container = tk.Frame(parent, bg=BG_COLOR)
    main_container.pack(fill="both", expand=True, padx=0, pady=0)
    
    # === SOL MEN��: AÇILIR KAPANIR ===
    # Ana içerik (menü kapalıyken tam ekran)
    content_container = tk.Frame(main_container, bg=BG_COLOR)
    content_container.place(x=0, y=0, relwidth=1.0, relheight=1.0)
    
    # === ÜST BÖLÜM: BARKOD OKUMA VE FİYAT GÖR ===
    top_section = tk.Frame(content_container, bg=BG_COLOR)
    top_section.pack(fill="x", padx=12, pady=(8,4))
    
    # Depo Seçimi
    wh_frame = tk.Frame(top_section, bg=BG_COLOR)
    wh_frame.pack(side="right", padx=(0, 0))
    
    warehouses = wh_svc.list_warehouses(cursor)
    wh_map = {w[1]: w[0] for w in warehouses}
    wh_names = list(wh_map.keys())
    selected_wh_id = tk.IntVar(value=warehouses[0][0] if warehouses else 1)

    tk.Label(wh_frame, text=t('warehouse') + ":", bg=BG_COLOR, fg=FG_COLOR, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 5))
    wh_cb = ttk.Combobox(wh_frame, values=wh_names, state="readonly", width=15, font=("Segoe UI", 10))
    if wh_names:
        wh_cb.set(wh_names[0])
    wh_cb.pack(side="left")
    
    def on_wh_change(event):
        w_name = wh_cb.get()
        if w_name in wh_map:
            selected_wh_id.set(wh_map[w_name])
            
    wh_cb.bind("<<ComboboxSelected>>", on_wh_change)

    # Barkod giriş alanı (sol)
    barcode_frame = tk.Frame(top_section, bg=CARD_COLOR, relief="flat", bd=1)
    barcode_frame.pack(side="left", fill="x", expand=True, padx=(0,8))
    
    tk.Label(barcode_frame, text="📷", font=("Segoe UI", 16), bg=CARD_COLOR, fg=FG_COLOR).pack(side="left", padx=10)
    barcode_entry = tk.Entry(barcode_frame, font=("Segoe UI", 14), bg="#ffffff", fg="#333333",
                             insertbackground="#000000", relief="flat", bd=0)
    barcode_entry.pack(side="left", fill="both", expand=True, padx=0, pady=8, ipady=6)
    barcode_entry.insert(0, t('scan_product_placeholder'))
    barcode_entry.config(fg="#999999")
    
    # FONKSİYONLARI ÖNCE TANIMLA (butonlardan önce)
    def show_product_list():
        """Ürün listesini göster (ara butonuna basıldığında)"""
        search_text = barcode_entry.get().strip()
        if t('scan_product_placeholder') in search_text:
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
        
        cols = ("no", t('name'), t('barcode'), t('price'), t('stock'), t('unit'))
        search_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=15)
        search_tree.heading("no", text="No"); search_tree.column("no", width=50, anchor="center")
        for c in cols[1:]:
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
            idx = 1
            for p in products:
                pid, name, barcode, price, stock, buy_price, unit, category = p
                if filter_text.lower() in name.lower() or filter_text in (barcode or ""):
                    search_tree.insert("", "end", values=(idx, name, barcode or "", f"{float(price):.2f}", 
                                                          f"{float(stock):.2f}", unit or "adet"))
                    idx += 1
        
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
                pname = search_tree.item(sel[0])["values"][1]
                add_product_to_cart(pname, 1)
                
                # Ana ekrandaki arama kutusunu temizle
                try:
                    barcode_entry.delete(0, tk.END)
                    barcode_entry.insert(0, t('scan_product_placeholder'))
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
        if t('scan_product_placeholder') in barcode or not barcode:
            messagebox.showwarning(t('warning'), t('scan_barcode'))
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
             bg=CARD_COLOR, fg=FG_COLOR)
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
    
    product_tree.tag_configure('oddrow', background=BG_COLOR)
    product_tree.tag_configure('evenrow', background=CARD_COLOR)

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
            frame = tk.Frame(product_tree, bg=CARD_COLOR, highlightbackground="black", highlightthickness=1)
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
            qty_entry = tk.Entry(frame, justify="center", font=("Segoe UI", 10, "bold"), bg=CARD_COLOR, fg=FG_COLOR, relief="flat")
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
            frame = tk.Frame(product_tree, bg=CARD_COLOR, highlightbackground="black", highlightthickness=1)
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
            price_entry = tk.Entry(frame, justify="center", font=("Segoe UI", 10, "bold"), bg=CARD_COLOR, fg=FG_COLOR, relief="flat")
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
    paid_label = tk.Label(info_grid, text="0", font=("Segoe UI", 18, "bold"), bg=CARD_COLOR, fg=FG_COLOR)
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
    
    def update_payment_visuals():
        method = payment_var.get()
        try:
            nakit_btn.config(bg="#1a7c34" if method == "NAKİT" else "#28a745")
            pos_btn.config(bg="#117a8b" if method == "credit_card" else "#17a2b8")
            open_acc_btn.config(bg="#d5620a" if method == "AÇIK HESAP" else "#fd7e14")
            fragmented_btn.config(bg="#0056b3" if method == "PARÇALI" else "#007bff")
        except: pass

    def on_nakit_click():
        payment_var.set("NAKİT")
        update_payment_visuals()
        complete_sale()

    def on_pos_click():
        payment_var.set("credit_card")
        update_payment_visuals()
        complete_sale()

    def on_open_acc_click():
        payment_var.set("AÇIK HESAP")
        update_payment_visuals()
        complete_sale()

    def on_fragmented_click():
        items = product_tree.get_children()
        if not items:
            messagebox.showwarning(t('warning'), t('cart_empty'))
            return
        
        total_amount = 0.0
        for item in items:
            vals = product_tree.item(item)["values"]
            try: total_amount += float(str(vals[6]).replace(",", "."))
            except: pass
            
        show_partial_payment_dialog(total_amount)

    nakit_btn = tk.Button(payment_methods_frame, text="💵 " + t('cash_register') + "\n(F8)",
                         font=("Segoe UI", 10, "bold"), bg="#28a745", fg="white",
                         relief="flat", padx=0, pady=14, cursor="hand2", borderwidth=0,
                         activebackground="#218838", command=on_nakit_click)
    nakit_btn.pack(side="left", fill="x", expand=True, padx=2)
    
    pos_btn = tk.Button(payment_methods_frame, text="💳 " + t('pos_payment') + "\n(F9)",
                       font=("Segoe UI", 10, "bold"), bg="#17a2b8", fg="white",
                       relief="flat", padx=0, pady=14, cursor="hand2", borderwidth=0,
                       activebackground="#138496", command=on_pos_click)
    pos_btn.pack(side="left", fill="x", expand=True, padx=2)
    
    open_acc_btn = tk.Button(payment_methods_frame, text="📋 " + t('open_account') + "\n(F10)",
                            font=("Segoe UI", 10, "bold"), bg="#fd7e14", fg="white",
                            relief="flat", padx=0, pady=14, cursor="hand2", borderwidth=0,
                            activebackground="#e96d0b", command=on_open_acc_click)
    open_acc_btn.pack(side="left", fill="x", expand=True, padx=2)
    
    fragmented_btn = tk.Button(payment_methods_frame, text="🔀 " + t('fragmented'),
                              font=("Segoe UI", 10, "bold"), bg="#007bff", fg="white",
                              relief="flat", padx=0, pady=14, cursor="hand2", borderwidth=0,
                              activebackground="#0056b3", command=on_fragmented_click)
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
    selected_customer_id = tk.IntVar(value=0) # Seçilen cari ID

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
        selected_customer_id.set(_cid)
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
    
    # === FONKSİYONLAR ===
    def add_product_to_cart(pname, qty=1):
        """Ürünü sepete ekle"""
        r = product_svc.get_price_stock_by_name(cursor, pname, selected_wh_id.get())
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
        if not barcode or t('scan_product_placeholder') in barcode:
            return
        
        result = product_svc.get_by_barcode(cursor, barcode, selected_wh_id.get())
        if result:
            pid, pname, price, stock, unit = result
            add_product_to_cart(pname, 1)
            barcode_entry.delete(0, tk.END)
            barcode_entry.insert(0, t('scan_product_placeholder'))
            barcode_entry.config(fg="#999999")
        else:
            # Barkod bulunamazsa Ara penceresini aç
            show_product_list()
    
    def barcode_focus_in(event):
        if t('scan_product_placeholder') in barcode_entry.get():
            barcode_entry.delete(0, tk.END)
            barcode_entry.config(fg="#333333")
    
    def barcode_focus_out(event):
        if not barcode_entry.get().strip():
            barcode_entry.insert(0, t('scan_product_placeholder'))
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
                 bg=BG_COLOR, fg=FG_COLOR).pack(pady=(10, 5))
        
        # Bilgi
        info_frame = tk.Frame(content, bg=BG_COLOR)
        info_frame.pack(pady=(0, 20))
        
        tk.Label(info_frame, text=f"{t('total')}: {total_amount:.2f} ₺", font=("Segoe UI", 12, "bold"), 
                 bg=BG_COLOR, fg="#ffc107").pack(pady=5)
        tk.Label(info_frame, text=f"{t('customer')}: {customer_name}", font=("Segoe UI", 10), 
                 bg=BG_COLOR, fg=FG_COLOR).pack()
        
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

    def show_partial_payment_dialog(total_amount):
        dialog = tk.Toplevel(parent)
        dialog.title("PARÇALI ÖDEME AL")
        dialog.geometry("600x400")
        dialog.configure(bg=BG_COLOR)
        dialog.transient(parent)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f'+{x}+{y}')

        # Header
        header = tk.Frame(dialog, bg="#007bff", height=50)
        header.pack(fill="x")
        tk.Label(header, text="PARÇALI ÖDEME AL", font=("Segoe UI", 14, "bold"), bg="#007bff", fg="white").pack(pady=10)

        # Description
        desc = "Parçalı ödeme almak için aşağıdaki formu doldurunuz. Parçalı ödeme \"Açık Hesap\" kaydedilmektedir. Kalan tutar müşteri hesabına borç olarak yazılacaktır."
        tk.Label(dialog, text=desc, font=("Segoe UI", 10), bg=BG_COLOR, fg=FG_COLOR, wraplength=550, justify="left").pack(pady=10, padx=20)

        form_frame = tk.Frame(dialog, bg=BG_COLOR)
        form_frame.pack(pady=10)

        # Styles
        lbl_style = {"font": ("Segoe UI", 14, "bold"), "bg": BG_COLOR, "fg": FG_COLOR, "anchor": "e"}
        entry_font = ("Segoe UI", 14)

        # TOTAL
        tk.Label(form_frame, text="TOPLAM :", **lbl_style).grid(row=0, column=0, padx=10, pady=5, sticky="e")
        lbl_total = tk.Label(form_frame, text=f"{total_amount:.2f}", font=("Segoe UI", 14, "bold"), bg="#dfe6e9", fg="black", width=15, anchor="w")
        lbl_total.grid(row=0, column=1, padx=10, pady=5)

        # CASH
        tk.Label(form_frame, text="NAKİT :", **lbl_style).grid(row=1, column=0, padx=10, pady=5, sticky="e")
        sv_cash = tk.StringVar()
        entry_cash = tk.Entry(form_frame, textvariable=sv_cash, font=entry_font, width=15)
        entry_cash.grid(row=1, column=1, padx=10, pady=5)

        # POS
        tk.Label(form_frame, text="POS :", **lbl_style).grid(row=2, column=0, padx=10, pady=5, sticky="e")
        sv_pos = tk.StringVar()
        entry_pos = tk.Entry(form_frame, textvariable=sv_pos, font=entry_font, width=15)
        entry_pos.grid(row=2, column=1, padx=10, pady=5)

        # REMAINING
        tk.Label(form_frame, text="KALAN :", **lbl_style).grid(row=3, column=0, padx=10, pady=5, sticky="e")
        lbl_remaining = tk.Label(form_frame, text=f"{total_amount:.2f}", font=("Segoe UI", 14, "bold"), bg="#dfe6e9", fg="black", width=15, anchor="w")
        lbl_remaining.grid(row=3, column=1, padx=10, pady=5)

        def update_remaining(*args):
            try:
                cash = float(sv_cash.get().replace(",", ".") or 0)
            except: cash = 0.0
            try:
                pos = float(sv_pos.get().replace(",", ".") or 0)
            except: pos = 0.0
            
            remaining = total_amount - (cash + pos)
            lbl_remaining.config(text=f"{remaining:.2f}")

        sv_cash.trace("w", update_remaining)
        sv_pos.trace("w", update_remaining)

        # Buttons
        btn_frame = tk.Frame(dialog, bg=BG_COLOR)
        btn_frame.pack(side="bottom", fill="x", pady=20, padx=20)

        def do_sale():
            try:
                cash = float(sv_cash.get().replace(",", ".") or 0)
            except: cash = 0.0
            try:
                pos = float(sv_pos.get().replace(",", ".") or 0)
            except: pos = 0.0
            
            remaining = total_amount - (cash + pos)
            
            if remaining < -0.01: # Allow small float error
                messagebox.showwarning("Hata", "Ödenen tutar toplam tutardan fazla olamaz!", parent=dialog)
                return

            # Store data
            global PARTIAL_PAYMENT_DATA
            PARTIAL_PAYMENT_DATA = {
                "total": total_amount,
                "cash": cash,
                "pos": pos,
                "remaining": remaining
            }
            
            payment_var.set("PARÇALI")
            update_payment_visuals()
            dialog.destroy()
            complete_sale()

        tk.Button(btn_frame, text="Kapat", font=("Segoe UI", 10), bg="#007bff", fg="white", command=dialog.destroy, width=10).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Satış Yap", font=("Segoe UI", 10), bg="#28a745", fg="white", command=do_sale, width=10).pack(side="right", padx=5)

        entry_cash.focus_set()
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
            # Ödeme yöntemini standartlaştır
            pm_map = {
                "NAKİT": "cash",
                "credit_card": "credit_card",
                "AÇIK HESAP": "open_account",
                "PARÇALI": "fragmented"
            }
            final_pm = pm_map.get(payment_method, "cash")

            sales_list_for_print = []
            wh_id = selected_wh_id.get()
            for d in sales_data:
                product_svc.decrement_stock(conn, cursor, d['pname'], d['qty'], warehouse_id=wh_id)
                sales_svc.insert_sale_line(conn, cursor, fis_id, d['pname'], d['qty'], d['price'], d['total'], payment_method=final_pm, warehouse_id=wh_id)
                sales_list_for_print.append((d['pname'], d['qty'], d['price'], d['total']))
            
            # CARİ İŞLEMLERİ (Otomatik Cari Oluşturma ve Kayıt)
            # Müşteri adı girildiyse işlem yap
            if customer and customer != t('customer'):
                try:
                    from services import cari_service as cs
                    cid = selected_customer_id.get()
                    
                    # ID yoksa isme göre bul veya oluştur
                    if cid == 0:
                        found = cs.get_by_name(cursor, customer)
                        if found:
                            cid = found[0]
                        else:
                            # Yeni cari oluştur (Varsayılan: Borçlu)
                            try:
                                cs.add_cari(conn, cursor, customer, "", "", 0.0, "borclu")
                                # Yeni oluşturulan ID'yi al
                                found_new = cs.get_by_name(cursor, customer)
                                if found_new:
                                    cid = found_new[0]
                            except Exception as e:
                                print(f"Yeni cari oluşturma hatası: {e}")
                    
                    if cid > 0:
                        # 1. AÇIK HESAP: Sadece borç kaydet
                        if payment_method == "AÇIK HESAP":
                            cs.add_borc(conn, cursor, cid, total_amount, f"Satış Fişi: {fis_id}")
                            
                        # 2. NAKİT veya KART: Borç kaydet VE Alacak (Ödeme) kaydet
                        elif payment_method in ["NAKİT", "credit_card"]:
                            # Satışı borç olarak işle
                            cs.add_borc(conn, cursor, cid, total_amount, f"Satış Fişi: {fis_id}")
                            
                            # Ödemeyi alacak olarak işle
                            desc = "Nakit Ödeme" if payment_method == "NAKİT" else "Kredi Kartı Ödemesi"
                            cs.add_alacak(conn, cursor, cid, total_amount, f"{desc} - Fiş: {fis_id}")
                            
                        # 3. PARÇALI ÖDEME: Sadece kalanı borç kaydet (Mevcut mantık)
                        elif payment_method == "PARÇALI":
                            remaining = PARTIAL_PAYMENT_DATA.get("remaining", 0.0)
                            if remaining > 0.01:
                                cs.add_borc(conn, cursor, cid, remaining, f"Satış Fişi (Parçalı): {fis_id}")

                except Exception as e:
                    print(f"Cari işlem hatası: {e}")

            conn.commit()
            
            # 2. UI Temizle
            for item in product_tree.get_children():
                product_tree.delete(item)
            
            # Frame'leri temizle (Adet ve Fiyat girişleri)
            for f in list(qty_frames.values()): 
                try: f.destroy()
                except: pass
            qty_frames.clear()
            
            for f in list(price_frames.values()): 
                try: f.destroy()
                except: pass
            price_frames.clear()

            customer_entry.delete(0, tk.END)
            selected_customer_id.set(0) # ID sıfırla
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
    
    # Klavye kısayolları
    def keyboard_shortcuts(event):
        """Klavye kısayollarını yönet"""
        if event.keysym == "F7":
            # F7: Fiyat Gör
            show_price()
        elif event.keysym == "F8":
            # F8: Nakit ödeme
            payment_var.set("NAKİT")
            update_payment_visuals()
            complete_sale()
        elif event.keysym == "F9":
            # F9: POS ödeme
            payment_var.set("credit_card")
            update_payment_visuals()
            complete_sale()
        elif event.keysym == "F10":
            # F10: Açık hesap
            payment_var.set("AÇIK HESAP")
            update_payment_visuals()
            complete_sale()
    
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

    # Date Filter
    filt = tk.Frame(parent, bg=CARD_COLOR)
    filt.pack(fill="x", padx=12, pady=(0, 8))
    
    sv_from = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    sv_to = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    
    tk.Label(filt, text="📅 " + t('start_date'), bg=CARD_COLOR, fg=FG_COLOR,
             font=("Segoe UI", 10, "bold")).pack(side="left", padx=(10,6))
    from_entry = ttk.Entry(filt, textvariable=sv_from, width=12, font=("Segoe UI", 11))
    from_entry.pack(side="left", padx=(0,16), ipady=4)
    
    tk.Label(filt, text="📅 " + t('end_date'), bg=CARD_COLOR, fg=FG_COLOR,
             font=("Segoe UI", 10, "bold")).pack(side="left", padx=(10,6))
    to_entry = ttk.Entry(filt, textvariable=sv_to, width=12, font=("Segoe UI", 11))
    to_entry.pack(side="left", padx=(0,12), ipady=4)

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
    tree.tag_configure('oddrow', background=BG_COLOR)
    tree.tag_configure('evenrow', background=CARD_COLOR)
    
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
        
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        try:
            datetime.strptime(frm, "%Y-%m-%d")
            datetime.strptime(to, "%Y-%m-%d")
        except:
            # Fallback if date is invalid
            return

        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        
        # Use list_receipts_between instead of list_recent_receipts
        results = sales_svc.list_receipts_between(cursor, f"{frm} 00:00:00", to_plus)

        for fis_id, ts, sum_total, pay in results:
            ts_disp = (ts or "").replace("T"," ")
            # Ödeme yöntemi ikonlu
            if pay == 'cash' or pay == 'nakit':
                pay_display = "💵 " + t('cash')
            elif pay == 'credit_card':
                pay_display = "💳 " + t('credit_card')
            elif pay == 'open_account':
                pay_display = "📋 " + t('open_account')
            elif pay == 'fragmented':
                pay_display = "🔀 " + t('fragmented')
            else:
                # Bilinmeyen veya eski kayıtlar için varsayılan
                pay_display = "💳 " + t('credit_card') if pay != 'cash' else "💵 " + t('cash')
            
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
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=';')
        w.writerow([t('csv_receipt_no'), t('csv_product'), t('csv_qty'), t('csv_price'), t('csv_total'), t('csv_date')])
        for r in rows: w.writerow([r[0],r[1],r[2],f"{float(r[3]):.2f}".replace('.', ','),f"{float(r[4]):.2f}".replace('.', ','),r[5]])
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
             bg=BG_COLOR, fg=FG_COLOR, wraplength=350).pack(pady=(0, 20))
    
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
    sidebar_state: dict = {"collapsed": True}

    # Sabit başlık (ikon + başlık + daralt butonu)
    header_bar = ttk.Frame(menu_container, style="Card.TFrame")
    header_bar.pack(fill="x", padx=0, pady=(12,6))
    header_label = ttk.Label(header_bar, text="📂 " + t('action_menu'), style="Header.TLabel")
    header_label.pack(side="left", padx=(8,0))
    collapse_btn = tk.Button(header_bar, text="◀", bg=CARD_COLOR, fg=FG_COLOR,
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
        b = tk.Button(parent, text=text, bg=CARD_COLOR, fg=FG_COLOR,
                      font=("Segoe UI",10,"bold"), activebackground=ACCENT,
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
        b = tk.Button(parent, text="   • " + text, bg=CARD_COLOR, fg=FG_COLOR,
                      font=("Segoe UI",9), activebackground=ACCENT,
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
        msub(stock_sub, t('category_mgmt'), lambda: mount_kategori(right_panel))
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
        msub(purchase_sub, t('dispatch_list'), lambda: mount_irsaliye_listesi(right_panel))
        msub(purchase_sub, t('invoice_list'), lambda: mount_fatura_listesi(right_panel))

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
        msub(warehouse_sub, t('stock_list'), lambda: mount_depo_stok_listesi(right_panel))
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
        msub(reports_sub, t('profit_loss_report_menu'), lambda: mount_profit_loss_report(right_panel))

        # Diğer menüler
        mbtn(menu, "🧾 " + t('receipts'), lambda: mount_receipts(right_panel))
        mbtn(menu, "💾 " + t('daily_report'), export_daily_report)
        
        # Ayarlar Menüsü
        settings_header = mbtn(menu, "⚙️ " + t('settings'), None)
        settings_sub = ttk.Frame(menu, style="Card.TFrame")
        settings_visible = {"v": False}
        def toggle_settings():
            if settings_visible["v"]:
                settings_sub.pack_forget(); settings_visible["v"] = False
            else:
                open_section(settings_header, settings_sub, settings_visible)
        settings_header.config(command=toggle_settings)
        register_section(settings_header, settings_sub, settings_visible)
        
        msub(settings_sub, t('quick_menu_settings'), lambda: mount_quick_menu_settings(right_panel))
        msub(settings_sub, t('theme_settings'), lambda: mount_theme_settings(right_panel))
        
    else:
        mbtn(menu, "🛒 " + t('sales'), lambda: mount_sales(right_panel))
        mbtn(menu, "🛑 " + t('cancel_sale'), lambda: mount_cancel_sales(right_panel))
        mbtn(menu, "🧾 " + t('receipts'), lambda: mount_receipts(right_panel))

    # Menüyü daralt/genişlet
    if "locked" not in sidebar_state:
        sidebar_state["locked"] = False

    def apply_menu_collapse():
        collapsed = sidebar_state["collapsed"]
        locked = sidebar_state.get("locked", False)
        
        target_w = 64 if collapsed else 280
        
        # Başlık ve buton güncellemeleri
        if collapsed:
            header_label.config(text="📂")
            collapse_btn.config(text="▶", fg="white")
            
            # Scrollbar'ı gizle
            try:
                menu_scrollbar.pack_forget()
            except: pass
            
            # Alt menüleri kapat
            close_all_sections()
            
            # İkon moduna geç
            for meta in top_buttons:
                try:
                    meta["btn"].config(text=meta["icon"], anchor="center", padx=0)
                except: pass
                
        else:
            header_label.config(text="📂 " + t('action_menu'))
            if locked:
                collapse_btn.config(text="📌", fg="#e74c3c")
            else:
                collapse_btn.config(text="◀", fg="white")
                
            # Metinleri tam hale getir
            for meta in top_buttons:
                try:
                    meta["btn"].config(text=meta["full"], anchor="w", padx=10)
                except: pass
                
            # Scrollbar'ı geri getir
            try:
                menu_scrollbar.pack(side="right", fill="y")
            except: pass

        # Genişliği hemen uygula (Animasyonsuz)
        menu_container.config(width=target_w)
        body.grid_columnconfigure(0, minsize=target_w)
        
        # Varsa önceki animasyonu iptal et (temizlik için)
        if "anim_id" in sidebar_state:
            try:
                main.after_cancel(sidebar_state["anim_id"])
                del sidebar_state["anim_id"]
            except: pass

    def toggle_menu_collapse():
        # Butona basınca kilit durumunu değiştir
        sidebar_state["locked"] = not sidebar_state.get("locked", False)
        
        if sidebar_state["locked"]:
            sidebar_state["collapsed"] = False # Kilitlenince aç
        else:
            # Kilidi açınca hemen kapatma, mouse çıkınca kapanır
            pass
            
        apply_menu_collapse()

    def on_menu_enter(event):
        if sidebar_state["collapsed"]:
            sidebar_state["collapsed"] = False
            apply_menu_collapse()

    def on_menu_leave(event):
        if sidebar_state.get("locked", False):
            return
            
        try:
            x, y = main.winfo_pointerxy()
            widget = main.winfo_containing(x, y)
            # Eğer mouse hala menü üzerindeyse kapatma
            if widget == menu_container or str(widget).startswith(str(menu_container)):
                return
        except: pass
        
        sidebar_state["collapsed"] = True
        apply_menu_collapse()

    collapse_btn.config(command=toggle_menu_collapse)
    
    # Hover olaylarını bağla
    menu_container.bind("<Enter>", on_menu_enter)
    menu_container.bind("<Leave>", on_menu_leave)
    
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