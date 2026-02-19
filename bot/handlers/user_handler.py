from __future__ import annotations

from decimal import Decimal
import re

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
    MENU_BAKIYE,
    MENU_CEKIM,
    MENU_DESTEK,
    MENU_DURUM,
    MENU_GECMIS,
    MENU_KURALLAR,
    MENU_SSS,
    MENU_YUKLEME,
    main_menu_keyboard,
)
from bot.services import (
    DepositService,
    TemplateService,
    UserService,
    WithdrawalService,
    verify_receipt_image,
)
from bot.texts.messages import DEFAULT_TEXT_TEMPLATES

(
    MENU,
    WAIT_BALANCE_AMOUNT,
    WAIT_BANK_RECEIPT,
    WAIT_WITHDRAW_NAME,
    WAIT_WITHDRAW_IBAN,
    WAIT_WITHDRAW_BANK,
    WAIT_WITHDRAW_CONFIRM,
) = range(7)

_MENU_ITEMS = [MENU_BAKIYE, MENU_YUKLEME, MENU_CEKIM, MENU_DURUM, MENU_GECMIS, MENU_KURALLAR, MENU_SSS, MENU_DESTEK]
MENU_REGEX = r"^(" + "|".join(re.escape(item) for item in _MENU_ITEMS) + r")$"

STATUS_MAP_TR = {
    "pending": "Beklemede",
    "approved": "Onaylandı",
    "rejected": "Reddedildi",
    "pending_payment": "Ödeme Bekleniyor",
    "detected": "Ödeme Tespit Edildi",
    "paid_waiting_proof": "SS Bekleniyor",
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


def _req_code(request_id: int) -> str:
    return f"DS-#{request_id}"


def _support_url(settings: Settings) -> str:
    return f"https://t.me/{settings.support_username}"


def _normalize_iban(text: str) -> str:
    return text.strip().replace(" ", "").upper()


def _is_valid_iban(text: str) -> bool:
    iban = _normalize_iban(text)
    return len(iban) == 26 and iban.startswith("TR") and iban[2:].isdigit()


def _next_step_for_status(status: str, flow: str) -> str:
    if flow == "bank":
        if status == "pending":
            return "Admin dekontu inceliyor."
        if status == "approved":
            return "Yükleme tamamlandı."
        if status == "rejected":
            return "Destek ile iletişime geçin."
    if flow == "crypto":
        if status == "pending_payment":
            return "TRX transferi bekleniyor."
        if status == "detected":
            return "Transfer tespit edildi, admin onayı bekleniyor."
        if status == "approved":
            return "Yükleme tamamlandı."
        if status == "rejected":
            return "Destek ile iletişime geçin."
    if flow == "withdraw":
        if status == "pending":
            return "Admin çekim talebinizi inceliyor."
        if status == "paid_waiting_proof":
            return "Ödeme sonrası SS yükleyin."
        if status == "completed":
            return "Çekim tamamlandı."
        if status == "rejected":
            return "Tutar bakiyenize iade edildi."
    return "İşlem takibi için destekle iletişime geçin."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        UserService.get_or_create_user(session, update.effective_user)

    settings: Settings = context.application.bot_data["settings"]
    welcome_text = _render_text("welcome_text", support_username=f"@{settings.support_username}")
    welcome_text = (
        f"{welcome_text}\n"
        f"Son güncelleme: {settings.app_last_updated}\n"
        "Tüm işlemler kayıt altındadır."
    )
    await update.effective_message.reply_text(
        welcome_text,
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
    if text == MENU_CEKIM:
        return await start_withdrawal(update, context)
    if text == MENU_DURUM:
        return await show_request_status(update, context)
    if text == MENU_GECMIS:
        return await show_history(update, context)
    if text == MENU_KURALLAR:
        return await show_rules(update, context)
    if text == MENU_SSS:
        return await show_faq(update, context)
    if text == MENU_DESTEK:
        return await show_support(update, context)

    if update.effective_message:
        settings: Settings = context.application.bot_data["settings"]
        await update.effective_message.reply_text(
            _get_text("use_menu_buttons_text"),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Desteğe Git", url=_support_url(settings))]]
            ),
        )
        await update.effective_message.reply_text("Ana menü aşağıdadır.", reply_markup=main_menu_keyboard())
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
            request_code_hint="DS-#(otomatik)",
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
    file_mime_type: str | None = "image/jpeg"

    if update.effective_message.photo:
        file_id = update.effective_message.photo[-1].file_id
        file_type = "photo"
        file_mime_type = "image/jpeg"
    elif update.effective_message.document:
        file_id = update.effective_message.document.file_id
        file_type = "document"
        file_mime_type = update.effective_message.document.mime_type

    if not file_id:
        await update.effective_message.reply_text(_get_text("upload_receipt_only_text"))
        return WAIT_BANK_RECEIPT

    payment_try = Decimal(str(payment_try_raw))
    settings: Settings = context.application.bot_data["settings"]

    receipt_check_summary = "AI dekont kontrolü uygulanmadı."
    if settings.receipt_ai_enabled:
        if file_mime_type and file_mime_type.startswith("image/"):
            try:
                tg_file = await context.bot.get_file(file_id)
                file_bytes = await tg_file.download_as_bytearray()
                check = verify_receipt_image(
                    settings=settings,
                    image_bytes=bytes(file_bytes),
                    expected_amount_try=payment_try,
                )
                receipt_check_summary = check.summary
                if not check.passed:
                    await update.effective_message.reply_text(_get_text("receipt_ai_reject_text"))
                    return WAIT_BANK_RECEIPT
            except Exception:
                receipt_check_summary = "AI dekont kontrolü sırasında hata oluştu. Manuel inceleme gerekli."
                if settings.receipt_ai_strict:
                    await update.effective_message.reply_text(_get_text("receipt_ai_reject_text"))
                    return WAIT_BANK_RECEIPT
        else:
            receipt_check_summary = "Belge formatı AI dekont kontrolüne uygun değil (manuel inceleme)."
            if settings.receipt_ai_strict:
                await update.effective_message.reply_text(_get_text("receipt_ai_reject_text"))
                return WAIT_BANK_RECEIPT

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

    request_code = _req_code(req.id)
    user_text = _render_text(
        "deposit_received_text",
        request_id=req.id,
        request_code=request_code,
        waiting_text=waiting_text,
    )
    if request_code not in user_text:
        user_text = f"{user_text}\nTalep Kodu: {request_code}"

    await update.effective_message.reply_text(
        user_text,
        reply_markup=main_menu_keyboard(),
        )

    caption = _render_text(
        "receipt_caption_admin_text",
        request_id=req.id,
        request_code=request_code,
        telegram_id=update.effective_user.id,
        balance_amount=_fmt_int(int(requested_amount)),
        payment_try=_fmt_try(payment_try),
    )
    caption = f"{caption}\nAI Kontrol: {receipt_check_summary}"
    if request_code not in caption:
        caption = f"{caption}\nTalep Kodu: {request_code}"

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


async def start_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)
        has_pending = WithdrawalService.has_pending_request(session, user.id)

    if user.coin_balance <= 0:
        await update.effective_message.reply_text(
            _get_text("withdraw_zero_balance_text"),
            reply_markup=main_menu_keyboard(),
        )
        return MENU

    if has_pending:
        await update.effective_message.reply_text(
            _get_text("withdraw_pending_exists_text"),
            reply_markup=main_menu_keyboard(),
        )
        return MENU

    context.user_data["withdraw_amount"] = int(user.coin_balance)
    await update.effective_message.reply_text(
        _render_text("withdraw_start_text", balance=_fmt_int(int(user.coin_balance))),
    )
    return WAIT_WITHDRAW_NAME


async def handle_withdraw_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return WAIT_WITHDRAW_NAME
    full_name = update.effective_message.text.strip()
    if len(full_name.split()) < 2:
        await update.effective_message.reply_text("Lütfen ad soyad şeklinde yazın.")
        return WAIT_WITHDRAW_NAME

    context.user_data["withdraw_full_name"] = full_name
    await update.effective_message.reply_text(_get_text("withdraw_ask_iban_text"))
    return WAIT_WITHDRAW_IBAN


async def handle_withdraw_iban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return WAIT_WITHDRAW_IBAN
    iban = _normalize_iban(update.effective_message.text)
    if not _is_valid_iban(iban):
        await update.effective_message.reply_text(_get_text("withdraw_invalid_iban_text"))
        return WAIT_WITHDRAW_IBAN

    context.user_data["withdraw_iban"] = iban
    await update.effective_message.reply_text(_get_text("withdraw_ask_bank_name_text"))
    return WAIT_WITHDRAW_BANK


async def handle_withdraw_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return WAIT_WITHDRAW_BANK

    bank_name = update.effective_message.text.strip()
    if len(bank_name) < 2:
        await update.effective_message.reply_text("Lütfen geçerli banka adı yazın.")
        return WAIT_WITHDRAW_BANK

    context.user_data["withdraw_bank_name"] = bank_name

    amount = int(context.user_data.get("withdraw_amount", 0))
    full_name = str(context.user_data.get("withdraw_full_name", ""))
    iban = str(context.user_data.get("withdraw_iban", ""))
    confirm_text = _render_text(
        "withdraw_confirm_text",
        full_name=full_name,
        iban=iban,
        bank_name=bank_name,
        amount=_fmt_int(amount),
    )
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Çekim Talebi Gönder", callback_data="user_withdraw_submit")],
            [InlineKeyboardButton("İptal", callback_data="user_withdraw_cancel")],
        ]
    )
    await update.effective_message.reply_text(confirm_text, reply_markup=markup)
    return WAIT_WITHDRAW_CONFIRM


async def handle_withdraw_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not update.effective_user:
        return MENU

    await query.answer()
    data = query.data or ""

    if data == "user_withdraw_cancel":
        context.user_data.clear()
        await query.edit_message_text(_get_text("cancel_text"))
        await query.message.reply_text(_get_text("use_menu_buttons_text"), reply_markup=main_menu_keyboard())
        return MENU

    if data != "user_withdraw_submit":
        return WAIT_WITHDRAW_CONFIRM

    full_name = str(context.user_data.get("withdraw_full_name", "")).strip()
    iban = str(context.user_data.get("withdraw_iban", "")).strip()
    bank_name = str(context.user_data.get("withdraw_bank_name", "")).strip()

    if not full_name or not iban or not bank_name:
        context.user_data.clear()
        await query.edit_message_text("Çekim oturumu süresi doldu. Lütfen tekrar başlatın.")
        await query.message.reply_text(_get_text("use_menu_buttons_text"), reply_markup=main_menu_keyboard())
        return MENU

    try:
        with session_scope() as session:
            user = UserService.get_or_create_user(session, update.effective_user)
            req = WithdrawalService.create_full_balance_request(
                session,
                user_id=user.id,
                full_name=full_name,
                iban=iban,
                bank_name=bank_name,
            )
    except ValueError as exc:
        context.user_data.clear()
        await query.edit_message_text(str(exc))
        await query.message.reply_text(_get_text("use_menu_buttons_text"), reply_markup=main_menu_keyboard())
        return MENU

    request_code = _req_code(req.id)
    await query.edit_message_text(
        _render_text(
            "withdraw_submitted_text",
            request_code=request_code,
            amount=_fmt_int(int(req.amount_coins)),
        )
    )
    await query.message.reply_text(_get_text("withdraw_waiting_text"), reply_markup=main_menu_keyboard())

    settings: Settings = context.application.bot_data["settings"]
    admin_text = _render_text(
        "withdraw_admin_caption_text",
        request_code=request_code,
        telegram_id=update.effective_user.id,
        username=update.effective_user.username or "-",
        full_name=req.full_name,
        iban=req.iban,
        bank_name=req.bank_name,
        amount=_fmt_int(int(req.amount_coins)),
    )
    admin_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Onayla", callback_data=f"admin_withdraw_ok:{req.id}"),
                InlineKeyboardButton("Reddet", callback_data=f"admin_withdraw_no:{req.id}"),
            ]
        ]
    )
    await send_message_to_admins(
        context.application,
        settings,
        text=admin_text,
        reply_markup=admin_markup,
    )

    context.user_data.clear()
    return MENU


async def handle_menu_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
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
        await update.effective_message.reply_text(_get_text("withdraw_proof_only_text"), reply_markup=main_menu_keyboard())
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)
        waiting_req = WithdrawalService.get_latest_waiting_proof_for_user(session, user.id)
        if not waiting_req:
            await update.effective_message.reply_text(
                "Şu anda SS bekleyen bir çekim talebiniz yok.",
                reply_markup=main_menu_keyboard(),
            )
            return MENU
        req = WithdrawalService.submit_proof(session, waiting_req.id, file_id, file_type)

    await update.effective_message.reply_text(_get_text("withdraw_proof_received_text"), reply_markup=main_menu_keyboard())

    settings: Settings = context.application.bot_data["settings"]
    request_code = _req_code(req.id)
    caption = _render_text(
        "withdraw_proof_admin_caption_text",
        request_code=request_code,
        telegram_id=update.effective_user.id,
        username=update.effective_user.username or "-",
    )
    await send_receipt_to_admins(
        context.application,
        settings,
        receipt_file_id=file_id,
        file_type=file_type,
        caption=caption,
        reply_markup=None,
    )
    return MENU


async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return MENU

    settings: Settings = context.application.bot_data["settings"]
    url = _support_url(settings)
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Desteğe Git", url=url)]]
    )
    await update.effective_message.reply_text(
        _render_text("support_contact_text", support_url=url),
        reply_markup=markup,
    )
    return MENU


async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return MENU
    settings: Settings = context.application.bot_data["settings"]
    text = _render_text(
        "rules_text",
        rate_percent=str((settings.balance_payment_rate * Decimal("100")).quantize(Decimal("0.01"))).replace(".", ","),
        min_amount=_fmt_int(settings.min_balance_amount),
        max_amount=_fmt_int(settings.max_balance_amount),
        support_username=settings.support_username,
    )
    await update.effective_message.reply_text(text, reply_markup=main_menu_keyboard())
    return MENU


async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return MENU
    await update.effective_message.reply_text(_get_text("faq_text"), reply_markup=main_menu_keyboard())
    return MENU


async def show_request_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)
        bank = DepositService.list_user_bank_deposits(session, user.id, limit=1)
        crypto = DepositService.list_user_crypto_deposits(session, user.id, limit=1)
        withdrawal = WithdrawalService.list_user_requests(session, user.id, limit=1)

    if not bank and not crypto and not withdrawal:
        await update.effective_message.reply_text(_get_text("request_status_empty_text"), reply_markup=main_menu_keyboard())
        return MENU

    lines = [_get_text("request_status_header_text"), ""]
    if bank:
        item = bank[0]
        lines.append(f"Banka: {_req_code(item.id)} | {_status_text(item.status)}")
        lines.append(_render_text("request_status_next_step_text", next_step=_next_step_for_status(item.status, "bank")))
        lines.append("")
    if crypto:
        item = crypto[0]
        lines.append(f"Kripto: {_req_code(item.id)} | {_status_text(item.status)}")
        lines.append(_render_text("request_status_next_step_text", next_step=_next_step_for_status(item.status, "crypto")))
        lines.append("")
    if withdrawal:
        item = withdrawal[0]
        lines.append(f"Çekim: {_req_code(item.id)} | {_status_text(item.status)}")
        lines.append(_render_text("request_status_next_step_text", next_step=_next_step_for_status(item.status, "withdraw")))

    await update.effective_message.reply_text("\n".join(lines), reply_markup=main_menu_keyboard())
    return MENU


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)
        bank_deposits = DepositService.list_user_bank_deposits(session, user.id, limit=20)
        crypto_deposits = DepositService.list_user_crypto_deposits(session, user.id, limit=20)
        withdrawals = WithdrawalService.list_user_requests(session, user.id, limit=20)

    lines = [_get_text("history_header_text"), ""]
    lines.append(_get_text("bank_history_header_text"))

    if bank_deposits:
        for item in bank_deposits:
            lines.append(
                f"{_req_code(item.id)} | {_status_text(item.status)} | {_fmt_int(item.package.coin_amount)} BAKİYE | {_fmt_try(Decimal(item.package.try_price))}"
            )
    else:
        lines.append(_get_text("no_bank_deposit_records_text"))

    lines.append("")
    lines.append(_get_text("crypto_history_header_text"))
    if crypto_deposits:
        for item in crypto_deposits:
            lines.append(
                f"{_req_code(item.id)} | {_status_text(item.status)} | {Decimal(item.expected_trx):.6f} TRX"
            )
    else:
        lines.append(_get_text("no_crypto_deposit_records_text"))

    lines.append("")
    lines.append(_get_text("withdraw_history_header_text"))
    if withdrawals:
        for item in withdrawals:
            lines.append(
                f"{_req_code(item.id)} | {_status_text(item.status)} | {_fmt_int(int(item.amount_coins))} BAKİYE"
            )
    else:
        lines.append(_get_text("no_withdraw_records_text"))

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
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_menu_media),
            ],
            WAIT_BALANCE_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_balance_amount)
            ],
            WAIT_BANK_RECEIPT: [
                MessageHandler(~filters.COMMAND, handle_bank_receipt)
            ],
            WAIT_WITHDRAW_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_name)
            ],
            WAIT_WITHDRAW_IBAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_iban)
            ],
            WAIT_WITHDRAW_BANK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_bank_name)
            ],
            WAIT_WITHDRAW_CONFIRM: [
                CallbackQueryHandler(handle_withdraw_confirm_callback, pattern=r"^user_withdraw_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )
