from __future__ import annotations

from decimal import Decimal, InvalidOperation
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

from bot.config.settings import Settings
from bot.database.session import session_scope
from bot.keyboards.admin import admin_panel_keyboard, approve_reject_keyboard
from bot.models import User
from bot.services import AdminService, DepositService, ShopService

logger = logging.getLogger(__name__)

(
    ADMIN_MENU,
    ADMIN_WAIT_GAME_NAME,
    ADMIN_WAIT_GAME_REQUIRES,
    ADMIN_WAIT_GAME_LABEL,
    ADMIN_WAIT_PRODUCT_GAME_ID,
    ADMIN_WAIT_PRODUCT_NAME,
    ADMIN_WAIT_PRODUCT_DESC,
    ADMIN_WAIT_PRODUCT_PRICE,
    ADMIN_WAIT_PACKAGE_NAME,
    ADMIN_WAIT_PACKAGE_TRY,
    ADMIN_WAIT_PACKAGE_COIN,
    ADMIN_WAIT_PACKAGE_TRX,
    ADMIN_WAIT_SEARCH_QUERY,
    ADMIN_WAIT_MANUAL_USER_TG,
    ADMIN_WAIT_MANUAL_DELTA,
    ADMIN_WAIT_MANUAL_REASON,
    ADMIN_WAIT_TEMPLATE_KEY,
    ADMIN_WAIT_TEMPLATE_CONTENT,
) = range(100, 118)


async def open_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_admin(update, context):
        return ConversationHandler.END

    target = update.effective_message
    if target:
        await target.reply_text("Admin Panel", reply_markup=admin_panel_keyboard())
    return ADMIN_MENU


async def admin_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_admin(update, context):
        return ConversationHandler.END

    query = update.callback_query
    if not query:
        return ADMIN_MENU

    await query.answer()
    data = query.data or ""

    if data == "admin_back_panel":
        await query.edit_message_text("Admin Panel", reply_markup=admin_panel_keyboard())
        return ADMIN_MENU

    if data == "admin_bank_list":
        await _show_pending_bank(query, context)
        return ADMIN_MENU

    if data.startswith("admin_bank_ok:"):
        request_id = int(data.split(":", 1)[1])
        await _approve_bank(query, context, request_id)
        return ADMIN_MENU

    if data.startswith("admin_bank_no:"):
        request_id = int(data.split(":", 1)[1])
        await _reject_bank(query, context, request_id)
        return ADMIN_MENU

    if data == "admin_crypto_list":
        await _show_pending_crypto(query, context)
        return ADMIN_MENU

    if data.startswith("admin_crypto_ok:"):
        request_id = int(data.split(":", 1)[1])
        await _approve_crypto(query, context, request_id)
        return ADMIN_MENU

    if data.startswith("admin_crypto_no:"):
        request_id = int(data.split(":", 1)[1])
        await _reject_crypto(query, context, request_id)
        return ADMIN_MENU

    if data == "admin_orders_list":
        await _show_pending_orders(query, context)
        return ADMIN_MENU

    if data.startswith("admin_order_done:"):
        order_id = int(data.split(":", 1)[1])
        await _complete_order(query, context, order_id)
        return ADMIN_MENU

    if data == "admin_games":
        await _show_games_menu(query)
        return ADMIN_MENU

    if data.startswith("admin_game_toggle:"):
        game_id = int(data.split(":", 1)[1])
        await _toggle_game(query, context, game_id)
        return ADMIN_MENU

    if data == "admin_game_add":
        await query.edit_message_text("Send game name:")
        return ADMIN_WAIT_GAME_NAME

    if data == "admin_products":
        await _show_products_menu(query)
        return ADMIN_MENU

    if data.startswith("admin_product_toggle:"):
        product_id = int(data.split(":", 1)[1])
        await _toggle_product(query, context, product_id)
        return ADMIN_MENU

    if data == "admin_product_add":
        await query.edit_message_text("Send game ID for this product:")
        return ADMIN_WAIT_PRODUCT_GAME_ID

    if data == "admin_packages":
        await _show_packages_menu(query)
        return ADMIN_MENU

    if data.startswith("admin_package_toggle:"):
        package_id = int(data.split(":", 1)[1])
        await _toggle_package(query, context, package_id)
        return ADMIN_MENU

    if data == "admin_package_add":
        await query.edit_message_text("Send package name:")
        return ADMIN_WAIT_PACKAGE_NAME

    if data == "admin_search":
        await query.edit_message_text("Send Telegram ID or username to search:")
        return ADMIN_WAIT_SEARCH_QUERY

    if data == "admin_manual":
        await query.edit_message_text("Send target user Telegram ID:")
        return ADMIN_WAIT_MANUAL_USER_TG

    if data == "admin_templates":
        await _show_templates_menu(query)
        return ADMIN_MENU

    if data == "admin_tpl_add":
        await query.edit_message_text("Send new template key (example: welcome_text):")
        context.user_data["template_edit_key"] = None
        return ADMIN_WAIT_TEMPLATE_KEY

    if data.startswith("admin_tpl_edit:"):
        template_id = int(data.split(":", 1)[1])
        with session_scope() as session:
            templates = AdminService.list_templates(session)
            tpl = next((t for t in templates if t.id == template_id), None)
        if not tpl:
            await query.edit_message_text("Template not found.")
            return ADMIN_MENU

        context.user_data["template_edit_key"] = tpl.key
        await query.edit_message_text(
            f"Send new content for template key '{tpl.key}':\n\nCurrent:\n{tpl.content}"
        )
        return ADMIN_WAIT_TEMPLATE_CONTENT

    await query.edit_message_text("Unknown admin action.")
    return ADMIN_MENU


