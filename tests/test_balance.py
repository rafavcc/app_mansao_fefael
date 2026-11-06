"""
Tests for balance calculation logic.
Uses unique names per test to avoid conflicts.
"""
import pytest
from decimal import Decimal
from app.database import get_session, init_db
from app import crud
from app.balance import calculate_monthly_balance


class TestBalanceCalculation:
    """Tests for balance calculation."""

    def test_basic_balance_calculation(self, db_session):
        """Test basic balance calculation with default 2/3 ratio."""
        from app.models import VariableCategory, RegularCategory
        
        # Setup users and categories
        fafa = crud.create_user(db_session, name="BALANCE_TEST_001", full_name="Fafa Test 001")
        
        comida_cat = crud.create_variable_category(db_session, "Comida")
        aluguel_cat = crud.create_regular_category(db_session, "Aluguel")
        
        # Create expenses totaling R$ 2100.50 (adjusted for ratio calculation)
        # Variable: R$ 600.50 (Fafa: 450.50, Fefe: 150.00)
        crud.create_variable_expense(db_session, {
            "place": "Carrefour",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 450.50,
            "paid_by": "FAFA",
            "category_name": comida_cat.name
        })
        
        crud.create_variable_expense(db_session, {
            "place": "Pet Shop",
            "day": 10,
            "month": 5,
            "year": 2026,
            "value": 150.00,
            "paid_by": "FEFE",
            "category_name": comida_cat.name
        })
        
        crud.upsert_regular_expense(db_session, {
            "day": 5,
            "month": 5,
            "year": 2026,
            "value": 1500.00,
            "paid_by": "FAFA",
            "category_name": aluguel_cat.name
        })
        
        # Calculate balance for May 2026
        balance = calculate_monthly_balance(db_session, month=5, year=2026)
        
        # Verify total expenses (should be ~2100.50)
        assert abs(balance["total_expenses"] - 2100.50) < 0.01
        assert balance["balance"] > 0  # Positive means Fafa paid more, so Fefe owes
        assert balance["fafa_paid"] > balance["fafa_should_pay"]  # Fafa paid more than her share

    def test_no_expenses(self, db_session):
        """Test with no expenses - all zeros."""
        # Calculate balance for a month with no expenses
        balance = calculate_monthly_balance(db_session, month=5, year=2026)
        
        assert balance["total_expenses"] == 0.0
        assert balance["fafa_paid"] == 0.0
        assert balance["fefe_paid"] == 0.0
        assert balance["balance"] == 0.0

    def test_equal_payment(self, db_session):
        """Test when both paid exactly their share."""
        from app.models import VariableCategory, RegularCategory, MonthRatio
        
        fafa = crud.create_user(db_session, name="EQUAL_TEST_001", full_name="Fafa Equal")
        
        comida_cat = crud.create_variable_category(db_session, "Comida")
        
        # Create expenses totaling R$ 300.00
        # Fafa should pay 2/3 = R$ 200.00
        # Fefe should pay 1/3 = R$ 100.00
        crud.create_variable_expense(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 200.00,
            "paid_by": "FAFA",
            "category_name": comida_cat.name
        })
        
        crud.create_variable_expense(db_session, {
            "place": "Padaria",
            "day": 10,
            "month": 5,
            "year": 2026,
            "value": 100.00,
            "paid_by": "FEFE",
            "category_name": comida_cat.name
        })
        
        balance = calculate_monthly_balance(db_session, month=5, year=2026)
        
        assert abs(balance["balance"]) < 0.01  # Essentially zero


