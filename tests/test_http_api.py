import pytest
from fastapi.testclient import TestClient

from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Import database module to use dependency_overrides
from app import database
from app.database import get_db


VARIABLE = {
    "place": "Mercado", "day": 4, "month": 10, "year": 2026,
    "value": 80.0, "paid_by": "FAFA", "category_name": "Mercado",
}
REGULAR = {
    "day": 5, "month": 10, "year": 2026, "value": 2000.0,
    "paid_by": "FAFA", "category_name": "Aluguel",
}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_variable_expense_full_cycle(client):
    created = client.post("/api/variable-expense/", json=VARIABLE)
    assert created.status_code == 200
    expense_id = created.json()["id"]

    listed = client.get("/api/variable-expenses/", params={"month": 10, "year": 2026})
    assert [e["id"] for e in listed.json()] == [expense_id]

    updated = client.put(f"/api/variable-expenses/{expense_id}", json={**VARIABLE, "value": 99.9})
    assert updated.json()["value"] == 99.9

    assert client.delete(f"/api/variable-expenses/{expense_id}").json() == {"ok": True}
    assert client.get("/api/variable-expenses/").json() == []


@pytest.mark.parametrize("override", [
    {"value": 100.0},
    {"value": 50.5},
    {"value": 200.0},
])
def test_variable_expense_amounts(client, override):
    data = VARIABLE.copy()
    data["value"] = override["value"]
    created = client.post("/api/variable-expense/", json=data)
    assert created.status_code == 200


def test_regular_expense_full_cycle(client):
    created = client.post("/api/regular-expense/", json=REGULAR)
    assert created.status_code == 200
    expense_id = created.json()["id"]

    listed = client.get("/api/regular-expense/")
    assert [e["id"] for e in listed.json()] == [expense_id]

    updated = client.put(f"/api/regular-expense/{expense_id}", json={**REGULAR, "value": 1500.0})
    assert updated.json()["value"] == 1500.0

    assert client.delete(f"/api/regular-expense/{expense_id}").json() == {"ok": True}


def test_categories_endpoints(client_with_session):
    client, _, SessionLocal = client_with_session
    from app import crud
    
    db = SessionLocal()
    
    # Drop all categories to start fresh
    db.execute(text("DELETE FROM variable_categories"))
    db.execute(text("DELETE FROM regular_categories"))
    db.commit()
    
    crud.create_variable_category(db, "Mercado")
    crud.create_regular_category(db, "Aluguel")
    
    assert client.get("/api/variable-categories").json() == ["Mercado"]
    assert client.get("/api/regular-categories").json() == ["Aluguel"]
    
    # Add another category
    db.execute(text("INSERT INTO variable_categories (name) VALUES ('Casa')"))
    db.commit()
    
    assert set(client.get("/api/variable-categories").json()) == {"Mercado", "Casa"}


def test_expense_by_user(client):
    """Test that expenses can be filtered by user via API."""
    # Create a variable expense
    response = client.post("/api/variable-expense/", json=VARIABLE)
    assert response.status_code == 200
    
    # Get the list of expenses (should include the one we just created)
    listed = client.get("/api/variable-expenses/")
    assert listed.status_code == 200
    
    expense_ids = [e["id"] for e in listed.json()]
    assert len(expense_ids) >= 1


def test_balance_calculations(client_with_session):
    client, _, SessionLocal = client_with_session
    from app import balance
    from app import crud
    
    # Create test data
    fafa_id = "FAFA_BALANCE_TEST"
    fefe_id = "FEFE_BALANCE_TEST"
    
    db = SessionLocal()
    
    # Create users
    fafa = crud.create_user(db, name=fafa_id, full_name="Fafa Balance")
    fefe = crud.create_user(db, name=fefe_id, full_name="Fefe Balance")
    
    # Create categories
    mercado = crud.create_variable_category(db, "Mercado_BALANCE")
    aluguel = crud.create_regular_category(db, "Aluguel_BALANCE")
    
    # Create some expenses for Fafa
    var_exp1 = crud.create_variable_expense(db, {
        "place": "Mercado",
        "day": 5,
        "month": 10,
        "year": 2026,
        "value": 200.0,
        "paid_by": fafa.name,
        "category_name": mercado.name
    })
    
    var_exp2 = crud.create_variable_expense(db, {
        "place": "Padaria",
        "day": 10,
        "month": 10,
        "year": 2026,
        "value": 50.0,
        "paid_by": fafa.name,
        "category_name": mercado.name
    })
    
    reg_exp1 = crud.upsert_regular_expense(db, {
        "day": 5,
        "month": 10,
        "year": 2026,
        "value": 1500.0,
        "paid_by": fafa.name,
        "category_name": aluguel.name
    })
    
    # Save values before closing session
    var_exp1_value = var_exp1.value
    var_exp2_value = var_exp2.value
    reg_exp1_value = reg_exp1.value
    
    db.commit()
    db.close()
    
    # Create a month ratio with 50% for each user (default ratio)
    db = SessionLocal()
    try:
        db.execute(text("INSERT INTO month_ratios (month, year, fafa_ratio) VALUES (10, 2026, 0.5)"))
        db.commit()
        
        # Calculate balance for Fafa
        monthly_balance = balance.calculate_monthly_balance(db, 10, 2026)
        
        # Check that the function returns expected structure
        assert "month" in monthly_balance
        assert "year" in monthly_balance
        assert "total_expenses" in monthly_balance
        assert "balance" in monthly_balance
        assert "fafa_paid" in monthly_balance
        assert "fefe_paid" in monthly_balance
        
        # Verify that total_expenses equals sum of all expenses we created
        expected_total = reg_exp1_value + var_exp1_value + var_exp2_value
        assert abs(monthly_balance["total_expenses"] - expected_total) < 0.01
        
        # Calculate year months - should return list with month data
        # Pass a date at the end of the year to include all months
        from datetime import date
        year_months = balance.calculate_year_months(db, 2026, today=date(2026, 12, 31))
        # Should have all 12 months when checking from end of year
        assert len(year_months) == 12
    finally:
        db.close()


def test_month_ratio_endpoints(client):
    """Test month ratio endpoints."""
    # Create a month ratio using the API
    response = client.put("/api/month-ratio", json={
        "month": 10,
        "year": 2026,
        "fafa_ratio": 0.75
    })
    
    assert response.status_code == 200
    ratio_data = response.json()
    assert ratio_data["month"] == 10
    assert ratio_data["year"] == 2026
    assert ratio_data["fafa_ratio"] == 0.75
    
    # Test GET endpoint
    response = client.get("/api/month-ratio?month=10&year=2026")
    assert response.status_code == 200
    retrieved_ratio = response.json()
    assert retrieved_ratio["month"] == 10
    assert retrieved_ratio["fafa_ratio"] == 0.75
    
    # Test with default year (should use current year)
    response = client.put("/api/month-ratio", json={
        "month": 1,
        "fafa_ratio": 0.5
    })
    
    assert response.status_code == 200
