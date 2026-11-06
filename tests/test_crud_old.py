"""
Tests for CRUD operations.
"""
import pytest
from app.database import get_session, init_db
from app import crud
from app.models import User, VariableCategory, RegularCategory


class TestUserCRUD:
    """Tests for user CRUD operations."""
    
    def test_create_user(self):
        """Test creating a user."""
        init_db()
        
        with get_session() as db:
            user = crud.create_user(db, name="TEST_USER", full_name="Test User")
            
            assert user.name == "TEST_USER"
            assert user.full_name == "Test User"
    
    def test_get_users(self):
        """Test getting all users."""
        init_db()
        
        with get_session() as db:
            # Create two users
            crud.create_user(db, name="USER_CRUD_28", full_name="User USER_CRUD_28")
            
            users = crud.get_users(db)
            
            assert len(users) == 2
            user_names = {u.name for u in users}
            assert "FAFA" in user_names
            assert "FEFE" in user_names
    
    def test_user_already_exists(self):
        """Test that creating duplicate user raises error."""
        init_db()
        
        with get_session() as db:
            # Create user first time
            crud.create_user(db, name="TEST", full_name="Test")
            
            # Try to create again should fail
            with pytest.raises(Exception):
                crud.create_user(db, name="TEST", full_name="Test2")


class TestVariableCategoryCRUD:
    """Tests for variable category CRUD operations."""
    
    def test_create_variable_category(self):
        """Test creating a variable category."""
        init_db()
        
        with get_session() as db:
            cat = crud.create_variable_category(db, "NovoGrupo")
            
            assert cat.name == "NovoGrupo"
    
    def test_get_variable_categories(self):
        """Test getting all variable categories."""
        init_db()
        
        with get_session() as db:
            # Create some categories
            for name in ["Comida", "Carro", "Lazer"]:
                crud.create_variable_category(db, name)
            
            cats = crud.get_variable_categories(db)
            
            assert len(cats) == 3


class TestRegularCategoryCRUD:
    """Tests for regular category CRUD operations."""
    
    def test_create_regular_category(self):
        """Test creating a regular category."""
        init_db()
        
        with get_session() as db:
            cat = crud.create_regular_category(db, "Aluguel")
            
            assert cat.name == "Aluguel"
    
    def test_get_regular_categories(self):
        """Test getting all regular categories."""
        init_db()
        
        with get_session() as db:
            # Create some categories
            for name in ["Aluguel", "Internet", "Cemig"]:
                crud.create_regular_category(db, name)
            
            cats = crud.get_regular_categories(db)
            
            assert len(cats) == 3


class TestVariableExpenseCRUD:
    """Tests for variable expense CRUD operations."""
    
    def test_create_variable_expense(self):
        """Test creating a variable expense."""
        init_db()
        
        with get_session() as db:
            # Setup: create user and category
            user = crud.create_user(db, name="USER_CRUD_112", full_name="User USER_CRUD_112")
            
            # Create expense
            expense = crud.create_variable_expense(db, {
                "place": "Mercado",
                "day": 15,
                "month": 5,
                "year": 2026,
                "value": 100.50,
                "paid_by": "FAFA",
                "category_name": "Comida"
            })
            
            assert expense.place == "Mercado"
            assert expense.value == 100.50
    
    def test_get_variable_expenses_no_filter(self):
        """Test getting all variable expenses."""
        init_db()
        
        with get_session() as db:
            user = crud.create_user(db, name="USER_CRUD_134")
            
            # Create multiple expenses
            for i in range(3):
                crud.create_variable_expense(db, {
                    "place": f"Mercado {i}",
                    "day": 10 + i,
                    "month": 5,
                    "year": 2026,
                    "value": 50.0,
                    "paid_by": "FAFA",
                    "category_name": "Comida"
                })
            
            expenses = crud.get_variable_expenses(db)
            
            assert len(expenses) == 3
    
    def test_get_variable_expenses_with_month_filter(self):
        """Test filtering variable expenses by month."""
        init_db()
        
        with get_session() as db:
            user = crud.create_user(db, name="USER_CRUD_158")
            
            # Create expenses in different months
            crud.create_variable_expense(db, {
                "place": "Jan",
                "day": 1,
                "month": 1,
                "year": 2026,
                "value": 50.0,
                "paid_by": "FAFA",
                "category_name": "Comida"
            })
            
            crud.create_variable_expense(db, {
                "place": "Mai",
                "day": 15,
                "month": 5,
                "year": 2026,
                "value": 100.0,
                "paid_by": "FAFA",
                "category_name": "Comida"
            })
            
            # Filter by month 5
            expenses = crud.get_variable_expenses(db, month=5)
            
            assert len(expenses) == 1
            assert expenses[0].place == "Mai"
    
    def test_get_variable_expenses_with_category_filter(self):
        """Test filtering variable expenses by category."""
        init_db()
        
        with get_session() as db:
            user = crud.create_user(db, name="USER_CRUD_193")
            # Create categories and expenses
            cat1 = crud.create_variable_category(db, "Comida")
            cat2 = crud.create_variable_category(db, "Carro")
            
            crud.create_variable_expense(db, {
                "place": "Mercado",
                "day": 1,
                "month": 5,
                "year": 2026,
                "value": 50.0,
                "paid_by": "FAFA",
                "category_name": "Comida"
            })
            
            crud.create_variable_expense(db, {
                "place": "Gas Station",
                "day": 15,
                "month": 5,
                "year": 2026,
                "value": 80.0,
                "paid_by": "FAFA",
                "category_name": "Carro"
            })
            
            # Filter by category
            expenses = crud.get_variable_expenses(db, category="Comida")
            
            assert len(expenses) == 1
            assert expenses[0].place == "Mercado"


