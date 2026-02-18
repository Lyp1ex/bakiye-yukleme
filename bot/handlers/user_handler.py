from __future__ import annotations

from decimal import Decimal
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.admin.notifier import send_message_to_admins, send_receipt_to_admins
from bot.config.settings import Settings
from bot.database.session import session_scope
from bot.keyboards.common import (
    confirm_buy_keyboard,
    games_keyboard,
    main_menu_keyboard,
    packages_keyboard,
    payment_method_keyboard,
    products_keyboard,
)
from bot.models import User
from bot.services import DepositService, ShopService, TemplateService, UserService
from bot.texts.messages import (
    BANK_RECEIPT_REQUEST,
    LOAD_COINS,
    NO_ACTIVE_ITEMS,
    SHOP_SELECT_GAME,
    TRX_PAYMENT_TEXT,
    WELCOME,
)
from bot.utils.formatters import fmt_trx, fmt_try

logger = logging.getLogger(__name__)

MENU, WAIT_BANK_RECEIPT, WAIT_GAME_USER_ID, WAIT_IBAN, WAIT_FULL_NAME, WAIT_BANK_NAME = range(6)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        UserService.get_or_create_user(session, update.effective_user)

    await update.effective_message.reply_text(WELCOME, reply_markup=main_menu_keyboard())
    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _clear_user_context(context)
    if update.effective_message:
        await update.effective_message.reply_text(
            "Cancelled. Back to main menu.",
            reply_markup=main_menu_keyboard(),
        )
    return MENU


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text if update.effective_message else "").strip()

    if text == "Balance":
        return await show_balance(update, context)
    if text == "Load Coins":
        return await show_load_packages(update, context)
    if text == "Shop":
        return await show_games(update, context)
    if text == "My Orders":
        return await show_my_orders(update, context)
    if text == "History":
        return await show_history(update, context)

    if update.effective_message:
        await update.effective_message.reply_text(
            "Please use the menu buttons.",
            reply_markup=main_menu_keyboard(),
        )
    return MENU


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)

    await update.effective_message.reply_text(
        f"Your balance: {user.coin_balance} COIN",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def show_load_packages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return MENU

    with session_scope() as session:
        packages = DepositService.list_active_packages(session)

    if not packages:
        await update.effective_message.reply_text(NO_ACTIVE_ITEMS, reply_markup=main_menu_keyboard())
        return MENU

    await update.effective_message.reply_text(LOAD_COINS, reply_markup=packages_keyboard(packages))
    return MENU


async def show_games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return MENU

    with session_scope() as session:
        games = ShopService.list_active_games(session)

    if not games:
        await update.effective_message.reply_text(NO_ACTIVE_ITEMS, reply_markup=main_menu_keyboard())
        return MENU

    await update.effective_message.reply_text(SHOP_SELECT_GAME, reply_markup=games_keyboard(games))
    return MENU


async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)
        orders = ShopService.list_user_orders(session, user.id, pending_only=True)

    if not orders:
        await update.effective_message.reply_text("No active orders.", reply_markup=main_menu_keyboard())
        return MENU

    lines = ["My Orders:"]
    for order in orders:
        lines.append(
            f"#{order.id} | {order.product.name} | {order.status} | {order.created_at:%Y-%m-%d %H:%M}"
        )

    await update.effective_message.reply_text("\n".join(lines), reply_markup=main_menu_keyboard())
    return MENU


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)
        orders = ShopService.list_user_orders(session, user.id, pending_only=False)
        bank_deposits = DepositService.list_user_bank_deposits(session, user.id, limit=10)
        crypto_deposits = DepositService.list_user_crypto_deposits(session, user.id, limit=10)

    lines = ["History (latest):", ""]
    lines.append("Bank Deposits:")
    if bank_deposits:
        for item in bank_deposits:
            lines.append(f"#{item.id} | {item.status} | {item.created_at:%Y-%m-%d %H:%M}")
    else:
        lines.append("- no bank deposit records")

    lines.append("")
    lines.append("Crypto Deposits:")
    if crypto_deposits:
        for item in crypto_deposits:
            lines.append(
                f"#{item.id} | {item.status} | {Decimal(item.expected_trx):.6f} TRX | {item.created_at:%Y-%m-%d %H:%M}"
            )
    else:
        lines.append("- no crypto deposit records")

    lines.append("")
    lines.append("Orders:")
    if orders:
        for order in orders:
            lines.append(f"#{order.id} | {order.product.name} | {order.status}")
    else:
        lines.append("- no order records")

    await update.effective_message.reply_text("\n".join(lines), reply_markup=main_menu_keyboard())
    return MENU


