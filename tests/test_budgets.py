from datetime import date

import pytest

from app.budgets import (
    BudgetError,
    PeriodConflict,
    add_period,
    budget_for_month,
    covered_months,
    delete_period,
    format_period,
    update_period,
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


def period_budget(db, name):
    return create_budget(db, name)


def test_ranges_that_touch_do_not_overlap(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    add_period(db_session, a.id, (2026, 1), (2026, 10))
    add_period(db_session, b.id, (2026, 11))
    c, d = period_budget(db_session, "C"), period_budget(db_session, "D")
    add_period(db_session, c.id, (2020, 1), (2020, 12))
    add_period(db_session, d.id, (2021, 1), (2021, 6))
    assert db_session.query(BudgetPeriod).count() == 4


def test_overlap_with_another_budget_is_rejected(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    pa = add_period(db_session, a.id, (2024, 1), (2026, 10))
    with pytest.raises(PeriodConflict) as exc:
        add_period(db_session, b.id, (2026, 6), (2026, 12))
    assert "A" in str(exc.value)
    assert "outro orçamento" in str(exc.value)
    assert exc.value.conflicts == [pa]
    assert exc.value.closable is None
    assert db_session.query(BudgetPeriod).count() == 1


def test_overlap_inside_same_budget_is_rejected(db_session):
    a = period_budget(db_session, "A")
    add_period(db_session, a.id, (2024, 1), (2024, 12))
    with pytest.raises(PeriodConflict) as exc:
        add_period(db_session, a.id, (2024, 12), (2025, 3))
    assert "outro período deste orçamento" in str(exc.value)
    assert "outro orçamento" not in str(exc.value)


def test_open_range_is_offered_for_closing_and_closed_on_confirm(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    pa = add_period(db_session, a.id, (2024, 1))
    with pytest.raises(PeriodConflict) as exc:
        add_period(db_session, b.id, (2026, 11))
    assert exc.value.closable == pa
    pb = add_period(db_session, b.id, (2026, 11), close_conflict=True)
    assert (pb.end_year, pb.end_month) == (None, None)
    db_session.refresh(pa)
    assert (pa.end_year, pa.end_month) == (2026, 10)
    assert budget_for_month(db_session, 10, 2026).id == a.id
    assert budget_for_month(db_session, 11, 2026).id == b.id


def test_closing_across_a_year_boundary(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    pa = add_period(db_session, a.id, (2024, 1))
    add_period(db_session, b.id, (2027, 1), close_conflict=True)
    db_session.refresh(pa)
    assert (pa.end_year, pa.end_month) == (2026, 12)


def test_closing_not_offered_for_a_bounded_new_range(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    add_period(db_session, a.id, (2024, 1))
    with pytest.raises(PeriodConflict) as exc:
        add_period(db_session, b.id, (2026, 11), (2026, 12))
    assert exc.value.closable is None
    with pytest.raises(PeriodConflict):
        add_period(db_session, b.id, (2026, 11), (2026, 12), close_conflict=True)


def test_closing_not_offered_when_open_range_starts_at_or_after_new_start(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    add_period(db_session, a.id, (2026, 11))
    for start in ((2026, 11), (2026, 9)):
        with pytest.raises(PeriodConflict) as exc:
            add_period(db_session, b.id, start)
        assert exc.value.closable is None


def test_failed_add_leaves_everything_unchanged(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    pa = add_period(db_session, a.id, (2024, 1), (2026, 10))
    with pytest.raises(PeriodConflict):
        add_period(db_session, b.id, (2026, 6), close_conflict=True)
    assert db_session.query(BudgetPeriod).count() == 1
    db_session.refresh(pa)
    assert (pa.end_year, pa.end_month) == (2026, 10)


def test_update_period_ignores_itself(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    pa = add_period(db_session, a.id, (2024, 1), (2026, 10))
    add_period(db_session, b.id, (2026, 11))
    update_period(db_session, pa.id, (2024, 1), (2026, 10))
    update_period(db_session, pa.id, (2024, 1), (2026, 6))
    with pytest.raises(PeriodConflict) as exc:
        update_period(db_session, pa.id, (2024, 1), (2026, 12))
    assert exc.value.closable is None
    db_session.refresh(pa)
    assert (pa.end_year, pa.end_month) == (2026, 6)


def test_end_before_start_is_rejected(db_session):
    a = period_budget(db_session, "A")
    with pytest.raises(BudgetError):
        add_period(db_session, a.id, (2026, 5), (2026, 4))
    with pytest.raises(BudgetError):
        add_period(db_session, a.id, (2026, 13))
    assert db_session.query(BudgetPeriod).count() == 0


def test_delete_period(db_session):
    a = period_budget(db_session, "A")
    p = add_period(db_session, a.id, (2026, 1))
    assert delete_period(db_session, p.id) is True
    assert delete_period(db_session, p.id) is False


def test_budget_for_month_returns_none_outside_any_range(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    add_period(db_session, a.id, (2026, 1), (2026, 3))
    add_period(db_session, b.id, (2026, 6), (2026, 8))
    assert budget_for_month(db_session, 12, 2025) is None
    assert budget_for_month(db_session, 4, 2026) is None
    assert budget_for_month(db_session, 3, 2026).id == a.id
    assert budget_for_month(db_session, 6, 2026).id == b.id


def test_covered_months_newest_first_and_capped_at_today(db_session):
    a, b = period_budget(db_session, "A"), period_budget(db_session, "B")
    add_period(db_session, a.id, (2026, 11))
    add_period(db_session, b.id, (2025, 1), (2026, 6))
    db_session.refresh(a)
    db_session.refresh(b)
    assert covered_months(a, date(2027, 2, 10)) == [(2027, 2), (2027, 1), (2026, 12), (2026, 11)]
    assert covered_months(b, date(2025, 3, 1)) == [(2025, 3), (2025, 2), (2025, 1)]
    assert covered_months(b, date(2030, 1, 1))[0] == (2026, 6)


def test_format_period(db_session):
    a = period_budget(db_session, "A")
    p1 = add_period(db_session, a.id, (2024, 1), (2026, 10))
    p2 = add_period(db_session, a.id, (2026, 11))
    assert format_period(p1) == "Jan/2024 – Out/2026"
    assert format_period(p2) == "Nov/2026 →"


def test_budget_name_is_unique_at_database_level(db_session):
    from sqlalchemy.exc import IntegrityError

    from app.models import Budget

    db_session.add(Budget(name="Babá"))
    db_session.commit()
    db_session.add(Budget(name="Babá"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
