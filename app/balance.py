from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import crud
from app.models import DEFAULT_FAFA_RATIO


def build_month_balance(month: int, year: int, totals: dict, fafa_ratio: float) -> dict:
    fefe_ratio = 1.0 - fafa_ratio
    total = totals["variable_total"] + totals["regular_total"]
    fafa_should = total * fafa_ratio
    fefe_should = total * fefe_ratio

    # Positive: Fafa paid more than their share, so Fefe owes Fafa.
    balance = totals["fafa_paid"] - fafa_should

    return {
        "month": month,
        "year": year,
        "total_expenses": round(total, 2),
        "variable_total": round(totals["variable_total"], 2),
        "regular_total": round(totals["regular_total"], 2),
        "fafa_ratio": round(fafa_ratio, 4),
        "fefe_ratio": round(fefe_ratio, 4),
        "fafa_should_pay": round(fafa_should, 2),
        "fefe_should_pay": round(fefe_should, 2),
        "fafa_paid": round(totals["fafa_paid"], 2),
        "fefe_paid": round(totals["fefe_paid"], 2),
        "balance": round(balance, 2),
    }


def calculate_monthly_balance(db: Session, month: int, year: int) -> dict:
    totals = crud.get_month_totals(db, month, year)
    ratio = crud.get_month_ratio(db, month, year)
    return build_month_balance(month, year, totals, ratio.fafa_ratio)


def _previous(month: int, year: int) -> tuple[int, int]:
    return (12, year - 1) if month == 1 else (month - 1, year)


def _category_list(current: dict[str, float], previous: dict[str, float]) -> list[dict]:
    items = [
        {"name": name, "total": round(total, 2), "previous_total": round(previous.get(name, 0.0), 2)}
        for name, total in current.items()
    ]
    return sorted(items, key=lambda item: (-item["total"], item["name"]))


def build_month_detail(
    month: int,
    year: int,
    totals: dict,
    fafa_ratio: float,
    categories: dict,
    previous_totals: dict,
    previous_categories: dict,
) -> dict:
    """Balance of a single month plus its categories and the comparison with the previous month."""
    detail = build_month_balance(month, year, totals, fafa_ratio)
    previous_total = round(previous_totals["variable_total"] + previous_totals["regular_total"], 2)
    change = round(detail["total_expenses"] - previous_total, 2)

    detail.update(
        has_expenses=detail["total_expenses"] > 0,
        variable_categories=_category_list(categories["variable"], previous_categories["variable"]),
        regular_categories=_category_list(categories["regular"], previous_categories["regular"]),
        previous_total=previous_total,
        total_change=change,
        total_change_pct=round(change / previous_total * 100, 1) if previous_total else None,
    )
    return detail


def _empty_categories() -> dict:
    return {"variable": {}, "regular": {}}


def _last_month_to_show(year: int, today: date, months_with_data: set[int]) -> int:
    if year < today.year:
        return 12
    last = today.month if year == today.year else 0
    return max([last, *months_with_data])


def calculate_month_detail(db: Session, month: int, year: int) -> dict:
    prev_month, prev_year = _previous(month, year)
    return build_month_detail(
        month,
        year,
        crud.get_month_totals(db, month, year),
        crud.get_month_ratio(db, month, year).fafa_ratio,
        crud.get_monthly_category_totals(db, year, month).get(month, _empty_categories()),
        crud.get_month_totals(db, prev_month, prev_year),
        crud.get_monthly_category_totals(db, prev_year, prev_month).get(prev_month, _empty_categories()),
    )


def calculate_year_months(db: Session, year: int, today: Optional[date] = None) -> list[dict]:
    """One independent detail per month of the year (January first). Nothing is summed across months."""
    today = today or date.today()
    totals = crud.get_monthly_totals(db, year)
    categories = crud.get_monthly_category_totals(db, year)
    ratios = crud.get_year_ratios(db, year)

    last_month = _last_month_to_show(year, today, set(totals))
    if last_month == 0:
        return []

    december_totals = crud.get_month_totals(db, 12, year - 1)
    december_categories = crud.get_monthly_category_totals(db, year - 1, 12).get(12, _empty_categories())

    months = []
    for month in range(1, last_month + 1):
        if month == 1:
            previous_totals, previous_categories = december_totals, december_categories
        else:
            previous_totals = totals.get(month - 1, crud.empty_totals())
            previous_categories = categories.get(month - 1, _empty_categories())
        months.append(build_month_detail(
            month,
            year,
            totals.get(month, crud.empty_totals()),
            ratios.get(month, DEFAULT_FAFA_RATIO),
            categories.get(month, _empty_categories()),
            previous_totals,
            previous_categories,
        ))
    return months
