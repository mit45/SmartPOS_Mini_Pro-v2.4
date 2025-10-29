import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3, os, sys, csv, subprocess, time, glob, tempfile
from datetime import datetime, date
from PIL import Image, ImageTk # type: ignore
from languages import LANGUAGES

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
"""Veritabanı bağlantısı ve şema kurulumu"""
from pos.db_handler import get_connection, init_schema
DB_PATH = "database.db"
conn, cursor = get_connection(DB_PATH)
init_schema(conn, cursor)

# Dil tercihini yükle
load_language_preference()

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
from reportlab.lib.pagesizes import A4 # type: ignore
from reportlab.lib.units import mm # type: ignore # type: ignore
from reportlab.pdfgen import canvas as pdfcanvas # type: ignore
from reportlab.pdfbase import pdfmetrics # type: ignore
from reportlab.pdfbase.ttfonts import TTFont # type: ignore

FONT_READY = False
try:
    font_path = os.path.join("fonts","DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
        FONT_READY = True
except: pass

def print_receipt(sales_list, fis_id="", customer_name="Müşteri", kdv_rate=18.0, discount_rate=0.0,
                  open_after: bool = True, show_message: bool = True):
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
    c.drawString(25*mm, y, t('receipt_header'))
    y -= 8*mm
    c.setFont(face, 10)
    c.drawString(25*mm, y, f"{t('receipt_no')} {fis_id}")
    y -= 6*mm
    c.drawString(25*mm, y, f"{t('receipt_customer')} {customer_name}")
    y -= 6*mm
    c.drawString(25*mm, y, f"{t('receipt_date')} {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    y -= 8*mm
    c.drawString(25*mm, y, "-"*75); y -= 6*mm

    c.setFont(face, 10)
    c.drawString(25*mm, y, t('receipt_product'))
    c.drawString(90*mm, y, t('receipt_quantity'))
    c.drawString(110*mm, y, t('receipt_price'))
    c.drawString(135*mm, y, t('receipt_total'))
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
    c.drawRightString(155*mm, y, f"{t('receipt_subtotal')} {subtotal:.2f} ₺"); y -= 6*mm
    c.drawRightString(155*mm, y, f"{t('receipt_discount')} ({discount_rate:.1f}%): -{discount_amt:.2f} ₺"); y -= 6*mm
    c.drawRightString(155*mm, y, f"{t('receipt_vat')} ({kdv_rate:.1f}%): +{kdv_amt:.2f} ₺"); y -= 8*mm
    c.setFont(face, 12)
    c.drawRightString(155*mm, y, f"{t('receipt_grand_total')} {grand_total:.2f} ₺"); y -= 10*mm
    c.setFont(face, 10)
    c.drawString(25*mm, y, t('receipt_thank_you'))

    c.save()

    # Windows'ta aç (opsiyonel)
    if open_after:
        try:
            if os.name == "nt":
                os.startfile(filename)  # type: ignore
            else:
                subprocess.call(("open", filename))
        except Exception:
            pass

    if show_message:
        messagebox.showinfo(t('receipt_created'), f"{t('receipt_saved')}\n{filename}")

def print_thermal_receipt(sales_list, fis_id="", customer_name="Müşteri", kdv_rate=18.0, discount_rate=0.0):
    """
    Termal yazıcıya direkt yazdırma fonksiyonu (ESC/POS)
    Sürüm uyumluluğu: python-escpos'un farklı sürümlerinde p.set parametreleri değişebiliyor.
    Bu nedenle set_style yardımcı fonksiyonu ile bold/hizalama/genişlik/yükseklik ayarlarını
    geriye dönük uyumlu biçimde uyguluyoruz.
    """
    try:
        # python-escpos kütüphanesi gerekli
        from escpos.printer import Win32Raw  # Windows için
        # from escpos.printer import Usb  # USB yazıcı için alternatif
        
        # Windows'ta yazıcı adını belirtin (Cihazlar ve Yazıcılar'dan bakabilirsiniz)
        printer_name = "POS-58"  # Yazıcı adınızı buraya yazın
        
        try:
            p = Win32Raw(printer_name)
        except:
            # Eğer yazıcı bulunamazsa kullanıcıya sor
            printer_name = simpledialog.askstring(
                t('printer_setup'),
                t('enter_printer_name'),
                initialvalue="POS-58"
            )
            if not printer_name:
                return
            p = Win32Raw(printer_name)
        
        # Sürüm uyumlu stil ayarı
        def set_style(align='left', bold=False, width=1, height=1):
            """python-escpos sürümleri arasında güvenli set() çağrısı (text_type kullanmadan)"""
            try:
                # Bazı sürümlerde bold parametresi desteklenir
                p.set(align=align, bold=bold, width=width, height=height)
            except TypeError:
                # Bold desteklenmiyorsa sadece align/size ayarla ve ESC/POS ile kalınlığı yönet
                p.set(align=align, width=width, height=height)
                # ESC E n : n=1 bold on, n=0 bold off
                try:
                    p._raw(b"\x1b\x45" + (b"\x01" if bold else b"\x00"))
                except Exception:
                    pass
        
        # Fiş başlığı
        set_style(align='center', bold=True, width=2, height=2)
        p.text(t('receipt_header') + "\n")
        p.text("=" * 32 + "\n")
        
        # Fiş bilgileri
        set_style(align='left', bold=False, width=1, height=1)
        p.text(f"{t('receipt_no')} {fis_id}\n")
        p.text(f"{t('receipt_customer')} {customer_name}\n")
        p.text(f"{t('receipt_date')} {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
        p.text("-" * 32 + "\n")
        
        # Ürün başlıkları
        p.text(f"{t('receipt_product'):<15} {t('receipt_quantity'):>4} {t('receipt_price'):>6} {t('receipt_total'):>7}\n")
        p.text("-" * 32 + "\n")
        
        # Ürünler
        subtotal = 0.0
        for pname, qty, price, line_total in sales_list:
            pname_short = str(pname)[:15]
            p.text(f"{pname_short:<15} {qty:>4} {price:>6.2f} {line_total:>7.2f}\n")
            subtotal += float(line_total)
        
        # Toplamlar
        discount_amt = subtotal * (float(discount_rate)/100.0)
        after_discount = subtotal - discount_amt
        kdv_amt = after_discount * (float(kdv_rate)/100.0)
        grand_total = after_discount + kdv_amt
        
        p.text("-" * 32 + "\n")
        p.text(f"{t('receipt_subtotal'):<20} {subtotal:>11.2f} TL\n")
        p.text(f"{t('receipt_discount')} ({discount_rate:.1f}%):{-discount_amt:>8.2f} TL\n")
        p.text(f"{t('receipt_vat')} ({kdv_rate:.1f}%):  {kdv_amt:>8.2f} TL\n")
        p.text("=" * 32 + "\n")
        
        # Genel toplam (büyük font)
        set_style(align='right', bold=True, width=2, height=2)
        p.text(f"{t('receipt_grand_total')}\n")
        p.text(f"{grand_total:.2f} TL\n")
        
        # Teşekkür
        set_style(align='center', bold=False, width=1, height=1)
        p.text("\n" + t('receipt_thank_you') + "\n")
        
        # Kağıdı kes (yazıcı destekliyorsa)
        p.cut()
        
        messagebox.showinfo(t('success'), t('receipt_printed'))
        
    except ImportError:
        messagebox.showerror(
            t('error'),
            "python-escpos kütüphanesi gerekli!\n\nTerminalden şu komutu çalıştırın:\npip install python-escpos"
        )
    except Exception as e:
        messagebox.showerror(t('error'), f"{t('print_error')}\n\n{str(e)}")

# ==========================
# Gömülü Modüller (tek pencere)
# ==========================
def mount_products(parent):
    for w in parent.winfo_children(): w.destroy()

    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text=t('product_management'), style="Header.TLabel").pack(side="left", padx=8)
    search_var = tk.StringVar()
    ttk.Entry(header, textvariable=search_var).pack(side="right", padx=8)
    ttk.Label(header, text=t('search'), style="TLabel").pack(side="right")

    # Ana gövde: sol tarafta liste, sağ tarafta tek sayfa form
    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    left = ttk.Frame(body, style="Card.TFrame"); left.pack(side="left", fill="both", expand=True, padx=(8,4), pady=8)
    right = ttk.Frame(body, style="Card.TFrame"); right.pack(side="left", fill="y", padx=(4,8), pady=8)

    cols = (t('id'), t('name'), t('barcode'), t('price'), t('stock'))
    tree = ttk.Treeview(left, columns=cols, show="headings")
    for c in cols: tree.heading(c, text=c)
    tree.column(t('id'), width=60, anchor="center")
    tree.column(t('name'), anchor="w", width=180)
    tree.column(t('barcode'), anchor="w", width=120)
    tree.column(t('price'), anchor="e", width=100)
    tree.column(t('stock'), anchor="center", width=90)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    # Tek sayfa form (sağ panel) - Modern ve renkli
    form_header = tk.Label(right, text="📦 ÜRÜN BİLGİLERİ", bg=CARD_COLOR, fg=ACCENT,
                          font=("Segoe UI", 11, "bold"))
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

    ttk.Label(right, text=t('stock'), font=("Segoe UI", 9, "bold")).grid(row=7, column=0, sticky="w", padx=10, pady=(12,4))
    stock_var = tk.StringVar()
    e_stock = ttk.Entry(right, textvariable=stock_var, width=26, font=("Segoe UI", 11, "bold"))
    e_stock.grid(row=8, column=0, sticky="ew", padx=10, ipady=4)

    right.grid_columnconfigure(0, weight=1)

    # Seçilen ürün ID'si (0 = seçili yok)
    selected_id = {"value": 0}

    # Alt butonlar
    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))

    from services import product_service as product_svc

    def load(filter_text=""):
        for r in tree.get_children(): tree.delete(r)
        for pid, name, barcode, price, stock in product_svc.list_products(cursor, filter_text):
            tree.insert("", "end", values=(pid, name, barcode, f"{float(price):.2f}", int(stock)))

    def clear_form():
        selected_id["value"] = 0
        name_var.set(""); barcode_var.set(""); price_var.set(""); stock_var.set("")

    def validate_form(require_complete=True):
        name = name_var.get().strip()
        barcode = barcode_var.get().strip()
        if not name and require_complete:
            messagebox.showwarning(t('warning'), t('product_name'))
            return None
        try:
            price = float(price_var.get().replace(',', '.')) if price_var.get().strip() else (0.0 if not require_complete else None)
        except Exception:
            price = None
        try:
            stock = int(stock_var.get()) if stock_var.get().strip() else (0 if not require_complete else None)
        except Exception:
            stock = None
        if price is None or stock is None:
            messagebox.showwarning(t('warning'), t('enter_valid'))
            return None
        return name, barcode, price, stock

    def populate_from_selection(_evt=None):
        sel = tree.selection()
        if not sel:
            clear_form(); return
        pid, name_cur, barcode_cur, price_cur, stock_cur = tree.item(sel[0])["values"]
        try:
            pid_int = int(pid)
        except Exception:
            pid_int = 0
        selected_id["value"] = pid_int
        name_var.set(name_cur)
        barcode_var.set(barcode_cur)
        price_var.set(str(price_cur))
        stock_var.set(str(stock_cur))

    tree.bind('<<TreeviewSelect>>', populate_from_selection)

    def add_product():
        res = validate_form(require_complete=True)
        if not res: return
        name, barcode, price, stock = res
        try:
            product_svc.add_product(conn, cursor, name, barcode, price, stock)
            load(search_var.get()); clear_form()
        except sqlite3.IntegrityError:
            messagebox.showerror(t('error'), t('duplicate_error'))
        except ValueError as ve:
            messagebox.showwarning(t('warning'), str(ve))

    def edit_product():
        if not selected_id["value"]:
            return messagebox.showwarning(t('warning'), t('select_item'))
        res = validate_form(require_complete=True)
        if not res: return
        name, barcode, price, stock = res
        try:
            product_svc.update_product(conn, cursor, selected_id["value"], name, barcode, price, stock)
            load(search_var.get())
        except sqlite3.IntegrityError:
            messagebox.showerror(t('error'), t('duplicate_error'))
        except ValueError as ve:
            messagebox.showwarning(t('warning'), str(ve))

    def delete_product():
        sel = tree.selection()
        if not sel: return messagebox.showwarning(t('warning'), t('select_item'))
        pid, name = tree.item(sel[0])["values"][:2]
        if messagebox.askyesno(t('confirm'), f"{name} {t('delete_confirm')}"):
            try:
                product_svc.delete_product(conn, cursor, int(pid))
                load(search_var.get()); clear_form()
            except Exception as e:
                messagebox.showerror(t('error'), str(e))

    # Modern butonlar - Ürün yönetimi
    def create_product_button(parent, text, command, bg_color, icon=""):
        btn = tk.Button(parent, text=icon + " " + text, command=command,
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
    
    create_product_button(btns, t('save'), add_product, "#10b981", "💾")
    create_product_button(btns, t('update_btn'), edit_product, "#00b0ff", "🔁")
    create_product_button(btns, t('delete'), delete_product, "#ef4444", "🗑")
    create_product_button(btns, t('clear_form'), clear_form, "#6b7280", "🧹")
    
    refresh_btn = tk.Button(btns, text="🔄 " + t('refresh'), command=lambda: load(search_var.get()),
                           bg="#8b5cf6", fg="white", font=("Segoe UI", 9, "bold"),
                           activebackground="#7c3aed", activeforeground="white",
                           relief="flat", padx=14, pady=8, cursor="hand2", borderwidth=0)
    refresh_btn.pack(side="right", padx=4, pady=8)
    
    def refresh_hover_in(e): refresh_btn.config(bg="#7c3aed")
    def refresh_hover_out(e): refresh_btn.config(bg="#8b5cf6")
    refresh_btn.bind("<Enter>", refresh_hover_in)
    refresh_btn.bind("<Leave>", refresh_hover_out)

    search_var.trace_add("write", lambda *_: load(search_var.get()))
    load()
    clear_form()

def mount_users(parent):
    for w in parent.winfo_children(): w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text=t('user_management'), style="Header.TLabel").pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    cols = (t('id'), t('user'), t('role'))
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for c in cols: tree.heading(c, text=c); tree.column(c, anchor="center", width=160)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))

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

    ttk.Button(btns, text=t('add'), command=add_user).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text=t('edit'), command=edit_user).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text=t('delete'), command=delete_user).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text=t('refresh'), command=load).pack(side="right", padx=6, pady=8)
    load()

