"""
Data rollback of the budgets migration: restore the old plan tables from the pre-migration backup,
drop the budget tables and keep everything else entered after the deploy.
"""
import hashlib
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import database
from scripts import rollback_budgets
from tests.test_budget_migration import EXPENSE_ROWS, INCOME_ROWS, SAVINGS_ROWS, backups, build_old_db

SCRIPT = Path(rollback_budgets.__file__)
PLAN_TABLES = ("income_items", "planned_expenses", "savings_items")
BUDGET_TABLES = ("budgets", "budget_periods")
OLD_INDEX = "CREATE INDEX ix_planned_category ON planned_expenses (category_name)"


def table_names(db_path):
    with sqlite3.connect(db_path) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    return names - {"sqlite_sequence"}


def snapshot(db_path, tables):
    """Schema and every row of the given tables, plus the indexes defined on them."""
    with sqlite3.connect(db_path) as conn:
        result = {}
        for name in sorted(tables):
            sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0]
            indexes = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL ORDER BY name",
                (name,),
            ).fetchall()
            result[name] = (sql, indexes, sorted(conn.execute(f"SELECT * FROM {name}").fetchall(), key=repr))
    conn.close()
    return result


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safety_backups(db_path):
    return sorted(Path(db_path).parent.glob("casa_pre_rollback_*.db"))


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    """An old-schema database (with an extra index) migrated by init_db; returns (db, backup, original copy)."""
    build_old_db(tmp_path, monkeypatch, INCOME_ROWS, EXPENSE_ROWS, SAVINGS_ROWS)
    db_path = tmp_path / "old.db"
    with sqlite3.connect(db_path) as raw:
        raw.execute(OLD_INDEX)
    raw.close()
    original = tmp_path / "original.db"
    shutil.copy(db_path, original)

    database.init_db()
    database.engine.dispose()
    [backup] = backups(tmp_path)
    assert "budgets" in table_names(db_path)
    return db_path, backup, original


def test_rollback_round_trip(migrated):
    db_path, backup, original = migrated
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO users (name) VALUES ('FAFA')")
        conn.execute("INSERT INTO variable_categories (name) VALUES ('Mercado')")
        conn.execute(
            "INSERT INTO variable_expenses (place, day, month, year, value, paid_by, category_name) "
            "VALUES ('Feira', 10, 11, 2026, 87.5, 'FAFA', 'Mercado')"
        )
        conn.execute("INSERT INTO payments (paid_on, value, method) VALUES ('2026-11-12', 300, 'PIX')")
        conn.execute("UPDATE income_items SET value = 9999 WHERE id = 3")
        budget_id = conn.execute("SELECT id FROM budgets").fetchone()[0]
        conn.execute(
            "INSERT INTO budget_periods (budget_id, start_month, start_year) VALUES (?, 11, 2026)", (budget_id,)
        )
    conn.close()
    others = table_names(db_path) - set(PLAN_TABLES) - set(BUDGET_TABLES)
    others_before = snapshot(db_path, others)

    result = rollback_budgets.rollback(db_path, backup)

    assert result["restored_income"] == len(INCOME_ROWS)
    assert result["restored_expenses"] == len(EXPENSE_ROWS)
    assert result["restored_savings"] == len(SAVINGS_ROWS)
    tables = table_names(db_path)
    assert not tables & set(BUDGET_TABLES)
    assert snapshot(db_path, PLAN_TABLES) == snapshot(original, PLAN_TABLES)
    assert snapshot(db_path, others) == others_before
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT place, value FROM variable_expenses").fetchall() == [("Feira", 87.5)]
        assert conn.execute("SELECT value, method FROM payments").fetchall() == [(300.0, "PIX")]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    conn.close()

    safety = result["safety_backup"]
    assert safety.exists() and safety.parent == db_path.parent and safety.name.startswith("casa_pre_rollback_")
    assert safety_backups(db_path) == [safety]
    # The safety backup is the database as it was just before the rollback.
    assert BUDGET_TABLES[0] in table_names(safety)
    with sqlite3.connect(safety) as conn:
        assert conn.execute("SELECT value FROM income_items WHERE id = 3").fetchone() == (9999.0,)
    conn.close()


