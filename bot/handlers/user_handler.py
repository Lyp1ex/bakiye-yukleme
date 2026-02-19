from __future__ import annotations

from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.admin.notifier import send_receipt_to_admins
from bot.config.settings import Settings
from bot.database.session import session_scope
from bot.keyboards.common import MENU_BAKIYE, MENU_GECMIS, MENU_YUKLEME, main_menu_keyboard
from bot.services import DepositService, TemplateService, UserService
from bot.texts.messages import DEFAULT_TEXT_TEMPLATES

MENU, WAIT_BALANCE_AMOUNT, WAIT_BANK_RECEIPT = range(3)
MENU_REGEX = rf"^({MENU_BAKIYE}|{MENU_YUKLEME}|{MENU_GECMIS})$"

STATUS_MAP_TR = {
    "pending": "Beklemede",
    "approved": "Onaylandı",
    "rejected": "Reddedildi",
    "pending_payment": "Ödeme Bekleniyor",
    "detected": "Ödeme Tespit Edildi",
    "waiting_user_info": "Kullanıcı Bilgisi Bekleniyor",
    "pending_admin": "Admin İşleminde",
    "completed": "Tamamlandı",
    "cancelled": "İptal Edildi",
}



def _get_text(key: str, fallback: str | None = None) -> str:
    default_value = fallback if fallback is not None else DEFAULT_TEXT_TEMPLATES.get(key, key)
    with session_scope() as session:
        return TemplateService.get_template(session, key=key, fallback=default_value)



def _render_text(key: str, **kwargs) -> str:
    fallback = DEFAULT_TEXT_TEMPLATES.get(key, key)
    value = _get_text(key, fallback=fallback)
    try:
        return value.format(**kwargs)
    except Exception:
        try:
            return fallback.format(**kwargs)
        except Exception:
            return fallback



def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")



def _fmt_try(value: Decimal) -> str:
    v = value.quantize(Decimal("0.01"))
    return f"{str(v).replace('.', ',')} TL"



def _parse_amount(text: str) -> int | None:
    cleaned = text.strip().replace(".", "").replace(",", "")
    if not cleaned.isdigit():
        return None
    return int(cleaned)


