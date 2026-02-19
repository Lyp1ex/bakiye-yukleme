from __future__ import annotations

from telegram import ReplyKeyboardMarkup

MENU_BAKIYE = "Bakiyem"
MENU_YUKLEME = "Bakiye Yükleme İşlemi"
MENU_GECMIS = "Geçmişim"



def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [MENU_BAKIYE, MENU_YUKLEME],
            [MENU_GECMIS],
        ],
        resize_keyboard=True,
    )