async def handle_game_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_admin(update, context):
        return ConversationHandler.END

    name = (update.effective_message.text if update.effective_message else "").strip()
    if len(name) < 2:
        await update.effective_message.reply_text("Invalid name. Send game name:")
        return ADMIN_WAIT_GAME_NAME

    context.user_data["new_game_name"] = name
    await update.effective_message.reply_text("Requires server? (yes/no)")
    return ADMIN_WAIT_GAME_REQUIRES


async def handle_game_requires(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text if update.effective_message else "").strip().lower()
    if text not in {"yes", "no", "y", "n"}:
        await update.effective_message.reply_text("Please answer yes or no.")
        return ADMIN_WAIT_GAME_REQUIRES

    context.user_data["new_game_requires"] = text in {"yes", "y"}
    await update.effective_message.reply_text("Send game id label (example: Player ID):")
    return ADMIN_WAIT_GAME_LABEL


async def handle_game_label(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message or not update.effective_user:
        return ADMIN_MENU

    label = update.effective_message.text.strip()
    if len(label) < 2:
        await update.effective_message.reply_text("Invalid label. Send again:")
        return ADMIN_WAIT_GAME_LABEL

    name = context.user_data.get("new_game_name")
    requires_server = bool(context.user_data.get("new_game_requires", False))

    with session_scope() as session:
        game = AdminService.create_game(
            session,
            admin_id=update.effective_user.id,
            name=str(name),
            requires_server=requires_server,
            id_label=label,
        )

    await update.effective_message.reply_text(
        f"Game created: #{game.id} {game.name}",
        reply_markup=admin_panel_keyboard(),
    )
    _clear_admin_create_game_context(context)
    return ADMIN_MENU


async def handle_product_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text if update.effective_message else "").strip()
    if not raw.isdigit():
        await update.effective_message.reply_text("Game ID must be numeric. Send game ID:")
        return ADMIN_WAIT_PRODUCT_GAME_ID

    context.user_data["new_product_game_id"] = int(raw)
    await update.effective_message.reply_text("Send product name:")
    return ADMIN_WAIT_PRODUCT_NAME


