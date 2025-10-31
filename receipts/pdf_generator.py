import os
import subprocess
from datetime import datetime
from tkinter import messagebox
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from languages import LANGUAGES


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
    Tasarım: metinsel çizgiler ve sağda toplamlar.
    """
    def t(key: str):
        return LANGUAGES.get(language_code, LANGUAGES["tr"]).get(key, key)

    try:
        os.makedirs("receipts", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join("receipts", f"receipt_{ts}.pdf")

        # Font ayarı (Türkçe karakterler için)
        try:
            pdfmetrics.registerFont(TTFont('DejaVu', 'fonts/DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVu-Bold', 'fonts/DejaVuSans-Bold.ttf'))
            font_name = 'DejaVu'
            bold_font_name = 'DejaVu-Bold'
        except Exception:
            font_name = 'Helvetica'
            bold_font_name = 'Helvetica-Bold'

        c = pdfcanvas.Canvas(filename, pagesize=A4)
        width, height = A4
        left = 20*mm
        right = width - 20*mm
        y = height - 30*mm

        def draw_text(x, y, text, size=12, bold=False):
            c.setFont(bold_font_name if bold else font_name, size)
            c.drawString(x, y, text)

        def draw_right_text(x, y, text, size=12, bold=False):
            c.setFont(bold_font_name if bold else font_name, size)
            c.drawRightString(x, y, text)

        # Başlık
        draw_text(left, y, t('receipt_header'), 18); y -= 14*mm

        # Fiş bilgileri
        draw_text(left, y, f"{t('receipt_no')} {fis_id}", 12); y -= 7*mm
        draw_text(left, y, f"{t('receipt_customer')} {customer_name}", 12); y -= 7*mm
        draw_text(left, y, f"{t('receipt_date')} {datetime.now().strftime('%d.%m.%Y %H:%M')}", 12); y -= 8*mm

        # Ayırıcı çizgi (metin)
        c.setFont(font_name, 11)
        c.drawString(left, y, "-"*100); y -= 7*mm
        # Başlık satırı
        draw_text(left, y, t('receipt_product'), 12)
        draw_text(left+110*mm, y, t('receipt_quantity'), 12)
        draw_text(left+140*mm, y, t('receipt_price'), 12)
        draw_text(right-5*mm, y, t('receipt_total'), 12); y -= 5*mm
        c.drawString(left, y, "-"*100); y -= 7*mm

        # Satırlar ve hesap
        rate = float(kdv_rate or 0.0)
        subtotal_net = 0.0
        subtotal_gross = 0.0
        for pname, qty, base_price, line_gross in sales_list:
            q = float(qty) if qty else 1.0
            lg = float(line_gross)
            unit_gross = (lg / q) if q else float(base_price)
            unit_net = unit_gross / (1.0 + rate/100.0) if rate else unit_gross
            line_net = q * unit_net
            subtotal_net += line_net
            subtotal_gross += lg

            draw_text(left, y, str(pname), 12)
            draw_right_text(left+125*mm, y, f"{int(q)}", 12)
            draw_right_text(left+160*mm, y, f"{unit_net:.2f}", 12)
            draw_right_text(right, y, f"{lg:.2f}", 12)
            y -= 7*mm

        c.drawString(left, y, "-"*100); y -= 8*mm

        # Toplamlar (sağ blok)
        discount_amt = subtotal_net * (float(discount_rate)/100.0)
        after_discount_net = subtotal_net - discount_amt
        kdv_amt = after_discount_net * (rate/100.0)
        grand_total = after_discount_net + kdv_amt

        draw_right_text(right, y, f"{t('receipt_subtotal')}: {subtotal_net:.2f} ₺", 12); y -= 6*mm
        draw_right_text(right, y, f"{t('receipt_discount')} ({float(discount_rate):.1f}%): {-discount_amt:.2f} ₺", 12); y -= 6*mm
        draw_right_text(right, y, f"KDV ({rate:.1f}%): {('+' if kdv_amt>=0 else '')}{kdv_amt:.2f} ₺", 12); y -= 10*mm

        c.setFillColorRGB(0,0,0)
        draw_right_text(right, y, f"{t('receipt_grand_total')}: {grand_total:.2f} ₺", 16, bold=True)
        y -= 14*mm

        # Teşekkür
        draw_text(left, y, t('receipt_thank_you'), 12)

        c.showPage(); c.save()

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
    except Exception as e:
        messagebox.showerror(t('error'), f"{t('print_error')}\n\n{e}")
