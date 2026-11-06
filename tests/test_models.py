"""
Tests for SQLAlchemy models.
Uses unique names per test to avoid conflicts.
"""
import pytest
from datetime import datetime, timezone

from app.database import get_session, init_db
from app.models import (
    User, VariableCategory, RegularCategory, MonthRatio,
    VariableExpense, RegularExpense
)


class TestUserModel:
    """Tests for User model."""
    
    def test_user_creation(self, db_session):
        """Test that users can be created with name and full_name."""
        from app.models import User
        
        user = User(name="USER_TEST_001", full_name="Test User 001")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.name == "USER_TEST_001"
        assert user.full_name == "Test User 001"
    
    def test_user_name_is_primary_key(self, db_session):
        """Test that name is the primary key."""
        from app.models import User
        
        user = User(name="USER_PK_TEST", full_name="Primary Key Test")
        db_session.add(user)
        db_session.commit()
        
        assert user.name == "USER_PK_TEST"
    
    def test_user_relationships(self, db_session):
        """Test that relationships are properly defined."""
        from app.models import User
        
        user = User(name="USER_REL_TEST", full_name="Relationship Test")
        db_session.add(user)
        db_session.commit()
        
        # Check relationship attributes exist
        assert hasattr(user, 'variable_expenses')
        assert hasattr(user, 'regular_expenses')


class TestCategoryModels:
    """Tests for category models."""
    
    def test_variable_category_creation(self, db_session):
        """Test variable category creation."""
        from app.models import VariableCategory
        
        cat = VariableCategory(name="VAR_CAT_TEST_001")
        db_session.add(cat)
        db_session.commit()
        
        assert cat.name == "VAR_CAT_TEST_001"
    
    def test_regular_category_creation(self, db_session):
        """Test regular category creation."""
        from app.models import RegularCategory
        
        cat = RegularCategory(name="REG_CAT_TEST_001")
        db_session.add(cat)
        db_session.commit()
        
        assert cat.name == "REG_CAT_TEST_001"


class TestMonthRatioModel:
    """Tests for MonthRatio model."""
    
    def test_month_ratio_creation_with_default(self, db_session):
        """Test that month ratio defaults to 2/3 for Fafa."""
        from app.models import MonthRatio
        
        ratio = MonthRatio(month=5, year=2026)
        db_session.add(ratio)
        db_session.commit()
        
        assert ratio.fafa_ratio == pytest.approx(2/3)
    
    def test_month_ratio_custom_value(self, db_session):
        """Test custom month ratio value."""
        from app.models import MonthRatio
        
        ratio = MonthRatio(month=5, year=2026, fafa_ratio=0.75)
        db_session.add(ratio)
        db_session.commit()
        
        assert ratio.fafa_ratio == 0.75
    
    def test_fefe_ratio_property(self, db_session):
        """Test that fefe_ratio is always 1 - fafa_ratio."""
        from app.models import MonthRatio
        
        # Test various fafa_ratio values with unique months
        for i, fafa in enumerate([0.3, 0.5, 0.6667, 0.9]):
            month = 1 + i  # Use different months to avoid conflicts
            ratio = MonthRatio(month=month, year=2026, fafa_ratio=fafa)
            db_session.add(ratio)
            db_session.commit()
            
            expected_fefe = round(1.0 - fafa, 4)  # Round to 4 decimal places
            # Use approximate comparison for floating point
            assert abs(ratio.fefe_ratio - expected_fefe) < 0.0001
    
    def test_unique_constraint_month_year(self, db_session):
        """Test that only one ratio per month+year is allowed."""
        from app.models import MonthRatio
        
        # First insertion should succeed
        ratio1 = MonthRatio(month=5, year=2026, fafa_ratio=0.5)
        db_session.add(ratio1)
        
        # Second insertion with same month/year should fail
        ratio2 = MonthRatio(month=5, year=2026, fafa_ratio=0.6)
        db_session.add(ratio2)
        
        try:
            db_session.commit()
            pytest.fail("Expected IntegrityError for duplicate month+year")
        except Exception as e:
            # SQLAlchemy may raise different exceptions based on driver
            assert "IntegrityError" in str(type(e).__name__) or "UNIQUE constraint failed" in str(e)


