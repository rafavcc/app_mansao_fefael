"""
Startup migration from the pre-budget schema: plan items move into one budget and savings are dropped.
Each test builds an old-schema database in tmp_path and points app.database at it.
"""
import logging
import sqlite3

import pytest
from sqlalchemy import inspect

from app import database

OLD_INCOME = (
    "CREATE TABLE income_items (id INTEGER NOT NULL, description VARCHAR NOT NULL, value FLOAT NOT NULL, "
    "is_gross BOOLEAN DEFAULT '0' NOT NULL, dependents INTEGER DEFAULT '0' NOT NULL, PRIMARY KEY (id), "
    "CONSTRAINT ck_income_value CHECK (value > 0), CONSTRAINT ck_income_dependents CHECK (dependents >= 0))"
)
OLD_EXPENSES = (
    "CREATE TABLE planned_expenses (id INTEGER NOT NULL, description VARCHAR NOT NULL, value FLOAT NOT NULL, "
    "category_name VARCHAR NOT NULL, PRIMARY KEY (id), CONSTRAINT ck_planned_value CHECK (value > 0))"
)
OLD_SAVINGS = (
    "CREATE TABLE savings_items (id INTEGER NOT NULL, description VARCHAR NOT NULL, value FLOAT NOT NULL, "
    "PRIMARY KEY (id), CONSTRAINT ck_savings_value CHECK (value > 0))"
)
INCOME_ROWS = [(3, "Salário Rafa", 9000.0, 1, 1), (7, "VR", 800.5, 0, 0)]
EXPENSE_ROWS = [(1, "Aluguel", 2500.0, "Aluguel"), (4, "Luz", 120.3, "Cemig"), (9, "Cinema", 50.0, "Lazer")]
SAVINGS_ROWS = [(1, "Reserva", 1000.0)]


def build_old_db(tmp_path, monkeypatch, income=(), expenses=(), savings=(), with_expenses_table=True):
    db_path = tmp_path / "old.db"
    with sqlite3.connect(db_path) as raw:
        raw.execute(OLD_INCOME)
        if with_expenses_table:
            raw.execute(OLD_EXPENSES)
        raw.execute(OLD_SAVINGS)
        raw.executemany("INSERT INTO income_items VALUES (?, ?, ?, ?, ?)", income)
        if with_expenses_table:
            raw.executemany("INSERT INTO planned_expenses VALUES (?, ?, ?, ?)", expenses)
        raw.executemany("INSERT INTO savings_items VALUES (?, ?, ?)", savings)
    raw.close()
    return point_app_at(db_path, monkeypatch)


