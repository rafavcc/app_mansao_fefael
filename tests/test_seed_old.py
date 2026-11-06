"""
Tests for seed functionality.
"""
import pytest
from app.database import get_session, init_db
from app import crud


class TestSeedFunctionality:
    """Tests to verify the seed data is correct."""
    
    def test_users_exist_after_seed(self):
        """Test that FAFA and FEFE users exist after seeding."""
        init_db()
        
        with get_session() as db:
            users = crud.get_users(db)
            
            user_names = {u.name for u in users}
            
            assert "FAFA" in user_names
            assert "FEFE" in user_names
    
    def test_variable_categories_exist_after_seed(self):
        """Test that all variable categories exist after seeding."""
        init_db()
        
        with get_session() as db:
            categories = crud.get_variable_categories(db)
            
            expected_categories = [
                "Carro", "Casa", "Comida", "Cartao", "Outros",
                "Faxina", "Gasolina", "Lazer", "Taxi", "Tomtom",
                "Bacana", "Viagem"
            ]
            
            category_names = {c.name for c in categories}
            
            for cat in expected_categories:
                assert cat in category_names, f"Missing category: {cat}"
    
    def test_regular_categories_exist_after_seed(self):
        """Test that all regular categories exist after seeding."""
        init_db()
        
        with get_session() as db:
            categories = crud.get_regular_categories(db)
            
            expected_categories = [
                "Aluguel", "Internet", "Cond", "Cemig",
                "ConsorcioMG", "IPTU"
            ]
            
            category_names = {c.name for c in categories}
            
            for cat in expected_categories:
                assert cat in category_names, f"Missing category: {cat}"
    
    def test_seed_is_idempotent(self):
        """Test that running seed multiple times is safe."""
        init_db()
        
        with get_session() as db:
            # Get initial counts
            initial_users = len(crud.get_users(db))
            initial_var_cats = len(crud.get_variable_categories(db))
            initial_reg_cats = len(crud.get_regular_categories(db))
            
            # Re-initialize (simulating a fresh seed)
            init_db()
            
            with get_session() as db:
                # Counts should remain the same
                final_users = len(crud.get_users(db))
                final_var_cats = len(crud.get_variable_categories(db))
                final_reg_cats = len(crud.get_regular_categories(db))
                
                assert initial_users == final_users
                assert initial_var_cats == final_var_cats
                assert initial_reg_cats == final_reg_cats
    
    def test_user_full_names_are_correct(self):
        """Test that user full names are set correctly."""
        init_db()
        
        with get_session() as db:
            users = crud.get_users(db)
            
            fafa_user = next(u for u in users if u.name == "FAFA")
            fefe_user = next(u for u in users if u.name == "FEFE")
            
            assert fafa_user.full_name == "Rafael Viegas"
            assert fefe_user.full_name == "Fernanda Lages"
