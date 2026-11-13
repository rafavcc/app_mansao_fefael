import pytest

from app.budgets import (
    BudgetError,
    budget_counts,
    create_budget,
    delete_budget,
    list_budgets,
    rename_budget,
)
from app.models import BudgetPeriod, IncomeItem, PlannedExpense


def test_create_budget_strips_name(db_session):
    assert create_budget(db_session, "  Babá  ").name == "Babá"


def test_create_budget_rejects_blank_or_duplicate_name(db_session):
    create_budget(db_session, "Babá")
    for name in ("", "   ", "babá"):
        with pytest.raises(BudgetError):
            create_budget(db_session, name)
    assert [b.name for b in list_budgets(db_session)] == ["Babá"]


def test_duplicate_copies_items_but_not_periods(db_session):
    source = create_budget(db_session, "Base")
    db_session.add_all([
        IncomeItem(budget_id=source.id, description="Salário", value=5000.0, is_gross=True, dependents=2),
        PlannedExpense(budget_id=source.id, description="Aluguel", value=1500.0, category_name="Aluguel"),
        BudgetPeriod(budget_id=source.id, start_month=1, start_year=2027),
    ])
    db_session.commit()

    copy = create_budget(db_session, "Cópia", copy_from=source.id)

    def fields(item):
        return {c.name: getattr(item, c.name) for c in item.__table__.columns if c.name not in ("id", "budget_id")}

    assert copy.id != source.id
    assert [fields(i) for i in copy.income_items] == [fields(i) for i in source.income_items]
    assert [fields(i) for i in copy.expense_items] == [fields(i) for i in source.expense_items]
    assert len(copy.income_items) == 1 and copy.income_items[0].is_gross and copy.income_items[0].dependents == 2
    assert copy.income_items[0].budget_id == copy.id
    assert copy.periods == []
    assert len(source.income_items) == 1 and len(source.expense_items) == 1 and len(source.periods) == 1


def test_duplicate_from_missing_budget_fails(db_session):
    with pytest.raises(BudgetError):
        create_budget(db_session, "X", copy_from=999)


def test_rename_rejects_duplicate_but_allows_same_name_recased(db_session):
    a = create_budget(db_session, "A")
    create_budget(db_session, "B")
    assert rename_budget(db_session, a.id, "a").name == "a"
    with pytest.raises(BudgetError):
        rename_budget(db_session, a.id, "b")


def test_budget_counts_and_delete_cascade(db_session):
    budget = create_budget(db_session, "Base")
    db_session.add_all([
        IncomeItem(budget_id=budget.id, description="Salário", value=5000.0),
        PlannedExpense(budget_id=budget.id, description="Aluguel", value=1500.0, category_name="Aluguel"),
        PlannedExpense(budget_id=budget.id, description="Luz", value=200.0, category_name="Luz"),
        BudgetPeriod(budget_id=budget.id, start_month=1, start_year=2027),
    ])
    db_session.commit()
    budget_id = budget.id

    assert budget_counts(db_session, budget_id) == {"income": 1, "expenses": 2, "periods": 1}
    assert delete_budget(db_session, budget_id) is True
    assert db_session.query(IncomeItem).count() == 0
    assert db_session.query(PlannedExpense).count() == 0
    assert db_session.query(BudgetPeriod).count() == 0
    assert delete_budget(db_session, budget_id) is False
