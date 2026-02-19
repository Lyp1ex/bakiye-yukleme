from __future__ import annotations

import asyncio
from datetime import time, timezone as dt_timezone
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import os
from typing import Any
import threading
from urllib.parse import parse_qs, quote_plus, urlparse

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from bot.config.logging_config import setup_logging
from bot.config.settings import Settings, get_settings
from bot.crypto.tron_client import TronClient
from bot.crypto.watcher import tron_watcher_job
from bot.database.bootstrap import initialize_database
from bot.database.session import session_scope
from bot.handlers import build_admin_conversation_handler, build_user_conversation_handler
from bot.admin.notifier import send_message_to_admins
from bot.services import ReminderService, create_database_backup, send_backup_to_admins
from bot.services.template_service import TemplateService
from bot.texts.messages import (
    DEFAULT_TEXT_TEMPLATES,
    LEGACY_TEXT_TEMPLATES_EN,
    OBSOLETE_TEMPLATE_KEYS,
    TEMPLATE_LABELS,
)

logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Yakalanmayan hata", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.")
        except Exception:
            logger.exception("Kullanıcıya hata mesajı gönderilemedi")


def _template_text(key: str) -> str:
    fallback = DEFAULT_TEXT_TEMPLATES.get(key, key)
    with session_scope() as session:
        return TemplateService.get_template(session, key=key, fallback=fallback)


async def pending_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not settings.reminder_enabled:
        return

    with session_scope() as session:
        targets = (
            ReminderService.list_due_bank(session, settings.reminder_min_age_minutes)
            + ReminderService.list_due_crypto(session, settings.reminder_min_age_minutes)
            + ReminderService.list_due_withdraw(session, settings.reminder_min_age_minutes)
        )
        eligible = [
            t
            for t in targets
            if ReminderService.can_send(
                session,
                entity_type=t.entity_type,
                entity_id=t.entity_id,
                cooldown_minutes=settings.reminder_cooldown_minutes,
            )
        ]

    for target in eligible:
        request_code = f"DS-#{target.entity_id}"
        if target.entity_type == "bank_deposit":
            tmpl = _template_text("reminder_bank_text")
            user_text = tmpl.format(request_code=request_code) if "{request_code}" in tmpl else tmpl
            admin_text = f"Hatırlatma: Banka talebi {request_code} beklemede."
        elif target.entity_type == "crypto_deposit":
            tmpl = _template_text("reminder_crypto_text")
            user_text = tmpl.format(request_code=request_code) if "{request_code}" in tmpl else tmpl
            admin_text = f"Hatırlatma: Kripto talebi {request_code} beklemede."
        else:
            tmpl = _template_text("reminder_withdraw_text")
            user_text = tmpl.format(request_code=request_code) if "{request_code}" in tmpl else tmpl
            admin_text = f"Hatırlatma: Çekim talebi {request_code} beklemede."

        sent_any = False
        try:
            await context.bot.send_message(chat_id=target.user_telegram_id, text=user_text)
            sent_any = True
        except Exception:
            logger.exception("Kullanıcıya hatırlatma gönderilemedi", extra={"request_code": request_code})

        try:
            await send_message_to_admins(context.application, settings, text=admin_text)
            sent_any = True
        except Exception:
            logger.exception("Adminlere hatırlatma gönderilemedi", extra={"request_code": request_code})

        if sent_any:
            with session_scope() as session:
                ReminderService.mark_sent(
                    session,
                    entity_type=target.entity_type,
                    entity_id=target.entity_id,
                )


async def daily_backup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not settings.auto_backup_enabled:
        return

    result = create_database_backup(settings)
    if not result.ok or not result.file_path:
        await send_message_to_admins(
            context.application,
            settings,
            text=f"Yedek alma başarısız: {result.message}",
        )
        return

    await send_backup_to_admins(context.application, settings, result.file_path)
    await send_message_to_admins(
        context.application,
        settings,
        text=f"Günlük yedek tamamlandı: {result.file_path.name}",
    )



def build_application() -> Application:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("Botu çalıştırmadan önce `.env` dosyasında `BOT_TOKEN` zorunludur.")
    setup_logging(settings.log_level)
    initialize_database()

    app = ApplicationBuilder().token(settings.bot_token).build()
    app.bot_data["settings"] = settings
    app.bot_data["tron_client"] = TronClient(settings.tron_rpc_url)

    app.add_handler(build_admin_conversation_handler())
    app.add_handler(build_user_conversation_handler())

    app.add_error_handler(on_error)

    app.job_queue.run_repeating(
        tron_watcher_job,
        interval=max(settings.tron_check_interval_sec, 30),
        first=20,
        name="tron_watcher",
    )
    app.job_queue.run_repeating(
        pending_reminder_job,
        interval=max(settings.reminder_interval_sec, 300),
        first=60,
        name="pending_reminder_job",
    )
    app.job_queue.run_daily(
        daily_backup_job,
        time=time(
            hour=max(0, min(settings.backup_hour_utc, 23)),
            minute=max(0, min(settings.backup_minute_utc, 59)),
            tzinfo=dt_timezone.utc,
        ),
        name="daily_backup_job",
    )

    return app


class _HealthHandler(BaseHTTPRequestHandler):
    admin_panel_token: str = ""

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/health"}:
            self._send_plain(200, "ok")
            return

        if parsed.path == "/admin-panel":
            if not self.admin_panel_token:
                self._send_plain(503, "ADMIN_PANEL_TOKEN ayarlanmamış.")
                return
            if not self._is_authorized(parsed):
                self._send_plain(403, "Yetkisiz erişim. /admin-panel?token=SENIN_TOKEN adresini kullanın.")
                return
            token = self._extract_token(parsed)
            self._send_html(200, _render_admin_panel_html(token))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path != "/admin-panel/save":
            self.send_response(404)
            self.end_headers()
            return

        if not self.admin_panel_token:
            self._send_plain(503, "ADMIN_PANEL_TOKEN ayarlanmamış.")
            return

        if not self._is_authorized(parsed):
            self._send_plain(403, "Yetkisiz erişim")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8", errors="ignore")
        payload = parse_qs(raw_body)

        key = (payload.get("key", [""])[0]).strip()
        content = (payload.get("content", [""])[0]).strip()

        if not key:
            self._send_plain(400, "`key` alanı zorunludur")
            return

        with session_scope() as session:
            TemplateService.set_template(session, key=key, content=content)

        token = self._extract_token(parsed)
        self.send_response(303)
        self.send_header("Location", f"/admin-panel?token={quote_plus(token)}")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _is_authorized(self, parsed) -> bool:
        token = self._extract_token(parsed)
        header_token = self.headers.get("X-Admin-Token", "").strip()
        return token == self.admin_panel_token or header_token == self.admin_panel_token

    def _extract_token(self, parsed) -> str:
        return parse_qs(parsed.query).get("token", [""])[0].strip()

    def _send_plain(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)



def _render_admin_panel_html(token: str) -> str:
    with session_scope() as session:
        db_rows = TemplateService.list_templates(session)

    db_map = {row.key: row.content for row in db_rows}
    hidden_legacy_keys = (set(LEGACY_TEXT_TEMPLATES_EN.keys()) - set(DEFAULT_TEXT_TEMPLATES.keys())) | OBSOLETE_TEMPLATE_KEYS
    all_keys = sorted((set(DEFAULT_TEXT_TEMPLATES.keys()) | set(db_map.keys())) - hidden_legacy_keys)

    sections: list[str] = []
    for key in all_keys:
        label = TEMPLATE_LABELS.get(key, key)
        value = db_map.get(key, DEFAULT_TEXT_TEMPLATES.get(key, ""))
        sections.append(
            (
                '<div class="card">'
                f"<h3>{escape(label)} <small>{escape(key)}</small></h3>"
                f'<form method="POST" action="/admin-panel/save?token={quote_plus(token)}">'
                f'<input type="hidden" name="key" value="{escape(key)}" />'
                f'<textarea name="content" rows="5">{escape(value)}</textarea>'
                '<button type="submit">Kaydet</button>'
                "</form>"
                "</div>"
            )
        )

    create_form = (
        '<div class="card">'
        "<h3>Yeni Metin Anahtarı Oluştur</h3>"
        f'<form method="POST" action="/admin-panel/save?token={quote_plus(token)}">'
        '<input type="text" name="key" placeholder="ornek_anahtar" required />'
        '<textarea name="content" rows="4" placeholder="Metin içeriği"></textarea>'
        '<button type="submit">Oluştur</button>'
        "</form>"
        "</div>"
    )

    return (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'><title>Bakiye Botu Metin Paneli</title>"
        "<style>"
        "body{font-family:Arial,sans-serif;background:#f5f7fb;margin:24px;}"
        "h1{margin-bottom:8px;}"
        ".muted{color:#666;margin-bottom:18px;}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px;}"
        ".card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:12px;}"
        "h3{margin:0 0 8px 0;font-size:16px;}"
        "h3 small{display:block;color:#777;font-size:12px;font-weight:normal;}"
        "textarea,input{width:100%;box-sizing:border-box;margin-bottom:8px;padding:8px;border:1px solid #bbb;border-radius:8px;}"
        "button{background:#111;color:#fff;border:none;padding:8px 12px;border-radius:8px;cursor:pointer;}"
        "button:hover{opacity:.9;}"
        "</style></head><body>"
        "<h1>Bakiye Botu Metin Yönetim Paneli</h1>"
        "<div class='muted'>Buradan bottaki yazıları kod değiştirmeden düzenleyebilirsiniz.</div>"
        "<div class='grid'>"
        + create_form
        + "".join(sections)
        + "</div></body></html>"
    )



def _start_health_server_if_needed(settings: Settings) -> None:
    port_raw = os.getenv("PORT", "").strip()
    if not port_raw:
        return

    try:
        port = int(port_raw)
    except ValueError:
        logger.warning("Geçersiz PORT değeri, health sunucusu devre dışı bırakıldı", extra={"port": port_raw})
        return

    _HealthHandler.admin_panel_token = settings.admin_panel_token

    def run_server() -> None:
        server = HTTPServer(("0.0.0.0", port), _HealthHandler)
        logger.info("Health/Admin sunucusu başlatıldı", extra={"port": port})
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()



def main() -> None:
    app = build_application()
    settings: Settings = app.bot_data["settings"]
    _start_health_server_if_needed(settings)
    logger.info("Bot long polling ile başlatılıyor")
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
