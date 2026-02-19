from __future__ import annotations

from telegram import ReplyKeyboardMarkup

MENU_BAKIYE = "Bakiyem"
MENU_YUKLEME = "Bakiye Yükleme İşlemi"
MENU_GECMIS = "Geçmişim"
MENU_CEKIM = "Çekim Talebi"
MENU_DURUM = "Talep Durumu"
MENU_KURALLAR = "Kurallar"
MENU_SSS = "SSS"
MENU_DESTEK = "Soru Sor / Destek"



def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [MENU_BAKIYE, MENU_YUKLEME],
            [MENU_CEKIM, MENU_DURUM],
            [MENU_GECMIS, MENU_KURALLAR],
            [MENU_SSS],
            [MENU_DESTEK],
        ],
        resize_keyboard=True,
    )