class TestRegularExpenseCRUD:
    """Tests for regular expense CRUD operations."""
    
    def test_upsert_regular_expense_create(self):
        """Test creating a new regular expense (upsert as create)."""
        init_db()
        
        with get_session() as db:
            user = crud.create_user(db, name="USER_CRUD_234")
            
            # Upsert should create since it doesn't exist
            expense = crud.upsert_regular_expense(db, {
                "day": 5,
                "month": 5,
                "year": 2026,
                "value": 1500.00,
                "paid_by": "FAFA",
                "category_name": "Aluguel"
            })
            
            assert expense.value == 1500.00
    
    def test_upsert_regular_expense_update(self):
        """Test updating an existing regular expense (upsert as update)."""
        init_db()
        
        with get_session() as db:
            user = crud.create_user(db, name="USER_CRUD_254")
            
            # Create first expense
            expense1 = crud.upsert_regular_expense(db, {
                "day": 5,
                "month": 5,
                "year": 2026,
                "value": 1500.00,
                "paid_by": "FAFA",
                "category_name": "Aluguel"
            })
            
            # Update with same category+month (should update)
            expense2 = crud.upsert_regular_expense(db, {
                "day": 10,
                "month": 5,
                "year": 2026,
                "value": 2000.00,
                "paid_by": "FAFA",
                "category_name": "Aluguel"
            })
            
            # Should have same id (same expense updated)
            assert expense1.id == expense2.id
            assert expense2.value == 2000.00
    
    def test_get_regular_expenses(self):
        """Test getting regular expenses."""
        init_db()
        
        with get_session() as db:
            user = crud.create_user(db, name="USER_CRUD_286")
            
            # Create multiple expenses in different months
            for month in [1, 3, 5]:
                crud.upsert_regular_expense(db, {
                    "day": 5,
                    "month": month,
                    "year": 2026,
                    "value": 1500.0,
                    "paid_by": "FAFA",
                    "category_name": "Aluguel"
                })
            
            expenses = crud.get_regular_expenses(db)
            
            assert len(expenses) == 3


class TestMonthRatioCRUD:
    """Tests for month ratio CRUD operations."""
    
    def test_get_month_ratio_default(self):
        """Test getting month ratio returns default when not set."""
        init_db()
        
        with get_session() as db:
            ratio = crud.get_month_ratio(db, month=5, year=2026)
            
            assert ratio.fafa_ratio == pytest.approx(2/3)
    
    def test_set_month_ratio(self):
        """Test setting a custom month ratio."""
        init_db()
        
        with get_session() as db:
            # Set custom ratio
            result = crud.set_month_ratio(db, 5, 2026, 0.75)
            
            assert result.fafa_ratio == 0.75
            assert result.fefe_ratio == 0.25
    
    def test_get_month_ratio_custom(self):
        """Test getting a custom month ratio."""
        init_db()
        
        with get_session() as db:
            # Set and retrieve
            crud.set_month_ratio(db, 5, 2026, 0.75)
            ratio = crud.get_month_ratio(db, 5, 2026)
            
            assert ratio.fafa_ratio == 0.75
    
    def test_update_existing_month_ratio(self):
        """Test updating an existing month ratio."""
        init_db()
        
        with get_session() as db:
            # Set initial ratio
            crud.set_month_ratio(db, 5, 2026, 0.5)
            
            # Update it
            result = crud.set_month_ratio(db, 5, 2026, 0.8)
            
            assert result.fafa_ratio == 0.8


class TestAggregationCRUD:
    """Tests for aggregation functions."""
    
    def test_get_month_totals(self):
        """Test getting monthly totals."""
        init_db()
        
        with get_session() as db:
            user1 = crud.create_user(db, name="USER_CRUD_361")
            
            # Create variable expenses
            cat = crud.create_variable_category(db, "Comida")
            
            crud.create_variable_expense(db, {
                "place": "Mercado",
                "day": 10,
                "month": 5,
                "year": 2026,
                "value": 300.0,
                "paid_by": "FAFA",
                "category_name": "Comida"
            })
            
            crud.create_variable_expense(db, {
                "place": "Padaria",
                "day": 15,
                "month": 5,
                "year": 2026,
                "value": 100.0,
                "paid_by": "FEFE",
                "category_name": "Comida"
            })
            
            # Create regular expenses
            cat_reg = crud.create_regular_category(db, "Aluguel")
            
            crud.upsert_regular_expense(db, {
                "day": 5,
                "month": 5,
                "year": 2026,
                "value": 1500.0,
                "paid_by": "FAFA",
                "category_name": "Aluguel"
            })
            
            totals = crud.get_month_totals(db, 5, 2026)
            
            # Fafa paid: 300 + 1500 = 1800
            # Fefe paid: 100
            # Variable total: 400
            # Regular total: 1500
            assert totals["fafa_paid"] == 1800.0
            assert totals["fefe_paid"] == 100.0
            assert totals["variable_total"] == 400.0
            assert totals["regular_total"] == 1500.0
    
    def test_get_month_totals_empty(self):
        """Test getting totals for empty month."""
        init_db()
        
        with get_session() as db:
            totals = crud.get_month_totals(db, 12, 2026)
            
            assert totals["fafa_paid"] == 0.0
            assert totals["fefe_paid"] == 0.0
            assert totals["variable_total"] == 0.0
            assert totals["regular_total"] == 0.0
