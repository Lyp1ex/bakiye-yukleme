from __future__ import annotations

import asyncio
from decimal import InvalidOperation
from io import BytesIO
import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.error import BadRequest
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
from bot.services import (
    AdminService,
    AuditService,
    DepositService,
    ReportService,
    RiskService,
    StatusCardService,
    TicketService,
    WithdrawalService,
    create_database_backup,
)
from bot.texts.messages import TEMPLATE_LABELS

logger = logging.getLogger(__name__)

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

(
    ADMIN_MENU,
    ADMIN_WAIT_SEARCH_QUERY,
    ADMIN_WAIT_MANUAL_USER_TG,
    ADMIN_WAIT_MANUAL_DELTA,
    ADMIN_WAIT_MANUAL_REASON,
    ADMIN_WAIT_TEMPLATE_KEY,
    ADMIN_WAIT_TEMPLATE_CONTENT,
    ADMIN_WAIT_BROADCAST_TEXT,
) = range(200, 208)


def _status_text(raw_status: str) -> str:
    return STATUS_MAP_TR.get(raw_status, raw_status)


def _req_code(request_id: int) -> str:
    return f"DS-#{request_id}"


def _source_text(source_type: str) -> str:
    return {
        "bank": "Banka",
        "crypto": "Kripto",
        "withdraw": "Çekim",
    }.get(source_type, source_type)


async def _notify_user_safely(context: ContextTypes.DEFAULT_TYPE, telegram_id: int, text: str) -> None:
    try:
        await context.bot.send_message(chat_id=telegram_id, text=text)
    except Exception:
        logger.exception("Kullanıcıya bildirim gönderilemedi", extra={"telegram_id": telegram_id})


async def _edit_query_message_safely(query, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    message = query.message
    if not message:
        return

    has_media = bool(message.photo or message.document or message.video or message.animation)
    try:
        if has_media:
            await query.edit_message_caption(caption=text, reply_markup=reply_markup)
        else:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
        return
    except BadRequest:
        # Bazı eski mesaj tiplerinde method uyuşmazlığı olabiliyor; diğer yönteme düş.
        pass
    except Exception:
        logger.exception("Callback mesajı düzenlenemedi, fallback deneniyor")

    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
        return
    except Exception:
        pass

    try:
        await query.edit_message_caption(caption=text, reply_markup=reply_markup)
        return
    except Exception:
        pass

    try:
        await message.reply_text(text=text, reply_markup=reply_markup)
    except Exception:
        logger.exception("Fallback admin mesajı gönderilemedi")


async def open_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_admin(update, context):
        return ConversationHandler.END

    target = update.effective_message
    if target:
        await target.reply_text("Admin Paneli", reply_markup=admin_panel_keyboard())
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
        await query.edit_message_text("Admin Paneli", reply_markup=admin_panel_keyboard())
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

    if data == "admin_withdraw_list":
        await _show_pending_withdrawals(query, context)
        return ADMIN_MENU

    if data.startswith("admin_withdraw_ok:"):
        request_id = int(data.split(":", 1)[1])
        await _approve_withdrawal(query, context, request_id)
        return ADMIN_MENU

    if data.startswith("admin_withdraw_no:"):
        request_id = int(data.split(":", 1)[1])
        await _reject_withdrawal(query, context, request_id)
        return ADMIN_MENU

    if data == "admin_daily_report":
        await _send_daily_report(query, context)
        return ADMIN_MENU

    if data == "admin_kpi":
        await _send_kpi_report(query, context)
        return ADMIN_MENU

    if data == "admin_export_csv":
        await _send_csv_export(query, context)
        return ADMIN_MENU

    if data == "admin_broadcast":
        await query.edit_message_text("Toplu duyuru metnini yazın:")
        return ADMIN_WAIT_BROADCAST_TEXT

    if data == "admin_ticket_list":
        await _show_open_tickets(query, context)
        return ADMIN_MENU

    if data.startswith("admin_ticket_ok:"):
        ticket_id = int(data.split(":", 1)[1])
        await _resolve_ticket(query, context, ticket_id)
        return ADMIN_MENU

    if data.startswith("admin_ticket_no:"):
        ticket_id = int(data.split(":", 1)[1])
        await _reject_ticket(query, context, ticket_id)
        return ADMIN_MENU

    if data == "admin_risk_list":
        await _show_open_risks(query, context)
        return ADMIN_MENU

    if data == "admin_sla_list":
        await _show_sla_overdue(query, context)
        return ADMIN_MENU

    if data == "admin_audit_list":
        await _show_audit_logs(query, context)
        return ADMIN_MENU

    if data.startswith("admin_risk_clear:"):
        risk_id = int(data.split(":", 1)[1])
        await _resolve_risk(query, context, risk_id)
        return ADMIN_MENU

    if data == "admin_backup_now":
        await _run_backup_now(query, context)
        return ADMIN_MENU

    if data == "admin_search":
        await query.edit_message_text("Aramak için Telegram ID veya kullanıcı adı yazın:")
        return ADMIN_WAIT_SEARCH_QUERY

    if data == "admin_manual":
        await query.edit_message_text("İşlem yapılacak kullanıcının Telegram ID değerini yazın:")
        return ADMIN_WAIT_MANUAL_USER_TG

    if data == "admin_templates":
        await _show_templates_menu(query)
        return ADMIN_MENU

    if data == "admin_tpl_add":
        context.user_data["template_edit_key"] = None
        await query.edit_message_text("Yeni şablon anahtarı yazın (örnek: hos_geldin_mesaji):")
        return ADMIN_WAIT_TEMPLATE_KEY

    if data.startswith("admin_tpl_edit:"):
        template_id = int(data.split(":", 1)[1])
        with session_scope() as session:
            templates = AdminService.list_templates(session)
            tpl = next((t for t in templates if t.id == template_id), None)

        if not tpl:
            await query.edit_message_text("Şablon bulunamadı.")
            return ADMIN_MENU

        context.user_data["template_edit_key"] = tpl.key
        await query.edit_message_text(
            f"'{tpl.key}' anahtarı için yeni metni gönderin:\n\nMevcut metin:\n{tpl.content}"
        )
        return ADMIN_WAIT_TEMPLATE_CONTENT

    await query.edit_message_text("Bilinmeyen admin işlemi.")
    return ADMIN_MENU


async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return ADMIN_MENU

    query = update.effective_message.text.strip()
    with session_scope() as session:
        users = AdminService.search_users(session, query)

    if not users:
        await update.effective_message.reply_text(
            "Kullanıcı bulunamadı.",
            reply_markup=admin_panel_keyboard(),
        )
        return ADMIN_MENU

    lines = [f"{len(users)} kullanıcı bulundu:"]
    for user in users[:30]:
        lines.append(
            f"id={user.id} | tg={user.telegram_id} | kullanıcı=@{user.username or '-'} | bakiye={user.coin_balance}"
        )

    await update.effective_message.reply_text("\n".join(lines), reply_markup=admin_panel_keyboard())
    return ADMIN_MENU


async def handle_manual_user_tg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text if update.effective_message else "").strip()
    if not raw.isdigit():
        await update.effective_message.reply_text("Telegram ID sayı olmalıdır. Tekrar yazın:")
        return ADMIN_WAIT_MANUAL_USER_TG

    context.user_data["manual_user_tg"] = int(raw)
    await update.effective_message.reply_text("Bakiye farkını yazın (örnek: +5000 veya -2500):")
    return ADMIN_WAIT_MANUAL_DELTA


async def handle_manual_delta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text if update.effective_message else "").strip().replace(" ", "")
    try:
        delta = int(raw)
    except (ValueError, InvalidOperation):
        await update.effective_message.reply_text("Geçersiz değer. Örnek: +5000 veya -2500")
        return ADMIN_WAIT_MANUAL_DELTA

    if delta == 0:
        await update.effective_message.reply_text("0 kabul edilmez. Tekrar yazın:")
        return ADMIN_WAIT_MANUAL_DELTA

    context.user_data["manual_delta"] = delta
    await update.effective_message.reply_text("Kayıt için açıklama yazın:")
    return ADMIN_WAIT_MANUAL_REASON


