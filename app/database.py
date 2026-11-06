from contextlib import contextmanager
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./casa.db"

engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """
    Fast API dependency: fetches a database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    _rebuild_planned_expenses()


def _add_missing_columns():
    """create_all does not alter existing tables; add columns introduced after a table was created."""
    new_columns = {
        "income_items": {
            "is_gross": "BOOLEAN NOT NULL DEFAULT 0",
            "dependents": "INTEGER NOT NULL DEFAULT 0",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in new_columns.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

def _rebuild_planned_expenses():
    """Drop the old kind column and the foreign key on category_name (SQLite cannot alter them in place)."""
    if "kind" not in {c["name"] for c in inspect(engine).get_columns("planned_expenses")}:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE planned_expenses RENAME TO planned_expenses_old"))
        conn.execute(text(
            "CREATE TABLE planned_expenses ("
            "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
            "description VARCHAR NOT NULL, value FLOAT NOT NULL, category_name VARCHAR NOT NULL, "
            "CONSTRAINT ck_planned_value CHECK (value > 0))"
        ))
        conn.execute(text(
            "INSERT INTO planned_expenses (id, description, value, category_name) "
            "SELECT id, description, value, category_name FROM planned_expenses_old"
        ))
        conn.execute(text("DROP TABLE planned_expenses_old"))

@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

