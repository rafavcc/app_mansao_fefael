import asyncio
import logging
import os

import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Query, Depends, UploadFile
from nicegui import ui
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Optional

from app.env import load_env_file

# Load .env first so it can also set CASA_DB_PATH / CASA_STORAGE_SECRET
load_env_file()

from app.database import get_db, get_session, get_session_factory, init_db
from app import crud, llm, photo_import
from app.backup import backup_loop
from app.schemas import (
    MonthDetail, MonthlyBalance, PhotoExtraction, MonthRatioCreate, MonthRatioResponse,
    RegularExpenseCreate, RegularExpenseResponse, VariableExpenseCreate, VariableExpenseResponse,
)
from app.models import PAYERS
from app.balance import calculate_monthly_balance, calculate_year_months
from app.ui import STATIC_DIR, register_pages

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

MAX_PHOTOS_PER_REQUEST = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only initialize DB if not in test mode (tests use their own fixtures)
    task = None
    if not os.environ.get("TESTING"):
        init_db()
        with get_session() as db:
            crud.autofill_current_month_regular_expenses(db)
        task = asyncio.create_task(backup_loop())
    try:
        yield
    finally:
        if task:
            task.cancel()


app = FastAPI(title="Mansao Fefael", lifespan=lifespan)  # lifespan skips init_db() when TESTING is set


@app.post("/api/variable-expense/", response_model=VariableExpenseResponse)
def add_variable_expense(data: VariableExpenseCreate, db: Session = Depends(get_db)):
    return crud.create_variable_expense(db, data.model_dump())


@app.post("/api/variable-expenses/extract", response_model=list[PhotoExtraction])
def extract_variable_expenses(
    files: list[UploadFile] = File(...),
    paid_by: str = Form(...),
    model: Optional[str] = Form(None),
    session_factory=Depends(get_session_factory),
):
    """Reads each photo with the vision LLM and returns draft rows. Never saves anything."""
    if paid_by not in PAYERS:
        raise HTTPException(status_code=422, detail="Pagador inválido.")
    if len(files) > MAX_PHOTOS_PER_REQUEST:
        raise HTTPException(status_code=422, detail=f"Envie no máximo {MAX_PHOTOS_PER_REQUEST} fotos por vez.")
    model = model or llm.llm_config().model
    # Short sessions only: a session kept open across the slow LLM calls would hold a SQLite lock.
    with session_factory() as db:
        ctx = photo_import.load_context(db, paid_by)
    results: list[PhotoExtraction] = []
    earlier = []
    for upload in files:
        name = upload.filename or "foto"
        # One byte over the limit is enough for extract_photo to reject the photo.
        result = photo_import.extract_photo(upload.file.read(photo_import.MAX_PHOTO_BYTES + 1), name, ctx, model)
        try:
            with session_factory() as db:
                photo_import.mark_duplicates(db, result.rows, earlier=earlier)
        except Exception:
            logger.exception("Erro ao verificar duplicados da foto %s", name)
            result = PhotoExtraction(filename=name, error=f"Foto '{name}': erro ao verificar duplicados.")
        earlier.extend(result.rows)
        results.append(result)
    return results


@app.get("/api/variable-expenses/", response_model=list[VariableExpenseResponse])
def list_variable_expenses(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return crud.get_variable_expenses(db, month=month, year=year, category=category)


@app.delete("/api/variable-expenses/{expense_id}")
def remove_variable_expense(expense_id: int, db: Session = Depends(get_db)):
    if not crud.delete_variable_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"ok": True}


@app.put("/api/variable-expenses/{expense_id}", response_model=VariableExpenseResponse)
def edit_variable_expense(expense_id: int, data: VariableExpenseCreate, db: Session = Depends(get_db)):
    expense = crud.update_variable_expense(db, expense_id, data.model_dump())
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


# --- Regular Expenses

@app.post("/api/regular-expense/", response_model=RegularExpenseResponse)
def add_regular_expense(data: RegularExpenseCreate, db: Session = Depends(get_db)):
    # Upsert: one entry per category and month, so a repeated POST updates instead of failing with a 500.
    return crud.upsert_regular_expense(db, data.model_dump())


@app.get("/api/regular-expense/", response_model=list[RegularExpenseResponse])
def list_regular_expense(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return crud.get_regular_expenses(db, month=month, year=year, category=category)


@app.delete("/api/regular-expense/{expense_id}")
def remove_regular_expense(expense_id: int, db: Session = Depends(get_db)):
    if not crud.delete_regular_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"ok": True}


@app.put("/api/regular-expense/{expense_id}", response_model=RegularExpenseResponse)
def edit_regular_expense(expense_id: int, data: RegularExpenseCreate, db: Session = Depends(get_db)):
    try:
        expense = crud.update_regular_expense(db, expense_id, data.model_dump())
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Category already has an expense in this month")
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


# --- Categories

@app.get("/api/variable-categories")
def list_variable_categories(db: Session = Depends(get_db)):
    return [c.name for c in crud.get_variable_categories(db)]


@app.get("/api/regular-categories")
def list_regular_categories(db: Session = Depends(get_db)):
    return [c.name for c in crud.get_regular_categories(db)]


# --- Month Ratios

@app.get("/api/month-ratio")
def get_month_ratio(month: int, year: int, db: Session = Depends(get_db)):
    ratio = crud.get_month_ratio(db, month, year)
    return {"month": ratio.month, "year": ratio.year, "fafa_ratio": ratio.fafa_ratio, "fefe_ratio": ratio.fefe_ratio}


@app.put("/api/month-ratio", response_model=MonthRatioResponse)
def set_month_ratio(data: MonthRatioCreate, db: Session = Depends(get_db)):
    return crud.set_month_ratio(db, data.month, data.year, data.fafa_ratio)


# --- Balance

@app.get("/api/balance", response_model=MonthlyBalance)
def get_balance(month: int = Query(..., ge=1, le=12), year: int = Query(..., ge=1), db: Session = Depends(get_db)):
    return calculate_monthly_balance(db, month, year)


@app.get("/api/balance/months", response_model=list[MonthDetail])
def get_balance_months(year: int, db: Session = Depends(get_db)):
    return calculate_year_months(db, year)


@app.get("/api/health")
def health():
    """Verify the server is running."""
    return {"status": "ok"}


# --- Secret

def _storage_secret() -> str:
    secret = os.getenv("CASA_STORAGE_SECRET")
    if not secret:
        logger.warning("CASA_STORAGE_SECRET not set; using a random secret (browser preferences reset on restart).")
        secret = secrets.token_urlsafe(32)
    return secret


register_pages()
ui.run_with(
    app,
    mount_path="/",
    storage_secret=_storage_secret(),
    title="Mansao Fefael",
    language="pt-BR",
    favicon=(STATIC_DIR / "favicon.svg").read_text(encoding="utf-8"),
    viewport="width=device-width, initial-scale=1, viewport-fit-cover",
)
