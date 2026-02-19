from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import gzip
import shutil
from pathlib import Path

from telegram import InputFile
from telegram.ext import Application

from bot.config.settings import Settings


@dataclass
class BackupResult:
    ok: bool
    file_path: Path | None
    message: str


def _sqlite_db_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    raw = database_url.replace("sqlite:///", "", 1)
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _cleanup_old_backups(backup_dir: Path, retention_days: int) -> int:
    removed = 0
    threshold = datetime.now(timezone.utc) - timedelta(days=max(retention_days, 1))
    for path in backup_dir.glob("db_backup_*.db.gz"):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < threshold:
                path.unlink(missing_ok=True)
                removed += 1
        except Exception:
            continue
    return removed


def create_database_backup(settings: Settings) -> BackupResult:
    db_path = _sqlite_db_path(settings.database_url)
    if not db_path:
        return BackupResult(
            ok=False,
            file_path=None,
            message="Sadece SQLite otomatik yedeği destekleniyor.",
        )
    if not db_path.exists():
        return BackupResult(ok=False, file_path=None, message=f"Veritabanı bulunamadı: {db_path}")

    backup_dir = Path(settings.backup_dir).expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    gz_path = backup_dir / f"db_backup_{stamp}.db.gz"

    with db_path.open("rb") as src, gzip.open(gz_path, "wb") as dst:
        shutil.copyfileobj(src, dst)

    removed = _cleanup_old_backups(backup_dir, settings.backup_retention_days)
    msg = f"Yedek alındı: {gz_path.name}"
    if removed > 0:
        msg += f" | Eski silinen: {removed}"
    return BackupResult(ok=True, file_path=gz_path, message=msg)


async def send_backup_to_admins(application: Application, settings: Settings, backup_path: Path) -> None:
    for admin_id in settings.admin_ids:
        with backup_path.open("rb") as fp:
            await application.bot.send_document(
                chat_id=admin_id,
                document=InputFile(fp, filename=backup_path.name),
                caption="Günlük veritabanı yedeği",
            )

