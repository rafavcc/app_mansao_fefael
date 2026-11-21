import calendar
import math
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from typing import Optional
from datetime import date, datetime

from app.dates import is_future_date, is_future_month
from app.models import PAYERS


class ExpenseDate(BaseModel):
    @field_validator("notes", check_fields=False)
    @classmethod
    def _strip_notes(cls, value):
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def _check_day_exists(self):
        last_day = calendar.monthrange(self.year, self.month)[1]
        if self.day > last_day:
            raise ValueError(f"Day {self.day} does not exist in {self.month}/{self.year}")
        return self


class VariableExpenseCreate(ExpenseDate):
    place: str = Field(..., min_length=1, max_length=300)
    day: int = Field(..., ge=1, le=31)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(default_factory=lambda: datetime.now().year)
    value: float = Field(..., gt=0)
    paid_by: str = Field(..., pattern="^(FAFA|FEFE)$")
    category_name: str = Field(..., min_length=1)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _not_in_future(self):
        if is_future_date(self.year, self.month, self.day):
            raise ValueError("Variable expenses cannot be dated in the future")
        return self


def variable_expense_problem(data: dict) -> Optional[str]:
    """First problem found in variable expense data (as a Portuguese message), or None."""
    if not (data.get("place") or "").strip():
        return "Preencha o local."
    try:
        when = date(data["year"], data["month"], data["day"])
    except (KeyError, TypeError, ValueError):
        return "Data inválida."
    if is_future_date(when.year, when.month, when.day):
        return "A data não pode estar no futuro."
    value = data.get("value")
    try:
        valid_value = value is not None and math.isfinite(value) and value > 0
    except (OverflowError, TypeError):
        valid_value = False
    if not valid_value:
        return "Valor deve ser maior que zero."
    if not data.get("category_name"):
        return "Selecione um grupo."
    if data.get("paid_by") not in PAYERS:
        return "Selecione quem pagou."
    try:
        VariableExpenseCreate(**data)
    except ValidationError:
        return "Dados inválidos."
    return None


class DraftExpense(BaseModel):
    """A expense read from a photo, still editable and not yet saved."""
    place: str = ""
    day: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None
    value: Optional[float] = None
    paid_by: str
    category_name: Optional[str] = None
    notes: Optional[str] = None
    error: Optional[str] = None
    possible_duplicate: bool = False
    duplicate_reason: Optional[str] = None
    selected: bool = True

    def expense_data(self) -> dict:
        """The VariableExpenseCreate fields of this draft."""
        return {
            "place": self.place.strip(),
            "day": self.day,
            "month": self.month,
            "year": self.year,
            "value": self.value,
            "paid_by": self.paid_by,
            "category_name": self.category_name,
            "notes": (self.notes or "").strip() or None,
        }


class PhotoExtraction(BaseModel):
    filename: str
    month: Optional[int] = None
    rows: list[DraftExpense] = []
    error: Optional[str] = None


class VariableExpenseResponse(BaseModel):
    id: int
    place: str
    day: int
    month: int
    year: int
    value: float
    paid_by: str
    category_name: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RegularExpenseCreate(ExpenseDate):
    day: int = Field(..., ge=1, le=31)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(default_factory=lambda: datetime.now().year)
    value: float = Field(..., gt=0)
    paid_by: str = Field(default="FAFA", pattern="^(FAFA|FEFE)$", description="Fixed expenses are always paid by Fafa")
    category_name: str = Field(..., min_length=1)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _not_in_future(self):
        if is_future_month(self.year, self.month):
            raise ValueError("Regular expenses cannot belong to a future month")
        return self


class RegularExpenseResponse(BaseModel):
    id: int
    day: int
    month: int
    year: int
    value: float
    paid_by: str
    category_name: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MonthRatioCreate(BaseModel):
    month: int = Field(..., ge=1, le=12)
    year: int = Field(default_factory=lambda: datetime.now().year)
    fafa_ratio: float = Field(..., ge=0, le=1, description="Fafa share as decimal")


class MonthRatioResponse(BaseModel):
    id: int
    month: int
    year: int
    fafa_ratio: float

    model_config = {"from_attributes": True}


class MonthlyBalance(BaseModel):
    # Fall monthly balance calculation
    month: int
    year: int
    total_expenses: float
    variable_total: float
    regular_total: float
    fafa_ratio: float
    fefe_ratio: float
    fafa_should_pay: float
    fefe_should_pay: float
    fafa_paid: float
    fefe_paid: float
    balance: float


class CategoryTotal(BaseModel):
    name: str
    total: float
    previous_total: float


class MonthDetail(MonthlyBalance):
    has_expenses: bool
    variable_categories: list[CategoryTotal]
    regular_categories: list[CategoryTotal]
    previous_total: float
    total_change: float
    total_change_pct: Optional[float] = None