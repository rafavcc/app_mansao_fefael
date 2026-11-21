from app.pages.photo_import import apply_date_text, date_text
from app.schemas import DraftExpense, variable_expense_problem


def _draft(**kw):
    base = dict(place="x", day=3, month=10, year=2026, value=10.0, paid_by="FEFE", category_name="Outros")
    base.update(kw)
    return DraftExpense(**base)


def test_date_text_is_empty_for_an_undated_draft():
    assert date_text(_draft(day=None, month=None, year=None)) == ""
    assert date_text(_draft(day=31, month=2)) == ""


def test_date_text_is_iso_for_a_valid_draft():
    assert date_text(_draft()) == "2026-10-03"


def test_clearing_or_mistyping_the_date_leaves_the_draft_invalid():
    draft = _draft()
    apply_date_text(draft, "")
    assert (draft.day, draft.month, draft.year) == (None, None, None)
    assert variable_expense_problem(draft.expense_data()) == "Data inválida."
    apply_date_text(draft, "2026-13-40")
    assert draft.day is None


def test_typing_a_valid_date_fixes_the_draft():
    draft = _draft(day=None, month=None, year=None)
    apply_date_text(draft, "2026-10-05")
    assert (draft.day, draft.month, draft.year) == (5, 10, 2026)
    assert variable_expense_problem(draft.expense_data()) is None
