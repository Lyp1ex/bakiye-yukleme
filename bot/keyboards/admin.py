from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup



def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Pending Bank Deposits", callback_data="admin_bank_list")],
            [InlineKeyboardButton("Pending Crypto Deposits", callback_data="admin_crypto_list")],
            [InlineKeyboardButton("Pending Orders", callback_data="admin_orders_list")],
            [InlineKeyboardButton("Manage Games", callback_data="admin_games")],
            [InlineKeyboardButton("Manage Products", callback_data="admin_products")],
            [InlineKeyboardButton("Manage Coin Packages", callback_data="admin_packages")],
            [InlineKeyboardButton("Search Users", callback_data="admin_search")],
            [InlineKeyboardButton("Manual coin add/remove", callback_data="admin_manual")],
            [InlineKeyboardButton("Message Templates", callback_data="admin_templates")],
        ]
    )



def approve_reject_keyboard(approve_data: str, reject_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve", callback_data=approve_data),
                InlineKeyboardButton("Reject", callback_data=reject_data),
            ]
        ]
    )
