"""
Tests for planning functionality.
Uses db_session fixture to avoid conflicts.
"""
from app import crud
from app.models import Budget, IncomeItem, PlannedExpense, RegularExpense, VariableExpense
from app.planning import calculate_plan


def make_budget(db, name="B1") -> Budget:
    budget = Budget(name=name)
    db.add(budget)
    db.commit()
    return budget


def test_plan_totals_free_balance_and_actual(db_session):
    budget = make_budget(db_session)
    crud.save_plan_item(db_session, "income", {"description": "Salário Fafa", "value": 6000, "budget_id": budget.id})
    crud.save_plan_item(db_session, "income", {"description": "VR Fefe", "value": 1000, "budget_id": budget.id})
    crud.save_plan_item(db_session, "expense", {
        "description": "Aluguel", "value": 3000, "category_name": "Aluguel", "budget_id": budget.id})
    crud.save_plan_item(db_session, "expense", {
        "description": "Bar", "value": 500, "category_name": "Aluguel", "budget_id": budget.id})
    db_session.add(RegularExpense(
        day=1, month=10, year=2026, value=3200, paid_by="FAFA", category_name="Aluguel"))
    db_session.commit()

    plan = calculate_plan(db_session, budget.id, 10, 2026)

    assert plan["income_total"] == 7000
    assert plan["expenses_total"] == 3500
    assert plan["free_balance"] == 3500
    assert plan["free_balance_pct"] == 50.0
    assert plan["actual_vs_planned"] == -300


def test_plan_without_income_has_no_percentages(db_session):
    budget = make_budget(db_session)
    plan = calculate_plan(db_session, budget.id, 10, 2026)
    assert plan["free_balance_pct"] is None


def test_update_and_delete_plan_item(db_session):
    budget = make_budget(db_session)
    item = crud.save_plan_item(db_session, "income", {"description": "X", "value": 10, "budget_id": budget.id})
    crud.save_plan_item(db_session, "income", {"value": 20}, item.id)
    assert crud.get_plan_items(db_session, "income", budget.id)[0].value == 20
    assert crud.delete_plan_item(db_session, "income", item.id)
    assert not crud.delete_plan_item(db_session, "income", item.id)


def test_plan_negative_free_balance_when_overspending(db_session):
    budget = make_budget(db_session)
    crud.save_plan_item(db_session, "income", {"description": "S", "value": 1000, "budget_id": budget.id})
    crud.save_plan_item(db_session, "expense", {
        "description": "A", "value": 1200, "category_name": "Aluguel", "budget_id": budget.id})
    plan = calculate_plan(db_session, budget.id, 10, 2026)
    assert plan["free_balance"] == -200
    assert plan["free_balance_pct"] == -20.0


def test_plan_actual_includes_variable_and_regular(db_session):
    budget = make_budget(db_session)
    db_session.add_all([
        VariableExpense(place="x", day=1, month=10, year=2026, value=100,
                        paid_by="FAFA", category_name="Mercado"),
        RegularExpense(day=1, month=10, year=2026, value=50,
                       paid_by="FAFA", category_name="Aluguel"),
    ])
    db_session.commit()
    plan = calculate_plan(db_session, budget.id, 10, 2026)
    assert plan["actual_total"] == 150
    assert plan["actual_vs_planned"] == 150


def test_plan_rejects_invalid_items(db_session):
    budget = make_budget(db_session)
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        crud.save_plan_item(db_session, "income", {"description": "S", "value": 0, "budget_id": budget.id})
    db_session.rollback()
    with pytest.raises(IntegrityError):
        crud.save_plan_item(db_session, "expense", {
            "description": "A", "value": 0, "category_name": "Aluguel", "budget_id": budget.id})


def test_update_missing_plan_item_returns_none(db_session):
    assert crud.save_plan_item(db_session, "income", {"value": 5}, 999) is None


def test_plan_uses_net_income_for_gross_salaries(db_session):
    budget = make_budget(db_session)
    from app.taxes import calculate_net_salary
    crud.save_plan_item(db_session, "income", {"description": "Salário", "value": 6000, "is_gross": True, "budget_id": budget.id})
    crud.save_plan_item(db_session, "income", {"description": "VR", "value": 800, "budget_id": budget.id})

    plan = calculate_plan(db_session, budget.id, 10, 2026)
    pay = calculate_net_salary(6000)

    assert plan["gross_income_total"] == 6800
    assert plan["taxes_total"] == pay["taxes"]
    assert plan["income_total"] == round(pay["net"] + 800, 2)
    assert plan["free_balance"] == plan["income_total"]