def test_cli_runs_without_the_app_and_says_budget_edits_are_lost(migrated):
    db_path, backup, original = migrated

    # A separate interpreter: the script must not need anything from the app package.
    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(backup), "--db", str(db_path), "--confirm-app-stopped"],
        capture_output=True, text=True, cwd=db_path.parent,
    )

    assert proc.returncode == 0, proc.stderr
    assert "lost" in proc.stdout.lower()
    [safety] = safety_backups(db_path)
    assert str(safety) in proc.stdout
    undo = [line for line in proc.stdout.splitlines() if "undo" in line.lower()]
    assert undo and str(safety) in undo[0] and "casa.db" in undo[0]
    assert snapshot(db_path, PLAN_TABLES) == snapshot(original, PLAN_TABLES)
    assert not table_names(db_path) & set(BUDGET_TABLES)


def test_rollback_requires_confirmation_and_a_free_database(migrated, monkeypatch):
    db_path, backup, _ = migrated
    before = file_hash(db_path)

    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(backup), "--db", str(db_path)], capture_output=True, text=True
    )
    assert proc.returncode != 0
    assert "--confirm-app-stopped" in proc.stderr
    assert file_hash(db_path) == before and safety_backups(db_path) == []

    monkeypatch.setattr(rollback_budgets, "LOCK_TIMEOUT", 0.2)
    other = sqlite3.connect(db_path, isolation_level=None)
    other.execute("BEGIN IMMEDIATE")  # what a running app does while it writes
    try:
        code = rollback_budgets.main([str(backup), "--db", str(db_path), "--confirm-app-stopped"])
        assert code not in (0, None)
        with pytest.raises(rollback_budgets.RollbackRefused, match="in use"):
            rollback_budgets.rollback(db_path, backup)
    finally:
        other.execute("ROLLBACK")
        other.close()
    assert file_hash(db_path) == before and safety_backups(db_path) == []


@pytest.mark.parametrize("kind", ["no_plan_tables", "already_migrated"])
def test_rollback_rejects_a_backup_without_plan_tables(migrated, tmp_path, kind):
    db_path, _, _ = migrated
    bad = tmp_path / "bad_backup.db"
    if kind == "no_plan_tables":
        with sqlite3.connect(bad) as conn:
            conn.execute("CREATE TABLE payments (id INTEGER PRIMARY KEY)")
        conn.close()
    else:
        shutil.copy(db_path, bad)  # taken after the migration: restoring it would restore nothing
    before = file_hash(db_path)

    code = rollback_budgets.main([str(bad), "--db", str(db_path), "--confirm-app-stopped"])

    assert code == 2
    assert file_hash(db_path) == before and safety_backups(db_path) == []


def test_rollback_refuses_a_missing_database(tmp_path, migrated):
    _, backup, _ = migrated
    missing = tmp_path / "nope" / "casa.db"

    code = rollback_budgets.main([str(backup), "--db", str(missing), "--confirm-app-stopped"])

    assert code not in (0, None)
    assert not missing.exists()


def test_rollback_refuses_a_database_that_is_not_migrated(migrated):
    db_path, backup, _ = migrated
    rollback_budgets.rollback(db_path, backup)
    before = file_hash(db_path)

    # A second run would overwrite plan rows edited after the first rollback.
    code = rollback_budgets.main([str(backup), "--db", str(db_path), "--confirm-app-stopped"])

    assert code not in (0, None)
    assert file_hash(db_path) == before and len(safety_backups(db_path)) == 1


def test_failed_restore_rolls_everything_back(migrated, monkeypatch):
    db_path, backup, _ = migrated
    tables_before = snapshot(db_path, table_names(db_path))

    original = rollback_budgets._copy_table

    def copy_then_fail(conn, name):
        count = original(conn, name)
        if name == "savings_items":  # after every table was dropped, recreated and filled
            raise RuntimeError("forced failure")
        return count

    monkeypatch.setattr(rollback_budgets, "_copy_table", copy_then_fail)

    with pytest.raises(RuntimeError, match="forced failure"):
        rollback_budgets.rollback(db_path, backup)

    assert snapshot(db_path, table_names(db_path)) == tables_before
    # The safety backup was made before the failed attempt and is kept.
    assert len(safety_backups(db_path)) == 1
