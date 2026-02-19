from __future__ import annotations

# Bu sözlük, bot içindeki kullanıcı/admin görünen tüm varsayılan metinlerdir.
# Admin panelinden aynı anahtarları güncelleyerek metinleri canlı değiştirebilirsiniz.
DEFAULT_TEXT_TEMPLATES: dict[str, str] = {
    "welcome_text": (
        "Bakiye Botu'na hoş geldiniz.\n"
        "Aşağıdaki menüden ilerleyin.\n"
        "Önemli: Tüm yüklemeler admin onayı ile tamamlanır.\n"
        "İletişim: @{support_username}"
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
        "Ödeme sonrası dekontu fotoğraf veya belge olarak gönderin.\n"
        "Referans Kodunuz: {request_code_hint}"
    ),
    "upload_receipt_only_text": "Lütfen dekontu fotoğraf veya belge olarak gönderin.",
    "receipt_ai_reject_text": (
        "Dekont otomatik kontrolden geçemedi.\n"
        "Lütfen net bir dekont görseli gönderin (tarih ve tutar okunaklı olmalı)."
    ),
    "deposit_waiting": "Talebiniz alındı. Bakiye yüklemesi admin onayı bekliyor.",
    "deposit_received_text": "Dekont alındı. Talep kodunuz: {request_code}\n{waiting_text}",
    "support_contact_text": "Soru ve manuel işlemler için buradan yazabilirsiniz: {support_url}",
    "rules_text": (
        "İşlem Kuralları\n"
        "1) Bakiye yükleme admin onayı olmadan tamamlanmaz.\n"
        "2) Ödeme tutarı, talep edilen bakiyenin %{rate_percent} oranıdır.\n"
        "3) Minimum bakiye talebi: {min_amount}\n"
        "4) Maksimum bakiye talebi: {max_amount}\n"
        "5) Çekim talebinde sistem, mevcut bakiyenin tamamını çeker.\n"
        "6) Yanlış/eksik dekont talepleri reddedilebilir.\n\n"
        "Destek: @{support_username}"
    ),
    "faq_text": (
        "Sık Sorulan Sorular\n"
        "S: Yükleme ne kadar sürer?\n"
        "C: Genelde 5-20 dakika içinde admin onayına göre tamamlanır.\n\n"
        "S: Çekim nasıl yapılır?\n"
        "C: Çekim Talebi menüsünden ad-soyad, IBAN ve banka adı girilir.\n\n"
        "S: Neden talep kodu var?\n"
        "C: Her işlem DS koduyla takip edilir.\n\n"
        "S: Destekle nasıl iletişim kurarım?\n"
        "C: Menüdeki Soru Sor / Destek butonunu kullanın."
    ),
    "request_status_header_text": "Talep Durumu (Son Kayıtlar):",
    "request_status_empty_text": "Henüz kayıtlı talebiniz bulunmuyor.",
    "request_status_next_step_text": "Sıradaki adım: {next_step}",
    "queue_info_text": "Sıra: {position}/{total} | Tahmini süre: {eta_minutes} dk",
    "appeal_intro_text": "İtiraz oluşturmak için reddedilen talebinizi seçin:",
    "appeal_no_rejected_text": "İtiraz açabileceğiniz reddedilmiş talep bulunmuyor.",
    "appeal_ask_message_text": "İtiraz gerekçenizi yazın (en az 5 karakter):",
    "appeal_submitted_text": "İtiraz kaydınız alındı: {ticket_code}. Admin incelemesine iletildi.",
    "ticket_status_header_text": "İtiraz Kayıtları (Son Kayıtlar):",
    "reminder_bank_text": "Banka talebiniz ({request_code}) halen incelemede. Lütfen bekleyin.",
    "reminder_crypto_text": "Kripto talebiniz ({request_code}) halen işlemde. Lütfen bekleyin.",
    "reminder_withdraw_text": "Çekim talebiniz ({request_code}) halen incelemede. Lütfen bekleyin.",
    "sla_delay_user_text": (
        "Talebinizde yoğunluk tespit edildi.\n"
        "Talep: {request_code}\n"
        "Gecikme Seviyesi: SLA-{level}\n"
        "Bekleme Süresi: {age_minutes} dk\n"
        "Takip için canlı talep kartınızı yenileyebilirsiniz."
    ),
    "status_card_created_text": "Canlı talep kartınız oluşturuldu. Durumu kart üzerinden anlık takip edebilirsiniz.",
    "risk_block_text": (
        "Hesabınız şu an güvenlik incelemesinde olduğu için yeni talep alınamıyor.\n"
        "Lütfen destek ekibiyle iletişime geçin."
    ),
    "rate_limit_block_text": (
        "Kısa sürede çok fazla yükleme talebi gönderildi.\n"
        "Lütfen bir süre sonra tekrar deneyin."
    ),
    "duplicate_receipt_block_text": (
        "Bu dekont daha önce farklı bir talepte kullanılmış görünüyor.\n"
        "Güvenlik nedeniyle talep durduruldu. Lütfen yeni dekont yükleyin."
    ),
    "withdraw_zero_balance_text": "Çekim için bakiyeniz bulunmuyor.",
    "withdraw_pending_exists_text": "Zaten bekleyen bir çekim talebiniz var. Önce o talep sonuçlanmalı.",
    "withdraw_start_text": (
        "Çekim işlemi başlatıldı.\n"
        "Çekilecek tutar: {balance} BAKİYE\n\n"
        "Lütfen ad soyad yazın:"
    ),
    "withdraw_ask_iban_text": "Şimdi IBAN yazın:",
    "withdraw_invalid_iban_text": "Geçersiz IBAN. Lütfen TR ile başlayan geçerli IBAN girin.",
    "withdraw_ask_bank_name_text": "Şimdi banka adını yazın:",
    "withdraw_confirm_text": (
        "Çekim Özeti\n"
        "Ad Soyad: {full_name}\n"
        "IBAN: {iban}\n"
        "Banka: {bank_name}\n"
        "Çekilecek Tutar: {amount} BAKİYE\n\n"
        "Onay için aşağıdaki butona basın."
    ),
    "withdraw_submitted_text": (
        "Çekim talebiniz alındı: {request_code}\n"
        "Tutar: {amount} BAKİYE\n"
        "Admin onayı bekleniyor."
    ),
    "withdraw_waiting_text": "Çekim talebiniz admin incelemesinde.",
    "withdraw_history_header_text": "Çekim Talepleri:",
    "no_withdraw_records_text": "- çekim talebiniz bulunmuyor",
    "withdraw_proof_request_text": (
        "Çekim talebiniz onaylandı: {request_code}\n"
        "Ödeme gönderildiyse lütfen ekran görüntüsü (SS) gönderin."
    ),
    "withdraw_proof_only_text": "Lütfen ekran görüntüsünü fotoğraf veya belge olarak gönderin.",
    "withdraw_proof_received_text": "Teşekkürler. SS alındı ve admin ekibine iletildi.",
    "withdraw_admin_caption_text": (
        "Bekleyen çekim talebi\n"
        "Talep Kodu: {request_code}\n"
        "Kullanıcı TG: {telegram_id}\n"
        "Kullanıcı Adı: @{username}\n"
        "Ad Soyad: {full_name}\n"
        "IBAN: {iban}\n"
        "Banka: {bank_name}\n"
        "Tutar: {amount} BAKİYE"
    ),
    "withdraw_proof_admin_caption_text": (
        "Çekim için SS geldi\n"
        "Talep Kodu: {request_code}\n"
        "Kullanıcı TG: {telegram_id}\n"
        "Kullanıcı Adı: @{username}"
    ),
    "history_header_text": "Geçmişim (son kayıtlar):",
    "bank_history_header_text": "Banka Yükleme Talepleri:",
    "crypto_history_header_text": "Kripto Yükleme Talepleri:",
    "no_bank_deposit_records_text": "- banka yükleme talebiniz bulunmuyor",
    "no_crypto_deposit_records_text": "- kripto yükleme talebiniz bulunmuyor",
    "receipt_caption_admin_text": (
        "Bekleyen banka yükleme talebi\n"
        "Talep Kodu: {request_code}\n"
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
    "receipt_ai_reject_text": "Dekont AI Red Mesajı",
    "deposit_waiting": "Yükleme Bekleme Mesajı",
    "deposit_received_text": "Dekont Alındı Mesajı",
    "support_contact_text": "Destek Mesajı",
    "rules_text": "Kurallar Metni",
    "faq_text": "SSS Metni",
    "request_status_header_text": "Talep Durumu Başlığı",
    "request_status_empty_text": "Talep Durumu Boş Mesajı",
    "request_status_next_step_text": "Talep Durumu Sonraki Adım",
    "queue_info_text": "Sıra ve Tahmini Süre Bilgisi",
    "appeal_intro_text": "İtiraz Giriş Metni",
    "appeal_no_rejected_text": "İtiraz Yok Metni",
    "appeal_ask_message_text": "İtiraz Mesajı İsteği",
    "appeal_submitted_text": "İtiraz Alındı Mesajı",
    "ticket_status_header_text": "İtiraz Durum Başlığı",
    "reminder_bank_text": "Banka Hatırlatma Mesajı",
    "reminder_crypto_text": "Kripto Hatırlatma Mesajı",
    "reminder_withdraw_text": "Çekim Hatırlatma Mesajı",
    "sla_delay_user_text": "SLA Gecikme Bildirimi",
    "status_card_created_text": "Canlı Kart Oluşturma Mesajı",
    "risk_block_text": "Risk Blokaj Mesajı",
    "rate_limit_block_text": "Hız Limiti Blokaj Mesajı",
    "duplicate_receipt_block_text": "Mükerrer Dekont Blokaj Mesajı",
    "withdraw_zero_balance_text": "Çekim Bakiye Yok",
    "withdraw_pending_exists_text": "Çekim Bekleyen Talep Uyarısı",
    "withdraw_start_text": "Çekim Başlangıç Mesajı",
    "withdraw_ask_iban_text": "Çekim IBAN İsteği",
    "withdraw_invalid_iban_text": "Çekim IBAN Hata Mesajı",
    "withdraw_ask_bank_name_text": "Çekim Banka İsteği",
    "withdraw_confirm_text": "Çekim Onay Özeti",
    "withdraw_submitted_text": "Çekim Talebi Alındı",
    "withdraw_waiting_text": "Çekim Bekleme Mesajı",
    "withdraw_history_header_text": "Çekim Geçmiş Başlığı",
    "no_withdraw_records_text": "Çekim Kayıt Yok",
    "withdraw_proof_request_text": "Çekim SS İsteği",
    "withdraw_proof_only_text": "Çekim SS Uyarısı",
    "withdraw_proof_received_text": "Çekim SS Alındı",
    "withdraw_admin_caption_text": "Çekim Admin Açıklaması",
    "withdraw_proof_admin_caption_text": "Çekim SS Admin Açıklaması",
    "history_header_text": "Geçmiş Başlığı",
    "bank_history_header_text": "Banka Geçmiş Başlığı",
    "crypto_history_header_text": "Kripto Geçmiş Başlığı",
    "no_bank_deposit_records_text": "Banka Kayıt Yok",
    "no_crypto_deposit_records_text": "Kripto Kayıt Yok",
    "receipt_caption_admin_text": "Admin Dekont Açıklaması",
}

WELCOME = DEFAULT_TEXT_TEMPLATES["welcome_text"]