def mount_receipts(parent):
    for w in parent.winfo_children(): w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text=t('receipts_title'), style="Header.TLabel").pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    tree = ttk.Treeview(body, columns=(t('file'), t('date')), show="headings")
    tree.heading(t('file'), text=t('file')); tree.heading(t('date'), text=t('date'))
    tree.column(t('file'), width=420); tree.column(t('date'), width=180, anchor="center")
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
                messagebox.showerror(t('error'), f"Açılamadı:\n{e}")

    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))
    ttk.Button(btns, text=t('open_print'), command=open_selected).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text=t('refresh'), command=load).pack(side="right", padx=6, pady=8)
    load()

def mount_reports(parent):
    for w in parent.winfo_children(): w.destroy()
    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text=t('reports_title'), style="Header.TLabel").pack(side="left", padx=8)

    filt = ttk.Frame(parent, style="Card.TFrame"); filt.pack(fill="x", padx=12, pady=8)
    sv_from = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    sv_to   = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
    ttk.Label(filt, text=t('start_date')).pack(side="left", padx=(10,6))
    ttk.Entry(filt, textvariable=sv_from, width=14).pack(side="left", padx=(0,12))
    ttk.Label(filt, text=t('end_date')).pack(side="left", padx=(10,6))
    ttk.Entry(filt, textvariable=sv_to, width=14).pack(side="left", padx=(0,12))

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    cols = (t('receipt_no'), t('date'), t('product'), t('quantity'), t('price'), t('total'))
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for c in cols: tree.heading(c, text=c)
    tree.column(t('receipt_no'), width=140, anchor="center")
    tree.column(t('date'),  width=140, anchor="center")
    tree.column(t('product'),   width=220, anchor="w")
    tree.column(t('quantity'),   width=80,  anchor="center")
    tree.column(t('price'),  width=100, anchor="e")
    tree.column(t('total'),width=110,anchor="e")
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    footer = ttk.Frame(parent, style="Card.TFrame"); footer.pack(fill="x", padx=12, pady=(0,12))
    lbl_sum = ttk.Label(footer, text=f"{t('quantity')}: 0 | {t('total')}: 0.00 ₺", style="TLabel")
    lbl_sum.pack(side="left", padx=10)

    def valid_date(s):
        try: datetime.strptime(s, "%Y-%m-%d"); return True
        except: return False

    from services import sales_service as sales_svc

    def load_report():
        frm, to = sv_from.get().strip(), sv_to.get().strip()
        if not (valid_date(frm) and valid_date(to)):
            return messagebox.showwarning(t('warning'), "Tarih formatı YYYY-MM-DD olmalı.")
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
            return messagebox.showwarning(t('warning'), "Tarih formatı YYYY-MM-DD olmalı.")
        to_plus = datetime.strptime(to, "%Y-%m-%d").replace(hour=23,minute=59,second=59).strftime("%Y-%m-%d %H:%M:%S")
        rows = sales_svc.list_sales_between(cursor, f"{frm} 00:00:00", to_plus)
        if not rows: return messagebox.showinfo("Bilgi","Bu aralıkta satış yok.")
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

    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))
    ttk.Button(btns, text="🔍 Listele", command=load_report).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text=t('export_csv'), command=export_csv).pack(side="left", padx=6, pady=8)

    load_report()

