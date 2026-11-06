from datetime import date

import pytest

from app import crud
from app.balance import build_month_balance, calculate_month_detail, calculate_year_months


def totals(variable=0.0, regular=0.0, fafa=0.0, fefe=0.0):
    return {"variable_total": variable, "regular_total": regular, "fafa_paid": fafa, "fefe_paid": fefe}


def test_balance_positive_means_fefe_owes_fafa():
    result = build_month_balance(10, 2026, totals(300, 0, fafa=300), 2 / 3)
    assert result["fafa_should_pay"] == 200
    assert result["fefe_should_pay"] == 100
    assert result["balance"] == 100


def test_balance_negative_means_fafa_owes_fefe():
    assert build_month_balance(10, 2026, totals(300, 0, fefe=300), 0.5)["balance"] == -150


def test_balance_with_no_expenses_is_zero():
    result = build_month_balance(1, 2026, totals(), 2 / 3)
    assert result["total_expenses"] == 0 and result["balance"] == 0


@pytest.mark.parametrize("ratio", [0, 1])
def test_extreme_ratios(ratio):
    result = build_month_balance(1, 2026, totals(100, 0, fafa=100), ratio)
    assert result["fafa_should_pay"] + result["fefe_should_pay"] == 100


def test_month_detail_compares_with_previous_month(db_session):
    for month, value in ((9, 100), (10, 150)):
        crud.create_variable_expense(db_session, dict(
            place="x", day=1, month=month, year=2026, value=value,
            paid_by="FAFA", category_name="Mercado"))

    detail = calculate_month_detail(db_session, 10, 2026)

    assert detail["previous_total"] == 100
    assert detail["total_change"] == 50
    assert detail["total_change_pct"] == 50.0
    assert detail["variable_categories"] == [{"name": "Mercado", "total": 150, "previous_total": 100}]


def test_month_detail_change_pct_is_none_without_previous_data(db_session):
    assert calculate_month_detail(db_session, 10, 2026)["total_change_pct"] is None


def test_january_compares_with_previous_december(db_session):
    crud.create_variable_expense(db_session, dict(
        place="x", day=1, month=12, year=2025, value=40, paid_by="FAFA", category_name="Mercado"))
    assert calculate_month_detail(db_session, 1, 2026)["previous_total"] == 40


def test_year_months_limits_current_year_to_today(db_session):
    months = calculate_year_months(db_session, 2026, today=date(2026, 3, 10))
    assert [m["month"] for m in months] == [1, 2, 3]


def test_year_months_past_year_has_twelve_and_future_year_is_empty(db_session):
    assert len(calculate_year_months(db_session, 2025, today=date(2026, 3, 10))) == 12
    assert calculate_year_months(db_session, 2027, today=date(2026, 3, 10)) == []


def test_year_months_uses_saved_ratio(db_session):
    crud.set_month_ratio(db_session, 2, 2026, 0.5)
    months = calculate_year_months(db_session, 2026, today=date(2026, 2, 1))
    assert months[1]["fafa_ratio"] == 0.5
    assert months[0]["fafa_ratio"] == round(2 / 3, 4)
