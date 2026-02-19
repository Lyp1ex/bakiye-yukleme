from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup



def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Bekleyen Banka Talepleri", callback_data="admin_bank_list")],
            [InlineKeyboardButton("Bekleyen Kripto Talepleri", callback_data="admin_crypto_list")],
            [InlineKeyboardButton("Bekleyen Çekim Talepleri", callback_data="admin_withdraw_list")],
            [InlineKeyboardButton("Kullanıcı Ara", callback_data="admin_search")],
            [InlineKeyboardButton("Manuel Bakiye Ekle/Çıkar", callback_data="admin_manual")],
            [InlineKeyboardButton("Mesaj Şablonları", callback_data="admin_templates")],
        ]
    )



def approve_reject_keyboard(approve_data: str, reject_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Onayla", callback_data=approve_data),
                InlineKeyboardButton("Reddet", callback_data=reject_data),
            ]
        ]
    )
