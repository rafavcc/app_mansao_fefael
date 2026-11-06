from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import crud
from app.balance import build_month_balance

# Months before this one are already settled and never count as debt.
FIRST_BILLED_MONTH = (2026, 7)


def closed_months(today: date, first: tuple[int, int] = FIRST_BILLED_MONTH) -> list[tuple[int, int]]:
    """Months from the first billed one up to the last that has already ended."""
    months = []
    year, month = first
    while (year, month) < (today.year, today.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def calculate_payments(db: Session, today: Optional[date] = None, first: tuple[int, int] = FIRST_BILLED_MONTH) -> dict:
    """Debt of Fefe to Fafa. A closed month's saldo is Fefe's share minus what Fefe paid directly.

    Positive saldo = Fefe owes Fafa; negative = Fafa owes Fefe and reduces the debt.
    Payments (advance ones too) are applied to the oldest owed months first;
    an excess stays as credit that reduces the next months.
    """
    today = today or date.today()
    payments = crud.get_payments(db)
    paid_total = round(sum(p.value for p in payments), 2)

    months = []
    for year, month in closed_months(today, first):
        totals = crud.get_month_totals(db, month, year)
        ratio = crud.get_month_ratio(db, month, year).fafa_ratio
        saldo = build_month_balance(month, year, totals, ratio)["balance"]
        months.append({"month": month, "year": year, "owed": round(saldo, 2)})

    # Months where Fafa owes Fefe also feed the pool that covers older debts.
    pool = paid_total + sum(-m["owed"] for m in months if m["owed"] < 0)
    for m in months:
        if m["owed"] <= 0:
            m.update(covered=0.0, remaining=0.0, status="credit" if m["owed"] < 0 else "settled")
            continue
        covered = round(min(pool, m["owed"]), 2)
        pool = round(pool - covered, 2)
        remaining = round(m["owed"] - covered, 2)
        m.update(
            covered=covered,
            remaining=remaining,
            status="paid" if remaining == 0 else "partial" if covered > 0 else "open",
        )

    billed_total = round(sum(m["owed"] for m in months), 2)
    return {
        "months": months,
        "billed_total": billed_total,
        "paid_total": paid_total,
        # Positive: Fefe still owes. Negative: Fefe is ahead (credit).
        "debt": round(billed_total - paid_total, 2),
        "open_months": sum(1 for m in months if m["remaining"] > 0),
    }