def test_init_db_adds_columns_to_existing_income_table(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from app import database

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE income_items (id INTEGER PRIMARY KEY, description TEXT, value FLOAT)"))
        conn.execute(text("INSERT INTO income_items (description, value) VALUES ('Antigo', 10)"))
    monkeypatch.setattr(database, "engine", engine)

    database.init_db()
    database.init_db()  # idempotent

    columns = {c["name"] for c in inspect(engine).get_columns("income_items")}
    assert {"is_gross", "dependents"} <= columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT is_gross, dependents FROM income_items")).one() == (0, 0)


def test_planning_categories_are_union_of_regular_and_variable(db_session):
    from app.models import RegularCategory, VariableCategory
    
    # Create all necessary categories first with unique names
    crud.create_regular_category(db_session, "ALUGUEL_TEST")
    db_session.add_all([RegularCategory(name="Mercado"), VariableCategory(name="Lazer")])
    db_session.commit()
    # "Mercado" exists in both lists and "ALUGUEL_TEST" only in regular ones
    assert crud.get_planning_categories(db_session) == ["ALUGUEL_TEST", "Lazer", "Mercado"]


def test_planned_expense_accepts_variable_only_category(db_session):
    budget = make_budget(db_session)
    from app.models import VariableCategory
    db_session.add(VariableCategory(name="Lazer"))
    db_session.commit()
    item = crud.save_plan_item(db_session, "expense", {"description": "Cinema", "value": 50, "category_name": "Lazer", "budget_id": budget.id})
    assert item.category_name == "Lazer"


def test_init_db_rebuilds_old_planned_expenses_table(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from app import database

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE regular_categories (name VARCHAR PRIMARY KEY)"))
        conn.execute(text(
            "CREATE TABLE planned_expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, description VARCHAR NOT NULL, "
            "value FLOAT NOT NULL, category_name VARCHAR NOT NULL REFERENCES regular_categories(name), "
            "kind VARCHAR NOT NULL)"))
        conn.execute(text("INSERT INTO planned_expenses (description, value, category_name, kind) "
                          "VALUES ('Luz', 120, 'Cemig', 'NECESSIDADE')"))
    monkeypatch.setattr(database, "engine", engine)

    database.init_db()
    database.init_db()  # idempotent

    assert "kind" not in {c["name"] for c in inspect(engine).get_columns("planned_expenses")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT description, value, category_name FROM planned_expenses")).one() == ("Luz", 120, "Cemig")


def test_plan_items_are_scoped_to_their_budget(db_session):
    b1, b2 = make_budget(db_session, "B1"), make_budget(db_session, "B2")
    crud.save_plan_item(db_session, "income", {"description": "A", "value": 100, "budget_id": b1.id})
    crud.save_plan_item(db_session, "income", {"description": "B", "value": 300, "budget_id": b2.id})

    items = crud.get_plan_items(db_session, "income", b1.id)
    assert [i.description for i in items] == ["A"]
    assert calculate_plan(db_session, b1.id, 10, 2026)["income_total"] == 100
    assert calculate_plan(db_session, b2.id, 10, 2026)["income_total"] == 300


def test_category_delete_moves_planned_items_of_every_budget(db_session):
    from app.models import VariableCategory
    db_session.add_all([VariableCategory(name="Lazer"), VariableCategory(name="Mercado")])
    db_session.commit()
    b1, b2 = make_budget(db_session, "B1"), make_budget(db_session, "B2")
    for b in (b1, b2):
        crud.save_plan_item(db_session, "expense", {
            "description": "Cinema", "value": 50, "category_name": "Lazer", "budget_id": b.id})

    crud.delete_category(db_session, "variable", "Lazer", "Mercado")

    for b in (b1, b2):
        assert [e.category_name for e in crud.get_plan_items(db_session, "expense", b.id)] == ["Mercado"]


def test_deleting_a_budget_deletes_its_items(db_session):
    budget = make_budget(db_session)
    crud.save_plan_item(db_session, "income", {"description": "A", "value": 100, "budget_id": budget.id})
    crud.save_plan_item(db_session, "expense", {
        "description": "B", "value": 10, "category_name": "Aluguel", "budget_id": budget.id})

    db_session.delete(budget)
    db_session.commit()

    assert db_session.query(IncomeItem).count() == 0
    assert db_session.query(PlannedExpense).count() == 0
