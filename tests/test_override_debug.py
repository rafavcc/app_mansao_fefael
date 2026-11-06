"""Test to debug the override_get_db behavior."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def test_override(test_db):
    """Test fixture that checks if override works."""
    from app import main, database
    
    test_engine, test_SessionLocal = test_db
    
    # Save original references
    original_get_db = database.get_db
    
    # Create a new get_db that uses our test engine directly
    def override_get_db():
        db = test_SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    # Set the dependency override in the app BEFORE creating TestClient
    main.app.dependency_overrides[original_get_db] = override_get_db
    
    yield test_engine, test_SessionLocal
    
    # Clean up
    main.app.dependency_overrides.clear()


def test_override_returns_correct_engine(test_override):
    """Test that override_get_db returns a connection from the correct engine."""
    test_engine, test_SessionLocal = test_override
    
    # Create a session using our override
    db = test_SessionLocal()
    
    # Check the bind (engine) of this session
    print(f"DEBUG: Session bind URL: {db.bind.url}")
    print(f"DEBUG: Test engine URL: {test_engine.url}")
    
    assert db.bind.url == test_engine.url, f"Session uses different engine! Got {db.bind.url}, expected {test_engine.url}"


def test_override_can_create_table(test_override):
    """Test that we can create a table using the override."""
    from app import crud
    
    test_engine, test_SessionLocal = test_override
    
    # Create a session
    db = test_SessionLocal()
    
    try:
        # Try to create a category
        result = crud.create_variable_category(db, "Test_OVERRIDE")
        
        print(f"DEBUG: Created category {result.name}")
        assert result.name == "Test_OVERRIDE"
    finally:
        db.close()


def test_override_can_query_table(test_override):
    """Test that we can query the table using the override."""
    from sqlalchemy import text
    
    test_engine, test_SessionLocal = test_override
    
    # Create a session
    db = test_SessionLocal()
    
    try:
        # Query the table
        result = db.execute(text("SELECT name FROM variable_categories"))
        rows = result.fetchall()
        
        print(f"DEBUG: Found {len(rows)} rows")
        assert len(rows) > 0, "No rows found in variable_categories"
    finally:
        db.close()
