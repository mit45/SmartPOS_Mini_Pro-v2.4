from datetime import datetime
from tkinter import messagebox, simpledialog
from languages import LANGUAGES


def print_thermal_receipt(sales_list, fis_id="", customer_name="Müşteri", kdv_rate=18.0, discount_rate=0.0, vat_included: bool = False, language_code: str = "tr"):
    """
    Termal yazıcıya direkt yazdırma fonksiyonu (ESC/POS)
    vat_included=True ise: base_price brüt kabul edilir, net düşülür, toplam=brüt*adet
    vat_included=False ise: base_price net kabul edilir, brüt ekleriz
    """
    def t(key: str):
        return LANGUAGES.get(language_code, LANGUAGES["tr"]).get(key, key)

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
        price_header = t('receipt_price') + (" (KDV Dahil)" if vat_included else " (KDV Hariç)")
        p.text(f"{t('receipt_product'):<15} {t('receipt_quantity'):>6} {price_header[:8]:>8} {t('receipt_total'):>7}\n")
        p.text("-" * 32 + "\n")
        
        # Ürünler
        subtotal_gross = 0.0
        rate = float(kdv_rate)
        for pname, qty, base_price_val, line_gross_val in sales_list:
            q = float(qty)
            base_price = float(base_price_val)
            if vat_included:
                unit_gross = base_price
                unit_net = unit_gross / (1.0 + rate/100.0) if rate else unit_gross
            else:
                unit_net = base_price
                unit_gross = unit_net * (1.0 + rate/100.0)
            
            disp_price = unit_gross if vat_included else unit_net
            line_total = q * unit_gross
            subtotal_gross += line_total

            pname_short = str(pname)[:15]
            qty_disp = (f"{q:.3f}" if abs(q - round(q)) > 1e-6 else f"{int(round(q))}")
            p.text(f"{pname_short:<15} {qty_disp:>6} {disp_price:>8.2f} {line_total:>7.2f}\n")
        
        # Toplamlar: Brüt toplam - İndirim = Genel Toplam
        discount_amt = subtotal_gross * (float(discount_rate)/100.0)
        grand_total = subtotal_gross - discount_amt
        
        p.text("-" * 32 + "\n")
        p.text(f"{t('receipt_subtotal'):<20} {subtotal_gross:>11.2f} TL\n")
        p.text(f"{t('receipt_discount')} ({discount_rate:.1f}%):{-discount_amt:>8.2f} TL\n")
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