async def handle_manual_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message or not update.effective_user:
        return ADMIN_MENU

    reason = update.effective_message.text.strip()
    if len(reason) < 2:
        await update.effective_message.reply_text("Açıklama çok kısa. Tekrar yazın:")
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
        f"Bakiye güncellendi. Kullanıcı {user.telegram_id} yeni bakiye: {user.coin_balance}",
        reply_markup=admin_panel_keyboard(),
    )

    try:
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Admin tarafından bakiyeniz güncellendi. Değişim: {delta}. Yeni bakiye: {user.coin_balance}",
        )
    except Exception:
        logger.exception("Kullanıcıya manuel bakiye bildirimi gönderilemedi")

    context.user_data.pop("manual_user_tg", None)
    context.user_data.pop("manual_delta", None)
    return ADMIN_MENU


async def handle_template_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message:
        return ADMIN_MENU

    key = update.effective_message.text.strip()
    if len(key) < 3 or " " in key:
        await update.effective_message.reply_text("Geçersiz anahtar. Boşluk olmadan tekrar yazın:")
        return ADMIN_WAIT_TEMPLATE_KEY

    context.user_data["template_edit_key"] = key
    await update.effective_message.reply_text("Şablon metnini yazın:")
    return ADMIN_WAIT_TEMPLATE_CONTENT


async def handle_template_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message or not update.effective_user:
        return ADMIN_MENU

    key = context.user_data.get("template_edit_key")
    content = update.effective_message.text.strip()

    if not key:
        await update.effective_message.reply_text(
            "Şablon anahtarı bulunamadı. Tekrar deneyin.",
            reply_markup=admin_panel_keyboard(),
        )
        return ADMIN_MENU

    if len(content) < 1:
        await update.effective_message.reply_text("Metin boş olamaz.")
        return ADMIN_WAIT_TEMPLATE_CONTENT

    with session_scope() as session:
        tpl = AdminService.upsert_template(
            session,
            admin_id=update.effective_user.id,
            key=str(key),
            content=content,
        )

    await update.effective_message.reply_text(
        f"Şablon kaydedildi: {tpl.key}",
        reply_markup=admin_panel_keyboard(),
    )
    context.user_data.pop("template_edit_key", None)
    return ADMIN_MENU


async def handle_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_message or not update.effective_user:
        return ADMIN_MENU

    text = update.effective_message.text.strip()
    if len(text) < 3:
        await update.effective_message.reply_text("Metin çok kısa. Tekrar yazın:")
        return ADMIN_WAIT_BROADCAST_TEXT

    with session_scope() as session:
        users = AdminService.list_all_users(session)

    success = 0
    failed = 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=text,
            )
            success += 1
            await asyncio.sleep(0.03)
        except Exception:
            failed += 1

    await update.effective_message.reply_text(
        f"Toplu duyuru tamamlandı. Başarılı: {success} | Hata: {failed}",
        reply_markup=admin_panel_keyboard(),
    )
    return ADMIN_MENU


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.effective_message:
        await update.effective_message.reply_text(
            "İşlem iptal edildi.",
            reply_markup=admin_panel_keyboard(),
        )
    return ADMIN_MENU


