# -*- coding: utf-8 -*-
"""
SmartPOS Mini Pro - Dil Dosyası / Language File
Türkçe ve İngilizce çeviri verileri
Turkish and English translation data
"""

LANGUAGES = {
    "tr": {
        "app_title": "SmartPOS Mini Pro",
        "subtitle": "Küçük işletmeler için satış sistemi",
        
        # İlk Kurulum
        "welcome": "Hoş Geldiniz!",
        "select_language": "Lütfen dil seçiniz / Please select language",
        "continue": "Devam Et",
        "setup_complete": "Kurulum tamamlandı!",
        "username": "Kullanıcı Adı:",
        "password": "Şifre:",
        "login": "Giriş Yap",
        "show": "Göster",
        "hide": "Gizle",
        "logout": "Çıkış Yap",
        "language": "Dil:",
        
        # Menü
        "sales": "🛒 Satış Yap",
        "products": "📦 Ürün Yönetimi",
        "users": "👥 Kullanıcı Yönetimi",
        "receipts": "🧾 Fişleri Görüntüle / Yazdır",
        "reports": "📊 Raporlar",
        "daily_report": "💾 Günlük Raporu Kaydet",
        
        # Ürün Yönetimi
        "product_management": "📦 Ürün Yönetimi",
        "search": "Ara:",
        "add": "➕ Ekle",
        "edit": "✏️ Düzenle",
        "delete": "🗑 Sil",
        "refresh": "🔄 Yenile",
    "save": "💾 Kaydet",
    "update_btn": "🔁 Güncelle",
    "clear_form": "🧹 Formu Temizle",
        "id": "ID",
        "name": "Ad",
        "price": "Fiyat",
        "stock": "Stok",
        
        # Kullanıcı Yönetimi
        "user_management": "👥 Kullanıcı Yönetimi",
        "user": "Kullanıcı",
        "role": "Rol",
        
        # Satış
        "sales_screen": "🛒 Satış Ekranı",
        "product": "Ürün",
        "quantity": "Adet",
        "unit_price": "Birim Fiyat",
        "total": "Toplam ₺",
    "payment_method": "Ödeme Yöntemi",
    "choose_payment": "Ödeme yöntemini seçiniz:",
    "cash": "Nakit",
    "credit_card": "Kredi Kartı",
        "customer_name": "Müşteri Adı:",
        "add_to_cart": "➕ Sepete Ekle",
        "remove_selected": "❌ Seçili Ürünü Kaldır",
        "clear_cart": "🗑 Sepeti Temizle",
        "complete_sale": "✅ Satışı Tamamla",
        "receipt_no": "Fiş No:",
        "discount": "İndirim (%):",
        "vat": "KDV (%):",
        "subtotal": "Ara Toplam:",
        "grand_total": "Genel Toplam:",
    "cancel_sale": "🛑 Satış İptal",
    "recent_receipts": "🧾 Son Fişler",
    "cancel_receipt": "Fişi İptal Et",
    "confirm_cancel_receipt": "Bu fişi iptal etmek istiyor musunuz?",
    "cancel_success": "Fiş iptal edildi.",
    "cancel_error": "İptal sırasında hata oluştu.",
        
        # Fişler
        "receipts_title": "🧾 Kayıtlı Fişler (PDF)",
        "file": "Dosya",
        "date": "Tarih",
        "open_print": "🖨 Aç / Yazdır",
        
        # Raporlar
        "reports_title": "📊 Satış Raporu",
        "start_date": "Başlangıç (YYYY-MM-DD):",
        "end_date": "Bitiş (YYYY-MM-DD):",
        "export_csv": "📥 CSV Dışa Aktar",
        
        # Mesajlar
        "warning": "Uyarı",
        "error": "Hata",
        "success": "Başarılı",
        "confirm": "Onay",
        "select_item": "Bir öğe seçin.",
        "login_error": "Kullanıcı adı veya şifre hatalı!",
        "delete_confirm": "silinsin mi?",
        "receipt_created": "Fiş Oluşturuldu",
        "receipt_saved": "Fatura kaydedildi:",
        "report_saved": "Rapor Kaydedildi",
        "thank_you": "Teşekkür ederiz - SmartPOS Mini Pro",
        "copyright": "SmartPOS Mini Pro © 2025",
        "timestamp": "Zaman damgası:",
        
        # Dialog
        "add_product": "Ürün Ekle",
        "product_name": "Ürün adı:",
        "price_input": "Fiyat (örn 99.90):",
        "stock_input": "Stok (örn 10):",
        "edit": "Düzenle",
        "new_user": "Yeni Kullanıcı",
        "role_input": "Rol (admin/cashier):",
        "new_password": "Yeni şifre (boş bırak=değişmesin):",
        "duplicate_error": "Bu ürün adı zaten mevcut!",
        "duplicate_user_error": "Bu kullanıcı adı zaten mevcut!",
        "admin_delete_error": "admin kullanıcısı silinemez!",
        "enter_valid": "Geçerli fiyat/stok girin.",
        "customer": "Müşteri",
        
        # PDF Fiş
        "receipt_header": "SMARTPOS MINI PRO - SATIŞ FİŞİ",
        "receipt_customer": "Müşteri:",
        "receipt_date": "Tarih:",
        "receipt_product": "Ürün",
        "receipt_quantity": "Adet",
        "receipt_price": "Fiyat",
        "receipt_total": "Tutar",
        "receipt_subtotal": "Ara Toplam:",
        "receipt_discount": "İndirim",
        "receipt_vat": "KDV",
        "receipt_grand_total": "Genel Toplam:",
        "receipt_thank_you": "Teşekkür ederiz - SmartPOS Mini Pro",
        
        # Termal Yazıcı
        "print_receipt": "Fiş Yazdır",
        "print_options": "Yazdırma seçeneğini seçin:",
        "thermal_printer": "Termal Yazıcı",
        "no_print": "Yazdırma",
        "printer_setup": "Yazıcı Ayarı",
        "enter_printer_name": "Yazıcı adını girin (Cihazlar ve Yazıcılar'dan bakın):",
        "receipt_printed": "Fiş yazıcıya gönderildi!",
        "print_error": "Yazıcı hatası",
        
        # Diğer
        "confirm_repeat": "Yinele işlemine devam edilsin mi?",
    },
    "en": {
        "app_title": "SmartPOS Mini Pro",
        "subtitle": "Point of Sale System for Small Businesses",
        
        # Initial Setup
        "welcome": "Welcome!",
        "select_language": "Please select language / Lütfen dil seçiniz",
        "continue": "Continue",
        "setup_complete": "Setup completed!",
        "username": "Username:",
        "password": "Password:",
        "login": "Login",
        "show": "Show",
        "hide": "Hide",
        "logout": "Logout",
        "language": "Language:",
        
        # Menu
        "sales": "🛒 Make Sale",
        "products": "📦 Product Management",
        "users": "👥 User Management",
        "receipts": "🧾 View / Print Receipts",
        "reports": "📊 Reports",
        "daily_report": "💾 Save Daily Report",
        
        # Product Management
        "product_management": "📦 Product Management",
        "search": "Search:",
        "add": "➕ Add",
        "edit": "✏️ Edit",
        "delete": "🗑 Delete",
        "refresh": "🔄 Refresh",
    "save": "💾 Save",
    "update_btn": "🔁 Update",
    "clear_form": "🧹 Clear Form",
        "id": "ID",
        "name": "Name",
        "price": "Price",
        "stock": "Stock",
        
        # User Management
        "user_management": "👥 User Management",
        "user": "User",
        "role": "Role",
        
        # Sales
        "sales_screen": "🛒 Sales Screen",
        "product": "Product",
        "quantity": "Qty",
        "unit_price": "Unit Price",
        "total": "Total ₺",
    "payment_method": "Payment Method",
    "choose_payment": "Choose payment method:",
    "cash": "Cash",
    "credit_card": "Credit Card",
        "customer_name": "Customer Name:",
        "add_to_cart": "➕ Add to Cart",
        "remove_selected": "❌ Remove Selected",
        "clear_cart": "🗑 Clear Cart",
        "complete_sale": "✅ Complete Sale",
        "receipt_no": "Receipt No:",
        "discount": "Discount (%):",
        "vat": "VAT (%):",
        "subtotal": "Subtotal:",
        "grand_total": "Grand Total:",
    "cancel_sale": "🛑 Cancel Sale",
    "recent_receipts": "🧾 Recent Receipts",
    "cancel_receipt": "Cancel Receipt",
    "confirm_cancel_receipt": "Do you want to cancel this receipt?",
    "cancel_success": "Receipt canceled.",
    "cancel_error": "An error occurred during cancellation.",
        
        # Receipts
        "receipts_title": "🧾 Saved Receipts (PDF)",
        "file": "File",
        "date": "Date",
        "open_print": "🖨 Open / Print",
        
        # Reports
        "reports_title": "📊 Sales Report",
        "start_date": "Start Date (YYYY-MM-DD):",
        "end_date": "End Date (YYYY-MM-DD):",
        "export_csv": "📥 Export CSV",
        
        # Messages
        "warning": "Warning",
        "error": "Error",
        "success": "Success",
        "confirm": "Confirm",
        "select_item": "Please select an item.",
        "login_error": "Invalid username or password!",
        "delete_confirm": "Delete?",
        "receipt_created": "Receipt Created",
        "receipt_saved": "Invoice saved:",
        "report_saved": "Report Saved",
        "thank_you": "Thank you - SmartPOS Mini Pro",
        "copyright": "SmartPOS Mini Pro © 2025",
        "timestamp": "Timestamp:",
        
        # Dialog
        "add_product": "Add Product",
        "product_name": "Product name:",
        "price_input": "Price (e.g. 99.90):",
        "stock_input": "Stock (e.g. 10):",
        "edit": "Edit",
        "new_user": "New User",
        "role_input": "Role (admin/cashier):",
        "new_password": "New password (leave empty=no change):",
        "duplicate_error": "This product name already exists!",
        "duplicate_user_error": "This username already exists!",
        "admin_delete_error": "Cannot delete admin user!",
        "enter_valid": "Please enter valid price/stock.",
        "customer": "Customer",
        
        # PDF Receipt
        "receipt_header": "SMARTPOS MINI PRO - SALES RECEIPT",
        "receipt_customer": "Customer:",
        "receipt_date": "Date:",
        "receipt_product": "Product",
        "receipt_quantity": "Qty",
        "receipt_price": "Price",
        "receipt_total": "Amount",
        "receipt_subtotal": "Subtotal:",
        "receipt_discount": "Discount",
        "receipt_vat": "VAT",
        "receipt_grand_total": "Grand Total:",
        "receipt_thank_you": "Thank you - SmartPOS Mini Pro",
        
        # Thermal Printer
        "print_receipt": "Print Receipt",
        "print_options": "Choose printing option:",
        "thermal_printer": "Thermal Printer",
        "no_print": "No Print",
        "printer_setup": "Printer Setup",
        "enter_printer_name": "Enter printer name (check Devices and Printers):",
        "receipt_printed": "Receipt sent to printer!",
        "print_error": "Printer error",

        # Other
        "confirm_repeat": "Do you want to continue the repeat operation?",
    }
}
