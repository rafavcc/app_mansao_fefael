# Mansao Fefael — Household Expense Tracker

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** A web app for Fafa and Fefe to track household expenses with monthly 2/3–1/3 split ratios.

**Architecture:** SQLite database → SQLAlchemy models → FastAPI REST endpoints → NiceGUI web UI. Single Python process, no frontend build step.

**Tech Stack:** Python 3.10+, SQLite, SQLAlchemy, FastAPI, NiceGUI, uvicorn

---

## What changed from the previous version

Six issues addressed in this revision:

| # | File | Problem | Fix |
|---|---|---|---|
| 1 | `crud.py` | `get_month_totals` fired 6 separate SQL queries per balance calculation | Replaced with 2 `GROUP BY` queries |
| 2 | `models.py` | `datetime.utcnow` is deprecated in Python 3.12+ | Changed to `datetime.now(timezone.utc)` |
| 3 | `models.py` + `crud.py` + `balance.py` | `MonthRatio` stored two floats that must sum to 1 — only one is needed | Removed `fefe_ratio` column; derived as `1.0 - fafa_ratio` everywhere |
| 4 | `database.py` + all pages | Raw `try/finally` for DB sessions is verbose and error-prone | Added `get_session()` context manager; pages use `with get_session() as db:` |
| 5 | `pages/variable.py` | No input validation before saving — empty place or zero value would crash or corrupt data | Added guards with `ui.notify()` before saving |
| 6 | `main.py` | `@app.on_event("startup")` is deprecated since FastAPI 0.93 | Replaced with `lifespan=` async context manager |

---

## Project Structure

```
casa-fafa-fefe/
├── app/
│   ├── __init__.py
│   ├── main.py              # NiceGUI + FastAPI entry point
│   ├── database.py          # SQLAlchemy engine, session, Base, context manager
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic schemas
│   ├── crud.py              # Database CRUD operations
│   ├── balance.py           # Monthly balance calculator
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── home.py          # Dashboard / monthly summary
│   │   ├── variable.py      # Variable expense entry + list
│   │   ├── regular.py       # Regular expense entry + list
│   │   └── balance.py       # Balance view + settlements
│   └── seed.py              # Seed users + categories
├── requirements.txt
└── PLAN.md
```

---

## Task 1: Project Setup

**Objective:** Create project directory, virtual environment, and install dependencies.

**Step 1: Create project directory**

```bash
mkdir -p /mnt/c/Users/rafavcc/casa-fafa-fefe/app/pages
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
```

**Step 2: Create venv and install dependencies**

```bash
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy nicegui
```

**Step 3: Create requirements.txt**

`requirements.txt`:
```
fastapi>=0.110.0
uvicorn>=0.29.0
sqlalchemy>=2.0.0
nicegui>=2.0.0
```

**Step 4: Create app/__init__.py and app/pages/__init__.py**

```python
# app/__init__.py
# This file is intentionally empty.
# Its presence tells Python that 'app' is a package (a folder you can import from).
```

```python
# app/pages/__init__.py
# Same as above — makes 'app/pages' importable as a Python package.
```

**Step 5: Commit**

```bash
git init
git add .
git commit -m "chore: project setup with dependencies"
```

---

## Task 2: Database Engine and Session

**Objective:** Set up SQLAlchemy engine, session factory, and a safe context manager for UI code.

**Files:**
- Create: `app/database.py`

**Step 1: Write database.py**

```python
# app/database.py
# This file sets up the database connection for the entire app.
# SQLAlchemy is an "ORM" (Object-Relational Mapper) — it lets us work with
# the database using Python objects instead of raw SQL queries.

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# The database URL tells SQLAlchemy where the database file lives.
# "sqlite:///./casa.db" means: SQLite, in a file called casa.db in the
# current working directory.
DATABASE_URL = "sqlite:///./casa.db"

# The engine is the core connection to the database.
# echo=False: SQLAlchemy won't print every SQL query to the terminal.
# check_same_thread=False: required for SQLite with multi-threaded web servers.
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

# SessionLocal is a factory for creating database sessions.
# A session is a temporary workspace — changes are staged here and only
# written to disk when you call db.commit().
# autocommit=False: you control when data is saved.
# autoflush=False: changes aren't pushed to the DB automatically before queries.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base is the parent class all our ORM models (tables) inherit from.
# SQLAlchemy uses it to track which Python classes map to database tables.
class Base(DeclarativeBase):
    pass


def get_db():
    """
    FastAPI dependency that provides a DB session per request.

    Used with FastAPI's Depends() system:
        @app.get("/something")
        def my_endpoint(db: Session = Depends(get_db)):
            ...

    Opens a session, hands it to the endpoint, and always closes it
    when the request finishes — even if an error was raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# FIX #4: Context manager for safe DB sessions in NiceGUI pages.
# Using 'with get_session() as db:' guarantees the session is always closed,
# with less code than a manual try/finally block in every function.
@contextmanager
def get_session():
    """
    Context manager for database sessions in NiceGUI page code.

    Usage:
        with get_session() as db:
            expenses = crud.get_variable_expenses(db, month=5, year=2026)
        # session is automatically closed here, even if an error occurred

    Prefer this over manually calling SessionLocal() + db.close() in UI code.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create all database tables defined in our models.

    Safe to call multiple times — SQLAlchemy only creates tables that
    don't already exist. Called once at app startup.
    """
    Base.metadata.create_all(bind=engine)
```

**Step 2: Verify**

```bash
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
source venv/bin/activate
python -c "from app.database import init_db; init_db(); print('OK')"
```

Expected: `OK` — creates `casa.db` file in project root.

**Step 3: Commit**

```bash
git add app/database.py
git commit -m "feat: add database engine, session, and context manager"
```

---

## Task 3: SQLAlchemy Models — Users, Categories, MonthRatios

**Objective:** Create ORM models for users, categories, and month_ratios.

**Files:**
- Create: `app/models.py`

**Step 1: Write models.py**