def point_app_at(db_path, monkeypatch):
    engine = database.make_engine(f"sqlite:///{db_path}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(database, "BACKUP_DIR", db_path.parent / "db_backup")
    return engine


def rows(engine, sql):
    with engine.connect() as conn:
        return conn.exec_driver_sql(sql).all()


def columns(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def backups(tmp_path):
    return sorted((tmp_path / "db_backup").glob("casa_pre_migration_*.db"))


def test_migration_moves_existing_items_into_one_budget(tmp_path, monkeypatch):
    engine = build_old_db(tmp_path, monkeypatch, INCOME_ROWS, EXPENSE_ROWS, SAVINGS_ROWS)

    database.init_db()

    budgets = rows(engine, "SELECT id, name FROM budgets")
    assert len(budgets) == 1 and budgets[0][1] == database.MIGRATED_BUDGET_NAME == "Orçamento atual"
    budget_id = budgets[0][0]
    assert rows(engine, "SELECT COUNT(*) FROM budget_periods") == [(0,)]
    assert rows(engine, "SELECT id, description, value, is_gross, dependents, budget_id FROM income_items ORDER BY id") == [
        (*r, budget_id) for r in INCOME_ROWS
    ]
    assert rows(engine, "SELECT id, description, value, category_name, budget_id FROM planned_expenses ORDER BY id") == [
        (*r, budget_id) for r in EXPENSE_ROWS
    ]
    tables = set(inspect(engine).get_table_names())
    assert "savings_items" not in tables
    assert not {t for t in tables if t.endswith("_old")}

    [backup] = backups(tmp_path)
    with sqlite3.connect(f"file:{backup}?mode=ro", uri=True) as old:
        assert old.execute("SELECT id, description, value FROM savings_items").fetchall() == SAVINGS_ROWS
    old.close()


def test_migrated_tables_enforce_the_budget_foreign_key(tmp_path, monkeypatch):
    engine = build_old_db(tmp_path, monkeypatch, INCOME_ROWS, EXPENSE_ROWS)
    database.init_db()

    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        with pytest.raises(Exception):
            conn.exec_driver_sql("INSERT INTO income_items (description, value, budget_id) VALUES ('x', 1, 999)")
    # Deleting the budget still cascades into the migrated tables.
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM budgets")
    assert rows(engine, "SELECT COUNT(*) FROM income_items") == [(0,)]
    assert rows(engine, "SELECT COUNT(*) FROM planned_expenses") == [(0,)]


def test_migration_on_empty_database_creates_no_budget(tmp_path, monkeypatch):
    engine = build_old_db(tmp_path, monkeypatch)

    database.init_db()

    assert rows(engine, "SELECT COUNT(*) FROM budgets") == [(0,)]
    assert "budget_id" in columns(engine, "income_items")
    assert "budget_id" in columns(engine, "planned_expenses")
    assert "savings_items" not in inspect(engine).get_table_names()


def test_migration_with_only_income_rows(tmp_path, monkeypatch):
    engine = build_old_db(tmp_path, monkeypatch, income=INCOME_ROWS, with_expenses_table=False)

    database.init_db()

    [(budget_id,)] = rows(engine, "SELECT id FROM budgets")
    assert rows(engine, "SELECT id, description, value, is_gross, dependents, budget_id FROM income_items ORDER BY id") == [
        (*r, budget_id) for r in INCOME_ROWS
    ]
    assert "budget_id" in columns(engine, "planned_expenses")
    assert rows(engine, "SELECT COUNT(*) FROM planned_expenses") == [(0,)]


def test_migration_is_idempotent(tmp_path, monkeypatch):
    engine = build_old_db(tmp_path, monkeypatch, INCOME_ROWS, EXPENSE_ROWS, SAVINGS_ROWS)

    database.init_db()
    database.init_db()

    assert rows(engine, "SELECT COUNT(*) FROM budgets") == [(1,)]
    assert rows(engine, "SELECT COUNT(*) FROM income_items") == [(len(INCOME_ROWS),)]
    assert rows(engine, "SELECT COUNT(*) FROM planned_expenses") == [(len(EXPENSE_ROWS),)]
    assert len(backups(tmp_path)) == 1


def test_fresh_database_gets_new_schema_without_backup(tmp_path, monkeypatch):
    db_path = tmp_path / "old.db"
    db_path.touch()
    engine = point_app_at(db_path, monkeypatch)

    database.init_db()

    tables = set(inspect(engine).get_table_names())
    assert {"budgets", "budget_periods"} <= tables
    assert "savings_items" not in tables
    assert "budget_id" in columns(engine, "income_items")
    assert backups(tmp_path) == []


@pytest.mark.parametrize(
    "fail_at, with_rows",
    [
        ("budget_insert", True),
        ("after_both_rebuilds", True),
        # Without rows there is no INSERT before the DDL, so only a real BEGIN makes the DDL undoable.
        ("after_both_rebuilds", False),
    ],
)
def test_migration_failure_leaves_old_schema(tmp_path, monkeypatch, caplog, fail_at, with_rows):
    income, expenses, savings = (INCOME_ROWS, EXPENSE_ROWS, SAVINGS_ROWS) if with_rows else ([], [], [])
    engine = build_old_db(tmp_path, monkeypatch, income, expenses, savings)

    def boom(*_args, **_kwargs):
        raise RuntimeError("forced failure")

    if fail_at == "budget_insert":
        monkeypatch.setattr(database, "_insert_migrated_budget", boom)
    else:
        # Let both tables be renamed, recreated, copied and dropped, then fail before the commit:
        # the rollback has to undo DDL, not just the budget row.
        original = database._rebuild_with_budget

        def rebuild_then_fail(conn, table, budget_id):
            original(conn, table, budget_id)
            if table.name == "planned_expenses":
                boom()

        monkeypatch.setattr(database, "_rebuild_with_budget", rebuild_then_fail)

    with caplog.at_level(logging.ERROR, logger="app.database"):
        database.init_db()  # logs, does not raise

    assert "forced failure" in caplog.text
    assert "budget_id" not in columns(engine, "income_items")
    assert "budget_id" not in columns(engine, "planned_expenses")
    tables = set(inspect(engine).get_table_names())
    assert "savings_items" in tables
    assert not {t for t in tables if t.endswith("_old")}
    assert rows(engine, "SELECT COUNT(*) FROM budgets") == [(0,)]
    assert rows(engine, "SELECT id, description, value, is_gross, dependents FROM income_items ORDER BY id") == income
    assert rows(engine, "SELECT id, description, value, category_name FROM planned_expenses ORDER BY id") == expenses
    assert rows(engine, "SELECT id, description, value FROM savings_items") == savings