def _status_text(raw_status: str) -> str:
    return STATUS_MAP_TR.get(raw_status, raw_status)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        UserService.get_or_create_user(session, update.effective_user)

    await update.effective_message.reply_text(
        _get_text("welcome_text"),
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.effective_message:
        await update.effective_message.reply_text(
            _get_text("cancel_text"),
            reply_markup=main_menu_keyboard(),
        )
    return MENU


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text if update.effective_message else "").strip()

    if text == MENU_BAKIYE:
        return await show_balance(update, context)
    if text == MENU_YUKLEME:
        return await start_balance_loading(update, context)
    if text == MENU_GECMIS:
        return await show_history(update, context)

    if update.effective_message:
        await update.effective_message.reply_text(
            _get_text("use_menu_buttons_text"),
            reply_markup=main_menu_keyboard(),
        )
    return MENU


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)

    await update.effective_message.reply_text(
        _render_text("balance_text", balance=_fmt_int(user.coin_balance)),
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def start_balance_loading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return MENU

    settings: Settings = context.application.bot_data["settings"]
    await update.effective_message.reply_text(
        _render_text(
            "load_balance_start_text",
            min_amount=_fmt_int(settings.min_balance_amount),
            max_amount=_fmt_int(settings.max_balance_amount),
        )
    )
    return WAIT_BALANCE_AMOUNT


async def handle_balance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return WAIT_BALANCE_AMOUNT

    settings: Settings = context.application.bot_data["settings"]
    amount = _parse_amount(update.effective_message.text)

    if amount is None or amount < settings.min_balance_amount or amount > settings.max_balance_amount:
        await update.effective_message.reply_text(
            _render_text(
                "invalid_balance_amount_text",
                min_amount=_fmt_int(settings.min_balance_amount),
                max_amount=_fmt_int(settings.max_balance_amount),
            )
        )
        return WAIT_BALANCE_AMOUNT

    payment_try = (Decimal(amount) * settings.balance_payment_rate).quantize(Decimal("0.01"))

    context.user_data["requested_balance_amount"] = amount
    context.user_data["payment_try_amount"] = str(payment_try)

    await update.effective_message.reply_text(
        _render_text(
            "payment_instruction_text",
            balance_amount=_fmt_int(amount),
            rate_percent=str((settings.balance_payment_rate * Decimal("100")).quantize(Decimal("0.01"))).replace(".", ","),
            payment_try=_fmt_try(payment_try),
            iban_text=settings.iban_text,
        )
    )
    return WAIT_BANK_RECEIPT


async def handle_bank_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    requested_amount = context.user_data.get("requested_balance_amount")
    payment_try_raw = context.user_data.get("payment_try_amount")
    if not requested_amount or not payment_try_raw:
        await update.effective_message.reply_text(
            _get_text("use_menu_buttons_text"),
            reply_markup=main_menu_keyboard(),
        )
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
        await update.effective_message.reply_text(_get_text("upload_receipt_only_text"))
        return WAIT_BANK_RECEIPT

    payment_try = Decimal(str(payment_try_raw))

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)
        package = DepositService.get_or_create_dynamic_package(
            session,
            balance_amount=int(requested_amount),
            payment_try=payment_try,
        )
        req = DepositService.create_bank_deposit_request(
            session,
            user_id=user.id,
            package_id=package.id,
            receipt_file_id=file_id,
            receipt_file_type=file_type,
        )
        waiting_text = TemplateService.get_template(
            session,
            key="deposit_waiting",
            fallback=DEFAULT_TEXT_TEMPLATES["deposit_waiting"],
        )

    await update.effective_message.reply_text(
        _render_text("deposit_received_text", request_id=req.id, waiting_text=waiting_text),
        reply_markup=main_menu_keyboard(),
    )

    settings: Settings = context.application.bot_data["settings"]
    caption = _render_text(
        "receipt_caption_admin_text",
        request_id=req.id,
        telegram_id=update.effective_user.id,
        balance_amount=_fmt_int(int(requested_amount)),
        payment_try=_fmt_try(payment_try),
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Onayla", callback_data=f"admin_bank_ok:{req.id}"),
                InlineKeyboardButton("Reddet", callback_data=f"admin_bank_no:{req.id}"),
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

    context.user_data.clear()
    return MENU


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)
        bank_deposits = DepositService.list_user_bank_deposits(session, user.id, limit=20)
        crypto_deposits = DepositService.list_user_crypto_deposits(session, user.id, limit=20)

    lines = [_get_text("history_header_text"), ""]
    lines.append(_get_text("bank_history_header_text"))

    if bank_deposits:
        for item in bank_deposits:
            lines.append(
                f"#{item.id} | {_status_text(item.status)} | {_fmt_int(item.package.coin_amount)} BAKİYE | {_fmt_try(Decimal(item.package.try_price))}"
            )
    else:
        lines.append(_get_text("no_bank_deposit_records_text"))

    lines.append("")
    lines.append(_get_text("crypto_history_header_text"))
    if crypto_deposits:
        for item in crypto_deposits:
            lines.append(
                f"#{item.id} | {_status_text(item.status)} | {Decimal(item.expected_trx):.6f} TRX"
            )
    else:
        lines.append(_get_text("no_crypto_deposit_records_text"))

    await update.effective_message.reply_text("\n".join(lines), reply_markup=main_menu_keyboard())
    return MENU



def build_user_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(MENU_REGEX), menu_router),
        ],
        states={
            MENU: [
                CommandHandler("start", start),
                MessageHandler(filters.Regex(MENU_REGEX), menu_router),
            ],
            WAIT_BALANCE_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_balance_amount)
            ],
            WAIT_BANK_RECEIPT: [
                MessageHandler(~filters.COMMAND, handle_bank_receipt)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )
