from __future__ import annotations

from decimal import Decimal
import hashlib
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
    MENU_ITIRAZ,
    MENU_KURALLAR,
    MENU_SSS,
    MENU_YUKLEME,
    main_menu_keyboard,
)
from bot.models import User
from bot.services import (
    DepositService,
    RiskService,
    TicketService,
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
    WAIT_APPEAL_MESSAGE,
) = range(8)

_MENU_ITEMS = [
    MENU_BAKIYE,
    MENU_YUKLEME,
    MENU_CEKIM,
    MENU_DURUM,
    MENU_ITIRAZ,
    MENU_GECMIS,
    MENU_KURALLAR,
    MENU_SSS,
    MENU_DESTEK,
]
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
    "open": "Açık",
    "resolved": "Çözüldü",
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


def _ticket_code(ticket_id: int) -> str:
    return f"ITR-#{ticket_id}"


def _support_url(settings: Settings) -> str:
    return f"https://t.me/{settings.support_username}"


def _source_text(source_type: str) -> str:
    return {
        "bank": "Banka",
        "crypto": "Kripto",
        "withdraw": "Çekim",
    }.get(source_type, source_type)


def _normalize_iban(text: str) -> str:
    return text.strip().replace(" ", "").upper()


def _is_valid_iban(text: str) -> bool:
    iban = _normalize_iban(text)
    return len(iban) == 26 and iban.startswith("TR") and iban[2:].isdigit()


def _extract_iban_from_text(text: str) -> str:
    raw = _normalize_iban(text)
    match = re.search(r"TR\d{24}", raw)
    return match.group(0) if match else ""


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
    if text == MENU_ITIRAZ:
        return await show_appeal_menu(update, context)
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
    expected_iban = _extract_iban_from_text(settings.iban_text)

    try:
        tg_file = await context.bot.get_file(file_id)
        file_bytes = bytes(await tg_file.download_as_bytearray())
    except Exception:
        await update.effective_message.reply_text("Dekont indirilemedi. Lütfen tekrar yükleyin.")
        return WAIT_BANK_RECEIPT

    file_sha256 = hashlib.sha256(file_bytes).hexdigest()

    ai_risk_score = 0
    ai_risk_flags: list[str] = []
    receipt_check_summary = "AI dekont kontrolü uygulanmadı."
    if settings.receipt_ai_enabled:
        if file_mime_type and file_mime_type.startswith("image/"):
            try:
                check = verify_receipt_image(
                    settings=settings,
                    image_bytes=file_bytes,
                    expected_amount_try=payment_try,
                    expected_iban=expected_iban,
                )
                receipt_check_summary = check.summary
                ai_risk_score = check.risk_score
                ai_risk_flags = list(check.risk_flags)
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

    duplicate_detected = False
    duplicate_owner_tg: int | None = None
    reject_by_hash_check = False
    req = None
    queue_info: tuple[int, int] | None = None
    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)

        if settings.receipt_hash_check_enabled:
            existing_fingerprint = DepositService.find_receipt_fingerprint(session, file_sha256)
            if existing_fingerprint:
                duplicate_detected = True
                duplicate_user = session.get(User, existing_fingerprint.user_id)
                duplicate_owner_tg = duplicate_user.telegram_id if duplicate_user else None
                ai_risk_score = min(100, ai_risk_score + 60)
                ai_risk_flags.append("duplicate_receipt_hash")
                if settings.receipt_ai_strict:
                    reject_by_hash_check = True

        if reject_by_hash_check:
            pass
        else:
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
            if settings.receipt_hash_check_enabled:
                DepositService.register_receipt_fingerprint(
                    session,
                    user_id=user.id,
                    file_sha256=file_sha256,
                    deposit_request_id=req.id,
                )
            queue_info = DepositService.get_bank_queue_position(session, req.id)

            if ai_risk_score >= settings.risk_flag_threshold or duplicate_detected:
                details = (
                    f"risk_score={ai_risk_score}; flags={','.join(ai_risk_flags) or '-'}; "
                    f"sha256={file_sha256}; duplicate_owner_tg={duplicate_owner_tg or '-'}"
                )
                RiskService.create_flag(
                    session,
                    user_id=user.id,
                    score=ai_risk_score,
                    source="receipt_risk",
                    reason="Dekontta riskli durum tespit edildi.",
                    details=details,
                    entity_type="bank_deposit",
                    entity_id=req.id,
                )

        waiting_text = TemplateService.get_template(
            session,
            key="deposit_waiting",
            fallback=DEFAULT_TEXT_TEMPLATES["deposit_waiting"],
        )

    if reject_by_hash_check:
        await update.effective_message.reply_text(_get_text("receipt_ai_reject_text"))
        return WAIT_BANK_RECEIPT

    if req is None:
        await update.effective_message.reply_text("Dekont işlenemedi. Lütfen tekrar deneyin.")
        return WAIT_BANK_RECEIPT

    if duplicate_detected:
        receipt_check_summary = (
            f"{receipt_check_summary} | Hash tekrar: Evet"
            f"{f' (ilk tg: {duplicate_owner_tg})' if duplicate_owner_tg else ''}"
        )

    request_code = _req_code(req.id)
    user_text = _render_text(
        "deposit_received_text",
        request_id=req.id,
        request_code=request_code,
        waiting_text=waiting_text,
    )
    if queue_info:
        position, total = queue_info
        eta = position * max(settings.bank_queue_eta_min_per_request, 1)
        user_text = f"{user_text}\n{_render_text('queue_info_text', position=position, total=total, eta_minutes=eta)}"
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
    caption = f"{caption}\nRisk Skoru: {ai_risk_score}/100"
    if ai_risk_flags:
        caption = f"{caption}\nRisk Bayrakları: {', '.join(ai_risk_flags)}"
    if queue_info:
        position, total = queue_info
        eta = position * max(settings.bank_queue_eta_min_per_request, 1)
        caption = f"{caption}\nSıra: {position}/{total} | Tahmini: {eta} dk"
    if settings.receipt_hash_check_enabled:
        caption = f"{caption}\nDekont Hash: {file_sha256[:16]}..."
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

    queue_info: tuple[int, int] | None = None
    reused_iban_flag = None
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
            queue_info = WithdrawalService.get_queue_position(session, req.id)
            reused_iban_flag = RiskService.flag_reused_iban_if_needed(
                session,
                user_id=user.id,
                iban=req.iban,
                withdrawal_request_id=req.id,
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
    waiting_text = _get_text("withdraw_waiting_text")
    if queue_info:
        position, total = queue_info
        eta = position * max(context.application.bot_data["settings"].withdraw_queue_eta_min_per_request, 1)
        waiting_text = (
            f"{waiting_text}\n"
            f"{_render_text('queue_info_text', position=position, total=total, eta_minutes=eta)}"
        )
    await query.message.reply_text(waiting_text, reply_markup=main_menu_keyboard())

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
    if queue_info:
        position, total = queue_info
        eta = position * max(settings.withdraw_queue_eta_min_per_request, 1)
        admin_text = f"{admin_text}\nSıra: {position}/{total} | Tahmini: {eta} dk"
    if reused_iban_flag:
        admin_text = f"{admin_text}\n⚠️ Risk: Aynı IBAN farklı kullanıcılarda da tespit edildi."
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
        tickets = TicketService.list_user_tickets(session, user.id, limit=1)
        bank_queue = (
            DepositService.get_bank_queue_position(session, bank[0].id)
            if bank and bank[0].status == "pending"
            else None
        )
        crypto_queue = (
            DepositService.get_crypto_queue_position(session, crypto[0].id)
            if crypto and crypto[0].status in {"pending_payment", "detected"}
            else None
        )
        withdraw_queue = (
            WithdrawalService.get_queue_position(session, withdrawal[0].id)
            if withdrawal and withdrawal[0].status == "pending"
            else None
        )

    if not bank and not crypto and not withdrawal and not tickets:
        await update.effective_message.reply_text(_get_text("request_status_empty_text"), reply_markup=main_menu_keyboard())
        return MENU

    settings: Settings = context.application.bot_data["settings"]
    lines = [_get_text("request_status_header_text"), ""]
    if bank:
        item = bank[0]
        lines.append(f"Banka: {_req_code(item.id)} | {_status_text(item.status)}")
        lines.append(_render_text("request_status_next_step_text", next_step=_next_step_for_status(item.status, "bank")))
        if bank_queue:
            p, t = bank_queue
            eta = p * max(settings.bank_queue_eta_min_per_request, 1)
            lines.append(_render_text("queue_info_text", position=p, total=t, eta_minutes=eta))
        lines.append("")
    if crypto:
        item = crypto[0]
        lines.append(f"Kripto: {_req_code(item.id)} | {_status_text(item.status)}")
        lines.append(_render_text("request_status_next_step_text", next_step=_next_step_for_status(item.status, "crypto")))
        if crypto_queue:
            p, t = crypto_queue
            eta = p * max(settings.crypto_queue_eta_min_per_request, 1)
            lines.append(_render_text("queue_info_text", position=p, total=t, eta_minutes=eta))
        lines.append("")
    if withdrawal:
        item = withdrawal[0]
        lines.append(f"Çekim: {_req_code(item.id)} | {_status_text(item.status)}")
        lines.append(_render_text("request_status_next_step_text", next_step=_next_step_for_status(item.status, "withdraw")))
        if withdraw_queue:
            p, t = withdraw_queue
            eta = p * max(settings.withdraw_queue_eta_min_per_request, 1)
            lines.append(_render_text("queue_info_text", position=p, total=t, eta_minutes=eta))
        lines.append("")
    if tickets:
        ticket = tickets[0]
        lines.append(
            f"İtiraz: {_ticket_code(ticket.id)} | {_status_text(ticket.status)} | Kaynak: {_source_text(ticket.source_type)} {_req_code(ticket.source_request_id)}"
        )
        if ticket.admin_note:
            lines.append(f"Not: {ticket.admin_note}")

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
        tickets = TicketService.list_user_tickets(session, user.id, limit=20)

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

    lines.append("")
    lines.append(_get_text("ticket_status_header_text"))
    if tickets:
        for item in tickets:
            lines.append(
                f"{_ticket_code(item.id)} | {_status_text(item.status)} | {_source_text(item.source_type)} {_req_code(item.source_request_id)}"
            )
    else:
        lines.append("- itiraz kaydınız bulunmuyor")

    await update.effective_message.reply_text("\n".join(lines), reply_markup=main_menu_keyboard())
    return MENU


async def show_appeal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    with session_scope() as session:
        user = UserService.get_or_create_user(session, update.effective_user)
        bank_rows = [
            r
            for r in DepositService.list_user_bank_deposits(session, user.id, limit=20)
            if r.status == "rejected"
        ]
        crypto_rows = [
            r
            for r in DepositService.list_user_crypto_deposits(session, user.id, limit=20)
            if r.status == "rejected"
        ]
        withdraw_rows = [
            r
            for r in WithdrawalService.list_user_requests(session, user.id, limit=20)
            if r.status == "rejected"
        ]

    rows: list[list[InlineKeyboardButton]] = []
    for item in bank_rows[:8]:
        rows.append(
            [InlineKeyboardButton(f"Banka {_req_code(item.id)}", callback_data=f"user_appeal_pick:bank:{item.id}")]
        )
    for item in crypto_rows[:8]:
        rows.append(
            [InlineKeyboardButton(f"Kripto {_req_code(item.id)}", callback_data=f"user_appeal_pick:crypto:{item.id}")]
        )
    for item in withdraw_rows[:8]:
        rows.append(
            [
                InlineKeyboardButton(
                    f"Çekim {_req_code(item.id)}",
                    callback_data=f"user_appeal_pick:withdraw:{item.id}",
                )
            ]
        )

    if not rows:
        await update.effective_message.reply_text(
            _get_text("appeal_no_rejected_text"),
            reply_markup=main_menu_keyboard(),
        )
        return MENU

    rows.append([InlineKeyboardButton("İptal", callback_data="user_appeal_cancel")])
    await update.effective_message.reply_text(
        _get_text("appeal_intro_text"),
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return MENU


async def handle_appeal_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return MENU
    await query.answer()

    data = query.data or ""
    if data == "user_appeal_cancel":
        context.user_data.pop("appeal_source_type", None)
        context.user_data.pop("appeal_source_request_id", None)
        await query.edit_message_text(_get_text("cancel_text"))
        return MENU

    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("Geçersiz seçim", show_alert=True)
        return MENU

    source_type = parts[1]
    try:
        source_request_id = int(parts[2])
    except ValueError:
        await query.answer("Geçersiz seçim", show_alert=True)
        return MENU

    context.user_data["appeal_source_type"] = source_type
    context.user_data["appeal_source_request_id"] = source_request_id
    await query.edit_message_text(
        f"Seçilen talep: {_req_code(source_request_id)} ({_source_text(source_type)})\n{_get_text('appeal_ask_message_text')}"
    )
    return WAIT_APPEAL_MESSAGE


async def handle_appeal_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.effective_message:
        return MENU

    source_type = str(context.user_data.get("appeal_source_type", "")).strip()
    source_request_id = int(context.user_data.get("appeal_source_request_id", 0) or 0)
    message = update.effective_message.text.strip()

    if not source_type or source_request_id <= 0:
        await update.effective_message.reply_text(
            "İtiraz oturumu bulunamadı. Menüden tekrar deneyin.",
            reply_markup=main_menu_keyboard(),
        )
        return MENU

    try:
        with session_scope() as session:
            user = UserService.get_or_create_user(session, update.effective_user)
            ticket = TicketService.create_ticket(
                session,
                user_id=user.id,
                source_type=source_type,
                source_request_id=source_request_id,
                message=message,
            )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
        return WAIT_APPEAL_MESSAGE

    ticket_code = _ticket_code(ticket.id)
    await update.effective_message.reply_text(
        _render_text("appeal_submitted_text", ticket_code=ticket_code),
        reply_markup=main_menu_keyboard(),
    )

    settings: Settings = context.application.bot_data["settings"]
    admin_text = (
        "Yeni itiraz kaydı\n"
        f"İtiraz Kodu: {ticket_code}\n"
        f"Kullanıcı TG: {update.effective_user.id}\n"
        f"Kullanıcı Adı: @{update.effective_user.username or '-'}\n"
        f"Kaynak Talep: {_req_code(source_request_id)} ({_source_text(source_type)})\n"
        f"Mesaj: {message}"
    )
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Kabul Et", callback_data=f"admin_ticket_ok:{ticket.id}"),
                InlineKeyboardButton("Reddet", callback_data=f"admin_ticket_no:{ticket.id}"),
            ]
        ]
    )
    await send_message_to_admins(
        context.application,
        settings,
        text=admin_text,
        reply_markup=markup,
    )

    context.user_data.pop("appeal_source_type", None)
    context.user_data.pop("appeal_source_request_id", None)
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
                CallbackQueryHandler(handle_appeal_pick_callback, pattern=r"^user_appeal_"),
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
            WAIT_APPEAL_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_appeal_message)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )
