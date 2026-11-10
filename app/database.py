import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

logger = logging.getLogger(__name__)

# Everything is anchored to the project folder, never to the directory the server was started from.
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CASA_DB_PATH") or BASE_DIR / "casa.db").resolve()
BACKUP_DIR = DB_PATH.parent / "db_backup"
LOG_DIR = Path(os.environ.get("CASA_LOG_DIR") or BASE_DIR / "logs")

DATABASE_URL = f"sqlite:///{DB_PATH}"


def _setup_sql_log() -> None:
    """Send every SQL statement to logs/sql.log instead of the terminal (echo stays off)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_DIR / "sql.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    sql_logger = logging.getLogger("sqlalchemy.engine")
    sql_logger.setLevel(logging.DEBUG)
    sql_logger.addHandler(handler)
    sql_logger.propagate = False


_setup_sql_log()

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False, "timeout": 30})


@event.listens_for(engine, "connect")
def _on_connect(dbapi_connection, _record):
    # SQLite ignores foreign keys unless this is switched on for every connection.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
    # Take transaction control from the driver, which would otherwise run DDL outside a transaction.
    dbapi_connection.isolation_level = None


@event.listens_for(engine, "begin")
def _on_begin(conn):
    conn.exec_driver_sql("BEGIN")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """
    Fast API dependency: fetches a database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app import models  # noqa: F401  # registers the tables on Base before create_all
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    _rebuild_planned_expenses()
    _add_check_constraints()


def _add_missing_columns():
    """create_all does not alter existing tables; add columns introduced after a table was created."""
    new_columns = {
        "income_items": {
            "is_gross": "BOOLEAN NOT NULL DEFAULT 0",
            "dependents": "INTEGER NOT NULL DEFAULT 0",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in new_columns.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

def _rebuild_planned_expenses():
    """Drop the old kind column and the foreign key on category_name (SQLite cannot alter them in place)."""
    if "kind" not in {c["name"] for c in inspect(engine).get_columns("planned_expenses")}:
        return
    _backup_before_migration()
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE planned_expenses RENAME TO planned_expenses_old"))
        conn.execute(text(
            "CREATE TABLE planned_expenses ("
            "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "description VARCHAR NOT NULL, value FLOAT NOT NULL, category_name VARCHAR NOT NULL, "
            "CONSTRAINT ck_planned_value CHECK (value > 0))"
        ))
        conn.execute(text(
            "INSERT INTO planned_expenses (id, description, value, category_name) "
            "SELECT id, description, value, category_name FROM planned_expenses_old"
        ))
        conn.execute(text("DROP TABLE planned_expenses_old"))


# Constraints added after their tables already existed: table -> {constraint name: valid-row condition}.
_LATE_CHECKS = {
    "variable_expenses": {"ck_var_month": "month >= 1 AND month <= 12"},
    "regular_expenses": {"ck_reg_month": "month >= 1 AND month <= 12"},
    "month_ratios": {
        "ck_ratio_month": "month >= 1 AND month <= 12",
        "ck_ratio_range": "fafa_ratio >= 0 AND fafa_ratio <= 1",
    },
}


def _add_check_constraints():
    """SQLite cannot add a CHECK to an existing table, so rebuild it from the model.

    Runs in one transaction per table, after a backup. A table whose current data
    breaks a new rule is left untouched and reported, so nothing is lost or rejected silently.
    """
    from app import models  # noqa: F401  # imported here: models imports Base from this module

    tables = {t.name: t for t in Base.metadata.sorted_tables}
    for name, checks in _LATE_CHECKS.items():
        with engine.connect() as conn:
            sql = conn.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).scalar() or ""
        if all(check in sql for check in checks):
            continue

        with engine.connect() as conn:
            for check, valid in checks.items():
                bad = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {name} WHERE NOT ({valid})").scalar()
                if bad:
                    logger.error("Migration skipped for %s: %d row(s) violate %s. Fix the data and restart.", name, bad, check)
                    break
            else:
                bad = 0
        if bad:
            continue

        _backup_before_migration()
        table = tables[name]
        with engine.begin() as conn:
            old_columns = [r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({name})")]
            shared = ", ".join(c.name for c in table.columns if c.name in old_columns)
            conn.exec_driver_sql(f"ALTER TABLE {name} RENAME TO {name}_old")
            table.create(conn)
            conn.exec_driver_sql(f"INSERT INTO {name} ({shared}) SELECT {shared} FROM {name}_old")
            conn.exec_driver_sql(f"DROP TABLE {name}_old")
        logger.info("Rebuilt %s with new CHECK constraints", name)


def _backup_before_migration() -> None:
    """Consistent copy of the database to db_backup/ before any structural change."""
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return
    BACKUP_DIR.mkdir(exist_ok=True)
    target = BACKUP_DIR / f"casa_pre_migration_{datetime.now():%Y-%m-%d_%H%M%S}.db"
    source = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    logger.info("Pre-migration backup created: %s", target)

@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

