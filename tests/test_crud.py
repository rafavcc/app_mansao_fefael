"""
Tests for CRUD operations.
Uses db_session fixture to avoid conflicts.
"""
import pytest
from app import crud


class TestUserCRUD:
    """Tests for user CRUD operations."""

    def test_create_user(self, db_session):
        """Test creating a user."""
        user = crud.create_user(db_session, name="TEST_USER_001", full_name="Test User 001")

        assert user.name == "TEST_USER_001"
        assert user.full_name == "Test User 001"

    def test_get_users(self, db_session):
        """Test getting all users."""
        # Create two users
        crud.create_user(db_session, name="USER_CRUD_28", full_name="User USER_CRUD_28")
        
        users = crud.get_users(db_session)

        assert len(users) == 1
        user_names = {u.name for u in users}
        assert "USER_CRUD_28" in user_names

    def test_user_already_exists(self, db_session):
        """Test that creating duplicate user raises error."""
        # Create user first time
        crud.create_user(db_session, name="TEST", full_name="Test")

        # Try to create again should fail
        with pytest.raises(Exception):
            crud.create_user(db_session, name="TEST", full_name="Test2")


class TestVariableCategoryCRUD:
    """Tests for variable category CRUD operations."""

    def test_create_variable_category(self, db_session):
        """Test creating a variable category."""
        cat = crud.create_variable_category(db_session, "Comida")

        assert cat.name == "Comida"
        assert cat.is_variable is True

    def test_get_variable_categories(self, db_session):
        """Test getting all variable categories."""
        # Create two categories
        crud.create_variable_category(db_session, "Comida")
        crud.create_variable_category(db_session, "Casa")

        cats = crud.get_variable_categories(db_session)

        assert len(cats) == 2
        cat_names = {c.name for c in cats}
        assert "Comida" in cat_names
        assert "Casa" in cat_names


class TestRegularCategoryCRUD:
    """Tests for regular category CRUD operations."""

    def test_create_regular_category(self, db_session):
        """Test creating a regular category."""
        cat = crud.create_regular_category(db_session, "Aluguel")

        assert cat.name == "Aluguel"
        assert cat.is_variable is False

    def test_get_regular_categories(self, db_session):
        """Test getting all regular categories."""
        # Create two categories
        crud.create_regular_category(db_session, "Aluguel")
        crud.create_regular_category(db_session, "Internet")

        cats = crud.get_regular_categories(db_session)

        assert len(cats) == 2
        cat_names = {c.name for c in cats}
        assert "Aluguel" in cat_names
        assert "Internet" in cat_names


class TestVariableExpenseCRUD:
    """Tests for variable expense CRUD operations."""

    def test_create_variable_expense(self, db_session):
        """Test creating a variable expense."""
        from app.models import VariableCategory

        cat = crud.create_variable_category(db_session, "Comida")
        
        expense = crud.create_variable_expense(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.00,
            "paid_by": "FAFA",
            "category_name": cat.name
        })

        assert expense.place == "Mercado"
        assert expense.value == 100.00
        assert expense.paid_by == "FAFA"

    def test_get_variable_expenses_with_filter(self, db_session):
        """Test getting variable expenses with date filter."""
        from app.models import VariableCategory

        cat = crud.create_variable_category(db_session, "Comida")
        
        # Create expense in May 2026
        crud.create_variable_expense(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.00,
            "paid_by": "FAFA",
            "category_name": cat.name
        })

        # Filter for May 2026
        expenses = crud.get_variable_expenses(db_session, year=2026, month=5)

        assert len(expenses) == 1
        assert expenses[0].month == 5

    def test_get_variable_expenses_no_filter(self, db_session):
        """Test getting all variable expenses without filter."""
        from app.models import VariableCategory

        cat = crud.create_variable_category(db_session, "Comida")
        
        # Create one expense
        crud.create_variable_expense(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.00,
            "paid_by": "FAFA",
            "category_name": cat.name
        })

        # Get all expenses (should be just the one we created)
        expenses = crud.get_variable_expenses(db_session)

        assert len(expenses) == 1