async def handle_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.effective_message.text if update.effective_message else "").strip()
    if len(name) < 2:
        await update.effective_message.reply_text("Invalid product name. Send again:")
        return ADMIN_WAIT_PRODUCT_NAME

    context.user_data["new_product_name"] = name
    await update.effective_message.reply_text("Send product description:")
    return ADMIN_WAIT_PRODUCT_DESC


async def handle_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc = (update.effective_message.text if update.effective_message else "").strip()
    context.user_data["new_product_desc"] = desc
    await update.effective_message.reply_text("Send product price in COIN (integer):")
    return ADMIN_WAIT_PRODUCT_PRICE


async def handle_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message or not update.effective_user:
        return ADMIN_MENU

    raw = update.effective_message.text.strip()
    if not raw.isdigit():
        await update.effective_message.reply_text("Price must be integer. Send again:")
        return ADMIN_WAIT_PRODUCT_PRICE

    game_id = int(context.user_data.get("new_product_game_id", 0))
    name = str(context.user_data.get("new_product_name", ""))
    desc = str(context.user_data.get("new_product_desc", ""))
    price = int(raw)

    try:
        with session_scope() as session:
            product = AdminService.create_product(
                session,
                admin_id=update.effective_user.id,
                game_id=game_id,
                name=name,
                description=desc,
                price_coins=price,
            )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
        return ADMIN_WAIT_PRODUCT_GAME_ID

    await update.effective_message.reply_text(
        f"Product created: #{product.id} {product.name}",
        reply_markup=admin_panel_keyboard(),
    )
    _clear_admin_create_product_context(context)
    return ADMIN_MENU


async def handle_package_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.effective_message.text if update.effective_message else "").strip()
    if len(name) < 2:
        await update.effective_message.reply_text("Invalid package name. Send again:")
        return ADMIN_WAIT_PACKAGE_NAME

    context.user_data["new_package_name"] = name
    await update.effective_message.reply_text("Send TRY price (example: 250.00):")
    return ADMIN_WAIT_PACKAGE_TRY


async def handle_package_try(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text if update.effective_message else "").strip().replace(",", ".")
    try:
        value = Decimal(raw)
        if value <= 0:
            raise ValueError("must be positive")
    except (InvalidOperation, ValueError):
        await update.effective_message.reply_text("Invalid TRY price. Send again:")
        return ADMIN_WAIT_PACKAGE_TRY

    context.user_data["new_package_try"] = str(value)
    await update.effective_message.reply_text("Send COIN amount (integer):")
    return ADMIN_WAIT_PACKAGE_COIN


async def handle_package_coin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text if update.effective_message else "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await update.effective_message.reply_text("Invalid COIN amount. Send again:")
        return ADMIN_WAIT_PACKAGE_COIN

    context.user_data["new_package_coin"] = int(raw)
    await update.effective_message.reply_text("Send TRX amount (example: 25.500000):")
    return ADMIN_WAIT_PACKAGE_TRX


async def handle_package_trx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message or not update.effective_user:
        return ADMIN_MENU

    raw = update.effective_message.text.strip().replace(",", ".")
    try:
        trx = Decimal(raw)
        if trx <= 0:
            raise ValueError("must be positive")
    except (InvalidOperation, ValueError):
        await update.effective_message.reply_text("Invalid TRX amount. Send again:")
        return ADMIN_WAIT_PACKAGE_TRX

    name = str(context.user_data.get("new_package_name"))
    try_price = Decimal(str(context.user_data.get("new_package_try")))
    coin_amount = int(context.user_data.get("new_package_coin"))

    with session_scope() as session:
        pkg = AdminService.create_coin_package(
            session,
            admin_id=update.effective_user.id,
            name=name,
            try_price=try_price,
            coin_amount=coin_amount,
            trx_amount=trx,
        )

    await update.effective_message.reply_text(
        f"Coin package created: #{pkg.id} {pkg.name}",
        reply_markup=admin_panel_keyboard(),
    )
    _clear_admin_create_package_context(context)
    return ADMIN_MENU


