from datetime import date
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    FAFA,
    FEFE,
    DEFAULT_FAFA_RATIO,
    IncomeItem,
    MonthRatio,
    Payment,
    PlannedExpense,
    RegularCategory,
    RegularExpense,
    SavingsItem,
    User,
    VariableCategory,
    VariableExpense,
)


def get_users(db: Session) -> List[User]:
    return db.query(User).all()


def create_user(db: Session, name: str, full_name=None) -> User:
    user = User(name=name, full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_variable_categories(db: Session) -> List[VariableCategory]:
    return db.query(VariableCategory).all()


def create_variable_category(db: Session, name: str) -> VariableCategory:
    cat = VariableCategory(name=name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def get_regular_categories(db: Session) -> List[RegularCategory]:
    return db.query(RegularCategory).all()


def create_regular_category(db: Session, name: str) -> RegularCategory:
    cat = RegularCategory(name=name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def create_variable_expense(db: Session, data: dict) -> VariableExpense:
    expense = VariableExpense(**data)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def get_variable_expenses(
    db: Session,
    month: Optional[int] = None,
    year: Optional[int] = None,
    category: Optional[str] = None,
) -> List[VariableExpense]:
    q = db.query(VariableExpense)
    if month:
        q = q.filter(VariableExpense.month == month)
    if year:
        q = q.filter(VariableExpense.year == year)
    if category:
        q = q.filter(VariableExpense.category_name == category)
    return q.order_by(
        VariableExpense.year.desc(),
        VariableExpense.month.desc(),
        VariableExpense.day.desc(),
        VariableExpense.id.desc(),
    ).all()


def _update(db: Session, model, expense_id: int, data: dict):
    expense = db.get(model, expense_id)
    if expense is None:
        return None
    for key, value in data.items():
        setattr(expense, key, value)
    db.commit()
    db.refresh(expense)
    return expense


def update_variable_expense(
    db: Session, expense_id: int, data: dict
) -> Optional[VariableExpense]:
    return _update(db, VariableExpense, expense_id, data)


def update_regular_expense(
    db: Session, expense_id: int, data: dict
) -> Optional[RegularExpense]:
    return _update(db, RegularExpense, expense_id, data)


def get_top_places(db: Session, limit: int = 5) -> List[str]:
    rows = (
        db.query(VariableExpense.place, func.count(VariableExpense.id).label("uses"))
        .group_by(VariableExpense.place)
        .order_by(func.count(VariableExpense.id).desc(), VariableExpense.place)
        .limit(limit)
        .all()
    )
    return [row.place for row in rows]


def get_available_years(db: Session) -> List[int]:
    years = set()
    for model in (VariableExpense, RegularExpense):
        years.update(y for (y,) in db.query(model.year).distinct())
    return sorted(years)


def delete_variable_expense(db: Session, expense_id: int) -> bool:
    expense = (
        db.query(VariableExpense)
        .filter(VariableExpense.id == expense_id)
        .first()
    )
    if expense:
        db.delete(expense)
        db.commit()
        return True
    return False


def create_regular_expense(db: Session, data: dict) -> RegularExpense:
    expense = RegularExpense(**data)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def get_regular_expenses(
    db: Session,
    month: Optional[int] = None,
    year: Optional[int] = None,
    category: Optional[str] = None,
) -> List[RegularExpense]:
    q = db.query(RegularExpense)
    if month:
        q = q.filter(RegularExpense.month == month)
    if year:
        q = q.filter(RegularExpense.year == year)
    if category:
        q = q.filter(RegularExpense.category_name == category)
    return q.order_by(RegularExpense.created_at.desc()).all()


def upsert_regular_expense(db: Session, data: dict) -> RegularExpense:
    """Create or update a regular expense for a given month/year/category.

    "Upsert" = UPDATE if exists, INSERT if not.
    Because regular expenses have a unique constraint on (month, year, category_name),
    inserting twice for the same category+month would crash without this logic.
    """
    existing = (
        db.query(RegularExpense)
        .filter(
            RegularExpense.month == data["month"],
            RegularExpense.year == data["year"],
            RegularExpense.category_name == data["category_name"],
        )
        .first()
    )

    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        return create_regular_expense(db, data)


def autofill_current_month_regular_expenses(
    db: Session,
    today: Optional[date] = None,
) -> int:
    """Copy last month's regular expenses into the current month when missing.

    Existing current-month rows with value > 0 are treated as manually filled
    and are never changed. The copy is done per category, so one filled category
    does not prevent another empty category from being copied.
    """
    today = today or date.today()
    current_month = today.month
    current_year = today.year

    if current_month == 1:
        previous_month = 12
        previous_year = current_year - 1
    else:
        previous_month = current_month - 1
        previous_year = current_year

    previous_expenses = (
        db.query(RegularExpense)
        .filter(
            RegularExpense.month == previous_month,
            RegularExpense.year == previous_year,
            RegularExpense.value > 0,
        )
        .all()
    )

    if not previous_expenses:
        return 0

    current_by_category = {
        expense.category_name: expense
        for expense in db.query(RegularExpense)
        .filter(
            RegularExpense.month == current_month,
            RegularExpense.year == current_year,
        )
        .all()
    }

    copied = 0
    for previous in previous_expenses:
        current = current_by_category.get(previous.category_name)
        if current and current.value > 0:
            continue

        data = {
            "day": previous.day,
            "month": current_month,
            "year": current_year,
            "value": previous.value,
            "paid_by": FAFA,
            "category_name": previous.category_name,
            "notes": previous.notes,
        }
        if current:
            for key, value in data.items():
                setattr(current, key, value)
            db.commit()
            copied += 1
        else:
            db.add(RegularExpense(**data))
            copied += 1

    if copied:
        db.commit()

    return copied


def delete_regular_expense(db: Session, expense_id: int) -> bool:
    expense = (
        db.query(RegularExpense)
        .filter(RegularExpense.id == expense_id)
        .first()
    )
    if expense:
        db.delete(expense)
        db.commit()
        return True
    return False


def get_month_ratio(db: Session, month: int, year: int) -> MonthRatio:
    ratio = (
        db.query(MonthRatio)
        .filter(MonthRatio.month == month, MonthRatio.year == year)
        .first()
    )
    if ratio:
        return ratio
    return MonthRatio(month=month, year=year, fafa_ratio=DEFAULT_FAFA_RATIO)


def get_year_ratios(db: Session, year: int) -> dict[int, float]:
    """Explicitly saved Fafa ratios for the year, keyed by month."""
    rows = db.query(MonthRatio).filter(MonthRatio.year == year).all()
    return {r.month: r.fafa_ratio for r in rows}


def set_month_ratio(
    db: Session, month: int, year: int, fafa: float
) -> MonthRatio:
    existing = (
        db.query(MonthRatio)
        .filter(
            MonthRatio.month == month,
            MonthRatio.year == year,
        )
        .first()
    )

    if existing:
        existing.fafa_ratio = fafa
    else:
        existing = MonthRatio(month=month, year=year, fafa_ratio=fafa)
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


def empty_totals() -> dict:
    return {
        "variable_total": 0.0,
        "regular_total": 0.0,
        "fafa_paid": 0.0,
        "fefe_paid": 0.0,
    }


def get_monthly_totals(
    db: Session, year: int, month: Optional[int] = None
) -> dict[int, dict]:
    """Totals per month (only months with expenses), keyed by month."""
    result: dict[int, dict] = {}
    for model, key in (
        (VariableExpense, "variable_total"),
        (RegularExpense, "regular_total"),
    ):
        q = db.query(
            model.month, model.paid_by, func.sum(model.value)
        ).filter(model.year == year)
        if month is not None:
            q = q.filter(model.month == month)
        for m, payer, total in q.group_by(model.month, model.paid_by):
            totals = result.setdefault(m, empty_totals())
            totals[key] += float(total)
            if payer == FAFA:
                totals["fafa_paid"] += float(total)
            elif payer == FEFE:
                totals["fefe_paid"] += float(total)
    return result


def get_month_totals(db: Session, month: int, year: int) -> dict:
    return get_monthly_totals(db, year, month).get(month, empty_totals())


def get_monthly_category_totals(
    db: Session, year: int, month: Optional[int] = None
) -> dict[int, dict]:
    """{"month": {"variable": {category: total}, "regular": {category: total}}}"""
    result: dict[int, dict] = {}
    for model, kind in (
        (VariableExpense, "variable"),
        (RegularExpense, "regular"),
    ):
        q = db.query(
            model.month, model.category_name, func.sum(model.value)
        ).filter(model.year == year)
        if month is not None:
            q = q.filter(model.month == month)
        for m, category, total in q.group_by(
            model.month, model.category_name
        ):
            result.setdefault(m, {"variable": {}, "regular": {}})[kind][
                category
            ] = float(total)
    return result

# --- Household plan (single recurring plan, no month)

PLAN_MODELS = {
    "income": IncomeItem,
    "expense": PlannedExpense,
    "savings": SavingsItem,
}


def get_plan_items(db: Session, kind: str) -> list:
    model = PLAN_MODELS[kind]
    return db.query(model).order_by(model.id).all()


def save_plan_item(db: Session, kind: str, data: dict, item_id: Optional[int] = None):
    model = PLAN_MODELS[kind]
    if item_id is None:
        item = model(**data)
        db.add(item)
    else:
        item = db.get(model, item_id)
        if item is None:
            return None
        for key, value in data.items():
            setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_plan_item(db: Session, kind: str, item_id: int) -> bool:
    item = db.get(PLAN_MODELS[kind], item_id)
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True


def get_planning_categories(db: Session) -> List[str]:
    """Union of regular and variable category names, without duplicates."""
    names = {c.name for c in get_regular_categories(db)}
    names |= {c.name for c in get_variable_categories(db)}
    return sorted(names, key=str.casefold)


# --- Payments (Fefe -> Fafa)

def get_payments(db: Session) -> List[Payment]:
    return db.query(Payment).order_by(Payment.paid_on.desc(), Payment.id.desc()).all()


def save_payment(db: Session, data: dict, payment_id: Optional[int] = None) -> Optional[Payment]:
    if payment_id is None:
        payment = Payment(**data)
        db.add(payment)
    else:
        payment = db.get(Payment, payment_id)
        if payment is None:
            return None
        for key, value in data.items():
            setattr(payment, key, value)
    db.commit()
    db.refresh(payment)
    return payment


def delete_payment(db: Session, payment_id: int) -> bool:
    payment = db.get(Payment, payment_id)
    if payment is None:
        return False
    db.delete(payment)
    db.commit()
    return True