```python
# app/models.py
# Defines the shape of our database tables as Python classes.
# Each class = one table. Each Column = one column in that table.

# FIX #2: Import timezone so we can create timezone-aware timestamps.
# datetime.utcnow() was deprecated in Python 3.12 — use datetime.now(timezone.utc) instead.
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


# ── Users ──────────────────────────────────────────────
class User(Base):
    """
    Represents a person who can pay for expenses.
    Only two users exist: "FAFA" and "FEFE".
    The name is the primary key — no separate numeric ID needed.
    """
    __tablename__ = "users"

    name = Column(String, primary_key=True)    # "FAFA" or "FEFE"
    full_name = Column(String, nullable=True)  # optional display name

    # Relationships let us navigate between tables in Python.
    # e.g. user.variable_expenses → all expenses paid by this user.
    variable_expenses = relationship("VariableExpense", back_populates="payer")
    regular_expenses = relationship("RegularExpense", back_populates="payer")


# ── Categories ─────────────────────────────────────────
class VariableCategory(Base):
    """
    Categories for variable (day-to-day) expenses.
    Examples: "Carro", "Comida", "Lazer"
    """
    __tablename__ = "variable_categories"

    name = Column(String, primary_key=True)
    expenses = relationship("VariableExpense", back_populates="category")


class RegularCategory(Base):
    """
    Categories for fixed monthly expenses.
    Examples: "Aluguel", "Internet", "Cemig"
    """
    __tablename__ = "regular_categories"

    name = Column(String, primary_key=True)
    expenses = relationship("RegularExpense", back_populates="category")


# ── Month Ratios (custom split per month) ──────────────
class MonthRatio(Base):
    """
    Stores the expense-split ratio for a specific month.
    Default: Fafa pays 2/3 (~66.67%), Fefe pays 1/3 (~33.33%).

    FIX #3: Only fafa_ratio is stored. fefe_ratio is always 1.0 - fafa_ratio,
    so storing both would create a consistency risk (they could drift apart).
    fefe_ratio is computed on the fly in crud.py and balance.py using a property.
    """
    __tablename__ = "month_ratios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(Integer, nullable=False)          # 1 = January, 12 = December
    year = Column(Integer, nullable=False)           # e.g. 2026
    fafa_ratio = Column(Float, nullable=False, default=2/3)  # e.g. 0.6667 (= 66.67%)
    # fefe_ratio is NOT stored — it's always derived as: 1.0 - fafa_ratio

    @property
    def fefe_ratio(self) -> float:
        """Fefe's ratio is always the complement of Fafa's. Cannot be inconsistent."""
        return round(1.0 - self.fafa_ratio, 6)

    # Only one ratio entry allowed per month+year pair.
    __table_args__ = (
        UniqueConstraint("month", "year", name="uq_month_ratio"),
    )
```

**Step 2: Verify**

```bash
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
source venv/bin/activate
python -c "
from app.database import init_db, SessionLocal
from app.models import User, VariableCategory, RegularCategory, MonthRatio
from sqlalchemy import text
init_db()
db = SessionLocal()
print('Tables:', db.execute(text('SELECT name FROM sqlite_master WHERE type=\"table\"')).fetchall())
db.close()
print('OK')
"
```

Expected: Lists all table names + `OK`.

**Step 3: Commit**

```bash
git add app/models.py
git commit -m "feat: add User, Category, MonthRatio models"
```

---

## Task 4: Expense Models — Variable and Regular

**Objective:** Create the two expense ORM models.

**Files:**
- Modify: `app/models.py` — append these classes after the existing ones

**Step 1: Append to models.py**

```python
# (append to app/models.py)

# ── Variable Expenses ──────────────────────────────────
class VariableExpense(Base):
    """
    A one-off, day-to-day expense (groceries, gas, leisure, etc.).
    Multiple of these can exist per month, unlike regular expenses.
    """
    __tablename__ = "variable_expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    place = Column(String, nullable=False)             # where the money was spent, e.g. "Carrefour"
    day = Column(Integer, nullable=False)              # day of the month (1-31)
    month = Column(Integer, nullable=False)            # 1-12
    year = Column(Integer, nullable=False)             # four-digit year, e.g. 2026
    value = Column(Float, nullable=False)              # amount in BRL, must be > 0
    paid_by = Column(String, ForeignKey("users.name"), nullable=False)
    category_name = Column(String, ForeignKey("variable_categories.name"), nullable=False)
    notes = Column(String, nullable=True)

    # FIX #2: Use timezone-aware UTC timestamp instead of deprecated datetime.utcnow.
    # lambda is used so the function is called at insert time, not at class-definition time.
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    payer = relationship("User", back_populates="variable_expenses")
    category = relationship("VariableCategory", back_populates="expenses")

    __table_args__ = (
        CheckConstraint("day >= 1 AND day <= 31", name="ck_var_day"),
        CheckConstraint("value > 0", name="ck_var_value"),
    )


# ── Regular Expenses (fixed monthly bills) ─────────────
class RegularExpense(Base):
    """
    A fixed monthly expense (rent, internet, utilities, etc.).
    Only one entry per category per month is allowed.
    Use upsert_regular_expense() in crud.py to create-or-update.
    """
    __tablename__ = "regular_expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day = Column(Integer, nullable=False)              # payment due day (e.g. 10th of the month)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    value = Column(Float, nullable=False)
    paid_by = Column(String, ForeignKey("users.name"), nullable=False)
    category_name = Column(String, ForeignKey("regular_categories.name"), nullable=False)
    notes = Column(String, nullable=True)

    # FIX #2: timezone-aware timestamp
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    payer = relationship("User", back_populates="regular_expenses")
    category = relationship("RegularCategory", back_populates="expenses")

    __table_args__ = (
        CheckConstraint("day >= 1 AND day <= 31", name="ck_reg_day"),
        CheckConstraint("value > 0", name="ck_reg_value"),
        # Prevents duplicate entries for the same category in the same month
        UniqueConstraint("month", "year", "category_name", name="uq_reg_per_month"),
    )
```

**Step 2: Verify**

```bash
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
source venv/bin/activate
python -c "
from app.database import init_db
init_db()
print('Tables recreated successfully')
"
```

**Step 3: Commit**

```bash
git add app/models.py
git commit -m "feat: add VariableExpense and RegularExpense models"
```

---

## Task 5: Pydantic Schemas

**Objective:** Create Pydantic schemas for request/response validation.

**Files:**
- Create: `app/schemas.py`

**Step 1: Write schemas.py**