async def user_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return MENU

    await query.answer()
    data = query.data or ""

    if data == "menu_back":
        await query.edit_message_text("Main menu is below.")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Choose an action:",
                reply_markup=main_menu_keyboard(),
            )
        return MENU

    if data == "load_back":
        with session_scope() as session:
            packages = DepositService.list_active_packages(session)
        if not packages:
            await query.edit_message_text(NO_ACTIVE_ITEMS)
            return MENU
        await query.edit_message_text(LOAD_COINS, reply_markup=packages_keyboard(packages))
        return MENU

    if data.startswith("load_pkg:"):
        package_id = int(data.split(":", 1)[1])
        with session_scope() as session:
            package = DepositService.get_package(session, package_id)
        if not package or not package.is_active:
            await query.edit_message_text("Package not available.")
            return MENU

        context.user_data["selected_package_id"] = package_id
        msg = (
            f"Selected package: {package.name}\n"
            f"TRY price: {fmt_try(package.try_price)}\n"
            f"COIN amount: {package.coin_amount}\n"
            f"TRX amount: {fmt_trx(package.trx_amount)}\n\n"
            "Choose payment method:"
        )
        await query.edit_message_text(msg, reply_markup=payment_method_keyboard(package_id))
        return MENU

    if data.startswith("pay_bank:"):
        package_id = int(data.split(":", 1)[1])
        context.user_data["selected_package_id"] = package_id

        settings: Settings = context.application.bot_data["settings"]
        with session_scope() as session:
            package = DepositService.get_package(session, package_id)
        if not package:
            await query.edit_message_text("Package not found.")
            return MENU

        await query.edit_message_text(
            f"{BANK_RECEIPT_REQUEST}\n\n"
            f"Package: {package.name} ({package.coin_amount} COIN)\n"
            f"Amount: {fmt_try(package.try_price)}\n\n"
            f"Bank details:\n{settings.iban_text}\n\n"
            "Now upload your receipt as photo/document.",
        )
        return WAIT_BANK_RECEIPT

    if data.startswith("pay_trx:"):
        package_id = int(data.split(":", 1)[1])
        settings: Settings = context.application.bot_data["settings"]

        if not update.effective_user:
            await query.edit_message_text("User not found.")
            return MENU

        try:
            with session_scope() as session:
                user = UserService.get_or_create_user(session, update.effective_user)
                req = DepositService.create_crypto_deposit_request(
                    session,
                    user_id=user.id,
                    package_id=package_id,
                    wallet_address=settings.tron_wallet_address,
                )
                package = DepositService.get_package(session, package_id)
        except ValueError as exc:
            await query.edit_message_text(f"Cannot create TRX request: {exc}")
            return MENU

        if not package:
            await query.edit_message_text("Package not found.")
            return MENU

        await query.edit_message_text(
            f"{TRX_PAYMENT_TEXT}\n\n"
            f"Request ID: #{req.id}\n"
            f"Wallet: {settings.tron_wallet_address}\n"
            f"Exact Amount: {fmt_trx(req.expected_trx)}\n"
            f"Package: {package.coin_amount} COIN\n\n"
            "After blockchain detection, admin will approve manually.",
        )

        await send_message_to_admins(
            context.application,
            settings,
            text=(
                "New TRX deposit request created.\n"
                f"Request: #{req.id}\n"
                f"User TG: {update.effective_user.id}\n"
                f"Expected: {fmt_trx(req.expected_trx)}"
            ),
        )
        return MENU

    if data == "shop_back_games":
        with session_scope() as session:
            games = ShopService.list_active_games(session)
        if not games:
            await query.edit_message_text(NO_ACTIVE_ITEMS)
            return MENU
        await query.edit_message_text(SHOP_SELECT_GAME, reply_markup=games_keyboard(games))
        return MENU

    if data.startswith("shop_game:"):
        game_id = int(data.split(":", 1)[1])
        context.user_data["shop_game_id"] = game_id

        with session_scope() as session:
            products = ShopService.list_active_products_by_game(session, game_id)

        if not products:
            await query.edit_message_text("No products for this game.")
            return MENU

        await query.edit_message_text("Select product:", reply_markup=products_keyboard(products))
        return MENU

    if data == "shop_back_products":
        game_id = context.user_data.get("shop_game_id")
        if not game_id:
            await query.edit_message_text("Session expired. Please select game again.")
            return MENU

        with session_scope() as session:
            products = ShopService.list_active_products_by_game(session, int(game_id))

        if not products:
            await query.edit_message_text("No products for this game.")
            return MENU

        await query.edit_message_text("Select product:", reply_markup=products_keyboard(products))
        return MENU

    if data.startswith("shop_product:"):
        product_id = int(data.split(":", 1)[1])
        with session_scope() as session:
            product = ShopService.get_product(session, product_id)

        if not product:
            await query.edit_message_text("Product not found.")
            return MENU

        await query.edit_message_text(
            f"{product.name}\n"
            f"Price: {product.price_coins} COIN\n"
            f"Description: {product.description or '-'}",
            reply_markup=confirm_buy_keyboard(product.id),
        )
        return MENU

    if data.startswith("shop_buy:"):
        if not update.effective_user:
            await query.edit_message_text("User not found.")
            return MENU

        product_id = int(data.split(":", 1)[1])

        try:
            with session_scope() as session:
                user = UserService.get_or_create_user(session, update.effective_user)
                order = ShopService.create_order_with_coin_deduction(
                    session,
                    user_id=user.id,
                    product_id=product_id,
                )
                product = ShopService.get_product(session, product_id)
                game = ShopService.get_game(session, product.game_id) if product else None
                new_balance = user.coin_balance
        except ValueError as exc:
            await query.edit_message_text(f"Purchase failed: {exc}")
            return MENU

        if not product or not game:
            await query.edit_message_text("Product/game not found.")
            return MENU

        context.user_data["pending_order_id"] = order.id
        context.user_data["pending_order_game_label"] = game.id_label

        await query.edit_message_text(
            f"Purchase success. {product.price_coins} COIN deducted.\n"
            f"New balance: {new_balance} COIN\n\n"
            f"Now send your {game.id_label}:"
        )
        return WAIT_GAME_USER_ID

    return MENU


