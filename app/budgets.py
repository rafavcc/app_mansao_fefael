from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

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