async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return ADMIN_MENU

    query = update.effective_message.text.strip()
    with session_scope() as session:
        users = AdminService.search_users(session, query)

    if not users:
        await update.effective_message.reply_text(
            "No users found.",
            reply_markup=admin_panel_keyboard(),
        )
        return ADMIN_MENU

    lines = [f"Found {len(users)} user(s):"]
    for user in users[:20]:
        lines.append(
            f"id={user.id} tg={user.telegram_id} username=@{user.username or '-'} balance={user.coin_balance}"
        )

    await update.effective_message.reply_text("\n".join(lines), reply_markup=admin_panel_keyboard())
    return ADMIN_MENU


async def handle_manual_user_tg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text if update.effective_message else "").strip()
    if not raw.isdigit():
        await update.effective_message.reply_text("Telegram ID must be numeric. Send again:")
        return ADMIN_WAIT_MANUAL_USER_TG

    context.user_data["manual_user_tg"] = int(raw)
    await update.effective_message.reply_text("Send coin delta (e.g. +100 or -50):")
    return ADMIN_WAIT_MANUAL_DELTA


async def handle_manual_delta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text if update.effective_message else "").strip().replace(" ", "")
    try:
        delta = int(raw)
    except ValueError:
        await update.effective_message.reply_text("Delta must be integer with sign. Send again:")
        return ADMIN_WAIT_MANUAL_DELTA

    if delta == 0:
        await update.effective_message.reply_text("Delta cannot be 0. Send again:")
        return ADMIN_WAIT_MANUAL_DELTA

    context.user_data["manual_delta"] = delta
    await update.effective_message.reply_text("Send reason for log:")
    return ADMIN_WAIT_MANUAL_REASON


async def handle_manual_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message or not update.effective_user:
        return ADMIN_MENU

    reason = update.effective_message.text.strip()
    if len(reason) < 2:
        await update.effective_message.reply_text("Reason too short. Send again:")
        return ADMIN_WAIT_MANUAL_REASON

    telegram_id = int(context.user_data.get("manual_user_tg", 0))
    delta = int(context.user_data.get("manual_delta", 0))

    try:
        with session_scope() as session:
            user = AdminService.manual_coin_adjust(
                session,
                admin_id=update.effective_user.id,
                telegram_id=telegram_id,
                delta=delta,
                reason=reason,
            )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=admin_panel_keyboard())
        return ADMIN_MENU

    await update.effective_message.reply_text(
        f"Balance updated. User {user.telegram_id} new balance: {user.coin_balance} COIN",
        reply_markup=admin_panel_keyboard(),
    )

    try:
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Your coin balance was updated by admin. Delta: {delta}. New balance: {user.coin_balance}",
        )
    except Exception:
        logger.exception("Failed to notify user after manual balance adjust")

    _clear_admin_manual_context(context)
    return ADMIN_MENU


async def handle_template_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return ADMIN_MENU

    key = update.effective_message.text.strip()
    if len(key) < 3 or " " in key:
        await update.effective_message.reply_text("Invalid key. Use letters/numbers/underscore, no spaces:")
        return ADMIN_WAIT_TEMPLATE_KEY

    context.user_data["template_edit_key"] = key
    await update.effective_message.reply_text("Send template content:")
    return ADMIN_WAIT_TEMPLATE_CONTENT


async def handle_template_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message or not update.effective_user:
        return ADMIN_MENU

    key = context.user_data.get("template_edit_key")
    content = update.effective_message.text.strip()

    if not key:
        await update.effective_message.reply_text(
            "Template key missing. Start again from templates menu.",
            reply_markup=admin_panel_keyboard(),
        )
        return ADMIN_MENU

    if len(content) < 2:
        await update.effective_message.reply_text("Content too short. Send again:")
        return ADMIN_WAIT_TEMPLATE_CONTENT

    with session_scope() as session:
        tpl = AdminService.upsert_template(
            session,
            admin_id=update.effective_user.id,
            key=str(key),
            content=content,
        )

    await update.effective_message.reply_text(
        f"Template saved: {tpl.key}",
        reply_markup=admin_panel_keyboard(),
    )
    context.user_data.pop("template_edit_key", None)
    return ADMIN_MENU


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _clear_admin_create_game_context(context)
    _clear_admin_create_product_context(context)
    _clear_admin_create_package_context(context)
    _clear_admin_manual_context(context)
    context.user_data.pop("template_edit_key", None)

    if update.effective_message:
        await update.effective_message.reply_text(
            "Cancelled admin action.",
            reply_markup=admin_panel_keyboard(),
        )
    return ADMIN_MENU