class TestRegularExpenseCRUD:
    """Tests for regular expense CRUD operations."""

    def test_upsert_regular_expense(self, db_session):
        """Test upserting a regular expense."""
        from app.models import RegularCategory

        cat = crud.create_regular_category(db_session, "Aluguel")
        
        # Create expense
        expense = crud.upsert_regular_expense(db_session, {
            "day": 5,
            "month": 5,
            "year": 2026,
            "value": 1500.00,
            "paid_by": "FAFA",
            "category_name": cat.name
        })

        assert expense.value == 1500.00

    def test_upsert_regular_expense_update(self, db_session):
        """Test updating an existing regular expense."""
        from app.models import RegularCategory

        cat = crud.create_regular_category(db_session, "Aluguel")
        
        # Create expense with value 1500
        crud.upsert_regular_expense(db_session, {
            "day": 5,
            "month": 5,
            "year": 2026,
            "value": 1500.00,
            "paid_by": "FAFA",
            "category_name": cat.name
        })

        # Update the same expense with value 2000
        crud.upsert_regular_expense(db_session, {
            "day": 5,
            "month": 5,
            "year": 2026,
            "value": 2000.00,
            "paid_by": "FAFA",
            "category_name": cat.name
        })

        # Get and verify updated expense
        expenses = crud.get_regular_expenses(db_session)
        assert len(expenses) == 1
        assert expenses[0].value == 2000.00


class TestMonthRatioCRUD:
    """Tests for month ratio CRUD operations."""

    def test_set_month_ratio(self, db_session):
        """Test setting a custom ratio for a month."""
        from app.models import User

        fafa = crud.create_user(db_session, name="FAFA_RATIO_001", full_name="Fafa Ratio")
        
        # Set custom ratio: 50/50
        result = crud.set_month_ratio(db_session, month=5, year=2026, fafa=0.5)

        assert result is True

    def test_get_month_ratios(self, db_session):
        """Test getting month ratios."""
        from app.models import User

        fafa = crud.create_user(db_session, name="FAFA_RATIO_002", full_name="Fafa Ratio")
        
        # Set custom ratio
        crud.set_month_ratio(db_session, month=5, year=2026, fafa=0.5)

        # Get ratios for May 2026
        ratios = crud.get_month_ratios(db_session, month=5, year=2026)

        assert len(ratios) == 1
        assert abs(ratios[0].fafa_ratio - 0.5) < 0.01


class TestPaymentCRUD:
    """Tests for payment CRUD operations."""

    def test_create_payment(self, db_session):
        """Test creating a payment."""
        from app.models import User, VariableCategory

        fafa = crud.create_user(db_session, name="FAFA_PAY_001", full_name="Fafa Pay")
        cat = crud.create_variable_category(db_session, "Comida")
        
        payment = crud.create_payment(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.00,
            "paid_by": fafa.name,
            "category_name": cat.name
        })

        assert payment.place == "Mercado"
        assert payment.value == 100.00
        assert payment.paid_by == fafa.name

    def test_get_payments(self, db_session):
        """Test getting all payments."""
        from app.models import User, VariableCategory

        fafa = crud.create_user(db_session, name="FAFA_PAY_002", full_name="Fafa Pay")
        cat = crud.create_variable_category(db_session, "Comida")
        
        # Create two payments
        crud.create_payment(db_session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.00,
            "paid_by": fafa.name,
            "category_name": cat.name
        })
        
        crud.create_payment(db_session, {
            "place": "Padaria",
            "day": 20,
            "month": 5,
            "year": 2026,
            "value": 50.00,
            "paid_by": fafa.name,
            "category_name": cat.name
        })

        payments = crud.get_payments(db_session)

        assert len(payments) == 2