def mount_sales(parent):
    for w in parent.winfo_children(): w.destroy()

    ttk.Label(parent, text=t('sales_screen'), style="Header.TLabel").pack(pady=(10,5))
    ttk.Label(parent, text="Ürünleri sepete ekle, müşteri bilgisi gir, KDV ve indirim uygula.", style="Sub.TLabel").pack()

    top_info = ttk.Frame(parent, style="Card.TFrame"); top_info.pack(fill="x", padx=12, pady=10)
    
    # Müşteri adı
    ttk.Label(top_info, text=t('customer_name'), font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=6, pady=6, sticky="w")
    customer_entry = ttk.Entry(top_info, width=30, font=("Segoe UI", 10))
    customer_entry.grid(row=0, column=1, padx=6, pady=6)

    # KDV
    ttk.Label(top_info, text=t('vat'), font=("Segoe UI", 10, "bold")).grid(row=0, column=2, padx=6, pady=6, sticky="e")
    vat_cb = ttk.Combobox(top_info, values=["%8","%18","Özel"], state="readonly", width=8, font=("Segoe UI", 10))
    vat_cb.set("%18"); vat_cb.grid(row=0, column=3, padx=6, pady=6)

    # Ödeme yöntemi - Modern toggle butonlar
    ttk.Label(top_info, text=t('payment_method'), font=("Segoe UI", 10, "bold")).grid(row=1, column=0, padx=6, pady=6, sticky="w")
    payment_var = tk.StringVar(value='cash')
    pm_box = tk.Frame(top_info, bg=BG_COLOR)
    pm_box.grid(row=1, column=1, padx=6, pady=6, sticky="w")
    
    def create_payment_button(parent, text, value, var):
        def toggle():
            var.set(value)
            update_payment_buttons()
        
        btn = tk.Button(parent, text=text, command=toggle,
                       font=("Segoe UI", 9, "bold"), relief="flat",
                       padx=16, pady=8, cursor="hand2", borderwidth=0)
        btn.pack(side="left", padx=2)
        return btn
    
    cash_btn = create_payment_button(pm_box, "💵 " + t('cash'), 'cash', payment_var)
    card_btn = create_payment_button(pm_box, "💳 " + t('credit_card'), 'card', payment_var)
    
    def update_payment_buttons():
        if payment_var.get() == 'cash':
            cash_btn.config(bg=ACCENT, fg="white", activebackground="#0090dd")
            card_btn.config(bg="#2a2a35", fg=TEXT_GRAY, activebackground="#3a3a45")
        else:
            card_btn.config(bg=ACCENT, fg="white", activebackground="#0090dd")
            cash_btn.config(bg="#2a2a35", fg=TEXT_GRAY, activebackground="#3a3a45")
    
    update_payment_buttons()

    # İndirim
    ttk.Label(top_info, text=t('discount'), font=("Segoe UI", 10, "bold")).grid(row=1, column=2, padx=6, pady=6, sticky="e")
    discount_entry = ttk.Entry(top_info, width=8, font=("Segoe UI", 10))
    discount_entry.insert(0,"0")
    discount_entry.grid(row=1, column=3, padx=6, pady=6)

    # Barkod okuyucu bölümü - BÜYÜK VE VURGULU
    barcode_container = tk.Frame(parent, bg="#1a4d2e", relief="solid", borderwidth=2)
    barcode_container.pack(fill="x", padx=12, pady=12)
    
    barcode_inner = tk.Frame(barcode_container, bg="#1a4d2e")
    barcode_inner.pack(fill="x", padx=3, pady=3)
    
    barcode_icon = tk.Label(barcode_inner, text="📷", font=("Segoe UI", 20), bg="#1a4d2e", fg="white")
    barcode_icon.pack(side="left", padx=(12,8))
    
    barcode_label = tk.Label(barcode_inner, text=t('barcode_scanner').upper(), 
                            font=("Segoe UI", 11, "bold"), bg="#1a4d2e", fg="#4ade80")
    barcode_label.pack(side="left", pady=8)
    
    barcode_entry = tk.Entry(barcode_inner, font=("Segoe UI", 14), width=35,
                            bg="#ffffff", fg="#000000", insertbackground="#000000",
                            relief="flat", borderwidth=0)
    barcode_entry.pack(side="left", padx=(12,12), pady=8, ipady=6)
    barcode_entry.insert(0, "🔍 " + t('scan_barcode'))
    
    # Barkod giriş animasyonu
    def barcode_animate():
        current_bg = barcode_container.cget("bg")
        new_bg = "#1a5d3e" if current_bg == "#1a4d2e" else "#1a4d2e"
        barcode_container.config(bg=new_bg)
        barcode_inner.config(bg=new_bg)
        barcode_icon.config(bg=new_bg)
        barcode_label.config(bg=new_bg)
        if barcode_entry.get().strip() and barcode_entry.get() != "🔍 " + t('scan_barcode'):
            parent.after(150, barcode_animate)
    
    barcode_entry.config(foreground="#999999")

    pick = ttk.Frame(parent, style="Card.TFrame"); pick.pack(fill="x", padx=12, pady=8)
    
    # Ürün seçimi
    ttk.Label(pick, text=t('product')+":", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=6, pady=6)
    cb_product = ttk.Combobox(pick, values=refresh_product_values_for_combo(), state="readonly", width=28, font=("Segoe UI", 10))
    cb_product.grid(row=0, column=1, padx=6, pady=6)

    ttk.Label(pick, text=t('quantity')+":", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, padx=6, pady=6)
    e_qty = ttk.Entry(pick, width=8, font=("Segoe UI", 11, "bold"))
    e_qty.insert(0,"1")
    e_qty.grid(row=0, column=3, padx=6, pady=6)

    ttk.Label(pick, text=t('price')+":", font=("Segoe UI", 9)).grid(row=1, column=0, padx=6, pady=6)
    lbl_price = ttk.Label(pick, text="-", style="Sub.TLabel", font=("Segoe UI", 10, "bold"))
    lbl_price.grid(row=1, column=1, sticky="w", padx=6, pady=6)

    ttk.Label(pick, text=t('stock')+":", font=("Segoe UI", 9)).grid(row=1, column=2, padx=6, pady=6)
    lbl_stock = ttk.Label(pick, text="-", style="Sub.TLabel", font=("Segoe UI", 10, "bold"))
    lbl_stock.grid(row=1, column=3, sticky="w", padx=6, pady=6)

    from services import product_service as product_svc
    from services import sales_service as sales_svc

    def barcode_focus_in(event):
        current = barcode_entry.get()
        if "🔍" in current or current == t('scan_barcode'):
            barcode_entry.delete(0, tk.END)
            barcode_entry.config(foreground="#000000")
            barcode_animate()

    def barcode_focus_out(event):
        if not barcode_entry.get().strip():
            barcode_entry.insert(0, "🔍 " + t('scan_barcode'))
            barcode_entry.config(foreground="#999999")

    def scan_barcode(event):
        barcode = barcode_entry.get().strip().replace("🔍", "").strip()
        if not barcode or barcode == t('scan_barcode'):
            return
        # Barkoda göre ürün bul
        result = product_svc.get_by_barcode(cursor, barcode)
        if not result:
            messagebox.showwarning(t('warning'), f"Barkod bulunamadı: {barcode}")
            barcode_entry.delete(0, tk.END)
            barcode_entry.insert(0, "🔍 " + t('scan_barcode'))
            barcode_entry.config(foreground="#999999")
            return
        pid, pname, price, stock = result
        qty = parse_int_safe(e_qty.get(), 1) or 1
        if qty > stock:
            messagebox.showerror(t('error'), f"Yetersiz stok! (Mevcut: {stock})")
            barcode_entry.delete(0, tk.END)
            barcode_entry.insert(0, "🔍 " + t('scan_barcode'))
            barcode_entry.config(foreground="#999999")
            return
        # Sepete ekle
        line_total = qty * price
        tree.insert("", "end", values=(pname, qty, f"{price:.2f}", f"{line_total:.2f}"))
        update_total_label()
        barcode_entry.delete(0, tk.END)
        barcode_entry.insert(0, "🔍 " + t('scan_barcode'))
        barcode_entry.config(foreground="#999999")
        barcode_entry.focus_set()
        # Başarı efekti
        barcode_container.config(bg="#15803d")
        barcode_inner.config(bg="#15803d")
        barcode_icon.config(bg="#15803d")
        barcode_label.config(bg="#15803d")
        parent.after(300, lambda: [
            barcode_container.config(bg="#1a4d2e"),
            barcode_inner.config(bg="#1a4d2e"),
            barcode_icon.config(bg="#1a4d2e"),
            barcode_label.config(bg="#1a4d2e")
        ])

    barcode_entry.bind("<FocusIn>", barcode_focus_in)
    barcode_entry.bind("<FocusOut>", barcode_focus_out)
    barcode_entry.bind("<Return>", scan_barcode)

    def update_info(*_):
        pname = cb_product.get()
        r = product_svc.get_price_stock_by_name(cursor, pname)
        if r:
            price, stock = r
            lbl_price.config(text=f"{float(price):.2f} ₺")
            lbl_stock.config(text=str(int(stock)))
        else:
            lbl_price.config(text="-"); lbl_stock.config(text="-")
    cb_product.bind("<<ComboboxSelected>>", update_info)

    mid = ttk.Frame(parent, style="Card.TFrame"); mid.pack(fill="both", expand=True, padx=12, pady=10)
    cols = (t('product'), t('quantity'), t('price'), t('total'))
    tree = ttk.Treeview(mid, columns=cols, show="headings", height=12)
    for c in cols: 
        tree.heading(c, text=c)
    tree.column(t('product'), width=280)
    tree.column(t('quantity'), width=80, anchor="center")
    tree.column(t('price'), width=100, anchor="e")
    tree.column(t('total'), width=110, anchor="e")
    
    # Zebrastripe ve hover efekti için tag
    tree.tag_configure('oddrow', background='#1f1f25')
    tree.tag_configure('evenrow', background='#252530')
    
    # Treeview override for hover
    original_insert = tree.insert
    def insert_with_tags(*args, **kwargs):
        item = original_insert(*args, **kwargs)
        idx = tree.index(item)
        tree.item(item, tags=('evenrow',) if idx % 2 == 0 else ('oddrow',))
        return item
    tree.insert = insert_with_tags
    
    tree.pack(fill="both", expand=True)

    # Toplam etiketi - daha büyük ve vurgulu
    total_frame = tk.Frame(parent, bg=CARD_COLOR)
    total_frame.pack(pady=12, fill="x", padx=12)
    total_label = tk.Label(total_frame, text=f"{t('subtotal')} 0.00 ₺", 
                          font=("Segoe UI", 18, "bold"), bg=CARD_COLOR, fg=ACCENT)
    total_label.pack()

    def update_total_label():
        total_sum = 0.0
        for row in tree.get_children():
            total_sum += float(tree.item(row)["values"][3])
        total_label.config(text=f"{t('subtotal')} {total_sum:.2f} ₺")

    def add_to_cart():
        pname = cb_product.get().strip(); qty = parse_int_safe(e_qty.get(), None)
        if not pname or qty is None or qty <= 0:
            return messagebox.showwarning(t('warning'), "Geçerli ürün ve adet girin.")
        r = product_svc.get_price_stock_by_name(cursor, pname)
        if not r:
            return messagebox.showerror(t('error'), "Ürün bulunamadı.")
        price, stock = float(r[0]), int(r[1])
        if qty > stock:
            return messagebox.showerror(t('error'), f"Yetersiz stok! (Mevcut: {stock})")
        line = qty * price
        tree.insert("", "end", values=(pname, qty, f"{price:.2f}", f"{line:.2f}"))
        update_total_label()

    def remove_selected():
        for s in tree.selection(): tree.delete(s)
        update_total_label()

    # Modern butonlar
    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,10))
    
    def create_action_button(parent, text, command, bg_color, icon=""):
        btn = tk.Button(parent, text=icon + " " + text, command=command,
                       bg=bg_color, fg="white", font=("Segoe UI", 10, "bold"),
                       activebackground=bg_color, activeforeground="white",
                       relief="flat", padx=16, pady=10, cursor="hand2", borderwidth=0)
        
        def on_enter(e):
            brightness = 1.2 if "00b0ff" in bg_color or "4ade80" in bg_color else 0.8
            btn.config(bg=adjust_brightness(bg_color, brightness))
        
        def on_leave(e):
            btn.config(bg=bg_color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn
    
    def adjust_brightness(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r, g, b = int(min(255, r * factor)), int(min(255, g * factor)), int(min(255, b * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    create_action_button(btns, t('add_to_cart'), add_to_cart, "#4ade80", "➕").pack(side="left", padx=6, pady=8)
    create_action_button(btns, t('remove_selected'), remove_selected, "#ef4444", "❌").pack(side="left", padx=6, pady=8)

    def confirm_sale():
        rows = tree.get_children()
        if not rows: return messagebox.showwarning(t('warning'), "Sepet boş.")
        customer_name = (customer_entry.get().strip() or t('customer'))
        kdv_text = vat_cb.get()
        discount_val = parse_float_safe(discount_entry.get(), 0.0) or 0.0
        # KDV
        if kdv_text == "%8": vat_rate = 8.0
        elif kdv_text == "%18": vat_rate = 18.0
        else:
            vat_rate = parse_float_safe(simpledialog.askstring("Özel KDV","KDV oranını gir (%):"), 0.0) or 0.0

        # Ödeme yöntemi: ekrandan alınır
        payment_method = payment_var.get() or 'cash'

        fis_id = f"FIS-{datetime.now().strftime('%Y%m%d')}-{os.urandom(3).hex().upper()}"

        sales_list = []
        subtotal = 0.0
        for row in rows:
            pname, qty, price, total = tree.item(row)["values"]
            qty = int(qty); price = float(price); total = float(total)
            # Stok düş
            product_svc.decrement_stock(conn, cursor, pname, qty)
            sales_svc.insert_sale_line(conn, cursor, fis_id, pname, qty, price, total, payment_method=payment_method)
            sales_list.append((pname, qty, price, total))
            subtotal += total

        conn.commit()

        # Kullanıcıya yazıcı seçeneği sun
        print_choice = messagebox.askyesnocancel(
            t('print_receipt'),
            f"{t('receipt_created')}\n\n{t('print_options')}\n\n" +
            f"Evet = {t('thermal_printer')}\n" +
            f"Hayır = PDF\n" +
            f"İptal = {t('no_print')}"
        )
        
        if print_choice is True:  # Evet - Termal yazıcı
            # 1) Termal yazıcıya gönder
            print_thermal_receipt(sales_list, fis_id=fis_id, customer_name=customer_name,
                                kdv_rate=vat_rate, discount_rate=discount_val)
            # 2) Aynı anda sessizce PDF olarak kaydet (açmadan ve mesaj göstermeden)
            print_receipt(sales_list, fis_id=fis_id, customer_name=customer_name,
                          kdv_rate=vat_rate, discount_rate=discount_val,
                          open_after=False, show_message=False)
        elif print_choice is False:  # Hayır - PDF
            print_receipt(sales_list, fis_id=fis_id, customer_name=customer_name,
                          kdv_rate=vat_rate, discount_rate=discount_val)
        # elif print_choice is None: İptal - Yazdırma

        # Bilgi
        # Genel toplam hesaplamak için:
        discount_amount = subtotal * (discount_val/100.0)
        after_discount = subtotal - discount_amount
        vat_amount = after_discount * (vat_rate/100.0)
        grand_total = after_discount + vat_amount

        messagebox.showinfo(t('success'),
            f"{t('customer')}: {customer_name}\n{t('receipt_no')} {fis_id}\n{t('total')}: {grand_total:.2f} ₺")

        # Paneli sıfırla
        for r in tree.get_children(): tree.delete(r)
        update_total_label()
        cb_product.set(""); lbl_price.config(text="-"); lbl_stock.config(text="-")
        customer_entry.delete(0, tk.END)
        discount_entry.delete(0, tk.END); discount_entry.insert(0, "0")

    # Satışı tamamla butonu - BÜYÜK VE VURGULU
    complete_btn_frame = tk.Frame(parent, bg=BG_COLOR)
    complete_btn_frame.pack(pady=(0,16), fill="x", padx=12)
    
    complete_btn = tk.Button(complete_btn_frame, text="✅ " + t('complete_sale').upper(),
                            command=confirm_sale, bg="#10b981", fg="white",
                            font=("Segoe UI", 14, "bold"), relief="flat",
                            padx=40, pady=16, cursor="hand2", borderwidth=0,
                            activebackground="#059669", activeforeground="white")
    
    def complete_hover_in(e):
        complete_btn.config(bg="#059669")
    def complete_hover_out(e):
        complete_btn.config(bg="#10b981")
    
    complete_btn.bind("<Enter>", complete_hover_in)
    complete_btn.bind("<Leave>", complete_hover_out)
    complete_btn.pack(expand=True)

def mount_cancel_sales(parent):
    for w in parent.winfo_children(): w.destroy()

    header = ttk.Frame(parent, style="Card.TFrame"); header.pack(fill="x", padx=12, pady=(12, 8))
    ttk.Label(header, text=t('cancel_sale'), style="Header.TLabel").pack(side="left", padx=8)

    body = ttk.Frame(parent, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=12, pady=8)
    cols = (t('receipt_no'), t('date'), t('total'), t('payment_method'))
    tree = ttk.Treeview(body, columns=cols, show="headings")
    for c in cols: tree.heading(c, text=c)
    tree.column(t('receipt_no'), width=160, anchor="center")
    tree.column(t('date'), width=160, anchor="center")
    tree.column(t('total'), width=120, anchor="e")
    tree.column(t('payment_method'), width=140, anchor="center")
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    from services import sales_service as sales_svc

    def load():
        for r in tree.get_children(): tree.delete(r)
        for fis_id, ts, sum_total, pay in sales_svc.list_recent_receipts(cursor, 200):
            ts_disp = (ts or "").replace("T"," ")
            tree.insert("", "end", values=(fis_id, ts_disp, f"{float(sum_total):.2f}", pay))

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

    btns = ttk.Frame(parent, style="Card.TFrame"); btns.pack(fill="x", padx=12, pady=(0,12))
    ttk.Button(btns, text=t('cancel_receipt'), command=cancel_selected).pack(side="left", padx=6, pady=8)
    ttk.Button(btns, text=t('refresh'), command=load).pack(side="right", padx=6, pady=8)
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
    main.title(f"{t('app_title')} - {role.upper()}")
    set_theme(main); center_window(main, 1080, 720)

    top_bar = ttk.Frame(main, style="Card.TFrame"); top_bar.pack(fill="x", padx=10, pady=(8,4))
    ttk.Label(top_bar, text=f"{t('app_title')} {APP_VERSION}", style="Header.TLabel").pack(side="left", padx=10)
    ttk.Label(top_bar, text=f"Oturum: {role.title()}", style="Sub.TLabel").pack(side="left", padx=8)
    
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
        mbtn(menu, t('sales'), lambda: mount_sales(right_panel))
        mbtn(menu, t('cancel_sale'), lambda: mount_cancel_sales(right_panel))
        mbtn(menu, t('products'), lambda: mount_products(right_panel))
        mbtn(menu, t('users'), lambda: mount_users(right_panel))
        mbtn(menu, t('receipts'), lambda: mount_receipts(right_panel))
        mbtn(menu, t('reports'), lambda: mount_reports(right_panel))
        mbtn(menu, t('daily_report'), export_daily_report)
    else:
        mbtn(menu, t('sales'), lambda: mount_sales(right_panel))
        mbtn(menu, t('cancel_sale'), lambda: mount_cancel_sales(right_panel))
        mbtn(menu, t('receipts'), lambda: mount_receipts(right_panel))

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
    set_theme(login_window); center_window(login_window, 420, 720)

    # Dil Seçici - İyileştirilmiş Tasarım
    lang_container = ttk.Frame(login_window, style="Card.TFrame")
    lang_container.pack(pady=(12, 0), padx=24, fill="x")
    
    lang_frame = tk.Frame(lang_container, bg=CARD_COLOR)
    lang_frame.pack(side="right")
    
    ttk.Label(lang_frame, text="🌐", style="TLabel", font=("Segoe UI", 12)).pack(side="left", padx=(0, 6))
    
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
                       font=("Segoe UI", 9, "bold" if is_active else "normal"),
                       activebackground="#0090dd" if is_active else "#3a3a45",
                       activeforeground="white",
                       relief="flat", padx=12, pady=6,
                       borderwidth=0, cursor="hand2",
                       command=select_lang)
        btn.pack(side="left", padx=2)
        return btn
    
    create_lang_button("tr", "TR", "🇹🇷")
    create_lang_button("en", "EN", "🇬🇧")

    ttk.Label(login_window, text=t('app_title'), style="Header.TLabel").pack(pady=(10, 4))
    ttk.Label(login_window, text=t('subtitle'), style="Sub.TLabel").pack(pady=(0, 12))

    frame = ttk.Frame(login_window, style="Card.TFrame"); frame.pack(pady=10, padx=24, fill="x")
    ttk.Label(frame, text=t('username')).pack(pady=(16,4), anchor="w")
    entry_username = ttk.Entry(frame, font=("Segoe UI",10)); entry_username.pack(pady=(0,8), ipady=3, fill="x", padx=16)

    ttk.Label(frame, text=t('password')).pack(pady=(8,4), anchor="w")
    pw_row = ttk.Frame(frame, style="Card.TFrame"); pw_row.pack(fill="x", padx=16)
    entry_password = ttk.Entry(pw_row, show="*", font=("Segoe UI",10)); entry_password.pack(side="left", fill="x", expand=True)
    btn_toggle_pw = ttk.Button(pw_row, text=f"👁 {t('show')}", command=toggle_password); btn_toggle_pw.pack(side="left", padx=(8,0))

    ttk.Button(frame, text=t('login'), command=login_action).pack(pady=20, ipadx=20)
    login_window.bind("<Return>", lambda e: login_action())
    ttk.Label(login_window, text=f"{APP_VERSION}", style="Sub.TLabel").pack(side="bottom", pady=10)
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
    ttk.Label(main_container, text="SmartPOS Mini Pro", style="Header.TLabel").pack(pady=(0, 5))
    ttk.Label(main_container, text="Please select language / Lütfen dil seçiniz", 
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
