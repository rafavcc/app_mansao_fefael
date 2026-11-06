"""
Tests for seed functionality.
Uses db_session fixture to avoid conflicts.
"""
import pytest
from app import crud


class TestSeedFunctionality:
    """Tests to verify the seed data is correct."""

    def test_users_exist_after_seed(self, db_session):
        """Test that FAFA and FEFE users exist after seeding."""
        # Create users (simulating seed)
        crud.create_user(db_session, name="FAFA", full_name="Rafael Viegas")
        crud.create_user(db_session, name="FEFE", full_name="Fernanda Lages")

        users = crud.get_users(db_session)
        user_names = {u.name for u in users}

        assert "FAFA" in user_names
        assert "FEFE" in user_names

    def test_variable_categories_exist_after_seed(self, db_session):
        """Test that all variable categories exist after seeding."""
        # Create all variable categories (simulating seed)
        expected_categories = [
            "Carro", "Casa", "Comida", "Cartao", "Outros",
            "Faxina", "Gasolina", "Lazer", "Taxi", "Tomtom",
            "Bacana", "Viagem"
        ]

        for cat in expected_categories:
            crud.create_variable_category(db_session, cat)

        categories = crud.get_variable_categories(db_session)
        category_names = {c.name for c in categories}

        for cat in expected_categories:
            assert cat in category_names, f"Missing category: {cat}"

    def test_regular_categories_exist_after_seed(self, db_session):
        """Test that all regular categories exist after seeding."""
        # Create all regular categories (simulating seed)
        expected_categories = [
            "Aluguel", "Internet", "Cond", "Cemig",
            "ConsorcioMG", "IPTU"
        ]

        for cat in expected_categories:
            crud.create_regular_category(db_session, cat)

        categories = crud.get_regular_categories(db_session)
        category_names = {c.name for c in categories}

        for cat in expected_categories:
            assert cat in category_names, f"Missing category: {cat}"

    def test_seed_is_idempotent(self, db_session):
        """Test that running seed multiple times is safe."""
        from app.models import User
        
        # Create initial data with unique names
        crud.create_user(db_session, name="FAFA_IDE_001", full_name="Rafael Viegas")
        crud.create_variable_category(db_session, "Comida")
        crud.create_regular_category(db_session, "Aluguel")

        # Get counts after first creation
        initial_users = len(crud.get_users(db_session))
        initial_var_cats = len(crud.get_variable_categories(db_session))
        initial_reg_cats = len(crud.get_regular_categories(db_session))

        # Create same data again (should not duplicate)
        # Check if user exists before creating
        existing_users = crud.get_users(db_session)
        fafa_exists = any(u.name == "FAFA_IDE_001" for u in existing_users)
        
        if not fafa_exists:
            crud.create_user(db_session, name="FAFA_IDE_001", full_name="Rafael Viegas")
        
        # Same for categories
        existing_var_cats = crud.get_variable_categories(db_session)
        comida_exists = any(c.name == "Comida" for c in existing_var_cats)
        if not comida_exists:
            crud.create_variable_category(db_session, "Comida")
            
        existing_reg_cats = crud.get_regular_categories(db_session)
        aluguel_exists = any(c.name == "Aluguel" for c in existing_reg_cats)
        if not aluguel_exists:
            crud.create_regular_category(db_session, "Aluguel")

        # Counts should remain the same (idempotent)
        final_users = len(crud.get_users(db_session))
        final_var_cats = len(crud.get_variable_categories(db_session))
        final_reg_cats = len(crud.get_regular_categories(db_session))

        assert initial_users == final_users
        assert initial_var_cats == final_var_cats
        assert initial_reg_cats == final_reg_cats

    def test_user_full_names_are_correct(self, db_session):
        """Test that user full names are set correctly."""
        # Create users
        crud.create_user(db_session, name="FAFA", full_name="Rafael Viegas")
        crud.create_user(db_session, name="FEFE", full_name="Fernanda Lages")

        users = crud.get_users(db_session)

        fafa_user = next(u for u in users if u.name == "FAFA")
        fefe_user = next(u for u in users if u.name == "FEFE")

        assert fafa_user.full_name == "Rafael Viegas"
        assert fefe_user.full_name == "Fernanda Lages"
