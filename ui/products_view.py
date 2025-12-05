import tkinter as tk
import sqlite3
from tkinter import ttk, messagebox
from services import product_service as product_svc

# Bu modül, Ürünler ekranının çizimini içerir.
# main.py'den conn, cursor ve t fonksiyonu enjekte edilir.

def mount_products(parent, conn, cursor, t,
                   FG_COLOR="#ffffff", BG_COLOR="#18181c", CARD_COLOR="#23232a", ACCENT="#00b0ff"):
    for w in parent.winfo_children():
        w.destroy()  # Clear existing widgets

    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text="📦 " + t('product_management'), style="Header.TLabel").pack(side="left", padx=8)
    search_var = tk.StringVar()
    ttk.Entry(header, textvariable=search_var).pack(side="right", padx=8)
    ttk.Label(header, text=t('search'), style="TLabel").pack(side="right")

    # Ana gövde: sol tarafta liste, sağ tarafta tek sayfa form
    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    left = ttk.Frame(body, style="Card.TFrame"); left.pack(side="left", fill="both", expand=True, padx=(8,4), pady=8)
    right = ttk.Frame(body, style="Card.TFrame"); right.pack(side="left", fill="y", padx=(4,8), pady=8)

    # Liste kolonları: ID, Ad, Barkod, Satış Fiyatı, Stok, Birim, Alış Fiyatı, Kategori
    cols = (t('seq'), t('name'), t('barcode'), t('sale_price'), t('stock'), t('unit'), t('buy_price'), t('category'))
    tree = ttk.Treeview(left, columns=cols, show="headings")
    for c in cols:
        tree.heading(c, text=c)
    tree.column(t('seq'), width=60, anchor="center")
    tree.column(t('name'), anchor="w", width=160)
    tree.column(t('barcode'), anchor="w", width=100)
    tree.column(t('sale_price'), anchor="e", width=90)
    tree.column(t('stock'), anchor="center", width=80)
    tree.column(t('unit'), anchor="center", width=60)
    tree.column(t('buy_price'), anchor="e", width=100)
    tree.column(t('category'), anchor="center", width=100)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    # Tek sayfa form (sağ panel) - Modern ve renkli
    form_header = tk.Label(right, text="📦 " + t('product_info'), bg=CARD_COLOR, fg=ACCENT, font=("Segoe UI", 11, "bold"))
    form_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8,16))

    ttk.Label(right, text=t('name'), font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", padx=10, pady=(8,4))
    name_var = tk.StringVar()
    e_name = ttk.Entry(right, textvariable=name_var, width=26, font=("Segoe UI", 10))
    e_name.grid(row=2, column=0, sticky="ew", padx=10, ipady=4)

    ttk.Label(right, text=t('barcode'), font=("Segoe UI", 9, "bold")).grid(row=3, column=0, sticky="w", padx=10, pady=(12,4))
    barcode_var = tk.StringVar()
    e_barcode = ttk.Entry(right, textvariable=barcode_var, width=26, font=("Segoe UI", 10))
    e_barcode.grid(row=4, column=0, sticky="ew", padx=10, ipady=4)

    ttk.Label(right, text=t('price'), font=("Segoe UI", 9, "bold")).grid(row=5, column=0, sticky="w", padx=10, pady=(12,4))
    price_var = tk.StringVar()
    e_price = ttk.Entry(right, textvariable=price_var, width=26, font=("Segoe UI", 11, "bold"))
    e_price.grid(row=6, column=0, sticky="ew", padx=10, ipady=4)

    ttk.Label(right, text=t('buy_price'), font=("Segoe UI", 9, "bold")).grid(row=7, column=0, sticky="w", padx=10, pady=(12,4))
    buy_price_var = tk.StringVar()
    e_buy_price = ttk.Entry(right, textvariable=buy_price_var, width=26, font=("Segoe UI", 11, "bold"))
    e_buy_price.grid(row=8, column=0, sticky="ew", padx=10, ipady=4)

    ttk.Label(right, text=t('stock'), font=("Segoe UI", 9, "bold")).grid(row=9, column=0, sticky="w", padx=10, pady=(12,4))
    stock_var = tk.StringVar()
    e_stock = ttk.Entry(right, textvariable=stock_var, width=26, font=("Segoe UI", 11, "bold"))
    e_stock.grid(row=10, column=0, sticky="ew", padx=10, ipady=4)

    # Birim seçimi (adet | kg)
    ttk.Label(right, text=t('unit'), font=("Segoe UI", 9, "bold")).grid(row=11, column=0, sticky="w", padx=10, pady=(12,4))
    unit_var = tk.StringVar(value='adet')
    unit_cb = ttk.Combobox(right, textvariable=unit_var, values=[t('adet'), t('kg')], state="readonly", width=24)
    unit_cb.grid(row=12, column=0, sticky="ew", padx=10, ipady=2)

    # Kategori seçimi
    ttk.Label(right, text=t('category'), font=("Segoe UI", 9, "bold")).grid(row=13, column=0, sticky="w", padx=10, pady=(12,4))
    category_var = tk.StringVar()
    category_cb = ttk.Combobox(right, textvariable=category_var, state="readonly", width=24)
    category_cb.grid(row=14, column=0, sticky="ew", padx=10, ipady=2)
    
    # Kategori listesini yükle
    def load_categories():
        try:
            from repositories import category_repository
            cats = category_repository.list_all(cursor)
            cat_names = ["-"] + [c[1] for c in cats]
            category_cb['values'] = cat_names
            if not category_var.get() or category_var.get() not in cat_names:
                category_var.set("-")
        except Exception:
            category_cb['values'] = ["-"]
            category_var.set("-")
    
    load_categories()

    right.grid_columnconfigure(0, weight=1)

    # Seçilen ürün ID'si (0 = seçili yok)
    selected_id = {"value": 0}

    # Alt butonlar
    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))

    def load(filter_text: str = ""):
        nonlocal row_id_map
        row_id_map = {}
        for r in tree.get_children():
            tree.delete(r)
        
        products = product_svc.list_products(cursor, filter_text)
        for idx, (pid, name, barcode, sale_price, stock, buy_price, unit, category) in enumerate(products, 1):
            stock_disp = f"{int(stock)}" if str(unit).lower()=="adet" else f"{float(stock):.3f}"
            item_iid = tree.insert("", "end", values=(idx, name, barcode, f"{float(sale_price):.2f}", stock_disp, unit, f"{float(buy_price):.2f}", category))
            row_id_map[item_iid] = pid

    def clear_form():
        selected_id["value"] = 0
        name_var.set(""); barcode_var.set(""); price_var.set(""); buy_price_var.set(""); stock_var.set(""); unit_var.set('adet')
        category_var.set("-")

    def validate_form(require_complete: bool = True):
        name = name_var.get().strip()
        barcode = barcode_var.get().strip()
        if not name and require_complete:
            messagebox.showwarning(t('warning'), t('product_name'))
            return None
        try:
            sale_price = float(price_var.get().replace(',', '.')) if price_var.get().strip() else (0.0 if not require_complete else None)
        except Exception:
            sale_price = None
        try:
            buy_price = float(buy_price_var.get().replace(',', '.')) if buy_price_var.get().strip() else 0.0
        except Exception:
            buy_price = None
        try:
            stock = float(stock_var.get().replace(',', '.')) if stock_var.get().strip() else (0.0 if not require_complete else None)
        except Exception:
            stock = None
        if sale_price is None or buy_price is None or stock is None:
            messagebox.showwarning(t('warning'), t('enter_valid'))
            return None
        # Birimi normalize et (tr/en farkı için)
        u = unit_var.get().strip().lower()
        if u in ('adet', 'piece', 'qty'):
            u = 'adet'
        elif u in ('kg', 'kilogram'):
            u = 'kg'
        else:
            u = 'adet'
        # Kategori ID'sini bul
        cat_id = None
        cat_name = category_var.get().strip()
        if cat_name and cat_name != "-":
            try:
                from repositories import category_repository
                cat = category_repository.get_by_name(cursor, cat_name)
                if cat:
                    cat_id = cat[0]
            except Exception:
                pass
        return name, barcode, sale_price, stock, buy_price, u, cat_id

    # ID eşleştirme haritası (Treeview Item ID -> Real DB ID)
    row_id_map = {}

    def populate_from_selection(_evt=None):
        sel = tree.selection()
        if not sel:
            clear_form(); return
        
        item_iid = sel[0]
        real_pid = row_id_map.get(item_iid)
        
        values = tree.item(item_iid)["values"]
        if len(values) < 8:
            clear_form(); return
        
        # values[0] artık sıra no, real_pid'yi map'ten alıyoruz
        _, name_cur, barcode_cur, sale_price_cur, stock_cur, unit_cur, buy_price_cur, category_cur = values
        
        if real_pid is None:
            # Fallback (eğer map'te yoksa, ki olmalı)
            real_pid = 0

        selected_id["value"] = real_pid
        name_var.set(name_cur)
        barcode_var.set(barcode_cur)
        price_var.set(str(sale_price_cur))
        buy_price_var.set(str(buy_price_cur))
        stock_var.set(str(stock_cur))
        unit_var.set(str(unit_cur).lower() if str(unit_cur).lower() in ('adet','kg') else 'adet')
        
        # Kategoriyi yükle
        category_var.set(str(category_cur) if category_cur else "-")

    tree.bind('<<TreeviewSelect>>', populate_from_selection)

    def add_product():
        res = validate_form(require_complete=True)
        if not res:
            return
        name, barcode, sale_price, stock, buy_price, u, cat_id = res
        try:
            product_svc.add_product(conn, cursor, name, barcode, sale_price, stock, buy_price, unit=u, category_id=cat_id)
            load(search_var.get()); clear_form()
            load_categories()  # Yenile
        except sqlite3.IntegrityError:
            messagebox.showerror(t('error'), t('duplicate_error'))
        except ValueError as ve:
            messagebox.showwarning(t('warning'), str(ve))

    def edit_product():
        if not selected_id["value"]:
            return messagebox.showwarning(t('warning'), t('select_item'))
        res = validate_form(require_complete=True)
        if not res:
            return
        name, barcode, sale_price, stock, buy_price, u, cat_id = res
        try:
            product_svc.update_product(conn, cursor, selected_id["value"], name, barcode, sale_price, stock, buy_price, unit=u, category_id=cat_id)
            load(search_var.get())
            load_categories()  # Yenile
        except sqlite3.IntegrityError:
            messagebox.showerror(t('error'), t('duplicate_error'))
        except ValueError as ve:
            messagebox.showwarning(t('warning'), str(ve))

    def delete_product():
        sel = tree.selection()
        if not sel:
            return messagebox.showwarning(t('warning'), t('select_item'))
        
        item_iid = sel[0]
        real_pid = row_id_map.get(item_iid)
        if not real_pid:
            return
            
        try:
            product_svc.delete_product(conn, cursor, int(real_pid))
            load(search_var.get()); clear_form()
        except Exception as e:
            messagebox.showerror(t('error'), str(e))

    # Modern butonlar - Ürün yönetimi
    def create_product_button(parent, text, command, bg_color):
        btn = tk.Button(parent, text=text, command=command,
                        bg=bg_color, fg="white", font=("Segoe UI", 9, "bold"),
                        activebackground=bg_color, activeforeground="white",
                        relief="flat", padx=14, pady=8, cursor="hand2", borderwidth=0)

        def on_enter(e):
            factor = 1.15 if bg_color in ["#10b981", "#00b0ff"] else 0.85
            new_color = adjust_color_brightness(bg_color, factor)
            btn.config(bg=new_color)

        def on_leave(e):
            btn.config(bg=bg_color)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.pack(side="left", padx=4, pady=8)

    def adjust_color_brightness(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(min(255, max(0, r * factor)))
        g = int(min(255, max(0, g * factor)))
        b = int(min(255, max(0, b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    create_product_button(btns, "💾 " + t('save'), add_product, "#10b981")
    create_product_button(btns, "🔁 " + t('update_btn'), edit_product, "#00b0ff")
    create_product_button(btns, "🗑 " + t('delete'), delete_product, "#ef4444")
    create_product_button(btns, "🧹 " + t('clear_form'), clear_form, "#6b7280")

    refresh_btn = tk.Button(btns, text="🔄 " + t('refresh'), command=lambda: load(search_var.get()),
                            bg="#8b5cf6", fg="white", font=("Segoe UI", 9, "bold"),
                            activebackground="#7c3aed", activeforeground="white",
                            relief="flat", padx=14, pady=8, cursor="hand2", borderwidth=0)
    refresh_btn.pack(side="right", padx=4, pady=8)
    def refresh_hover_in(e):
        refresh_btn.config(bg="#7c3aed")
    def refresh_hover_out(e):
        refresh_btn.config(bg="#8b5cf6")
    refresh_btn.bind("<Enter>", refresh_hover_in)
    refresh_btn.bind("<Leave>", refresh_hover_out)

    search_var.trace_add("write", lambda *_: load(search_var.get()))
    load()
    clear_form()