async def _show_pending_bank(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        rows = DepositService.list_pending_bank_requests(session)

    if not rows:
        await query.edit_message_text("No pending bank deposits.", reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(
        f"Pending bank deposits: {len(rows)}\nDetails sent below.",
        reply_markup=admin_panel_keyboard(),
    )

    chat_id = query.message.chat_id
    for req in rows[:20]:
        text = (
            f"Bank Request #{req.id}\n"
            f"User TG: {req.user.telegram_id}\n"
            f"Username: @{req.user.username or '-'}\n"
            f"Package: {req.package.name}\n"
            f"Coin: {req.package.coin_amount}\n"
            f"TRY: {req.package.try_price}\n"
            f"Created: {req.created_at:%Y-%m-%d %H:%M}"
        )
        markup = approve_reject_keyboard(
            approve_data=f"admin_bank_ok:{req.id}",
            reject_data=f"admin_bank_no:{req.id}",
        )

        if req.receipt_file_type == "document":
            await context.bot.send_document(
                chat_id=chat_id,
                document=req.receipt_file_id,
                caption=text,
                reply_markup=markup,
            )
        else:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=req.receipt_file_id,
                caption=text,
                reply_markup=markup,
            )


async def _approve_bank(query, context: ContextTypes.DEFAULT_TYPE, request_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            req = DepositService.approve_bank_request(session, request_id, admin_id)
            user = session.get(User, req.user_id)
    except ValueError as exc:
        await query.edit_message_text(f"Cannot approve: {exc}")
        return

    await query.edit_message_text(f"Bank request #{request_id} approved.")
    if user:
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Your bank deposit request #{request_id} is approved. Coins added.",
        )


async def _reject_bank(query, context: ContextTypes.DEFAULT_TYPE, request_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            req = DepositService.reject_bank_request(
                session,
                request_id,
                admin_id,
                note="Rejected by admin",
            )
            user = session.get(User, req.user_id)
    except ValueError as exc:
        await query.edit_message_text(f"Cannot reject: {exc}")
        return

    await query.edit_message_text(f"Bank request #{request_id} rejected.")
    if user:
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Your bank deposit request #{request_id} was rejected. Contact support.",
        )


async def _show_pending_crypto(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        rows = DepositService.list_pending_crypto_requests(session)

    if not rows:
        await query.edit_message_text("No pending crypto deposits.", reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(
        f"Pending crypto deposits: {len(rows)}\nDetails sent below.",
        reply_markup=admin_panel_keyboard(),
    )

    chat_id = query.message.chat_id
    for req in rows[:30]:
        text = (
            f"Crypto Request #{req.id}\n"
            f"User TG: {req.user.telegram_id}\n"
            f"Package: {req.package.name}\n"
            f"Expected: {req.expected_trx} TRX\n"
            f"Status: {req.status}\n"
            f"TX: {req.tx_hash or '-'}"
        )
        markup = approve_reject_keyboard(
            approve_data=f"admin_crypto_ok:{req.id}",
            reject_data=f"admin_crypto_no:{req.id}",
        )
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


async def _approve_crypto(query, context: ContextTypes.DEFAULT_TYPE, request_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            req = DepositService.approve_crypto_request(session, request_id, admin_id)
            user = session.get(User, req.user_id)
    except ValueError as exc:
        await query.edit_message_text(f"Cannot approve: {exc}")
        return

    await query.edit_message_text(f"Crypto request #{request_id} approved.")
    if user:
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Your crypto deposit request #{request_id} is approved. Coins added.",
        )


async def _reject_crypto(query, context: ContextTypes.DEFAULT_TYPE, request_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            req = DepositService.reject_crypto_request(
                session,
                request_id,
                admin_id,
                note="Rejected by admin",
            )
            user = session.get(User, req.user_id)
    except ValueError as exc:
        await query.edit_message_text(f"Cannot reject: {exc}")
        return

    await query.edit_message_text(f"Crypto request #{request_id} rejected.")
    if user:
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Your crypto deposit request #{request_id} was rejected. Contact support.",
        )


async def _show_pending_orders(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        rows = ShopService.list_pending_orders(session)

    if not rows:
        await query.edit_message_text("No pending orders.", reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(
        f"Pending orders: {len(rows)}\nDetails sent below.",
        reply_markup=admin_panel_keyboard(),
    )

    chat_id = query.message.chat_id
    for order in rows[:30]:
        text = (
            f"Order #{order.id}\n"
            f"User TG: {order.user.telegram_id}\n"
            f"Product: {order.product.name}\n"
            f"Game: {order.product.game.name}\n"
            f"Game User ID: {order.game_user_id}\n"
            f"IBAN: {order.iban}\n"
            f"Name: {order.full_name}\n"
            f"Bank: {order.bank_name}"
        )
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Complete", callback_data=f"admin_order_done:{order.id}")]]
        )
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


async def _complete_order(query, context: ContextTypes.DEFAULT_TYPE, order_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            order = ShopService.complete_order(session, order_id, admin_id)
            user = session.get(User, order.user_id)
    except ValueError as exc:
        await query.edit_message_text(f"Cannot complete: {exc}")
        return

    await query.edit_message_text(f"Order #{order_id} completed.")
    if user:
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Your order #{order_id} is completed by admin.",
        )


async def _show_games_menu(query) -> None:
    with session_scope() as session:
        games = AdminService.list_games(session)

    rows = [
        [
            InlineKeyboardButton(
                f"{'ON' if game.is_active else 'OFF'} | {game.name}",
                callback_data=f"admin_game_toggle:{game.id}",
            )
        ]
        for game in games
    ]
    rows.append([InlineKeyboardButton("+ Add Game", callback_data="admin_game_add")])
    rows.append([InlineKeyboardButton("Back", callback_data="admin_back_panel")])

    await query.edit_message_text("Manage Games", reply_markup=InlineKeyboardMarkup(rows))


async def _toggle_game(query, context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    with session_scope() as session:
        game = AdminService.toggle_game(session, query.from_user.id, game_id)

    await query.edit_message_text(
        f"Game updated: {game.name} active={game.is_active}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Back to Games", callback_data="admin_games")]]
        ),
    )


async def _show_products_menu(query) -> None:
    with session_scope() as session:
        products = AdminService.list_products(session)

    rows = [
        [
            InlineKeyboardButton(
                f"{'ON' if p.is_active else 'OFF'} | #{p.id} {p.name} ({p.price_coins})",
                callback_data=f"admin_product_toggle:{p.id}",
            )
        ]
        for p in products[:30]
    ]
    rows.append([InlineKeyboardButton("+ Add Product", callback_data="admin_product_add")])
    rows.append([InlineKeyboardButton("Back", callback_data="admin_back_panel")])

    await query.edit_message_text("Manage Products", reply_markup=InlineKeyboardMarkup(rows))


async def _toggle_product(query, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    with session_scope() as session:
        product = AdminService.toggle_product(session, query.from_user.id, product_id)

    await query.edit_message_text(
        f"Product updated: {product.name} active={product.is_active}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Back to Products", callback_data="admin_products")]]
        ),
    )


