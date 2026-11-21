"""NiceGUI components exercised inside a bare Client context (no browser)."""
from datetime import date

import pytest
from nicegui import Client, ui
from nicegui.page import page

from app.pages.photo_import import Section
from app.pages.variable import ExpenseForm
from app.schemas import DraftExpense, PhotoExtraction


@pytest.fixture
def client_context():
    with Client(page("/test-components")) as client:
        yield client


def _draft(**kw):
    base = dict(place="x", day=3, month=10, year=2026, value=10.0, paid_by="FEFE", category_name="Outros")
    base.update(kw)
    return DraftExpense(**base)


def test_remove_saved_keeps_an_error_only_section(client_context):
    emptied = []
    section = Section(PhotoExtraction(filename="a.png", error="Foto 'a.png': falhou"), [], ui.column(), emptied.append)
    section.remove_saved([_draft()])
    assert emptied == []
    assert not section.card.is_deleted


def test_remove_saved_drops_a_section_once_all_rows_are_saved(client_context):
    emptied = []
    drafts = [_draft(), _draft(place="y")]
    section = Section(PhotoExtraction(filename="a.png", month=10, rows=drafts), ["Outros"], ui.column(), emptied.append)
    section.remove_saved(drafts[:1])
    assert len(section.rows) == 1 and emptied == []
    section.remove_saved(drafts[1:])
    assert emptied == [section] and section.card.is_deleted


def _fill(form, **over):
    values = dict(place=" Mercado ", date=date.today().isoformat(), value="12,50", paid_by="FAFA",
                  category="Outros", notes="")
    values.update(over)
    form.place.value = values["place"]
    form.date.value = values["date"]
    form.value.value = values["value"]
    form.paid_by.value = values["paid_by"]
    form.category.value = values["category"]
    form.notes.value = values["notes"]


def test_expense_form_read_builds_validated_data(client_context):
    form = ExpenseForm(["Outros"])
    _fill(form)
    data = form.read()
    today = date.today()
    assert data == {
        "place": "Mercado", "day": today.day, "month": today.month, "year": today.year,
        "value": 12.5, "paid_by": "FAFA", "category_name": "Outros", "notes": None,
    }


def test_expense_form_read_rejects_too_high_and_missing_values(client_context, monkeypatch):
    notes = []
    monkeypatch.setattr(ui, "notify", lambda message, **kw: notes.append(message))
    form = ExpenseForm(["Outros"])
    _fill(form, value="2.000.000,00")
    assert form.read() is None
    _fill(form, value="")
    assert form.read() is None
    assert notes == ["Valor muito alto.", "Valor deve ser maior que zero."]
