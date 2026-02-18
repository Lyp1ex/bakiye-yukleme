from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import os
import threading

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from bot.config.logging_config import setup_logging
from bot.config.settings import get_settings
from bot.crypto.tron_client import TronClient
from bot.crypto.watcher import tron_watcher_job
from bot.database.bootstrap import initialize_database
from bot.handlers import build_admin_conversation_handler, build_user_conversation_handler

logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("An unexpected error occurred. Please try again.")
        except Exception:
            logger.exception("Failed to send error message to user")



def build_application() -> Application:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required in .env before running the bot.")
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

    return app


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path in {"/", "/health"}:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return



def _start_health_server_if_needed() -> None:
    port_raw = os.getenv("PORT", "").strip()
    if not port_raw:
        return

    try:
        port = int(port_raw)
    except ValueError:
        logger.warning("Invalid PORT value, health server disabled", extra={"port": port_raw})
        return

    def run_server() -> None:
        server = HTTPServer(("0.0.0.0", port), _HealthHandler)
        logger.info("Health server started", extra={"port": port})
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()



def main() -> None:
    app = build_application()
    _start_health_server_if_needed()
    logger.info("Starting bot with long polling")
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