```python
# app/schemas.py
# Pydantic schemas define the shape of data coming IN (requests from the client)
# and going OUT (responses from the API). They're separate from SQLAlchemy models —
# think of them as "data contracts" for the HTTP layer.
#
# *Create schemas: validate incoming data
# *Response schemas: define what gets sent back

from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime


# ── Variable Expense ───────────────────────────────────
class VariableExpenseCreate(BaseModel):
    """Data required to create a new variable expense."""
    place: str = Field(..., min_length=1, max_length=100)
    day: int = Field(..., ge=1, le=31)                      # ge=greater-or-equal, le=less-or-equal
    month: int = Field(..., ge=1, le=12)
    year: int = Field(default_factory=lambda: datetime.now().year)
    value: float = Field(..., gt=0)                         # gt=greater-than (must be positive)
    paid_by: str = Field(..., pattern="^(FAFA|FEFE)$")     # only "FAFA" or "FEFE" accepted
    category_name: str = Field(..., min_length=1)
    notes: Optional[str] = None


class VariableExpenseResponse(BaseModel):
    """Data returned after creating or listing a variable expense."""
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

    # Required in Pydantic v2: allows reading data from SQLAlchemy ORM objects
    model_config = {"from_attributes": True}


# ── Regular Expense ────────────────────────────────────
class RegularExpenseCreate(BaseModel):
    """Data required to create/update a regular (fixed) monthly expense."""
    day: int = Field(..., ge=1, le=31)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(default_factory=lambda: datetime.now().year)
    value: float = Field(..., gt=0)
    paid_by: str = Field(..., pattern="^(FAFA|FEFE)$")
    category_name: str = Field(..., min_length=1)
    notes: Optional[str] = None


class RegularExpenseResponse(BaseModel):
    """Data returned for a regular expense."""
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


# ── Month Ratio ────────────────────────────────────────
class MonthRatioCreate(BaseModel):
    """
    Data required to set a custom split ratio for a month.

    FIX #3: Only fafa_ratio is accepted (0 < x < 1).
    fefe_ratio is always derived as 1.0 - fafa_ratio — no need to send both,
    and no risk of them being inconsistent.
    """
    month: int = Field(..., ge=1, le=12)
    year: int = Field(default_factory=lambda: datetime.now().year)
    fafa_ratio: float = Field(..., gt=0, lt=1,
                              description="Fafa's share as a decimal, e.g. 0.6667 for 66.67%")


class MonthRatioResponse(BaseModel):
    """
    Data returned for a month ratio.
    Both ratios are included in the response for display convenience,
    but only fafa_ratio is stored in the database.
    """
    id: int
    month: int
    year: int
    fafa_ratio: float
    fefe_ratio: float  # computed by the @property on the model, included for display

    model_config = {"from_attributes": True}


# ── Balance ────────────────────────────────────────────
class MonthlyBalance(BaseModel):
    """
    The full monthly balance calculation.

    'balance' is from Fafa's perspective:
        positive → Fafa overpaid → Fefe owes Fafa
        negative → Fafa underpaid → Fafa owes Fefe
        zero     → All even!
    """
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


# ── Settlement ─────────────────────────────────────────
class SettlementCreate(BaseModel):
    """(Future use) Records a payment made to settle the balance."""
    from_user: str = Field(..., pattern="^(FAFA|FEFE)$")
    to_user: str = Field(..., pattern="^(FAFA|FEFE)$")
    amount: float = Field(..., gt=0)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(default_factory=lambda: datetime.now().year)
    date: Optional[str] = None
    note: Optional[str] = None
```

**Step 2: Verify**

```bash
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
source venv/bin/activate
python -c "from app.schemas import VariableExpenseCreate, RegularExpenseCreate; print('Schemas OK')"
```

**Step 3: Commit**

```bash
git add app/schemas.py
git commit -m "feat: add Pydantic schemas"
```

---

## Task 6: CRUD Operations

**Objective:** Database CRUD functions for expenses, categories, and ratios.

**Files:**
- Create: `app/crud.py`

**Step 1: Write crud.py**

```python
# app/crud.py
# CRUD = Create, Read, Update, Delete
# All functions that read from or write to the database live here.
# Each function takes a 'db: Session' as its first argument.

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.models import (
    User, VariableCategory, RegularCategory,
    VariableExpense, RegularExpense, MonthRatio,
)


# ── Users ──────────────────────────────────────────────

def get_users(db: Session) -> List[User]:
    """Return all users (FAFA and FEFE)."""
    return db.query(User).all()


def create_user(db: Session, name: str, full_name: str = None) -> User:
    """Create a new user. db.add() stages, db.commit() saves, db.refresh() reloads."""
    user = User(name=name, full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Variable Categories ────────────────────────────────

def get_variable_categories(db: Session) -> List[VariableCategory]:
    """Return all variable expense categories (e.g. Carro, Comida)."""
    return db.query(VariableCategory).all()


def create_variable_category(db: Session, name: str) -> VariableCategory:
    cat = VariableCategory(name=name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ── Regular Categories ─────────────────────────────────

def get_regular_categories(db: Session) -> List[RegularCategory]:
    """Return all regular (fixed) expense categories (e.g. Aluguel, Internet)."""
    return db.query(RegularCategory).all()


def create_regular_category(db: Session, name: str) -> RegularCategory:
    cat = RegularCategory(name=name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ── Variable Expenses ──────────────────────────────────

def create_variable_expense(db: Session, data: dict) -> VariableExpense:
    """
    Save a new variable expense. 'data' is a dict of field values.
    ** unpacks the dict into keyword arguments for the model constructor.
    """
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
    """
    Retrieve variable expenses with optional filters.
    Results are sorted newest-first.
    """
    q = db.query(VariableExpense)
    if month:
        q = q.filter(VariableExpense.month == month)
    if year:
        q = q.filter(VariableExpense.year == year)
    if category:
        q = q.filter(VariableExpense.category_name == category)
    return q.order_by(VariableExpense.created_at.desc()).all()


def delete_variable_expense(db: Session, expense_id: int) -> bool:
    """Delete a variable expense by ID. Returns True if deleted, False if not found."""
    expense = db.query(VariableExpense).filter(VariableExpense.id == expense_id).first()
    if expense:
        db.delete(expense)
        db.commit()
        return True
    return False


# ── Regular Expenses ───────────────────────────────────

def create_regular_expense(db: Session, data: dict) -> RegularExpense:
    """Save a new regular expense. Prefer upsert_regular_expense() to avoid duplicates."""
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
    """Retrieve regular expenses with optional filters."""
    q = db.query(RegularExpense)
    if month:
        q = q.filter(RegularExpense.month == month)
    if year:
        q = q.filter(RegularExpense.year == year)
    if category:
        q = q.filter(RegularExpense.category_name == category)
    return q.order_by(RegularExpense.created_at.desc()).all()


def upsert_regular_expense(db: Session, data: dict) -> RegularExpense:
    """
    Create or update a regular expense for a given month/year/category.

    'Upsert' = UPDATE if exists, INSERT if not.
    Because regular expenses have a unique constraint on (month, year, category_name),
    inserting twice for the same category+month would crash without this logic.
    """
    existing = db.query(RegularExpense).filter(
        RegularExpense.month == data["month"],
        RegularExpense.year == data["year"],
        RegularExpense.category_name == data["category_name"],
    ).first()

    if existing:
        # setattr(obj, "field", value) is the same as obj.field = value
        for key, value in data.items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        return create_regular_expense(db, data)


def delete_regular_expense(db: Session, expense_id: int) -> bool:
    """Delete a regular expense by ID. Returns True if deleted, False if not found."""
    expense = db.query(RegularExpense).filter(RegularExpense.id == expense_id).first()
    if expense:
        db.delete(expense)
        db.commit()
        return True
    return False


# ── Month Ratios ───────────────────────────────────────

def get_month_ratio(db: Session, month: int, year: int) -> MonthRatio:
    """
    Get the split ratio for a given month.
    Returns default (fafa=2/3) if no custom ratio has been set.
    The returned default is an in-memory object — it's not saved to the DB.
    """
    ratio = db.query(MonthRatio).filter(
        MonthRatio.month == month,
        MonthRatio.year == year,
    ).first()

    if ratio:
        return ratio

    # Default: Fafa pays 2/3. fefe_ratio is computed automatically via @property.
    return MonthRatio(month=month, year=year, fafa_ratio=2/3)


def set_month_ratio(db: Session, month: int, year: int, fafa: float) -> MonthRatio:
    """
    Create or update the split ratio for a specific month.

    FIX #3: Only fafa is stored. fefe is derived automatically via @property.
    """
    existing = db.query(MonthRatio).filter(
        MonthRatio.month == month,
        MonthRatio.year == year,
    ).first()

    if existing:
        existing.fafa_ratio = fafa
    else:
        existing = MonthRatio(month=month, year=year, fafa_ratio=fafa)
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


# ── Aggregations ───────────────────────────────────────

def get_month_totals(db: Session, month: int, year: int) -> dict:
    """
    Calculate expense totals for a given month, broken down by payer.

    FIX #1: Previously this ran 6 separate SQL queries. Now it runs 2 queries
    using GROUP BY paid_by — one for variable, one for regular expenses.

    GROUP BY groups all rows that share the same 'paid_by' value,
    then SUM() adds up the values within each group.
    Result is e.g. [("FAFA", 1200.0), ("FEFE", 300.0)].
    """
    def payer_sums(model):
        """
        Run a single SUM + GROUP BY query for a given expense model.
        Returns a dict: { "FAFA": total_paid, "FEFE": total_paid }
        """
        rows = db.query(
            model.paid_by,
            func.coalesce(func.sum(model.value), 0).label("total")
            # coalesce returns 0 if there are no rows (instead of None)
        ).filter(
            model.month == month,
            model.year == year,
        ).group_by(model.paid_by).all()

        # Convert list of (paid_by, total) tuples into a dict
        return {row.paid_by: float(row.total) for row in rows}

    var = payer_sums(VariableExpense)   # e.g. {"FAFA": 450.5, "FEFE": 0.0}
    reg = payer_sums(RegularExpense)    # e.g. {"FAFA": 1500.0, "FEFE": 0.0}

    return {
        "variable_total": sum(var.values()),                          # total of all variable expenses
        "regular_total": sum(reg.values()),                           # total of all regular expenses
        "fafa_paid": var.get("FAFA", 0.0) + reg.get("FAFA", 0.0),   # all spending by Fafa
        "fefe_paid": var.get("FEFE", 0.0) + reg.get("FEFE", 0.0),   # all spending by Fefe
    }
```