async def handle_bank_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    package_id = context.user_data.get("selected_package_id")
    if not package_id:
        await update.effective_message.reply_text("No package selected. Please start again.")
        return MENU

    file_id: str | None = None
    file_type = "photo"

    if update.effective_message.photo:
        file_id = update.effective_message.photo[-1].file_id
        file_type = "photo"
    elif update.effective_message.document:
        file_id = update.effective_message.document.file_id
        file_type = "document"

    if not file_id:
        await update.effective_message.reply_text("Please upload photo or document receipt.")
        return WAIT_BANK_RECEIPT

    try:
        with session_scope() as session:
            user = UserService.get_or_create_user(session, update.effective_user)
            req = DepositService.create_bank_deposit_request(
                session,
                user_id=user.id,
                package_id=int(package_id),
                receipt_file_id=file_id,
                receipt_file_type=file_type,
            )
            package = DepositService.get_package(session, int(package_id))
            waiting_text = TemplateService.get_template(
                session,
                key="deposit_waiting",
                fallback="Your deposit request has been received. Please wait for admin approval.",
            )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
        return MENU

    await update.effective_message.reply_text(
        f"Receipt received. Request ID: #{req.id}.\n"
        f"{waiting_text}",
        reply_markup=main_menu_keyboard(),
    )

    settings: Settings = context.application.bot_data["settings"]
    caption = (
        "Pending bank deposit\n"
        f"Request: #{req.id}\n"
        f"User TG: {update.effective_user.id}\n"
        f"Package: {package.name if package else '-'}\n"
        f"Coin: {package.coin_amount if package else '-'}"
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve", callback_data=f"admin_bank_ok:{req.id}"),
                InlineKeyboardButton("Reject", callback_data=f"admin_bank_no:{req.id}"),
            ]
        ]
    )
    await send_receipt_to_admins(
        context.application,
        settings,
        receipt_file_id=file_id,
        file_type=file_type,
        caption=caption,
        reply_markup=markup,
    )

    context.user_data.pop("selected_package_id", None)
    return MENU


