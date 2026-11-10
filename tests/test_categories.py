import pytest

from app import crud
from app.models import RegularCategory, RegularExpense, VariableCategory, VariableExpense


def _users_and_cats(db):
    from app.models import User
    if not db.get(User, "FAFA"):
        db.add(User(name="FAFA"))
    for name in ("Comida", "Lazer"):
        if not db.get(VariableCategory, name):
            db.add(VariableCategory(name=name))
    for name in ("Aluguel", "Casa"):
        if not db.get(RegularCategory, name):
            db.add(RegularCategory(name=name))
    db.commit()


def test_variable_delete_requires_replacement_and_moves(db_session):
    _users_and_cats(db_session)
    db_session.add(VariableExpense(place="x", day=1, month=1, year=2026, value=5, paid_by="FAFA", category_name="Lazer"))
    db_session.commit()
    with pytest.raises(crud.CategoryError):
        crud.delete_category(db_session, "variable", "Lazer", None)
    assert db_session.get(VariableCategory, "Lazer") is not None
    assert crud.delete_category(db_session, "variable", "Lazer", "Comida")["moved"] == 1
    assert db_session.get(VariableCategory, "Lazer") is None
    assert db_session.query(VariableExpense).one().category_name == "Comida"


def test_regular_delete_merges_same_month(db_session):
    _users_and_cats(db_session)
    for cat, val in (("Aluguel", 100), ("Casa", 50)):
        db_session.add(RegularExpense(day=1, month=1, year=2026, value=val, paid_by="FAFA", category_name=cat))
    db_session.commit()
    assert crud.delete_category(db_session, "regular", "Casa", "Aluguel")["merged"] == 1
    assert db_session.query(RegularExpense).one().value == 150