**Step 2: Commit**

```bash
git add app/crud.py
git commit -m "feat: add CRUD operations with optimised GROUP BY aggregation"
```

---

## Task 7: Balance Calculator

**Objective:** Function that computes monthly balance given all expenses and ratio.

**Files:**
- Create: `app/balance.py`

**Step 1: Write balance.py**

```python
# app/balance.py
# Core business logic: given all expenses for a month and the split ratio,
# calculate who owes whom.

from sqlalchemy.orm import Session
from app.crud import get_month_totals, get_month_ratio


def calculate_monthly_balance(db: Session, month: int, year: int) -> dict:
    """
    Calculate the expense balance for a given month.

    Steps:
    1. Get totals (how much was spent in total, and how much each person paid).
    2. Get the ratio (how much each person SHOULD pay).
    3. Compute fair shares: total × ratio.
    4. Balance = what Fafa paid − what she should have paid.

    Interpreting 'balance' (Fafa's perspective):
        balance > 0  →  Fafa overpaid → Fefe owes Fafa
        balance < 0  →  Fafa underpaid → Fafa owes Fefe
        balance == 0 →  All even!
    """
    totals = get_month_totals(db, month, year)
    ratio = get_month_ratio(db, month, year)

    total = totals["variable_total"] + totals["regular_total"]
    fafa_should = total * ratio.fafa_ratio
    fefe_should = total * ratio.fefe_ratio  # FIX #3: comes from @property, always consistent

    balance = totals["fafa_paid"] - fafa_should

    return {
        "month": month,
        "year": year,
        "total_expenses": round(total, 2),
        "variable_total": round(totals["variable_total"], 2),
        "regular_total": round(totals["regular_total"], 2),
        "fafa_ratio": round(ratio.fafa_ratio, 4),
        "fefe_ratio": round(ratio.fefe_ratio, 4),   # derived via @property
        "fafa_should_pay": round(fafa_should, 2),
        "fefe_should_pay": round(fefe_should, 2),
        "fafa_paid": round(totals["fafa_paid"], 2),
        "fefe_paid": round(totals["fefe_paid"], 2),
        "balance": round(balance, 2),
    }
```

**Step 2: Commit**

```bash
git add app/balance.py
git commit -m "feat: add monthly balance calculator"
```

---

## Task 8: Seed Data

**Objective:** Script to populate users and categories.

**Files:**
- Create: `app/seed.py`

**Step 1: Write seed.py**

```python
# app/seed.py
# Populates the database with users and categories on first run.
# Safe to re-run — checks for existing records before inserting.

import sys
sys.path.insert(0, ".")  # ensures Python can find the 'app' package

from app.database import get_session, init_db
from app.crud import (
    create_user, create_variable_category, create_regular_category,
    get_users, get_variable_categories, get_regular_categories,
)

VARIABLE_CATEGORIES = [
    "Carro",     # car-related (gas, maintenance, parking)
    "Casa",      # home supplies
    "Comida",    # groceries and food
    "Faxina",    # cleaning services
    "Gasolina",  # fuel
    "Lazer",     # leisure / fun
    "Taxi",      # rideshare / taxis
    "Bacana",    # treats / nice things
    "Viagem",    # travel
]

REGULAR_CATEGORIES = [
    "Aluguel",           # rent
    "Internet",          # internet bill
    "Cond",              # condominium fee
    "Cemig",             # electricity bill
    "ConsorcioMG",       # car consortium payment
    "IPTU",              # property tax
    "Extras from Fefe",
    "Extras from Fafa",
]


def seed():
    """Create tables and insert initial data. Skips records that already exist."""
    init_db()

    # FIX #4: Use the context manager instead of manual SessionLocal() + db.close()
    with get_session() as db:
        # Seed Users
        existing_users = {u.name for u in get_users(db)}
        if "FAFA" not in existing_users:
            create_user(db, "FAFA", "Fafa")
        if "FEFE" not in existing_users:
            create_user(db, "FEFE", "Fefe")
        print("✓ Users seeded")

        # Seed Variable Categories
        existing_var = {c.name for c in get_variable_categories(db)}
        for name in VARIABLE_CATEGORIES:
            if name not in existing_var:
                create_variable_category(db, name)
        print(f"✓ {len(VARIABLE_CATEGORIES)} variable categories seeded")

        # Seed Regular Categories
        existing_reg = {c.name for c in get_regular_categories(db)}
        for name in REGULAR_CATEGORIES:
            if name not in existing_reg:
                create_regular_category(db, name)
        print(f"✓ {len(REGULAR_CATEGORIES)} regular categories seeded")

    print("\nDatabase seeded successfully!")


if __name__ == "__main__":
    seed()
```

