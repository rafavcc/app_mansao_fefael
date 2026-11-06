from sqlalchemy.orm import Session

from app import crud
from app.taxes import calculate_net_salary


def income_breakdown(item) -> dict:
    """Gross salaries lose INSS and IRRF; any other income counts as received."""
    if item.is_gross:
        return calculate_net_salary(item.value, item.dependents)
    return {"gross": round(item.value, 2), "taxes": 0.0, "net": round(item.value, 2)}


def calculate_plan(db: Session, month: int, year: int) -> dict:
    income = [income_breakdown(i) for i in crud.get_plan_items(db, "income")]
    expenses = crud.get_plan_items(db, "expense")
    savings = crud.get_plan_items(db, "savings")

    # Planning works with the money that actually arrives: net income.
    income_total = sum(i["net"] for i in income)
    expenses_total = sum(e.value for e in expenses)
    savings_total = sum(s.value for s in savings)
    free_balance = income_total - expenses_total - savings_total

    actual = crud.get_month_totals(db, month, year)
    actual_total = actual["variable_total"] + actual["regular_total"]

    def pct(value: float):
        return round(value / income_total * 100, 1) if income_total else None

    return {
        "gross_income_total": round(sum(i["gross"] for i in income), 2),
        "taxes_total": round(sum(i["taxes"] for i in income), 2),
        "income_total": round(income_total, 2),
        "expenses_total": round(expenses_total, 2),
        "savings_total": round(savings_total, 2),
        "free_balance": round(free_balance, 2),
        "free_balance_pct": pct(free_balance),
        "actual_total": round(actual_total, 2),
        # Positive: spending above what was planned.
        "actual_vs_planned": round(actual_total - expenses_total, 2),
    }