async def _show_packages_menu(query) -> None:
    with session_scope() as session:
        packages = AdminService.list_coin_packages(session)

    rows = [
        [
            InlineKeyboardButton(
                f"{'ON' if p.is_active else 'OFF'} | #{p.id} {p.name}",
                callback_data=f"admin_package_toggle:{p.id}",
            )
        ]
        for p in packages
    ]
    rows.append([InlineKeyboardButton("+ Add Package", callback_data="admin_package_add")])
    rows.append([InlineKeyboardButton("Back", callback_data="admin_back_panel")])

    await query.edit_message_text("Manage Coin Packages", reply_markup=InlineKeyboardMarkup(rows))


async def _toggle_package(query, context: ContextTypes.DEFAULT_TYPE, package_id: int) -> None:
    with session_scope() as session:
        package = AdminService.toggle_coin_package(session, query.from_user.id, package_id)

    await query.edit_message_text(
        f"Package updated: {package.name} active={package.is_active}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Back to Packages", callback_data="admin_packages")]]
        ),
    )


async def _show_templates_menu(query) -> None:
    with session_scope() as session:
        templates = AdminService.list_templates(session)

    rows = [
        [InlineKeyboardButton(f"Edit: {tpl.key}", callback_data=f"admin_tpl_edit:{tpl.id}")]
        for tpl in templates[:30]
    ]
    rows.append([InlineKeyboardButton("+ Add Template", callback_data="admin_tpl_add")])
    rows.append([InlineKeyboardButton("Back", callback_data="admin_back_panel")])

    await query.edit_message_text("Manage Message Templates", reply_markup=InlineKeyboardMarkup(rows))


