"""Expenses cannot be dated in the future: variable up to today, regular up to the current month."""
from datetime import date, timedelta

from app.dates import is_future_date, is_future_month

TODAY = date(2026, 11, 10)


def test_variable_limit_is_today():
    assert not is_future_date(2026, 11, 10, TODAY)
    assert not is_future_date(2026, 11, 9, TODAY)
    assert is_future_date(2026, 11, 11, TODAY)
    assert is_future_date(2027, 1, 1, TODAY)


def test_regular_limit_is_current_month():
    assert not is_future_month(2026, 11, TODAY)
    assert not is_future_month(2026, 1, TODAY)
    assert not is_future_month(2025, 12, TODAY)
    assert is_future_month(2026, 12, TODAY)
    assert is_future_month(2027, 1, TODAY)


def _variable(day: date) -> dict:
    return {"place": "Mercado", "day": day.day, "month": day.month, "year": day.year,
            "value": 10.0, "paid_by": "FAFA", "category_name": "Comida"}


def test_api_accepts_today_and_rejects_tomorrow(client):
    today = date.today()
    assert client.post("/api/variable-expense/", json=_variable(today)).status_code == 200
    tomorrow = today + timedelta(days=1)
    assert client.post("/api/variable-expense/", json=_variable(tomorrow)).status_code == 422


def test_api_regular_accepts_current_month_and_rejects_next(client):
    today = date.today()
    current = {"day": 5, "month": today.month, "year": today.year, "value": 100.0,
               "paid_by": "FAFA", "category_name": "Aluguel"}
    assert client.post("/api/regular-expense/", json=current).status_code == 200
    next_year, next_month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    future = {**current, "month": next_month, "year": next_year}
    assert client.post("/api/regular-expense/", json=future).status_code == 422


def test_api_update_cannot_move_expense_to_the_future(client):
    today = date.today()
    created = client.post("/api/variable-expense/", json=_variable(today)).json()
    future = _variable(today + timedelta(days=1))
    assert client.put(f"/api/variable-expenses/{created['id']}", json=future).status_code == 422
