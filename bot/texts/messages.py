from __future__ import annotations

# Bu sözlük, bot içindeki kullanıcı/admin görünen tüm varsayılan metinlerdir.
# Admin panelinden aynı anahtarları güncelleyerek metinleri canlı değiştirebilirsiniz.
DEFAULT_TEXT_TEMPLATES: dict[str, str] = {
    "welcome_text": (
        "Bakiye Botu'na hoş geldiniz.\n"
        "Aşağıdaki menüden ilerleyin.\n"
        "Önemli: Tüm yüklemeler admin onayı ile tamamlanır."
    ),
    "cancel_text": "İşlem iptal edildi. Ana menüye dönüldü.",
    "use_menu_buttons_text": "Lütfen menüdeki butonları kullanın.",
    "balance_text": "Mevcut bakiyeniz: {balance} BAKİYE",
    "load_balance_start_text": (
        "Ne kadar bakiye yüklemek istiyorsunuz?\n"
        "Minimum: {min_amount}\n"
        "Maksimum: {max_amount}\n\n"
        "Sadece sayı girin. Örnek: 50000"
    ),
    "invalid_balance_amount_text": (
        "Geçersiz tutar.\n"
        "Minimum: {min_amount}\n"
        "Maksimum: {max_amount}\n"
        "Sadece sayı girmelisiniz."
    ),
    "payment_instruction_text": (
        "Talep edilen bakiye: {balance_amount}\n"
        "Ödemeniz gereken tutar (%{rate_percent}): {payment_try}\n\n"
        "Lütfen aşağıdaki IBAN'a ödemeyi yapın:\n{iban_text}\n\n"
        "Ödeme sonrası dekontu fotoğraf veya belge olarak gönderin."
    ),
    "upload_receipt_only_text": "Lütfen dekontu fotoğraf veya belge olarak gönderin.",
    "deposit_waiting": "Talebiniz alındı. Bakiye yüklemesi admin onayı bekliyor.",
    "deposit_received_text": "Dekont alındı. Talep numaranız: #{request_id}\n{waiting_text}",
    "history_header_text": "Geçmişim (son kayıtlar):",
    "bank_history_header_text": "Banka Yükleme Talepleri:",
    "crypto_history_header_text": "Kripto Yükleme Talepleri:",
    "no_bank_deposit_records_text": "- banka yükleme talebiniz bulunmuyor",
    "no_crypto_deposit_records_text": "- kripto yükleme talebiniz bulunmuyor",
    "receipt_caption_admin_text": (
        "Bekleyen banka yükleme talebi\n"
        "Talep: #{request_id}\n"
        "Kullanıcı TG: {telegram_id}\n"
        "İstenen bakiye: {balance_amount}\n"
        "Ödenmesi gereken: {payment_try}"
    ),
}

# Eski İngilizce varsayılanlar.
# Kullanıcı metni elle değiştirmediyse bootstrap sırasında otomatik Türkçeye çevrilir.
LEGACY_TEXT_TEMPLATES_EN: dict[str, str] = {
    "welcome_text": (
        "Welcome to Coin Shop Bot.\n"
        "Use the menu buttons below.\n"
        "Important: All deposits require manual admin approval."
    ),
    "cancel_text": "Cancelled. Back to main menu.",
    "use_menu_buttons_text": "Please use the menu buttons.",
    "balance_text": "Your balance: {balance} COIN",
    "history_header_text": "History (latest):",
    "no_bank_deposit_records_text": "- no bank deposit records",
    "no_crypto_deposit_records_text": "- no crypto deposit records",
    "upload_receipt_only_text": "Please upload photo or document receipt.",
    "deposit_received_text": "Receipt received. Request ID: #{request_id}.\n{waiting_text}",
    "deposit_waiting": "Your deposit request has been received. Please wait for admin approval.",
}

OBSOLETE_TEMPLATE_KEYS: set[str] = {
    "load_coins_text",
    "shop_select_game_text",
    "no_active_items_text",
    "bank_receipt_request_text",
    "trx_payment_text",
    "no_active_orders_text",
    "no_order_records_text",
    "main_menu_below_text",
    "choose_action_text",
    "package_not_available_text",
    "choose_payment_method_text",
    "package_not_found_text",
    "upload_receipt_prompt_text",
    "no_products_for_game_text",
    "select_product_text",
    "session_expired_select_game_text",
    "product_not_found_text",
    "user_not_found_text",
    "purchase_failed_text",
    "purchase_success_text",
    "no_package_selected_text",
    "invalid_game_user_id_text",
    "ask_iban_text",
    "invalid_iban_text",
    "ask_full_name_text",
    "invalid_full_name_text",
    "ask_bank_name_text",
    "invalid_bank_name_text",
    "order_session_expired_text",
    "order_submitted_text",
    "order_received",
}

TEMPLATE_LABELS: dict[str, str] = {
    "welcome_text": "Karşılama Mesajı",
    "cancel_text": "İptal Mesajı",
    "use_menu_buttons_text": "Menü Uyarısı",
    "balance_text": "Bakiye Mesajı",
    "load_balance_start_text": "Bakiye Tutarı Sorusu",
    "invalid_balance_amount_text": "Geçersiz Tutar Uyarısı",
    "payment_instruction_text": "Ödeme Talimatı",
    "upload_receipt_only_text": "Dekont Uyarısı",
    "deposit_waiting": "Yükleme Bekleme Mesajı",
    "deposit_received_text": "Dekont Alındı Mesajı",
    "history_header_text": "Geçmiş Başlığı",
    "bank_history_header_text": "Banka Geçmiş Başlığı",
    "crypto_history_header_text": "Kripto Geçmiş Başlığı",
    "no_bank_deposit_records_text": "Banka Kayıt Yok",
    "no_crypto_deposit_records_text": "Kripto Kayıt Yok",
    "receipt_caption_admin_text": "Admin Dekont Açıklaması",
}

WELCOME = DEFAULT_TEXT_TEMPLATES["welcome_text"]
