from datetime import date, datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Date, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

FAFA = "FAFA"
FEFE = "FEFE"
PAYERS = (FAFA, FEFE)
DEFAULT_FAFA_RATIO = 2 / 3


class User(Base):
    __tablename__ = "users"

    name = Column(String, primary_key=True)
    full_name = Column(String, nullable=True)

    variable_expenses = relationship("VariableExpense", back_populates="payer")
    regular_expenses = relationship("RegularExpense", back_populates="payer")


class VariableCategory(Base):
    __tablename__ = "variable_categories"

    name = Column(String, primary_key=True)
    expenses = relationship("VariableExpense", back_populates="category")


class RegularCategory(Base):
    __tablename__ = "regular_categories"

    name = Column(String, primary_key=True)
    expenses = relationship("RegularExpense", back_populates="category")


class MonthRatio(Base):
    __tablename__ = "month_ratios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    fafa_ratio = Column(Float, nullable=False, default=DEFAULT_FAFA_RATIO)

    @property
    def fefe_ratio(self) -> float:
        return 1.0 - self.fafa_ratio

    __table_args__ = (
        UniqueConstraint("month", "year", name="uq_month_ratio"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_ratio_month"),
        CheckConstraint("fafa_ratio >= 0 AND fafa_ratio <= 1", name="ck_ratio_range"),
    )


class VariableExpense(Base):
    __tablename__ = "variable_expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    place = Column(String, nullable=False)
    day = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    value = Column(Float, nullable=False)
    paid_by = Column(String, ForeignKey("users.name"), nullable=False)
    category_name = Column(String, ForeignKey("variable_categories.name"), nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    payer = relationship("User", back_populates="variable_expenses")
    category = relationship("VariableCategory", back_populates="expenses")

    __table_args__ = (
        CheckConstraint("day >= 1 AND day <= 31", name="ck_var_day"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_var_month"),
        CheckConstraint("value > 0", name="ck_var_value"),
    )


class RegularExpense(Base):
    __tablename__ = "regular_expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    value = Column(Float, nullable=False)
    paid_by = Column(String, ForeignKey("users.name"), nullable=False)
    category_name = Column(String, ForeignKey("regular_categories.name"), nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    payer = relationship("User", back_populates="regular_expenses")
    category = relationship("RegularCategory", back_populates="expenses")

    __table_args__ = (
        CheckConstraint("day >= 1 AND day <= 31", name="ck_reg_day"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_reg_month"),
        CheckConstraint("value > 0", name="ck_reg_value"),
        UniqueConstraint("month", "year", "category_name", name="uq_reg_per_month"),
    )

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    periods = relationship("BudgetPeriod", back_populates="budget", cascade="all, delete-orphan")
    income_items = relationship("IncomeItem", cascade="all, delete-orphan")
    expense_items = relationship("PlannedExpense", cascade="all, delete-orphan")


class BudgetPeriod(Base):
    __tablename__ = "budget_periods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False)
    start_month = Column(Integer, nullable=False)
    start_year = Column(Integer, nullable=False)
    # Both NULL means the period is open-ended.
    end_month = Column(Integer)
    end_year = Column(Integer)

    budget = relationship("Budget", back_populates="periods")

    __table_args__ = (
        CheckConstraint("start_month >= 1 AND start_month <= 12", name="ck_period_start_month"),
        CheckConstraint("end_month IS NULL OR (end_month >= 1 AND end_month <= 12)", name="ck_period_end_month"),
        CheckConstraint("(end_month IS NULL) = (end_year IS NULL)", name="ck_period_end_both"),
        CheckConstraint(
            "end_year IS NULL OR end_year * 12 + end_month >= start_year * 12 + start_month",
            name="ck_period_order",
        ),
    )


class IncomeItem(Base):
    __tablename__ = "income_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False)
    description = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    # Gross salaries get INSS and IRRF deducted; other income (e.g. meal vouchers) is net.
    is_gross = Column(Boolean, nullable=False, default=False, server_default="0")
    dependents = Column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        CheckConstraint("value > 0", name="ck_income_value"),
        CheckConstraint("dependents >= 0", name="ck_income_dependents"),
    )


class PlannedExpense(Base):
    __tablename__ = "planned_expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False)
    description = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    # Name from the union of regular and variable categories, so it is not a foreign key.
    category_name = Column(String, nullable=False)

    __table_args__ = (CheckConstraint("value > 0", name="ck_planned_value"),)


class Payment(Base):
    """Money Fefe transfers to Fafa; reduces the accumulated debt, even in advance."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paid_on = Column(Date, nullable=False, default=date.today)
    value = Column(Float, nullable=False)
    method = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    __table_args__ = (CheckConstraint("value > 0", name="ck_payment_value"),)