**Step 2: Run seed**

```bash
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
source venv/bin/activate
python app/seed.py
```

Expected: `✓ Users seeded`, `✓ 9 variable categories seeded`, `✓ 8 regular categories seeded`, `Database seeded successfully!`

**Step 3: Commit**

```bash
git add app/seed.py
git commit -m "feat: add seed data script"
```

---

## Task 9: FastAPI Endpoints

**Objective:** REST API for expenses, balance, categories, and ratios.

**Files:**
- Create: `app/main.py` (FastAPI portion)

**Step 1: Write main.py**

```python
# app/main.py
# REST API using FastAPI.
# Each @app.get / @app.post / etc. decorated function is an "endpoint" — a URL
# the frontend or curl can call to read or write data.
# FastAPI auto-validates incoming data and generates docs at /docs.

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, init_db
from app import crud
from app.schemas import (
    VariableExpenseCreate, VariableExpenseResponse,
    RegularExpenseCreate, RegularExpenseResponse,
    MonthRatioCreate, MonthRatioResponse,
    MonthlyBalance,
)
from app.balance import calculate_monthly_balance


# FIX #6: Use the modern lifespan pattern instead of the deprecated @app.on_event("startup").
# @asynccontextmanager turns this into a context manager FastAPI calls automatically.
# Code before 'yield' runs on startup; code after 'yield' runs on shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs init_db() on startup. Nothing extra needed on shutdown for SQLite."""
    init_db()
    yield


# Pass lifespan= to FastAPI so it calls our startup/shutdown logic
app = FastAPI(title="Mansao Fefael", lifespan=lifespan)


# ── Variable Expenses ──────────────────────────────────

@app.post("/api/variable-expenses", response_model=VariableExpenseResponse)
def add_variable_expense(data: VariableExpenseCreate, db: Session = Depends(get_db)):
    """Create a new variable expense. 'data' is auto-parsed from the JSON body."""
    return crud.create_variable_expense(db, data.model_dump())


@app.get("/api/variable-expenses", response_model=list[VariableExpenseResponse])
def list_variable_expenses(
    month: Optional[int] = Query(None, ge=1, le=12),   # ?month=5
    year: Optional[int] = None,                         # ?year=2026
    category: Optional[str] = None,                     # ?category=Comida
    db: Session = Depends(get_db),
):
    """List variable expenses with optional query-parameter filters."""
    return crud.get_variable_expenses(db, month=month, year=year, category=category)


@app.delete("/api/variable-expenses/{expense_id}")
def remove_variable_expense(expense_id: int, db: Session = Depends(get_db)):
    """Delete a variable expense by ID. Returns 404 if not found."""
    if not crud.delete_variable_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"ok": True}


# ── Regular Expenses ───────────────────────────────────

@app.post("/api/regular-expenses", response_model=RegularExpenseResponse)
def add_regular_expense(data: RegularExpenseCreate, db: Session = Depends(get_db)):
    """Create or update a regular expense (upsert on category+month)."""
    return crud.upsert_regular_expense(db, data.model_dump())


@app.get("/api/regular-expenses", response_model=list[RegularExpenseResponse])
def list_regular_expenses(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List regular expenses with optional filters."""
    return crud.get_regular_expenses(db, month=month, year=year, category=category)


@app.delete("/api/regular-expenses/{expense_id}")
def remove_regular_expense(expense_id: int, db: Session = Depends(get_db)):
    """Delete a regular expense by ID."""
    if not crud.delete_regular_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"ok": True}


# ── Categories ─────────────────────────────────────────

@app.get("/api/variable-categories")
def list_variable_categories(db: Session = Depends(get_db)):
    return [c.name for c in crud.get_variable_categories(db)]


@app.get("/api/regular-categories")
def list_regular_categories(db: Session = Depends(get_db)):
    return [c.name for c in crud.get_regular_categories(db)]


# ── Month Ratios ───────────────────────────────────────

@app.get("/api/month-ratio")
def get_ratio(month: int, year: int, db: Session = Depends(get_db)):
    """Get split ratio for a month. Returns default 2/3:1/3 if not set."""
    r = crud.get_month_ratio(db, month, year)
    return {"month": month, "year": year, "fafa_ratio": r.fafa_ratio, "fefe_ratio": r.fefe_ratio}


@app.put("/api/month-ratio", response_model=MonthRatioResponse)
def set_ratio(data: MonthRatioCreate, db: Session = Depends(get_db)):
    """Set or update the split ratio for a month. FIX #3: only fafa_ratio is sent."""
    return crud.set_month_ratio(db, data.month, data.year, data.fafa_ratio)


# ── Balance ────────────────────────────────────────────

@app.get("/api/balance", response_model=MonthlyBalance)
def get_balance(month: int, year: int, db: Session = Depends(get_db)):
    """Full monthly balance: totals, fair shares, who paid, who owes whom."""
    return calculate_monthly_balance(db, month, year)


# ── Health ─────────────────────────────────────────────

@app.get("/api/health")
def health():
    """Verify the server is running."""
    return {"status": "ok"}
```

**Step 2: Test API**

```bash
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
source venv/bin/activate
python app/seed.py
uvicorn app.main:app --reload &
sleep 2
curl -s http://localhost:8000/api/health | python -m json.tool
curl -s http://localhost:8000/api/variable-categories | python -m json.tool
```

Expected: `{"status": "ok"}` and list of 9 categories.

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add FastAPI endpoints with lifespan startup"
```

---

## Task 10: NiceGUI — Home Page (Dashboard)

**Files:**
- Create: `app/pages/home.py`

**Step 1: Write home.py**

```python
# app/pages/home.py
# Dashboard: monthly totals, who should pay what, and who owes whom.

from nicegui import ui
from app.balance import calculate_monthly_balance
from app.database import get_session   # FIX #4: use context manager
from datetime import datetime