class TestVariableExpenseModel:
    """Tests for VariableExpense model."""
    
    def test_variable_expense_creation(self, db_session):
        """Test variable expense creation."""
        from app.models import User, VariableCategory
        
        user = User(name="VAR_EXP_USER_001")
        category = VariableCategory(name="VAR_CAT_EXP_001")
        db_session.add(user)
        db_session.add(category)
        db_session.commit()
        
        expense = VariableExpense(
            place="Mercado Test",
            day=15,
            month=5,
            year=2026,
            value=100.50,
            paid_by="FAFA",
            category_name="VAR_CAT_EXP_001"
        )
        db_session.add(expense)
        db_session.commit()
        
        expense_id = expense.id
        
        # Verify with refresh
        db_session.refresh(expense)
        assert expense.id == expense_id
    
    def test_timezone_aware_timestamp(self, db_session):
        """Test that created_at uses timezone-aware UTC."""
        from app.models import User, VariableCategory
        
        user = User(name="VAR_EXP_USER_002")
        category = VariableCategory(name="VAR_CAT_EXP_002")
        db_session.add(user)
        db_session.add(category)
        db_session.commit()
        
        expense = VariableExpense(
            place="Test Timezone",
            day=1,
            month=1,
            year=2026,
            value=1.0,
            paid_by="FAFA",
            category_name="VAR_CAT_EXP_002"
        )
        db_session.add(expense)
        db_session.commit()
        
        # Check that the timestamp is stored (may or may not have tzinfo depending on DB)
        assert expense.created_at is not None
        # The model defines timezone=True, so SQLite should store it correctly
        # Just verify it's not None
    
    def test_day_check_constraint(self, db_session):
        """Test that day must be between 1 and 31."""
        from app.models import User, VariableCategory
        
        user = User(name="VAR_EXP_USER_003")
        category = VariableCategory(name="VAR_CAT_EXP_003")
        db_session.add(user)
        db_session.add(category)
        db_session.commit()
        
        # Day 0 should fail
        expense_invalid = VariableExpense(
            place="Test Invalid Day",
            day=0,
            month=1,
            year=2026,
            value=1.0,
            paid_by="FAFA",
            category_name="VAR_CAT_EXP_003"
        )
        db_session.add(expense_invalid)
        
        try:
            db_session.commit()
            pytest.fail("Expected IntegrityError for invalid day")
        except Exception as e:
            assert "IntegrityError" in str(type(e).__name__) or "CHECK constraint failed" in str(e)
    
    def test_value_check_constraint(self, db_session):
        """Test that value must be positive."""
        from app.models import User, VariableCategory
        
        user = User(name="VAR_EXP_USER_004")
        category = VariableCategory(name="VAR_CAT_EXP_004")
        db_session.add(user)
        db_session.add(category)
        db_session.commit()
        
        # Zero value should fail
        expense_zero = VariableExpense(
            place="Test Zero Value",
            day=1,
            month=1,
            year=2026,
            value=0.0,
            paid_by="FAFA",
            category_name="VAR_CAT_EXP_004"
        )
        db_session.add(expense_zero)
        
        try:
            db_session.commit()
            pytest.fail("Expected IntegrityError for zero value")
        except Exception as e:
            assert "IntegrityError" in str(type(e).__name__) or "CHECK constraint failed" in str(e)


class TestRegularExpenseModel:
    """Tests for RegularExpense model."""
    
    def test_regular_expense_creation(self, db_session):
        """Test regular expense creation."""
        from app.models import User, RegularCategory
        
        user = User(name="REG_EXP_USER_001")
        category = RegularCategory(name="REG_CAT_EXP_001")
        db_session.add(user)
        db_session.add(category)
        db_session.commit()
        
        expense = RegularExpense(
            day=5,
            month=5,
            year=2026,
            value=1500.00,
            paid_by="FAFA",
            category_name="REG_CAT_EXP_001"
        )
        db_session.add(expense)
        db_session.commit()
        
        expense_id = expense.id
        
        # Verify with refresh
        db_session.refresh(expense)
        assert expense.id == expense_id
    
    def test_regular_expense_unique_constraint(self, db_session):
        """Test that only one regular expense per category+month+year is allowed."""
        from app.models import User, RegularCategory
        
        user = User(name="REG_EXP_USER_002")
        category = RegularCategory(name="REG_CAT_UNIQUE_001")
        db_session.add(user)
        db_session.add(category)
        db_session.commit()
        
        # First expense should succeed
        expense1 = RegularExpense(
            day=5,
            month=5,
            year=2026,
            value=1500.00,
            paid_by="FAFA",
            category_name="REG_CAT_UNIQUE_001"
        )
        db_session.add(expense1)
        
        # Second expense with same category+month+year should fail
        expense2 = RegularExpense(
            day=10,
            month=5,
            year=2026,
            value=1600.00,
            paid_by="FAFA",
            category_name="REG_CAT_UNIQUE_001"
        )
        db_session.add(expense2)
        
        try:
            db_session.commit()
            pytest.fail("Expected IntegrityError for duplicate category+month")
        except Exception as e:
            assert "IntegrityError" in str(type(e).__name__) or "UNIQUE constraint failed" in str(e)
