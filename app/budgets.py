from datetime import date
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.formatting import month_name
from app.models import Budget, BudgetPeriod, IncomeItem, PlannedExpense


class BudgetError(ValueError):
    """A budget operation was refused; the message is meant for the user."""


def list_budgets(db: Session) -> List[Budget]:
    return db.query(Budget).order_by(func.lower(Budget.name), Budget.id).all()


def _clean_name(db: Session, name: str, ignore_id: Optional[int] = None) -> str:
    name = (name or "").strip()
    if not name:
        raise BudgetError("Informe um nome para o orçamento.")
    for other in db.query(Budget).all():
        if other.id != ignore_id and other.name.casefold() == name.casefold():
            raise BudgetError("Já existe um orçamento com esse nome.")
    return name


def _copy_row(item, **overrides):
    """New instance of the same model with every column copied except id and budget_id."""
    values = {
        c.key: getattr(item, c.key)
        for c in type(item).__table__.columns
        if c.key not in ("id", "budget_id")
    }
    values.update(overrides)
    return type(item)(**values)


def create_budget(db: Session, name: str, copy_from: Optional[int] = None) -> Budget:
    """Create a budget; with `copy_from`, also copy that budget's income and expense items (not periods)."""
    name = _clean_name(db, name)
    source = None
    if copy_from is not None:
        source = db.get(Budget, copy_from)
        if source is None:
            raise BudgetError("Orçamento de origem não encontrado.")
    try:
        budget = Budget(name=name)
        db.add(budget)
        if source is not None:
            budget.income_items = [_copy_row(i) for i in source.income_items]
            budget.expense_items = [_copy_row(e) for e in source.expense_items]
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(budget)
    return budget


def rename_budget(db: Session, budget_id: int, name: str) -> Budget:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise BudgetError("Orçamento não encontrado.")
    budget.name = _clean_name(db, name, ignore_id=budget_id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(budget)
    return budget


def budget_counts(db: Session, budget_id: int) -> dict:
    return {
        "income": db.query(IncomeItem).filter(IncomeItem.budget_id == budget_id).count(),
        "expenses": db.query(PlannedExpense).filter(PlannedExpense.budget_id == budget_id).count(),
        "periods": db.query(BudgetPeriod).filter(BudgetPeriod.budget_id == budget_id).count(),
    }


def delete_budget(db: Session, budget_id: int) -> bool:
    """Delete a budget with its items and periods. Returns False when it does not exist."""
    budget = db.get(Budget, budget_id)
    if budget is None:
        return False
    try:
        db.delete(budget)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


YearMonth = tuple  # (year, month)

_FAR_FUTURE = (9999, 12)


class PeriodConflict(BudgetError):
    """A month range overlaps existing ones. `closable` is the open-ended period
    that can be closed to make room, when the closing rule allows it."""

    def __init__(self, message: str, conflicts: List[BudgetPeriod], closable: Optional[BudgetPeriod] = None):
        super().__init__(message)
        self.conflicts = conflicts
        self.closable = closable


def _start(p: BudgetPeriod) -> YearMonth:
    return (p.start_year, p.start_month)


def _end(p: BudgetPeriod) -> Optional[YearMonth]:
    return None if p.end_year is None else (p.end_year, p.end_month)


def format_period(period: BudgetPeriod) -> str:
    start = f"{month_name(period.start_month, short=True)}/{period.start_year}"
    if period.end_year is None:
        return f"{start} →"
    return f"{start} – {month_name(period.end_month, short=True)}/{period.end_year}"


def _valid_month(value) -> bool:
    return (
        isinstance(value, tuple) and len(value) == 2
        and all(isinstance(v, int) for v in value) and 1 <= value[1] <= 12
    )


def _check_range(start: YearMonth, end: Optional[YearMonth]) -> None:
    if not _valid_month(start) or (end is not None and not _valid_month(end)):
        raise BudgetError("Mês inválido.")
    if end is not None and end < start:
        raise BudgetError("O mês final não pode ser anterior ao mês inicial.")


def _save_period(db, period, budget_id, start, end, close_conflict, ignore_id=None):
    _check_range(start, end)
    eff_end = end if end is not None else _FAR_FUTURE
    others = (
        db.query(BudgetPeriod).options(joinedload(BudgetPeriod.budget))
        .filter(BudgetPeriod.id != (ignore_id or 0)).all()
    )
    conflicts = [
        o for o in others
        if _start(o) <= eff_end and start <= (_end(o) or _FAR_FUTURE)
    ]
    closable = None
    if (
        end is None and len(conflicts) == 1
        and _end(conflicts[0]) is None and _start(conflicts[0]) < start
    ):
        closable = conflicts[0]
    if conflicts and not (close_conflict and closable is not None):
        names = "; ".join(f"{c.budget.name} ({format_period(c)})" for c in conflicts)
        raise PeriodConflict(
            f"Esse período se sobrepõe a outro orçamento: {names}.", conflicts, closable
        )
    try:
        if conflicts:
            year, month = start
            closable.end_year, closable.end_month = (year - 1, 12) if month == 1 else (year, month - 1)
        if period is None:
            period = BudgetPeriod(budget_id=budget_id)
            db.add(period)
        period.start_year, period.start_month = start
        period.end_year, period.end_month = end if end is not None else (None, None)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(period)
    return period


def add_period(db: Session, budget_id: int, start: YearMonth, end: Optional[YearMonth] = None,
               close_conflict: bool = False) -> BudgetPeriod:
    if db.get(Budget, budget_id) is None:
        raise BudgetError("Orçamento não encontrado.")
    return _save_period(db, None, budget_id, start, end, close_conflict)


def update_period(db: Session, period_id: int, start: YearMonth, end: Optional[YearMonth] = None,
                  close_conflict: bool = False) -> BudgetPeriod:
    period = db.get(BudgetPeriod, period_id)
    if period is None:
        raise BudgetError("Período não encontrado.")
    return _save_period(db, period, period.budget_id, start, end, close_conflict, ignore_id=period_id)


def delete_period(db: Session, period_id: int) -> bool:
    period = db.get(BudgetPeriod, period_id)
    if period is None:
        return False
    try:
        db.delete(period)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def budget_for_month(db: Session, month: int, year: int) -> Optional[Budget]:
    target = (year, month)
    for p in db.query(BudgetPeriod).options(joinedload(BudgetPeriod.budget)).all():
        if _start(p) <= target <= (_end(p) or _FAR_FUTURE):
            return p.budget
    return None


def covered_months(budget: Budget, today: date) -> List[YearMonth]:
    """Every month of the budget's periods up to and including today's month, newest first."""
    cap = (today.year, today.month)
    months = set()
    for p in budget.periods:
        year, month = _start(p)
        last = min(_end(p) or cap, cap)
        while (year, month) <= last:
            months.add((year, month))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return sorted(months, reverse=True)