def build_home() -> None:
    now = datetime.now()

    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        ui.label("🏠 Mansao Fefael").classes("text-2xl font-bold")

        with ui.row().classes("gap-4 items-center mt-4"):
            month_select = ui.select(
                options={i: f"{i:02d} - {datetime(2000, i, 1).strftime('%b')}" for i in range(1, 13)},
                value=now.month,
            ).classes("w-32")
            year_input = ui.number(value=now.year, min=2020, max=2030).classes("w-24")
            ui.button("📊 Ver", on_click=lambda: refresh())

        balance_container = ui.column().classes("w-full mt-4")

        def refresh():
            balance_container.clear()
            with balance_container:
                # FIX #4: context manager guarantees session is closed even on error
                with get_session() as db:
                    bal = calculate_monthly_balance(db, month_select.value, int(year_input.value))

                with ui.row().classes("gap-4 w-full"):
                    with ui.card().classes("flex-1"):
                        ui.label("Total").classes("text-sm text-gray-500")
                        ui.label(f"R$ {bal['total_expenses']:,.2f}").classes("text-2xl font-bold")
                    with ui.card().classes("flex-1"):
                        ui.label("Fafa deve pagar").classes("text-sm text-gray-500")
                        ui.label(f"R$ {bal['fafa_should_pay']:,.2f}").classes("text-2xl font-bold")
                    with ui.card().classes("flex-1"):
                        ui.label("Fefe deve pagar").classes("text-sm text-gray-500")
                        ui.label(f"R$ {bal['fefe_should_pay']:,.2f}").classes("text-2xl font-bold")

                with ui.row().classes("gap-4 w-full mt-4"):
                    with ui.card().classes("flex-1"):
                        ui.label(f"Fafa pagou: R$ {bal['fafa_paid']:,.2f}").classes("text-sm")
                        color = "text-green-600" if bal['balance'] >= 0 else "text-red-600"
                        ui.label(f"Diferença: R$ {bal['balance']:,.2f}").classes(f"font-bold {color}")
                    with ui.card().classes("flex-1"):
                        ui.label(f"Fefe pagou: R$ {bal['fefe_paid']:,.2f}").classes("text-sm")
                        diff = -bal['balance']
                        color = "text-green-600" if diff >= 0 else "text-red-600"
                        ui.label(f"Diferença: R$ {diff:,.2f}").classes(f"font-bold {color}")

                with ui.card().classes("w-full mt-4"):
                    if bal['balance'] > 0:
                        ui.label(f"⚠️ Fefe deve R$ {bal['balance']:,.2f} para Fafa").classes("text-lg")
                    elif bal['balance'] < 0:
                        ui.label(f"⚠️ Fafa deve R$ {-bal['balance']:,.2f} para Fefe").classes("text-lg")
                    else:
                        ui.label("✅ Contas iguais este mês!").classes("text-lg text-green-600")

                ui.label(
                    f"Ratio: Fafa {bal['fafa_ratio']*100:.1f}% / Fefe {bal['fefe_ratio']*100:.1f}%"
                ).classes("text-sm text-gray-400 mt-2")

        refresh()
```

**Step 2: Commit**

```bash
git add app/pages/home.py
git commit -m "feat: add home dashboard page"
```

---

## Task 11: NiceGUI — Variable Expenses Page

**Files:**
- Create: `app/pages/variable.py`

**Step 1: Write variable.py**

```python
# app/pages/variable.py
# Page for adding and viewing variable (day-to-day) expenses.
# Section 1: form to add a new expense (with input validation)
# Section 2: filterable list of expenses for the selected month

from nicegui import ui
from datetime import datetime
from app.database import get_session   # FIX #4
from app import crud


def build_variable_expenses() -> None:
    now = datetime.now()

    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        ui.label("💸 Gastos Variáveis").classes("text-2xl font-bold")

        # ── Add Expense Form ───────────────────────────────────────────
        with ui.card().classes("w-full mt-4"):
            ui.label("Novo Gasto").classes("text-lg font-bold mb-2")

            # FIX #4: fetch categories with context manager
            with get_session() as db:
                categories = [c.name for c in crud.get_variable_categories(db)]

            place = ui.input("Local").classes("w-full")
            with ui.row().classes("gap-2"):
                day = ui.number("Dia", value=now.day, min=1, max=31).classes("w-20")
                month = ui.select(
                    options={i: f"{i:02d}" for i in range(1, 13)},
                    value=now.month,
                ).classes("w-20")
                year = ui.number("Ano", value=now.year, min=2020, max=2030).classes("w-24")
            value_input = ui.number("Valor (R$)", min=0.01, step=1.0, format="%.2f").classes("w-48")
            category_select = ui.select(options=categories, label="Grupo").classes("w-48")
            paid_by = ui.select(options=["FAFA", "FEFE"], label="Pago por").classes("w-32")
            notes = ui.input("Notas").classes("w-full")

            result_label = ui.label("")

            def add_expense():
                # FIX #5: Validate all required fields before touching the database.
                # This prevents crashes and bad data from slipping through.
                if not place.value or not place.value.strip():
                    ui.notify("Por favor, preencha o local.", type="warning")
                    return
                if not category_select.value:
                    ui.notify("Selecione uma categoria.", type="warning")
                    return
                if not paid_by.value:
                    ui.notify("Selecione quem pagou.", type="warning")
                    return
                if not value_input.value or value_input.value <= 0:
                    ui.notify("Valor deve ser maior que zero.", type="warning")
                    return

                # FIX #4: context manager for safe session handling
                with get_session() as db:
                    crud.create_variable_expense(db, {
                        "place": place.value.strip(),
                        "day": int(day.value),
                        "month": month.value,
                        "year": int(year.value),
                        "value": float(value_input.value),
                        "paid_by": paid_by.value,
                        "category_name": category_select.value,
                        "notes": notes.value.strip() if notes.value else None,
                    })

                result_label.set_text("✅ Adicionado!")
                result_label.classes("text-green-600")
                place.set_value("")
                value_input.set_value(None)
                notes.set_value("")
                refresh_list()

            ui.button("Adicionar", on_click=add_expense, icon="add").classes("mt-2")

        # ── Filter Controls ────────────────────────────────────────────
        with ui.row().classes("gap-4 mt-4 items-center"):
            ui.label("Filtrar:").classes("text-sm")
            filter_month = ui.select(
                options={i: f"{i:02d}" for i in range(1, 13)},
                value=now.month,
            ).classes("w-20")
            filter_year = ui.number(value=now.year, min=2020, max=2030).classes("w-24")

        expense_list = ui.column().classes("w-full mt-2")

        def refresh_list():
            expense_list.clear()
            with expense_list:
                # FIX #4: context manager
                with get_session() as db:
                    expenses = crud.get_variable_expenses(
                        db, month=filter_month.value, year=int(filter_year.value)
                    )

                if not expenses:
                    ui.label("Nenhum gasto este mês.").classes("text-gray-500 mt-4")
                    return

                total = 0
                for e in expenses:
                    total += e.value
                    with ui.card().classes("w-full"):
                        with ui.row().classes("justify-between items-center"):
                            with ui.column():
                                ui.label(f"{e.category_name} — {e.place}").classes("font-bold")
                                ui.label(f"Dia {e.day} — Pago por {e.paid_by}").classes("text-sm text-gray-500")
                                if e.notes:
                                    ui.label(e.notes).classes("text-xs text-gray-400")
                            ui.label(f"R$ {e.value:,.2f}").classes("text-lg font-bold text-blue-600")

                ui.label(f"Total: R$ {total:,.2f}").classes("text-lg font-bold mt-2")

        filter_month.on("update:model-value", lambda: refresh_list())
        filter_year.on("update:model-value", lambda: refresh_list())
        refresh_list()
```

**Step 2: Commit**

```bash
git add app/pages/variable.py
git commit -m "feat: add variable expenses page with input validation"
```

---

## Task 12: NiceGUI — Regular Expenses Page

**Files:**
- Create: `app/pages/regular.py`

**Step 1: Write regular.py**

```python
# app/pages/regular.py
# Monthly grid of fixed expenses — one row per category, pre-filled from the DB.
# "Salvar Tudo" upserts all rows where value > 0.

