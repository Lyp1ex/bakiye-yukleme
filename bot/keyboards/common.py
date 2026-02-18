from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup



def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Balance", "Load Coins"],
            ["Shop", "My Orders"],
            ["History"],
        ],
        resize_keyboard=True,
    )



def packages_keyboard(packages: list) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"{pkg.name} - {pkg.coin_amount} COIN",
                callback_data=f"load_pkg:{pkg.id}",
            )
        ]
        for pkg in packages
    ]
    rows.append([InlineKeyboardButton("Main Menu", callback_data="menu_back")])
    return InlineKeyboardMarkup(rows)



def payment_method_keyboard(package_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Pay with Bank Transfer", callback_data=f"pay_bank:{package_id}")],
            [InlineKeyboardButton("Pay with TRX", callback_data=f"pay_trx:{package_id}")],
            [InlineKeyboardButton("Back", callback_data="load_back")],
        ]
    )



def games_keyboard(games: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(game.name, callback_data=f"shop_game:{game.id}")] for game in games
    ]
    rows.append([InlineKeyboardButton("Main Menu", callback_data="menu_back")])
    return InlineKeyboardMarkup(rows)



def products_keyboard(products: list) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"{product.name} - {product.price_coins} COIN",
                callback_data=f"shop_product:{product.id}",
            )
        ]
        for product in products
    ]
    rows.append([InlineKeyboardButton("Back to Games", callback_data="shop_back_games")])
    return InlineKeyboardMarkup(rows)



def confirm_buy_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Buy Now", callback_data=f"shop_buy:{product_id}")],
            [InlineKeyboardButton("Back", callback_data="shop_back_products")],
        ]
    )
