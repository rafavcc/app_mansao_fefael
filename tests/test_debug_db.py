"""Debug tests to investigate database issue."""
import pytest
from sqlalchemy import inspect, text


def test_debug_database(test_db):
    """Debug test to check if tables exist in test engine."""
    from app import models
    
    test_engine, test_SessionLocal = test_db
    
    # Check if tables exist
    inspector = inspect(test_engine)
    table_names = inspector.get_table_names()
    
    print(f"DEBUG: Tables in test engine: {table_names}")
    
    assert "variable_categories" in table_names, f"Table 'variable_categories' not found. Available tables: {table_names}"
    assert "regular_categories" in table_names, f"Table 'regular_categories' not found. Available tables: {table_names}"


def test_debug_database_query(test_db):
    """Debug test to check if we can query the database."""
    from app import crud
    
    test_engine, test_SessionLocal = test_db
    
    # Create a category using the test session
    db = test_SessionLocal()
    try:
        crud.create_variable_category(db, "Test_Category")
        
        # Verify it was created
        result = db.execute(text("SELECT name FROM variable_categories"))
        rows = result.fetchall()
        
        print(f"DEBUG: Found {len(rows)} rows in variable_categories")
        assert len(rows) == 1
        
    finally:
        db.close()
