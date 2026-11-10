"""
Pytest configuration and fixtures for Mansao Fefael tests.
Uses SQLite in-memory database with separate connection per test.

IMPORTANT: This file must NOT import any app modules at the top level,
as that would trigger FastAPI initialization before fixtures run.
All imports are done inside fixture functions when needed.
"""
import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# No imports from app here! All imports must be inside fixtures.

# Tests must never touch the real casa.db, its backups or its logs. These variables are read by
# app.database when it is first imported, so they have to be set before any test imports the app.
_SANDBOX = tempfile.mkdtemp(prefix="casa_tests_")
os.environ["CASA_DB_PATH"] = os.path.join(_SANDBOX, "casa.db")
os.environ["CASA_LOG_DIR"] = os.path.join(_SANDBOX, "logs")


def pytest_sessionstart(session):
    """Abort the whole run if the app would still point at anything outside the sandbox."""
    from app import database

    if not str(database.DB_PATH).startswith(_SANDBOX):
        pytest.exit(f"Refusing to run: database points to {database.DB_PATH}, not the test sandbox", returncode=2)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_SANDBOX, ignore_errors=True)


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh in-memory SQLite database for each test."""
    # Set TESTING environment variable to prevent init_db() from being called in lifespan
    import os
    original_testing = os.environ.get("TESTING")
    os.environ["TESTING"] = "1"
    
    try:
        # Use a file-based database instead of :memory: to ensure all connections use the same DB
        # This avoids the issue where each create_engine(":memory:") creates a separate DB
        import tempfile
        import shutil
        
        # Create a temporary database file
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test.db")
        
        engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        
        # Create all tables BEFORE importing app modules
        from app import models
        
        models.Base.metadata.create_all(bind=engine)
        
        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        yield engine, SessionLocal, temp_dir
        
        # Cleanup - drop all tables and remove temp files
        models.Base.metadata.drop_all(bind=engine)
        shutil.rmtree(temp_dir, ignore_errors=True)
    finally:
        # Restore original TESTING value
        if original_testing is None:
            del os.environ["TESTING"]
        else:
            os.environ["TESTING"] = original_testing


@pytest.fixture(scope="function")
def db_session(test_db):
    """Provide a fresh database session for each test."""
    from app import database
    
    engine, SessionLocal, _ = test_db
    db = SessionLocal()
    try:
        yield db
        # Rollback on test failure to keep tests isolated
        db.rollback()
    finally:
        db.close()


def _seed_reference_data(session_factory):
    """Users and categories the API tests expect to exist, same lists the real seed uses."""
    from app import crud
    from app.seed import REGULAR_CATEGORIES, VARIABLE_CATEGORIES

    with session_factory() as db:
        crud.create_user(db, "FAFA", "Rafael Viegas")
        crud.create_user(db, "FEFE", "Fernanda Lages")
        for name in VARIABLE_CATEGORIES:
            crud.create_variable_category(db, name)
        for name in REGULAR_CATEGORIES:
            crud.create_regular_category(db, name)


@pytest.fixture(scope="function")
def client(test_db):
    """Create a FastAPI test client with our test database."""
    from app import main, database
    
    # Get our test engine and sessionmaker directly from test_db fixture
    test_engine, test_SessionLocal, temp_dir = test_db
    
    # Save original references
    original_engine = database.engine
    original_SessionLocal = database.SessionLocal
    original_get_db = database.get_db
    
    # Replace get_db to use our test engine directly (don't replace database.engine)
    def override_get_db():
        db = test_SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    # Set the dependency override in the app BEFORE creating TestClient
    main.app.dependency_overrides[original_get_db] = override_get_db
    
    _seed_reference_data(test_SessionLocal)

    # Create TestClient for FastAPI - it will use our overridden get_db
    test_client = TestClient(main.app)
    
    yield test_client
    
    # Clean up the override after test and restore original references
    main.app.dependency_overrides.clear()
    database.get_db = original_get_db


@pytest.fixture(scope="function")
def client_with_session(test_db):
    """Create a FastAPI test client with access to the database session."""
    from app import main, database
    
    # Get our test engine and sessionmaker directly from test_db fixture
    test_engine, test_SessionLocal, temp_dir = test_db
    
    # Save original references
    original_engine = database.engine
    original_SessionLocal = database.SessionLocal
    original_get_db = database.get_db
    
    # Replace get_db to use our test engine directly (don't replace database.engine)
    def override_get_db():
        db = test_SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    # Set the dependency override in the app BEFORE creating TestClient
    main.app.dependency_overrides[original_get_db] = override_get_db
    
    # Create TestClient for FastAPI - it will use our overridden get_db
    test_client = TestClient(main.app)
    
    yield test_client, test_engine, test_SessionLocal
    
    # Clean up the override after test and restore original references
    main.app.dependency_overrides.clear()
    database.get_db = original_get_db


@pytest.fixture(scope="function")
def client_session(client_with_session):
    """Get the database session from the test client."""
    _, _, SessionLocal = client_with_session
    db = SessionLocal()
    yield db
    db.close()


# User fixtures with unique names to avoid conflicts
@pytest.fixture(scope="function")
def user(db_session):
    """Create a test user with unique name."""
    from app.models import User
    from app import crud
    
    with db_session as session:
        # Generate unique name using timestamp
        import time
        unique_id = f"USER_{int(time.time() * 1000)}"
        user = crud.create_user(session, name=unique_id, full_name=f"Test User {unique_id}")
        return user


@pytest.fixture(scope="function")
def fefe_user(db_session):
    """Create a test user with unique name."""
    from app.models import User
    from app import crud
    
    with db_session as session:
        # Generate unique name using timestamp
        import time
        unique_id = f"USER_{int(time.time() * 1000)}_FEFE"
        user = crud.create_user(session, name=unique_id, full_name=f"Fefe Test {unique_id}")
        return user


# Category fixtures
@pytest.fixture(scope="function")
def categories(db_session):
    """Create some test categories."""
    from app.models import VariableCategory, RegularCategory
    from app import crud
    
    with db_session as session:
        comida = crud.create_variable_category(session, "Comida_TEST")
        casa = crud.create_variable_category(session, "Casa_TEST")
        aluguel = crud.create_regular_category(session, "Aluguel_TEST")
        internet = crud.create_regular_category(session, "Internet_TEST")
        
        return {
            "variable": [comida, casa],
            "regular": [aluguel, internet]
        }


@pytest.fixture(scope="function")
def sample_data(db_session, categories):
    """Create some sample data for testing."""
    from app.models import VariableExpense, RegularExpense, User
    from app import crud
    
    with db_session as session:
        # Create users
        fafa = crud.create_user(session, name="FAFA_SAMPLE", full_name="Fafa Sample")
        fefe = crud.create_user(session, name="FEFE_SAMPLE", full_name="Fefe Sample")
        
        # Create some variable expenses
        var_exp1 = crud.create_variable_expense(session, {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 200.00,
            "paid_by": fafa.name,
            "category_name": categories["variable"][0].name
        })
        
        var_exp2 = crud.create_variable_expense(session, {
            "place": "Padaria",
            "day": 10,
            "month": 5,
            "year": 2026,
            "value": 100.00,
            "paid_by": fefe.name,
            "category_name": categories["variable"][0].name
        })
        
        # Create some regular expenses
        reg_exp1 = crud.upsert_regular_expense(session, {
            "day": 5,
            "month": 5,
            "year": 2026,
            "value": 1500.00,
            "paid_by": fafa.name,
            "category_name": categories["regular"][0].name
        })
        
        return {
            "users": [fafa, fefe],
            "variable_expenses": [var_exp1, var_exp2],
            "regular_expenses": [reg_exp1]
        }


@pytest.fixture(scope="function")
def sample_balance_data(db_session):
    """Create a specific set of data for balance calculations."""
    from app.models import User, VariableCategory, RegularCategory
    from app import crud
    
    with db_session as session:
        # Create users with unique names
        import time
        fafa_id = f"FAFA_{int(time.time() * 1000)}"
        fefe_id = f"FEFE_{int(time.time() * 1000)}"
        
        fafa = crud.create_user(session, name=fafa_id, full_name=f"Fafa {fafa_id}")
        fefe = crud.create_user(session, name=fefe_id, full_name=f"Fefe {fefe_id}")
