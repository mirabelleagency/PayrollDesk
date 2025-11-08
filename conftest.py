import os
import shutil
import tempfile
import pytest
from sqlalchemy import event

# Create a temporary SQLite database file for the whole test session
_TEMP_DIR = tempfile.mkdtemp(prefix="payroll_tests_")
_DB_FILE = os.path.join(_TEMP_DIR, "test_payroll.db")
os.environ["PAYROLL_DATABASE_URL"] = f"sqlite:///{_DB_FILE}"


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initialize a fresh temporary SQLite database for tests and clean it up after."""
    # Import after setting env var so the app uses the temp DB
    from app.database import Base, engine, init_db

    # Enable SQLite foreign keys
    if "sqlite" in str(engine.url):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Create schema and seed admin
    Base.metadata.create_all(bind=engine)
    init_db()

    yield

    # Dispose engine and remove temp directory
    try:
        engine.dispose()
    except Exception:
        pass
    shutil.rmtree(_TEMP_DIR, ignore_errors=True)


# Function-scope autouse fixture to ensure each test starts with a clean domain state.
# This prevents data leakage (payouts, models, runs, adhoc payments, etc.) between tests
# while preserving user accounts for authentication-related tests.
@pytest.fixture(autouse=True)
def _clean_domain_tables():
    from app import crud
    from app.database import SessionLocal
    session = SessionLocal()
    try:
        crud.reset_application_data(session)
    finally:
        try:
            session.close()
        except Exception:
            pass


@pytest.fixture
def test_db():
    """Provide a database session for each test with automatic rollback."""
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        try:
            session.rollback()
        except Exception:
            pass
        session.close()
