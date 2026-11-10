import asyncio
import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from app.database import BACKUP_DIR, DB_PATH

logger = logging.getLogger(__name__)

KEEP_DAYS = None  # backups older than this many days are removed; None keeps everything


def backup_path(day: date, backup_dir: Path = BACKUP_DIR) -> Path:
    return backup_dir / f"casa_{day.isoformat()}.db"


def create_backup(
    day: Optional[date] = None,
    db_file: Optional[Path] = None,
    backup_dir: Path = BACKUP_DIR,
) -> Optional[Path]:
    """Copy the database to db_backup/casa_YYYY-MM-DD.db and return the new path.

    Uses SQLite's online backup API, so the copy is consistent even while the
    app is writing. The same day's file is replaced. Returns None when there is
    no database to copy.
    """
    db_file = db_file or DB_PATH
    if not db_file.exists() or db_file.stat().st_size == 0:
        logger.warning("Backup skipped: %s does not exist or is empty", db_file)
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_path(day or date.today(), backup_dir)
    tmp = target.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)

    source = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    dest = sqlite3.connect(tmp)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    tmp.replace(target)  # atomic: a half-written file never takes the final name
    logger.info("Database backup created: %s", target)
    return target


def prune_backups(today: Optional[date] = None, backup_dir: Path = BACKUP_DIR, keep_days: Optional[int] = KEEP_DAYS) -> None:
    if keep_days is None or not backup_dir.exists():
        return
    limit = (today or date.today()) - timedelta(days=keep_days)
    for file in backup_dir.glob("casa_*.db"):
        try:
            file_day = date.fromisoformat(file.stem.removeprefix("casa_"))
        except ValueError:
            continue  # not one of ours
        if file_day < limit:
            file.unlink()


def seconds_until_midnight(now: Optional[datetime] = None) -> float:
    now = now or datetime.now()
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    return (midnight - now).total_seconds()


def _run_backup() -> None:
    try:
        create_backup()
        prune_backups()
    except Exception:
        logger.exception("Database backup failed")


async def backup_loop() -> None:
    """Back up on startup if today has no backup yet, then every midnight (server local time)."""
    if not backup_path(date.today()).exists():
        await asyncio.to_thread(_run_backup)
    while True:
        await asyncio.sleep(seconds_until_midnight() + 1)
        await asyncio.to_thread(_run_backup)