class TestBalanceEdgeCases:
    """Tests for edge cases in balance calculation."""

    def test_fafa_underpays(self, db_session):
        """Test when Fafa underpays - negative balance."""
        from app.models import VariableCategory
        
        fafa = crud.create_user(db_session, name="UNDERPAY_TEST_001", full_name="Fafa Underpay")
        
        comida_cat = crud.create_variable_category(db_session, "Comida")
        
        # Fefe pays everything
        crud.create_variable_expense(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 300.00,
            "paid_by": "FEFE",
            "category_name": comida_cat.name
        })
        
        balance = calculate_monthly_balance(db_session, month=5, year=2026)
        
        assert balance["balance"] < 0  # Negative means Fafa owes Fefe
        # Check that balance is negative (Fafa should pay Fefe)
        assert balance["fafa_paid"] < balance["fafa_should_pay"]

    def test_custom_ratio_50_50(self, db_session):
        """Test with custom 50/50 ratio."""
        from app.models import VariableCategory, RegularCategory, MonthRatio
        
        fafa = crud.create_user(db_session, name="RATIO_TEST_001", full_name="Fafa Ratio")
        
        comida_cat = crud.create_variable_category(db_session, "Comida")
        
        # Set custom ratio: 50/50
        crud.set_month_ratio(db_session, month=5, year=2026, fafa=0.5)
        
        # Create expense R$ 300.00 - each should pay R$ 150.00
        crud.create_variable_expense(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 150.00,
            "paid_by": "FAFA",
            "category_name": comida_cat.name
        })
        
        crud.create_variable_expense(db_session, {
            "place": "Padaria",
            "day": 10,
            "month": 5,
            "year": 2026,
            "value": 150.00,
            "paid_by": "FEFE",
            "category_name": comida_cat.name
        })
        
        balance = calculate_monthly_balance(db_session, month=5, year=2026)
        
        assert abs(balance["balance"]) < 0.01  # Equal payment


class TestBalanceRounding:
    """Tests for rounding and precision."""

    def test_rounding_to_2_decimals(self, db_session):
        """Test that balance rounds to 2 decimal places."""
        from app.models import VariableCategory
        
        fafa = crud.create_user(db_session, name="ROUND_TEST_001", full_name="Fafa Round")
        
        comida_cat = crud.create_variable_category(db_session, "Comida")
        
        # Create expenses with cents that might cause rounding issues
        crud.create_variable_expense(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.333,  # This will round to 100.33
            "paid_by": "FAFA",
            "category_name": comida_cat.name
        })
        
        balance = calculate_monthly_balance(db_session, month=5, year=2026)
        
        # Balance should be rounded to 2 decimals
        assert isinstance(balance["balance"], (int, float))
        assert round(balance["balance"], 2) == balance["balance"]

    def test_small_values(self, db_session):
        """Test with very small expense values."""
        from app.models import VariableCategory
        
        fafa = crud.create_user(db_session, name="SMALL_TEST_001", full_name="Fafa Small")
        
        comida_cat = crud.create_variable_category(db_session, "Comida")
        
        # Very small value
        crud.create_variable_expense(db_session, {
            "place": "Coca-Cola",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 0.33,
            "paid_by": "FAFA",
            "category_name": comida_cat.name
        })
        
        balance = calculate_monthly_balance(db_session, month=5, year=2026)
        
        assert balance["total_expenses"] == 0.33

    def test_large_values(self, db_session):
        """Test with very large expense values."""
        from app.models import VariableCategory
        
        fafa = crud.create_user(db_session, name="LARGE_TEST_001", full_name="Fafa Large")
        
        casa_cat = crud.create_variable_category(db_session, "Casa")
        
        # Very large value (like a car payment)
        crud.create_variable_expense(db_session, {
            "place": "Financeira",
            "day": 5,
            "month": 5,
            "year": 2026,
            "value": 99999.99,
            "paid_by": "FAFA",
            "category_name": casa_cat.name
        })
        
        balance = calculate_monthly_balance(db_session, month=5, year=2026)
        
        assert abs(balance["total_expenses"] - 99999.99) < 0.01


class TestBalanceWithBothPaid:
    """Tests when both users paid for the same expense."""

    def test_both_paid_same_expense(self, db_session):
        """Test when both FAFA and FEFE paid for the same expense."""
        from app.models import VariableCategory
        
        fafa = crud.create_user(db_session, name="BOTH_TEST_001", full_name="Fafa Both")
        
        comida_cat = crud.create_variable_category(db_session, "Comida")
        
        # Both paid for the same R$ 300.00 expense
        # Fafa: R$ 200.00 (2/3)
        # Fefe: R$ 100.00 (1/3)
        crud.create_variable_expense(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 200.00,
            "paid_by": "FAFA",
            "category_name": comida_cat.name
        })
        
        crud.create_variable_expense(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.00,
            "paid_by": "FEFE",
            "category_name": comida_cat.name
        })
        
        balance = calculate_monthly_balance(db_session, month=5, year=2026)
        
        assert abs(balance["balance"]) < 0.01  # Equal payment