from nicegui import ui
from datetime import datetime
from app.database import get_session   # FIX #4
from app import crud


def build_regular_expenses() -> None:
    now = datetime.now()

    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        ui.label("📋 Gastos Fixos").classes("text-2xl font-bold")

        with ui.row().classes("gap-4 mt-4 items-center"):
            month_select = ui.select(
                options={i: f"{i:02d} - {datetime(2000, i, 1).strftime('%b')}" for i in range(1, 13)},
                value=now.month,
            ).classes("w-32")
            year_input = ui.number(value=now.year, min=2020, max=2030).classes("w-24")

        form_container = ui.column().classes("w-full mt-4")
        result_label = ui.label("")

        def build_form():
            form_container.clear()

            # FIX #4: context manager
            with get_session() as db:
                categories = crud.get_regular_categories(db)
                existing = {
                    e.category_name: e
                    for e in crud.get_regular_expenses(
                        db, month=month_select.value, year=int(year_input.value)
                    )
                }

            inputs = {}

            with ui.card().classes("w-full"):
                with ui.row().classes("font-bold text-sm border-b pb-2 w-full"):
                    ui.label("Categoria").classes("flex-1")
                    ui.label("Dia").classes("w-16")
                    ui.label("Valor (R$)").classes("w-32")
                    ui.label("Pago por").classes("w-24")

                for cat in categories:
                    exp = existing.get(cat.name)
                    with ui.row().classes("items-center gap-2 py-1 w-full"):
                        ui.label(cat.name).classes("flex-1 text-sm")
                        day_input = ui.number(
                            value=exp.day if exp else 15, min=1, max=31
                        ).classes("w-16").props("dense")
                        value_input = ui.number(
                            value=exp.value if exp else 0.0, min=0.0, step=1.0, format="%.2f"
                        ).classes("w-32").props("dense")
                        paid_input = ui.select(
                            options=["FAFA", "FEFE"],
                            value=exp.paid_by if exp else "FAFA",
                        ).classes("w-24").props("dense")
                        inputs[cat.name] = (day_input, value_input, paid_input)

                def save_all():
                    # FIX #4: context manager
                    with get_session() as db:
                        for cat_name, (day_in, val_in, paid_in) in inputs.items():
                            if val_in.value and val_in.value > 0:
                                crud.upsert_regular_expense(db, {
                                    "day": int(day_in.value),
                                    "month": month_select.value,
                                    "year": int(year_input.value),
                                    "value": float(val_in.value),
                                    "paid_by": paid_in.value,
                                    "category_name": cat_name,
                                })
                    result_label.set_text("✅ Salvo!")
                    result_label.classes("text-green-600 mt-2")

                with ui.row().classes("gap-2 mt-4"):
                    ui.button("💾 Salvar Tudo", on_click=save_all, icon="save")
                    ui.button("🔄 Recarregar", on_click=build_form, icon="refresh")

                existing_values = [v for v in existing.values() if v and v.value]
                if existing_values:
                    total = sum(v.value for v in existing_values)
                    ui.label(f"Total: R$ {total:,.2f}").classes("text-lg font-bold mt-2")

        month_select.on("update:model-value", lambda: build_form())
        year_input.on("update:model-value", lambda: build_form())
        build_form()
```

**Step 2: Commit**

```bash
git add app/pages/regular.py
git commit -m "feat: add regular expenses page"
```

---

## Task 13: NiceGUI — Balance & Ratio Page

**Files:**
- Create: `app/pages/balance.py`

**Step 1: Write balance.py**

```python
# app/pages/balance.py
# Shows the monthly balance breakdown and lets you adjust the split ratio.

from nicegui import ui
from datetime import datetime
from app.database import get_session   # FIX #4
from app import crud
from app.balance import calculate_monthly_balance


def build_balance() -> None:
    now = datetime.now()

    with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
        ui.label("⚖️ Balanço & Saldos").classes("text-2xl font-bold")

        with ui.row().classes("gap-4 mt-4 items-center"):
            month_select = ui.select(
                options={i: f"{i:02d} - {datetime(2000, i, 1).strftime('%b')}" for i in range(1, 13)},
                value=now.month,
            ).classes("w-32")
            year_input = ui.number(value=now.year, min=2020, max=2030).classes("w-24")

        content = ui.column().classes("w-full mt-4")

        def refresh():
            content.clear()
            with content:
                # FIX #4: one context manager block for all reads on this refresh
                with get_session() as db:
                    bal = calculate_monthly_balance(db, month_select.value, int(year_input.value))
                    current_ratio = crud.get_month_ratio(db, month_select.value, int(year_input.value))

                # ── Ratio Editor ───────────────────────────────────────────
                with ui.card().classes("w-full"):
                    ui.label("Ratio do Mês").classes("font-bold")
                    # FIX #3: only one input needed — Fafa's percentage.
                    # Fefe's is always 100 - Fafa's. A live label shows the derived value.
                    with ui.row().classes("gap-4 mt-2 items-center"):
                        fafa_pct = ui.number(
                            "Fafa %", value=round(current_ratio.fafa_ratio * 100, 1),
                            min=1, max=99, step=1, format="%.1f",
                        ).classes("w-32")
                        fefe_label = ui.label(
                            f"Fefe: {round(current_ratio.fefe_ratio * 100, 1):.1f}%"
                        ).classes("text-sm text-gray-500 self-end mb-1")

                    # Update the Fefe label dynamically as Fafa's value changes
                    def update_fefe_label():
                        if fafa_pct.value is not None:
                            fefe_label.set_text(f"Fefe: {100 - fafa_pct.value:.1f}%")

                    fafa_pct.on("update:model-value", lambda: update_fefe_label())

                    def save_ratio():
                        if not fafa_pct.value or not (1 <= fafa_pct.value <= 99):
                            ui.notify("Fafa % deve estar entre 1 e 99.", type="warning")
                            return
                        # FIX #3: only pass fafa_ratio; fefe is derived in crud
                        with get_session() as db:
                            crud.set_month_ratio(
                                db, month_select.value, int(year_input.value),
                                fafa_pct.value / 100,
                            )
                        ui.notify("Ratio salvo!", type="positive")
                        refresh()

                    ui.button("Salvar Ratio", on_click=save_ratio, icon="save").classes("mt-2")

                # ── Balance Details ─────────────────────────────────────────
                with ui.card().classes("w-full mt-4"):
                    ui.label("Detalhes").classes("font-bold")
                    ui.label(f"Total: R$ {bal['total_expenses']:,.2f}").classes("text-lg mt-2")
                    ui.label(
                        f"Variável: R$ {bal['variable_total']:,.2f} | Fixo: R$ {bal['regular_total']:,.2f}"
                    ).classes("text-sm text-gray-500")
                    ui.separator().classes("my-2")

                    ui.label(f"Fafa deve pagar: R$ {bal['fafa_should_pay']:,.2f}").classes("text-sm")
                    ui.label(f"Fafa pagou:       R$ {bal['fafa_paid']:,.2f}").classes("text-sm")
                    diff = bal['balance']
                    color = "text-green-600" if diff >= 0 else "text-red-600"
                    ui.label(f"Saldo Fafa: R$ {diff:,.2f}").classes(f"font-bold {color}")

                    ui.separator().classes("my-2")

                    ui.label(f"Fefe deve pagar: R$ {bal['fefe_should_pay']:,.2f}").classes("text-sm")
                    ui.label(f"Fefe pagou:       R$ {bal['fefe_paid']:,.2f}").classes("text-sm")
                    color2 = "text-green-600" if -diff >= 0 else "text-red-600"
                    ui.label(f"Saldo Fefe: R$ {-diff:,.2f}").classes(f"font-bold {color2}")

        month_select.on("update:model-value", lambda: refresh())
        year_input.on("update:model-value", lambda: refresh())
        refresh()
```

**Step 2: Commit**

```bash
git add app/pages/balance.py
git commit -m "feat: add balance and ratio page"
```

---

## Task 14: NiceGUI — Main App Entry Point

**Files:**
- Modify: `app/main.py` — append NiceGUI setup at bottom
- Create: `.gitignore`

**Step 1: Append to main.py**

```python
# ── NiceGUI pages ───────────────────────────────────────
from nicegui import ui, app as nice_app
from app.pages.home import build_home
from app.pages.variable import build_variable_expenses
from app.pages.regular import build_regular_expenses
from app.pages.balance import build_balance


def _nav_header(title: str):
    """Shared navigation bar rendered on every page."""
    with ui.header(elevated=True).classes("bg-blue-600 text-white"):
        ui.label(title).classes("text-lg font-bold")
        ui.space()
        ui.link("Início", "/").classes("text-white")
        ui.link("Variáveis", "/variable").classes("text-white")
        ui.link("Fixos", "/regular").classes("text-white")
        ui.link("Balanço", "/balance").classes("text-white")


@ui.page("/")
def page_home():
    _nav_header("Mansao Fefael")
    build_home()


@ui.page("/variable")
def page_variable():
    _nav_header("Gastos Variáveis")
    build_variable_expenses()


@ui.page("/regular")
def page_regular():
    _nav_header("Gastos Fixos")
    build_regular_expenses()


@ui.page("/balance")
def page_balance():
    _nav_header("Balanço")
    build_balance()


# Mount FastAPI inside NiceGUI — /api/* goes to FastAPI, everything else to NiceGUI
nice_app.mount(app)


def run():
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ in ("__main__", "__mp_main__"):
    run()
```

**Step 2: Create .gitignore**

```gitignore
venv/
__pycache__/
*.pyc
casa.db
.env
```

**Step 3: Run the app**

```bash
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
source venv/bin/activate
python app/seed.py
python app/main.py
```

Open http://localhost:8000

**Step 4: Commit**

```bash
git add app/main.py .gitignore
git commit -m "feat: wire up NiceGUI pages with navigation"
```

---

## Task 15: Verification — End-to-End Test

**Step 1: Start the app**

```bash
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
source venv/bin/activate
python app/main.py &
```

**Step 2: Add expenses via curl**

```bash
# Variable expense
curl -s -X POST http://localhost:8000/api/variable-expenses \
  -H "Content-Type: application/json" \
  -d '{"place":"Carrefour","day":15,"month":5,"year":2026,"value":450.50,"paid_by":"FAFA","category_name":"Comida"}' \
  | python -m json.tool

# Regular expense
curl -s -X POST http://localhost:8000/api/regular-expenses \
  -H "Content-Type: application/json" \
  -d '{"day":10,"month":5,"year":2026,"value":1500.00,"paid_by":"FAFA","category_name":"Aluguel"}' \
  | python -m json.tool

# Set a custom ratio (only send fafa_ratio now)
curl -s -X PUT http://localhost:8000/api/month-ratio \
  -H "Content-Type: application/json" \
  -d '{"month":5,"year":2026,"fafa_ratio":0.6667}' \
  | python -m json.tool

# Check balance
curl -s "http://localhost:8000/api/balance?month=5&year=2026" | python -m json.tool
```

Expected: Balance shows total R$1950.50, Fafa should pay R$1300.33, Fefe should pay R$650.17, balance = R$650.17 (Fefe owes Fafa).

**Step 3: Open browser at http://localhost:8000 and verify:**
- Home shows correct totals
- Variable page shows Carrefour expense
- Regular page shows Aluguel
- Balance page shows correct ratio and settlement message

---

## Summary

| Component | Technology | Purpose |
|---|---|---|
| Database | SQLite | Single file, zero setup |
| ORM | SQLAlchemy | Models, queries |
| API | FastAPI | REST endpoints at /api/* |
| UI | NiceGUI | Python-only web UI |
| Server | uvicorn | ASGI server |

### How to Use

```bash
cd /mnt/c/Users/rafavcc/casa-fafa-fefe
source venv/bin/activate

# First time or reset:
rm casa.db
python app/seed.py

# Run:
python app/main.py
# → http://localhost:8000

# Access from phone on same WiFi:
# http://<your-pc-ip>:8000
```

### Key Design Decisions

- **Two tables** for expenses (variable/regular) — clean separation, different constraints
- **Regular upsert** — one entry per category per month, auto-updates
- **Single ratio column** — only `fafa_ratio` is stored; `fefe_ratio` is always `1 - fafa_ratio`
- **2 GROUP BY queries** for balance calculation instead of 6 individual queries
- **Context manager sessions** in all UI code — no leaked connections
- **lifespan pattern** for FastAPI startup — forward-compatible with current FastAPI versions
- **No auth** — home network app. Can add HTTP Basic Auth later if needed.

---

## Full Fixes Summary

| # | File(s) changed | Problem | Fix |
|---|---|---|---|
| 1 | `crud.py` | 6 SQL queries to compute monthly totals | 2 `GROUP BY` queries via `payer_sums()` helper |
| 2 | `models.py` | `datetime.utcnow` deprecated in Python 3.12 | `lambda: datetime.now(timezone.utc)` |
| 3 | `models.py`, `crud.py`, `schemas.py`, `balance.py`, `pages/balance.py` | Two ratio columns that could go out of sync | Store only `fafa_ratio`; `fefe_ratio` is a `@property` |
| 4 | `database.py` + all pages + `seed.py` | Manual `try/finally` DB sessions everywhere | `get_session()` context manager; `with get_session() as db:` throughout |
| 5 | `pages/variable.py` | No validation before saving — empty/zero inputs could crash or corrupt | Guards + `ui.notify()` before every `crud` call |
| 6 | `main.py` | `@app.on_event("startup")` deprecated since FastAPI 0.93 | `@asynccontextmanager` + `lifespan=` on `FastAPI()` |