async def handle_game_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return WAIT_GAME_USER_ID

    game_user_id = update.effective_message.text.strip()
    if len(game_user_id) < 2:
        await update.effective_message.reply_text("Please enter a valid game user ID.")
        return WAIT_GAME_USER_ID

    context.user_data["pending_game_user_id"] = game_user_id
    await update.effective_message.reply_text("Now send your IBAN:")
    return WAIT_IBAN


async def handle_iban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return WAIT_IBAN

    iban = update.effective_message.text.strip().replace(" ", "")
    if len(iban) < 10:
        await update.effective_message.reply_text("Please enter a valid IBAN.")
        return WAIT_IBAN

    context.user_data["pending_iban"] = iban
    await update.effective_message.reply_text("Now send Name Surname:")
    return WAIT_FULL_NAME


async def handle_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return WAIT_FULL_NAME

    full_name = update.effective_message.text.strip()
    if len(full_name.split()) < 2:
        await update.effective_message.reply_text("Please enter full name and surname.")
        return WAIT_FULL_NAME

    context.user_data["pending_full_name"] = full_name
    await update.effective_message.reply_text("Now send Bank Name:")
    return WAIT_BANK_NAME


async def handle_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    bank_name = update.effective_message.text.strip()
    if len(bank_name) < 2:
        await update.effective_message.reply_text("Please enter bank name.")
        return WAIT_BANK_NAME

    order_id = context.user_data.get("pending_order_id")
    game_user_id = context.user_data.get("pending_game_user_id")
    iban = context.user_data.get("pending_iban")
    full_name = context.user_data.get("pending_full_name")

    if not order_id or not game_user_id or not iban or not full_name:
        await update.effective_message.reply_text("Order session expired. Please buy again.")
        _clear_user_context(context)
        return MENU

    with session_scope() as session:
        order = ShopService.attach_delivery_info(
            session,
            order_id=int(order_id),
            game_user_id=str(game_user_id),
            iban=str(iban),
            full_name=str(full_name),
            bank_name=bank_name,
        )
        user: User | None = UserService.get_by_telegram_id(session, update.effective_user.id)
        order_received_text = TemplateService.get_template(
            session,
            key="order_received",
            fallback="Your order is created. Our admin will complete delivery soon.",
        )

    await update.effective_message.reply_text(
        f"Order #{order.id} is submitted for admin processing.\n{order_received_text}",
        reply_markup=main_menu_keyboard(),
    )

    settings: Settings = context.application.bot_data["settings"]
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Complete Order", callback_data=f"admin_order_done:{order.id}")]]
    )
    await send_message_to_admins(
        context.application,
        settings,
        text=(
            "New pending order\n"
            f"Order: #{order.id}\n"
            f"User TG: {update.effective_user.id}\n"
            f"Game User ID: {game_user_id}\n"
            f"IBAN: {iban}\n"
            f"Name: {full_name}\n"
            f"Bank: {bank_name}\n"
            f"User balance now: {user.coin_balance if user else '?'}"
        ),
        reply_markup=markup,
    )

    _clear_user_context(context)
    return MENU



def build_user_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(r"^(Balance|Load Coins|Shop|My Orders|History)$"), menu_router),
            CallbackQueryHandler(
                user_callback_router,
                pattern=r"^(load_|pay_|shop_|menu_back|load_back)",
            ),
        ],
        states={
            MENU: [
                CommandHandler("start", start),
                MessageHandler(filters.Regex(r"^(Balance|Load Coins|Shop|My Orders|History)$"), menu_router),
                CallbackQueryHandler(
                    user_callback_router,
                    pattern=r"^(load_|pay_|shop_|menu_back|load_back)",
                ),
            ],
            WAIT_BANK_RECEIPT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_bank_receipt)
            ],
            WAIT_GAME_USER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_game_user_id)
            ],
            WAIT_IBAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_iban)],
            WAIT_FULL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_full_name)
            ],
            WAIT_BANK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bank_name)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )



def _clear_user_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    keys = [
        "selected_package_id",
        "pending_order_id",
        "pending_order_game_label",
        "pending_game_user_id",
        "pending_iban",
        "pending_full_name",
    ]
    for key in keys:
        context.user_data.pop(key, None)
