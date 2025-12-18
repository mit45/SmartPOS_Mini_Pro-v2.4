import os
import subprocess
import sqlite3
from datetime import datetime
from tkinter import messagebox
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from languages import LANGUAGES


def get_business_settings():
    """İşletme bilgilerini settings tablosundan çeker"""
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        
        def get_val(key, default=""):
            cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            r = cursor.fetchone()
            return r[0] if r else default
        
        settings = {
            'company_name': get_val('company_name', 'SMARTPOS MINI PRO'),
            'company_address': get_val('company_address', ''),
            'company_phone': get_val('company_phone', ''),
            'tax_office': get_val('tax_office', ''),
            'tax_number': get_val('tax_number', ''),
            'receipt_footer': get_val('receipt_footer', 'Teşekkür ederiz'),
            'currency': get_val('currency', '₺')
        }
        conn.close()
        return settings
    except Exception:
        return {
            'company_name': 'SMARTPOS MINI PRO',
            'company_address': '',
            'company_phone': '',
            'tax_office': '',
            'tax_number': '',
            'receipt_footer': 'Teşekkür ederiz',
            'currency': '₺'
        }


def print_receipt(
    sales_list,
    fis_id: str = "",
    customer_name: str = "Müşteri",
    kdv_rate: float = 18.0,
    discount_rate: float = 0.0,
    vat_included: bool = False,
    open_after: bool = True,
    show_message: bool = True,
    language_code: str = "tr",
):
    """
    PDF fişi üretir ve receipts/ klasörüne kaydeder.
    Tasarım: Gerçek fiş formatı - işletme bilgileri, detaylı hesaplama
    """
    def t(key: str):
        return LANGUAGES.get(language_code, LANGUAGES["tr"]).get(key, key)

    try:
        # İşletme bilgilerini yükle
        biz = get_business_settings()
        
        os.makedirs("receipts", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join("receipts", f"receipt_{ts}.pdf")

        # Font ayarı (Türkçe karakterler için)
        font_name = 'Helvetica'
        bold_font_name = 'Helvetica-Bold'
        
        # DejaVu fontunu yükle (eğer varsa)
        dejavu_path = os.path.join('fonts', 'DejaVuSans.ttf')
        
        if os.path.exists(dejavu_path):
            try:
                pdfmetrics.registerFont(TTFont('DejaVu', dejavu_path))
                font_name = 'DejaVu'
                bold_font_name = 'DejaVu'
            except Exception:
                pass

        c = pdfcanvas.Canvas(filename, pagesize=A4)
        width, height = A4
        left = 25*mm
        right = width - 25*mm
        y = height - 25*mm

        # === ÜST BİLGİLER (İşletme) ===
        c.setFont(bold_font_name, 14)
        comp_name = biz['company_name']
        comp_width = c.stringWidth(comp_name, bold_font_name, 14)
        c.drawString((width - comp_width) / 2, y, comp_name)
        y -= 6*mm
        
        # Adres ve iletişim
        c.setFont(font_name, 10)
        if biz['company_address']:
            addr_width = c.stringWidth(biz['company_address'], font_name, 10)
            c.drawString((width - addr_width) / 2, y, biz['company_address'])
            y -= 5*mm
        
        if biz['company_phone']:
            phone_text = f"Tel: {biz['company_phone']}"
            phone_width = c.stringWidth(phone_text, font_name, 10)
            c.drawString((width - phone_width) / 2, y, phone_text)
            y -= 5*mm
        
        # Vergi bilgileri
        if biz['tax_office'] or biz['tax_number']:
            tax_parts = []
            if biz['tax_office']:
                tax_parts.append(biz['tax_office'])
            if biz['tax_number']:
                tax_parts.append(f"VKN: {biz['tax_number']}")
            tax_text = " / ".join(tax_parts)
            tax_width = c.stringWidth(tax_text, font_name, 10)
            c.drawString((width - tax_width) / 2, y, tax_text)
            y -= 8*mm
        else:
            y -= 3*mm

        # Başlık
        c.setFont(bold_font_name, 16)
        header_text = "SATIŞ FİŞİ"
        header_width = c.stringWidth(header_text, bold_font_name, 16)
        c.drawString((width - header_width) / 2, y, header_text)
        y -= 10*mm

        # Fiş bilgileri (sol tarafa)
        c.setFont(font_name, 10)
        c.drawString(left, y, f"Fiş No:: {fis_id}")
        y -= 5*mm
        c.drawString(left, y, f"Müşteri:: {customer_name}")
        y -= 5*mm
        c.drawString(left, y, f"Tarih:: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        y -= 8*mm

        # Ayırıcı çizgi
        c.setLineWidth(1)
        c.line(left, y, right, y)
        y -= 7*mm
        
        # Tablo başlıkları
        c.setFont(bold_font_name, 10)
        c.drawString(left, y, "Ürün")
        c.drawRightString(left + 105*mm, y, "Adet")
        c.drawRightString(left + 140*mm, y, "Fiyat")
        c.drawRightString(right, y, "Tutar")
        y -= 5*mm
        
        c.setLineWidth(1)
        c.line(left, y, right, y)
        y -= 7*mm

        # Satırlar ve hesaplama
        rate = float(kdv_rate or 0.0)
        subtotal_net = 0.0
        
        for pname, qty, base_price, line_gross in sales_list:
            q = float(qty) if qty else 1.0
            lg = float(line_gross)
            unit_gross = (lg / q) if q else float(base_price)
            unit_net = unit_gross / (1.0 + rate/100.0) if rate else unit_gross
            line_net = q * unit_net
            subtotal_net += line_net

            c.setFont(font_name, 10)
            # Ürün adı (uzunsa kes)
            product_display = str(pname)[:40]
            c.drawString(left, y, product_display)
            
            # Adet (ondalık varsa göster)
            qty_disp = f"{q:.3f}" if abs(q - round(q)) > 1e-6 else f"{int(round(q))}"
            c.drawRightString(left + 105*mm, y, qty_disp)
            
            # Birim fiyat
            c.drawRightString(left + 140*mm, y, f"{unit_net:.2f}")
            
            # Tutar
            c.drawRightString(right, y, f"{lg:.2f}")
            y -= 6*mm
            
            # Yeni sayfa kontrolü
            if y < 40*mm:
                c.showPage()
                y = height - 30*mm
                c.setFont(font_name, 10)

        # Alt çizgi
        c.setLineWidth(1)
        c.line(left, y, right, y)
        y -= 10*mm

        # Toplamlar (sağ blok - resim 2'deki gibi)
        discount_amt = subtotal_net * (float(discount_rate)/100.0)
        after_discount = subtotal_net - discount_amt
        kdv_amt = after_discount * (rate/100.0)
        grand_total = after_discount + kdv_amt

        # Ara toplam
        c.setFont(font_name, 11)
        c.drawString(right - 90*mm, y, f"Ara Toplam:: {subtotal_net:.2f} {biz['currency']}")
        y -= 6*mm
        
        # İndirim (varsa)
        if discount_rate > 0:
            c.drawString(right - 90*mm, y, f"İndirim ({float(discount_rate):.1f}%): -{discount_amt:.2f} {biz['currency']}")
            y -= 6*mm
        
        # KDV
        c.drawString(right - 90*mm, y, f"KDV ({rate:.1f}%): +{kdv_amt:.2f} {biz['currency']}")
        y -= 10*mm

        # Genel Toplam (kalın ve büyük)
        c.setFont(bold_font_name, 14)
        c.drawString(right - 90*mm, y, f"Genel Toplam:: {grand_total:.2f} {biz['currency']}")
        y -= 12*mm

        # Alt bilgi (footer)
        c.setFont(font_name, 10)
        footer_text = biz['receipt_footer']
        footer_width = c.stringWidth(footer_text, font_name, 10)
        c.drawString((width - footer_width) / 2, y, footer_text)

        c.showPage()
        c.save()

        if show_message:
            messagebox.showinfo(t('receipt_created'), f"{t('receipt_saved')}\n{filename}")
        if open_after:
            try:
                if os.name == 'nt':
                    os.startfile(filename)  # type: ignore
                else:
                    subprocess.call(("open", filename))
            except Exception:
                pass
        
        return filename
    except Exception as e:
        messagebox.showerror(t('error'), f"{t('print_error')}\n\n{e}")
        return None