async def _show_pending_bank(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        rows = DepositService.list_pending_bank_requests(session)

    if not rows:
        await query.edit_message_text("Bekleyen banka talebi yok.", reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(
        f"Bekleyen banka talepleri: {len(rows)}\nDetaylar aşağıda gönderildi.",
        reply_markup=admin_panel_keyboard(),
    )

    chat_id = query.message.chat_id
    settings: Settings = context.application.bot_data["settings"]
    total_rows = len(rows)
    for idx, req in enumerate(rows[:40], start=1):
        eta = idx * max(settings.bank_queue_eta_min_per_request, 1)
        queue_text = f"\nSıra: {idx}/{total_rows} | Tahmini: {eta} dk"
        text = (
            f"Banka Talebi #{req.id}\n"
            f"Talep Kodu: {_req_code(req.id)}\n"
            f"Kullanıcı TG: {req.user.telegram_id}\n"
            f"Kullanıcı Adı: @{req.user.username or '-'}\n"
            f"Yüklenecek Bakiye: {req.package.coin_amount}\n"
            f"Ödenecek Tutar: {req.package.try_price} TL\n"
            f"Durum: {_status_text(req.status)}\n"
            f"Oluşturma: {req.created_at:%Y-%m-%d %H:%M}"
            f"{queue_text}"
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
        await _edit_query_message_safely(query, f"Onaylanamadı: {exc}")
        return

    if user:
        await _notify_user_safely(
            context,
            user.telegram_id,
            f"Banka yükleme talebiniz {_req_code(request_id)} onaylandı. Bakiye eklendi.",
        )
    await StatusCardService.sync_card(
        context.application,
        context.application.bot_data["settings"],
        "bank",
        request_id,
        event_text="Admin onayı verildi, bakiye başarıyla yüklendi.",
    )
    await _edit_query_message_safely(query, f"Banka talebi {_req_code(request_id)} onaylandı.")


async def _reject_bank(query, context: ContextTypes.DEFAULT_TYPE, request_id: int) -> None:
    admin_id = query.from_user.id
    risk_flagged = False
    try:
        with session_scope() as session:
            req = DepositService.reject_bank_request(
                session,
                request_id,
                admin_id,
                note="Admin tarafından reddedildi",
            )
            user = session.get(User, req.user_id)
            recent_reject_count = DepositService.count_recent_rejected_bank_for_user(session, req.user_id, hours=24)
            if recent_reject_count >= 3:
                RiskService.create_flag(
                    session,
                    user_id=req.user_id,
                    score=70,
                    source="repeated_rejects",
                    reason="Son 24 saatte çoklu banka talebi reddi tespit edildi.",
                    details=f"recent_reject_count={recent_reject_count}",
                    entity_type="bank_deposit",
                    entity_id=req.id,
                )
                risk_flagged = True
    except ValueError as exc:
        await _edit_query_message_safely(query, f"Reddedilemedi: {exc}")
        return

    message = f"Banka talebi {_req_code(request_id)} reddedildi."
    if risk_flagged:
        message += "\n⚠️ Kullanıcı için risk bayrağı oluşturuldu (çoklu red)."
    if user:
        await _notify_user_safely(
            context,
            user.telegram_id,
            f"Banka yükleme talebiniz {_req_code(request_id)} reddedildi. Destek ile iletişime geçin.",
        )
    await StatusCardService.sync_card(
        context.application,
        context.application.bot_data["settings"],
        "bank",
        request_id,
        event_text="Admin tarafından reddedildi. İsterseniz itiraz kaydı açabilirsiniz.",
    )
    await _edit_query_message_safely(query, message)


async def _show_pending_crypto(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        rows = DepositService.list_pending_crypto_requests(session)

    if not rows:
        await query.edit_message_text("Bekleyen kripto talebi yok.", reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(
        f"Bekleyen kripto talepleri: {len(rows)}\nDetaylar aşağıda gönderildi.",
        reply_markup=admin_panel_keyboard(),
    )

    chat_id = query.message.chat_id
    settings: Settings = context.application.bot_data["settings"]
    total_rows = len(rows)
    for idx, req in enumerate(rows[:40], start=1):
        eta = idx * max(settings.crypto_queue_eta_min_per_request, 1)
        queue_text = f"\nSıra: {idx}/{total_rows} | Tahmini: {eta} dk"
        text = (
            f"Kripto Talebi #{req.id}\n"
            f"Talep Kodu: {_req_code(req.id)}\n"
            f"Kullanıcı TG: {req.user.telegram_id}\n"
            f"Beklenen: {req.expected_trx} TRX\n"
            f"Durum: {_status_text(req.status)}\n"
            f"TX: {req.tx_hash or '-'}"
            f"{queue_text}"
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
        await _edit_query_message_safely(query, f"Onaylanamadı: {exc}")
        return

    if user:
        await _notify_user_safely(
            context,
            user.telegram_id,
            f"Kripto yükleme talebiniz {_req_code(request_id)} onaylandı. Bakiye eklendi.",
        )
    await StatusCardService.sync_card(
        context.application,
        context.application.bot_data["settings"],
        "crypto",
        request_id,
        event_text="Admin onayı verildi, bakiye hesabınıza yansıtıldı.",
    )
    await _edit_query_message_safely(query, f"Kripto talebi {_req_code(request_id)} onaylandı.")


async def _reject_crypto(query, context: ContextTypes.DEFAULT_TYPE, request_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            req = DepositService.reject_crypto_request(
                session,
                request_id,
                admin_id,
                note="Admin tarafından reddedildi",
            )
            user = session.get(User, req.user_id)
    except ValueError as exc:
        await _edit_query_message_safely(query, f"Reddedilemedi: {exc}")
        return

    if user:
        await _notify_user_safely(
            context,
            user.telegram_id,
            f"Kripto yükleme talebiniz {_req_code(request_id)} reddedildi. Destek ile iletişime geçin.",
        )
    await StatusCardService.sync_card(
        context.application,
        context.application.bot_data["settings"],
        "crypto",
        request_id,
        event_text="Admin tarafından reddedildi. İsterseniz itiraz kaydı açabilirsiniz.",
    )
    await _edit_query_message_safely(query, f"Kripto talebi {_req_code(request_id)} reddedildi.")


async def _show_pending_withdrawals(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        rows = WithdrawalService.list_pending_requests(session)

    if not rows:
        await query.edit_message_text("Bekleyen çekim talebi yok.", reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(
        f"Bekleyen çekim talepleri: {len(rows)}\nDetaylar aşağıda gönderildi.",
        reply_markup=admin_panel_keyboard(),
    )

    chat_id = query.message.chat_id
    settings: Settings = context.application.bot_data["settings"]
    total_rows = len(rows)
    for idx, req in enumerate(rows[:40], start=1):
        eta = idx * max(settings.withdraw_queue_eta_min_per_request, 1)
        queue_text = f"\nSıra: {idx}/{total_rows} | Tahmini: {eta} dk"
        text = (
            f"Çekim Talebi #{req.id}\n"
            f"Talep Kodu: {_req_code(req.id)}\n"
            f"Kullanıcı TG: {req.user.telegram_id}\n"
            f"Kullanıcı Adı: @{req.user.username or '-'}\n"
            f"Ad Soyad: {req.full_name}\n"
            f"IBAN: {req.iban}\n"
            f"Banka: {req.bank_name}\n"
            f"Tutar: {req.amount_coins} BAKİYE\n"
            f"Durum: {_status_text(req.status)}\n"
            f"Oluşturma: {req.created_at:%Y-%m-%d %H:%M}"
            f"{queue_text}"
        )
        markup = approve_reject_keyboard(
            approve_data=f"admin_withdraw_ok:{req.id}",
            reject_data=f"admin_withdraw_no:{req.id}",
        )
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


async def _approve_withdrawal(query, context: ContextTypes.DEFAULT_TYPE, request_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            req = WithdrawalService.approve_request(session, request_id, admin_id)
            user = session.get(User, req.user_id)
    except ValueError as exc:
        await _edit_query_message_safely(query, f"Onaylanamadı: {exc}")
        return

    if user:
        await _notify_user_safely(
            context,
            user.telegram_id,
            (
                f"Çekim talebiniz {_req_code(request_id)} onaylandı.\n"
                "Ödeme yapıldıysa lütfen ekran görüntüsünü (SS) bu sohbete gönderin."
            ),
        )
    await StatusCardService.sync_card(
        context.application,
        context.application.bot_data["settings"],
        "withdraw",
        request_id,
        event_text="Admin ödemeyi onayladı. Şimdi ekran görüntüsü (SS) bekleniyor.",
    )
    await _edit_query_message_safely(query, f"Çekim talebi {_req_code(request_id)} onaylandı.")


async def _reject_withdrawal(query, context: ContextTypes.DEFAULT_TYPE, request_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            req = WithdrawalService.reject_request(
                session,
                request_id,
                admin_id,
                note="Admin tarafından reddedildi",
            )
            user = session.get(User, req.user_id)
    except ValueError as exc:
        await _edit_query_message_safely(query, f"Reddedilemedi: {exc}")
        return

    if user:
        await _notify_user_safely(
            context,
            user.telegram_id,
            (
                f"Çekim talebiniz {_req_code(request_id)} reddedildi.\n"
                f"{req.amount_coins} BAKİYE hesabınıza geri eklendi."
            ),
        )
    await StatusCardService.sync_card(
        context.application,
        context.application.bot_data["settings"],
        "withdraw",
        request_id,
        event_text="Çekim talebi reddedildi, tutar bakiyenize geri iade edildi.",
    )
    await _edit_query_message_safely(
        query,
        f"Çekim talebi {_req_code(request_id)} reddedildi. Tutar kullanıcıya iade edildi.",
    )


async def _send_daily_report(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        report = ReportService.build_daily_finance_report(
            session, target_day=datetime.now(timezone.utc).date()
        )

    text = (
        f"Günlük Finans Raporu ({report.day:%Y-%m-%d})\n\n"
        f"Banka\n"
        f"- Bekleyen: {report.bank_pending}\n"
        f"- Bugün onaylanan: {report.bank_approved_today}\n"
        f"- Bugün reddedilen: {report.bank_rejected_today}\n"
        f"- Bugün onaylanan toplam TL: {report.bank_approved_try_total:.2f}\n"
        f"- Bugün eklenen toplam BAKİYE: {report.bank_approved_coin_total}\n\n"
        f"Kripto\n"
        f"- Bekleyen: {report.crypto_pending}\n"
        f"- Bugün onaylanan: {report.crypto_approved_today}\n"
        f"- Bugün reddedilen: {report.crypto_rejected_today}\n"
        f"- Bugün onaylanan toplam TRX: {report.crypto_approved_trx_total:.6f}\n"
        f"- Bugün eklenen toplam BAKİYE: {report.crypto_approved_coin_total}\n\n"
        f"Çekim\n"
        f"- Bekleyen: {report.withdraw_pending}\n"
        f"- Bugün tamamlanan: {report.withdraw_completed_today}\n"
        f"- Bugün reddedilen: {report.withdraw_rejected_today}\n"
        f"- Bugün tamamlanan toplam BAKİYE: {report.withdraw_completed_coin_total}"
    )
    await query.edit_message_text(text, reply_markup=admin_panel_keyboard())


async def _send_kpi_report(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        kpi = ReportService.build_kpi_dashboard(
            session, target_day=datetime.now(timezone.utc).date()
        )

    text = (
        f"KPI Paneli ({kpi.day:%Y-%m-%d})\n\n"
        f"Kullanıcılar\n"
        f"- Toplam kullanıcı: {kpi.total_users}\n"
        f"- Bugün yeni kullanıcı: {kpi.new_users_today}\n"
        f"- Son 24s aktif kullanıcı: {kpi.active_users_24h}\n"
        f"- Toplam sistem bakiyesi: {kpi.total_coin_balance}\n"
        f"- En yüksek bakiye: {kpi.highest_balance_amount} (TG: {kpi.highest_balance_telegram_id or '-'})\n\n"
        f"Operasyon\n"
        f"- Bekleyen banka: {kpi.bank_pending}\n"
        f"- Bekleyen kripto: {kpi.crypto_pending}\n"
        f"- Bekleyen çekim: {kpi.withdraw_pending}\n"
        f"- Açık itiraz kaydı: {kpi.open_tickets}\n"
        f"- Açık risk bayrağı: {kpi.open_risk_flags}\n\n"
        f"Bugün Performans\n"
        f"- Banka onay: {kpi.bank_approved_today}\n"
        f"- Banka red: {kpi.bank_rejected_today}\n"
        f"- Banka onay oranı: %{kpi.bank_approval_rate_today:.1f}\n"
        f"- Banka onaylanan toplam TL: {kpi.bank_approved_try_today:.2f}\n"
        f"- Çekim tamamlanan: {kpi.withdraw_completed_today}\n"
        f"- Çekim reddedilen: {kpi.withdraw_rejected_today}\n"
        f"- Çekim başarı oranı: %{kpi.withdraw_success_rate_today:.1f}\n"
        f"- Çekim tamamlanan toplam bakiye: {kpi.withdraw_completed_coin_today}"
    )
    await query.edit_message_text(text, reply_markup=admin_panel_keyboard())


async def _send_csv_export(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    await query.edit_message_text("CSV hazırlanıyor, lütfen bekleyin...", reply_markup=admin_panel_keyboard())

    with session_scope() as session:
        data = ReportService.export_all_transactions_csv(session)

    file_obj = BytesIO(data)
    file_obj.name = f"ds_finans_raporu_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv"
    file_obj.seek(0)

    chat_id = query.message.chat_id
    await context.bot.send_document(
        chat_id=chat_id,
        document=InputFile(file_obj, filename=file_obj.name),
        caption="CSV dışa aktarma tamamlandı.",
    )


async def _show_open_tickets(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        tickets = TicketService.list_open_tickets(session, limit=50)

    if not tickets:
        await query.edit_message_text("Açık itiraz kaydı bulunmuyor.", reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(
        f"Açık itiraz kaydı sayısı: {len(tickets)}\nDetaylar aşağıda gönderildi.",
        reply_markup=admin_panel_keyboard(),
    )

    chat_id = query.message.chat_id
    for ticket in tickets[:40]:
        text = (
            f"İtiraz #{ticket.id}\n"
            f"Kod: ITR-#{ticket.id}\n"
            f"Durum: {_status_text(ticket.status)}\n"
            f"Kullanıcı TG: {ticket.user.telegram_id if ticket.user else '-'}\n"
            f"Kullanıcı Adı: @{ticket.user.username if ticket.user and ticket.user.username else '-'}\n"
            f"Kaynak: {_source_text(ticket.source_type)} DS-#{ticket.source_request_id}\n"
            f"Mesaj: {ticket.message}\n"
            f"Tarih: {ticket.created_at:%Y-%m-%d %H:%M}"
        )
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Kabul Et", callback_data=f"admin_ticket_ok:{ticket.id}"),
                    InlineKeyboardButton("Reddet", callback_data=f"admin_ticket_no:{ticket.id}"),
                ]
            ]
        )
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


async def _resolve_ticket(query, context: ContextTypes.DEFAULT_TYPE, ticket_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            ticket = TicketService.resolve_ticket(
                session,
                ticket_id=ticket_id,
                admin_id=admin_id,
                note="İtiraz incelendi ve kabul edildi.",
            )
            user = session.get(User, ticket.user_id)
    except ValueError as exc:
        await query.edit_message_text(str(exc), reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(f"İtiraz ITR-#{ticket_id} kabul edildi.", reply_markup=admin_panel_keyboard())
    if user:
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"İtiraz kaydınız ITR-#{ticket_id} kabul edildi. Detay için destekle iletişime geçebilirsiniz.",
        )


async def _reject_ticket(query, context: ContextTypes.DEFAULT_TYPE, ticket_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            ticket = TicketService.reject_ticket(
                session,
                ticket_id=ticket_id,
                admin_id=admin_id,
                note="İtiraz incelendi ve reddedildi.",
            )
            user = session.get(User, ticket.user_id)
    except ValueError as exc:
        await query.edit_message_text(str(exc), reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(f"İtiraz ITR-#{ticket_id} reddedildi.", reply_markup=admin_panel_keyboard())
    if user:
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"İtiraz kaydınız ITR-#{ticket_id} reddedildi.",
        )


async def _show_open_risks(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        flags = RiskService.list_open_flags(session, limit=60)

    if not flags:
        await query.edit_message_text("Açık risk kaydı yok.", reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(
        f"Açık risk kaydı: {len(flags)}\nDetaylar aşağıda gönderildi.",
        reply_markup=admin_panel_keyboard(),
    )
    chat_id = query.message.chat_id
    for flag in flags[:40]:
        text = (
            f"Risk #{flag.id}\n"
            f"Skor: {flag.score}/100\n"
            f"Kaynak: {flag.source}\n"
            f"Kullanıcı TG: {flag.user.telegram_id if flag.user else '-'}\n"
            f"Kullanıcı Adı: @{flag.user.username if flag.user and flag.user.username else '-'}\n"
            f"Talep: {flag.entity_type or '-'} #{flag.entity_id or '-'}\n"
            f"Gerekçe: {flag.reason}\n"
            f"Detay: {flag.details or '-'}\n"
            f"Tarih: {flag.created_at:%Y-%m-%d %H:%M}"
        )
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Temizle", callback_data=f"admin_risk_clear:{flag.id}")]]
        )
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


async def _show_sla_overdue(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    with session_scope() as session:
        rows = StatusCardService.list_overdue_cards(
            session,
            settings,
            min_age_minutes=max(settings.sla_level1_minutes, 1),
            limit=40,
        )

    if not rows:
        await query.edit_message_text("SLA eşiğini aşan talep yok.", reply_markup=admin_panel_keyboard())
        return

    lines = [f"SLA Geciken Talepler ({len(rows)})", ""]
    for item in rows:
        lines.append(
            f"{item.request_code} | {_source_text(item.flow_type)} | {item.status_text} | {item.age_minutes} dk | SLA-{item.level}"
        )
    await query.edit_message_text("\n".join(lines[:80]), reply_markup=admin_panel_keyboard())


async def _show_audit_logs(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        logs = AuditService.list_recent(session, limit=35)

    if not logs:
        await query.edit_message_text("Denetim kaydı bulunmuyor.", reply_markup=admin_panel_keyboard())
        return

    lines = ["Denetim Kayıtları (son 35)", ""]
    for row in logs:
        ts = row.created_at.strftime("%d.%m %H:%M") if row.created_at else "-"
        actor = AuditService.actor_text(row)
        entity_id = row.entity_id if row.entity_id is not None else "-"
        lines.append(f"{ts} | {actor} | {row.action} | {row.entity_type}:{entity_id}")
        if row.details:
            lines.append(f"  -> {row.details[:120]}")

    await query.edit_message_text("\n".join(lines[:100]), reply_markup=admin_panel_keyboard())


async def _resolve_risk(query, context: ContextTypes.DEFAULT_TYPE, risk_id: int) -> None:
    admin_id = query.from_user.id
    try:
        with session_scope() as session:
            flag = RiskService.resolve_flag(
                session,
                flag_id=risk_id,
                admin_id=admin_id,
                note="Admin tarafından incelendi.",
            )
    except ValueError as exc:
        await query.edit_message_text(str(exc), reply_markup=admin_panel_keyboard())
        return

    await query.edit_message_text(
        f"Risk #{flag.id} kapatıldı.",
        reply_markup=admin_panel_keyboard(),
    )


async def _run_backup_now(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    result = create_database_backup(settings)
    if not result.ok or not result.file_path:
        await query.edit_message_text(
            f"Yedek alınamadı: {result.message}",
            reply_markup=admin_panel_keyboard(),
        )
        return

    await query.edit_message_text(
        f"Yedek hazır: {result.file_path.name}",
        reply_markup=admin_panel_keyboard(),
    )
    with result.file_path.open("rb") as fp:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=InputFile(fp, filename=result.file_path.name),
            caption=f"Manuel yedek tamamlandı. {result.message}",
        )


async def _show_templates_menu(query) -> None:
    with session_scope() as session:
        templates = AdminService.list_templates(session)

    rows = []
    for tpl in templates[:50]:
        label = TEMPLATE_LABELS.get(tpl.key, tpl.key)
        rows.append([
            InlineKeyboardButton(
                f"Düzenle: {label}",
                callback_data=f"admin_tpl_edit:{tpl.id}",
            )
        ])

    rows.append([InlineKeyboardButton("+ Yeni Şablon", callback_data="admin_tpl_add")])
    rows.append([InlineKeyboardButton("Geri", callback_data="admin_back_panel")])

    await query.edit_message_text("Mesaj Şablonları", reply_markup=InlineKeyboardMarkup(rows))


async def _require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    settings: Settings = context.application.bot_data["settings"]
    user = update.effective_user
    if user and user.id in settings.admin_ids:
        return True

    if update.callback_query:
        await update.callback_query.answer("Sadece admin kullanabilir.", show_alert=True)
    target = update.effective_message or (update.callback_query.message if update.callback_query else None)
    if target:
        await target.reply_text("Bu alan sadece admin içindir.")
    return False



def build_admin_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", open_admin_panel),
            CallbackQueryHandler(admin_callback_router, pattern=r"^admin_"),
        ],
        states={
            ADMIN_MENU: [CallbackQueryHandler(admin_callback_router, pattern=r"^admin_")],
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
            ADMIN_WAIT_BROADCAST_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_text)
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel)],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )
