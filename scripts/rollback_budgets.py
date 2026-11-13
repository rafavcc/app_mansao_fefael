"""Undo the budgets data migration: put the old plan tables back from a pre-migration backup.

    python scripts/rollback_budgets.py db_backup/casa_pre_migration_<stamp>.db [--db casa.db] --confirm-app-stopped

Restores income_items, planned_expenses and savings_items exactly as they are in the backup (schema,
indexes and rows) and drops budgets and budget_periods. Every other table (expenses, payments, ratios,
categories, users) is left as it is now. Budget edits made after the deploy are lost.

Safety: refuses unless --confirm-app-stopped is given and an exclusive lock on the database can be taken;
writes casa_pre_rollback_<stamp>.db next to the database before changing anything; the restore is one
transaction that is rolled back on any error.

Uses only sqlite3 and the standard library, so it still works after the app code was reverted to the
pre-budgets tag.
"""
import argparse
import os
import sqlite3
import sys
import traceback
from datetime import datetime
from pathlib import Path

PLAN_TABLES = ("income_items", "planned_expenses", "savings_items")
BUDGET_TABLES = ("budget_periods", "budgets")  # children first
LOCK_TIMEOUT = 2.0  # seconds to wait for other connections before refusing
DEFAULT_DB = Path(os.environ.get("CASA_DB_PATH") or Path(__file__).resolve().parent.parent / "casa.db")

EXIT_REFUSED = 1
EXIT_BAD_BACKUP = 2
EXIT_FAILED = 3


class RollbackRefused(Exception):
    """The rollback did not start; nothing was changed."""

    def __init__(self, message: str, exit_code: int = EXIT_REFUSED):
        super().__init__(message)
        self.exit_code = exit_code


def rollback(db_path: Path, backup_path: Path) -> dict:
    """Restore the pre-budget plan tables of db_path from backup_path. See the module docstring."""
    db_path, backup_path = Path(db_path).resolve(), Path(backup_path).resolve()
    if not db_path.is_file():
        raise RollbackRefused(f"Database not found: {db_path}")
    if not backup_path.is_file():
        raise RollbackRefused(f"Backup not found: {backup_path}", EXIT_BAD_BACKUP)
    if db_path.samefile(backup_path):
        raise RollbackRefused("The backup is the database itself", EXIT_BAD_BACKUP)

    # Autocommit mode: the module must not open or commit transactions on its own.
    conn = sqlite3.connect(db_path.as_uri(), uri=True, isolation_level=None, timeout=LOCK_TIMEOUT)
    try:
        # ATTACH and PRAGMA foreign_keys have no effect inside a transaction, so they come first.
        conn.execute("ATTACH DATABASE ? AS bak", (backup_path.as_uri() + "?mode=ro",))
        conn.execute("PRAGMA foreign_keys=OFF")  # dropping budgets must not cascade or fail
        backup_tables = _check_backup(conn, backup_path)
        _check_database_is_migrated(conn, db_path)
        _lock(conn)
        try:
            safety = _safety_backup(db_path)
            restored = _restore(conn, backup_tables)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return {
        "restored_income": restored["income_items"],
        "restored_expenses": restored["planned_expenses"],
        "restored_savings": restored["savings_items"],
        "safety_backup": safety,
    }


def _tables(conn, schema: str) -> set[str]:
    return {r[0] for r in conn.execute(f"SELECT name FROM {schema}.sqlite_master WHERE type='table'")}


def _columns(conn, schema: str, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f'PRAGMA {schema}.table_info("{table}")')}


def _check_backup(conn, backup_path: Path) -> set[str]:
    try:
        tables = _tables(conn, "bak")
    except sqlite3.DatabaseError as exc:
        raise RollbackRefused(f"Cannot read the backup {backup_path}: {exc}", EXIT_BAD_BACKUP) from exc
    if "income_items" not in tables:
        raise RollbackRefused(f"{backup_path} has no income_items table: not a pre-migration backup", EXIT_BAD_BACKUP)
    # The migration's own backup already has an empty budgets table (created on startup before the
    # migration), so the plan tables' columns are what tell a pre-migration backup apart.
    if any("budget_id" in _columns(conn, "bak", t) for t in PLAN_TABLES if t in tables):
        raise RollbackRefused(
            f"{backup_path} was taken after the budgets migration; use a casa_pre_migration_*.db backup",
            EXIT_BAD_BACKUP,
        )
    return tables & set(PLAN_TABLES)


def _check_database_is_migrated(conn, db_path: Path) -> None:
    present = _tables(conn, "main")
    if not any("budget_id" in _columns(conn, "main", t) for t in PLAN_TABLES if t in present):
        raise RollbackRefused(f"{db_path} plan tables have no budget_id column: it is not migrated (or was already rolled back)")


def _lock(conn) -> None:
    """Refuse if anything else is using the database, then keep other writers out until COMMIT.

    BEGIN EXCLUSIVE fails while any other connection reads or writes. The restore itself runs under
    BEGIN IMMEDIATE so the safety backup can still be read through a second connection while no one
    else can write in between.
    """
    try:
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("ROLLBACK")
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise RollbackRefused(f"The database is in use ({exc}). Stop the app and try again.") from exc


def _safety_backup(db_path: Path) -> Path:
    stamp = f"casa_pre_rollback_{datetime.now():%Y-%m-%d_%H%M%S}"
    target = db_path.parent / f"{stamp}.db"
    suffix = 1
    while target.exists():
        target = db_path.parent / f"{stamp}_{suffix}.db"
        suffix += 1
    source = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=LOCK_TIMEOUT)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
        if dest.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise RuntimeError(f"Safety backup {target} failed its integrity check")
    except BaseException:
        dest.close()
        target.unlink(missing_ok=True)
        raise
    finally:
        dest.close()
        source.close()
    return target


def _restore(conn, backup_tables: set[str]) -> dict[str, int]:
    """Inside the open transaction: drop the budget and plan tables, recreate the plan tables from the backup."""
    violations_before = set(conn.execute("PRAGMA main.foreign_key_check").fetchall())
    present = _tables(conn, "main")
    for name in (*BUDGET_TABLES, *PLAN_TABLES):
        if name in present:
            conn.execute(f'DROP TABLE main."{name}"')

    restored = {}
    for name in PLAN_TABLES:
        if name not in backup_tables:
            restored[name] = 0
            continue
        (create_sql,) = conn.execute("SELECT sql FROM bak.sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
        conn.execute(create_sql)
        restored[name] = _copy_table(conn, name)
        extras = conn.execute(
            "SELECT sql FROM bak.sqlite_master WHERE type IN ('index', 'trigger') AND tbl_name=? AND sql IS NOT NULL "
            "ORDER BY type = 'trigger', name",
            (name,),
        ).fetchall()
        for (sql,) in extras:
            conn.execute(sql)
        _restore_sequence(conn, name)
        if _columns(conn, "main", name) != _columns(conn, "bak", name):
            raise RuntimeError(f"{name}: restored columns differ from the backup")

    new_violations = set(conn.execute("PRAGMA main.foreign_key_check").fetchall()) - violations_before
    if new_violations:
        raise RuntimeError(f"Restore would break foreign keys: {sorted(new_violations)}")
    if conn.execute("PRAGMA main.quick_check").fetchone() != ("ok",):
        raise RuntimeError("Database failed its integrity check after the restore")
    return restored


def _copy_table(conn, name: str) -> int:
    conn.execute(f'INSERT INTO main."{name}" SELECT * FROM bak."{name}"')
    copied = conn.execute(f'SELECT COUNT(*) FROM main."{name}"').fetchone()[0]
    expected = conn.execute(f'SELECT COUNT(*) FROM bak."{name}"').fetchone()[0]
    if copied != expected:
        raise RuntimeError(f"{name}: copied {copied} of {expected} rows")
    return copied


def _restore_sequence(conn, name: str) -> None:
    """Keep the AUTOINCREMENT counter the backup had, so ids are not reused differently than before."""
    if "sqlite_sequence" not in _tables(conn, "bak") or "sqlite_sequence" not in _tables(conn, "main"):
        return
    row = conn.execute("SELECT seq FROM bak.sqlite_sequence WHERE name=?", (name,)).fetchone()
    if row is None:
        return
    if conn.execute("UPDATE main.sqlite_sequence SET seq=? WHERE name=?", (row[0], name)).rowcount == 0:
        conn.execute("INSERT INTO main.sqlite_sequence (name, seq) VALUES (?, ?)", (name, row[0]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Undo the budgets data migration from a pre-migration backup.")
    parser.add_argument("backup", type=Path, help="db_backup/casa_pre_migration_<stamp>.db")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"database to roll back (default: {DEFAULT_DB})")
    parser.add_argument("--confirm-app-stopped", action="store_true", help="confirm the app server is stopped")
    args = parser.parse_args(argv)

    if not args.confirm_app_stopped:
        print("Refusing: stop the app server first, then run again with --confirm-app-stopped.", file=sys.stderr)
        return EXIT_REFUSED
    print(f"Rolling back {args.db.resolve()} from {args.backup.resolve()}")
    try:
        result = rollback(args.db, args.backup)
    except RollbackRefused as exc:
        print(f"Refusing: {exc}\nNothing was changed.", file=sys.stderr)
        return exc.exit_code
    except Exception:
        traceback.print_exc()
        print("Rollback FAILED and was undone: the database is unchanged.", file=sys.stderr)
        return EXIT_FAILED

    print("Rollback complete. Restored from the backup:")
    print(f"  income_items:     {result['restored_income']} rows")
    print(f"  planned_expenses: {result['restored_expenses']} rows")
    print(f"  savings_items:    {result['restored_savings']} rows")
    print("Dropped: budgets, budget_periods. Expenses, payments, ratios, categories and users were kept.")
    print(f"Safety backup of the database as it was before the rollback: {result['safety_backup']}")
    print("WARNING: budget edits made after the deploy are lost (budgets, ranges and plan items changed since the backup).")
    print("Run the app from the pre-budgets code (git checkout pre-budgets) before starting it again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
