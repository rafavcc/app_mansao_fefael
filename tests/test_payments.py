from datetime import date

import pytest

from app import crud
from app.payments import calculate_payments, closed_months

FIRST = (2026, 7)


def expense(db, month, value, payer="FAFA", year=2026):
    crud.create_variable_expense(db, dict(
        place="x", day=1, month=month, year=year, value=value, paid_by=payer, category_name="Mercado"))


def pay(db, value, day=date(2026, 11, 5)):
    crud.save_payment(db, {"paid_on": day, "value": value, "method": "Pix"})


def calc(db, today=date(2026, 10, 2)):
    return calculate_payments(db, today=today, first=FIRST)


def test_closed_months_exclude_current_and_start_at_first():
    assert closed_months(date(2026, 10, 2), FIRST) == [(2026, 7), (2026, 8), (2026, 9)]
    assert closed_months(date(2026, 7, 31), FIRST) == []
    assert closed_months(date(2027, 2, 1), FIRST)[-2:] == [(2026, 12), (2027, 1)]


def test_month_becomes_debt_only_after_it_ends(db_session):
    expense(db_session, 7, 300)  # Fafa paid all; Fefe owes 1/3
    assert calc(db_session, today=date(2026, 7, 31))["debt"] == 0
    assert calc(db_session, today=date(2026, 8, 1))["debt"] == 100


def test_debts_of_unpaid_months_accumulate(db_session):
    expense(db_session, 7, 300)
    expense(db_session, 8, 600)
    summary = calc(db_session)
    assert summary["debt"] == 300
    assert summary["open_months"] == 2
    assert [m["status"] for m in summary["months"]] == ["open", "open", "settled"]


def test_fefe_direct_payments_reduce_what_she_owes(db_session):
    expense(db_session, 7, 300, payer="FAFA")
    expense(db_session, 7, 90, payer="FEFE")
    # total 390: Fefe share 130, she paid 90 directly -> owes 40
    assert calc(db_session)["months"][0]["owed"] == 40


def test_payments_apply_to_oldest_month_first_and_show_partial(db_session):
    expense(db_session, 7, 300)
    expense(db_session, 8, 300)
    pay(db_session, 150)
    months = calc(db_session)["months"]
    assert (months[0]["status"], months[0]["remaining"]) == ("paid", 0)
    assert (months[1]["status"], months[1]["covered"], months[1]["remaining"]) == ("partial", 50, 50)
    assert calc(db_session)["debt"] == 50


def test_advance_payment_leaves_credit_that_covers_future_months(db_session):
    pay(db_session, 3000)
    assert calc(db_session)["debt"] == -3000
    expense(db_session, 7, 300)
    expense(db_session, 8, 300)
    summary = calc(db_session)
    assert summary["debt"] == -2800
    assert all(m["remaining"] == 0 for m in summary["months"])


def test_three_month_cycle_evens_out(db_session):
    pay(db_session, 300)
    for month in (7, 8, 9):
        expense(db_session, month, 300)  # each month Fefe owes 100
    assert calc(db_session, today=date(2026, 10, 1))["debt"] == 0


def test_month_where_fafa_owes_fefe_reduces_total_debt(db_session):
    expense(db_session, 7, 300)
    expense(db_session, 8, 300, payer="FEFE")  # Fefe overpaid by 100
    summary = calc(db_session)
    assert summary["months"][1]["status"] == "credit"
    assert summary["debt"] == pytest.approx(100 - 200)
    assert all(m["remaining"] == 0 for m in summary["months"])


def test_uses_saved_month_ratio(db_session):
    crud.set_month_ratio(db_session, 7, 2026, 0.5)
    expense(db_session, 7, 300)
    assert calc(db_session)["debt"] == 150


def test_months_before_first_billed_are_ignored(db_session):
    expense(db_session, 6, 900)
    assert calc(db_session)["debt"] == 0


def test_payment_crud(db_session):
    payment = crud.save_payment(db_session, {"paid_on": date(2026, 11, 1), "value": 10})
    crud.save_payment(db_session, {"value": 20, "notes": "n"}, payment.id)
    assert crud.get_payments(db_session)[0].value == 20
    assert crud.save_payment(db_session, {"value": 1}, 999) is None
    assert crud.delete_payment(db_session, payment.id)
    assert not crud.delete_payment(db_session, payment.id)


def test_payment_must_be_positive(db_session):
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        crud.save_payment(db_session, {"paid_on": date(2026, 11, 1), "value": 0})