async def _require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    settings: Settings = context.application.bot_data["settings"]
    user = update.effective_user
    if user and user.id in settings.admin_ids:
        return True

    if update.callback_query:
        await update.callback_query.answer("Admin only", show_alert=True)
    target = update.effective_message or (update.callback_query.message if update.callback_query else None)
    if target:
        await target.reply_text("This command is admin only.")
    return False



def build_admin_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", open_admin_panel),
            CallbackQueryHandler(admin_callback_router, pattern=r"^admin_"),
        ],
        states={
            ADMIN_MENU: [CallbackQueryHandler(admin_callback_router, pattern=r"^admin_")],
            ADMIN_WAIT_GAME_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_game_name)
            ],
            ADMIN_WAIT_GAME_REQUIRES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_game_requires)
            ],
            ADMIN_WAIT_GAME_LABEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_game_label)
            ],
            ADMIN_WAIT_PRODUCT_GAME_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_game_id)
            ],
            ADMIN_WAIT_PRODUCT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_name)
            ],
            ADMIN_WAIT_PRODUCT_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_desc)
            ],
            ADMIN_WAIT_PRODUCT_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_price)
            ],
            ADMIN_WAIT_PACKAGE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_package_name)
            ],
            ADMIN_WAIT_PACKAGE_TRY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_package_try)
            ],
            ADMIN_WAIT_PACKAGE_COIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_package_coin)
            ],
            ADMIN_WAIT_PACKAGE_TRX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_package_trx)
            ],
            ADMIN_WAIT_SEARCH_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_query)
            ],
            ADMIN_WAIT_MANUAL_USER_TG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_user_tg)
            ],
            ADMIN_WAIT_MANUAL_DELTA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_delta)
            ],
            ADMIN_WAIT_MANUAL_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_reason)
            ],
            ADMIN_WAIT_TEMPLATE_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_template_key)
            ],
            ADMIN_WAIT_TEMPLATE_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_template_content)
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel)],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )



def _clear_admin_create_game_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ["new_game_name", "new_game_requires"]:
        context.user_data.pop(key, None)



def _clear_admin_create_product_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ["new_product_game_id", "new_product_name", "new_product_desc"]:
        context.user_data.pop(key, None)



def _clear_admin_create_package_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ["new_package_name", "new_package_try", "new_package_coin"]:
        context.user_data.pop(key, None)



def _clear_admin_manual_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ["manual_user_tg", "manual_delta"]:
        context.user_data.pop(key, None)
