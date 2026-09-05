import os
import shutil
import tempfile
import pytest

# Create a temporary SQLite database file for the whole test session
_TEMP_DIR = tempfile.mkdtemp(prefix="payroll_tests_")
_DB_FILE = os.path.join(_TEMP_DIR, "test_payroll.db")
os.environ["PAYROLL_DATABASE_URL"] = f"sqlite:///{_DB_FILE}"
os.environ["ENVIRONMENT"] = "test"
os.environ["SESSION_SECRET"] = "test-session-secret-for-pytest-only"
os.environ["API_RATE_SECRET"] = "test-rate-secret-for-pytest-only-32chars"
os.environ["API_CURSOR_SECRET"] = "test-cursor-secret-for-pytest-32c"


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initialize a fresh temporary SQLite database for tests and clean it up after."""
    # Import after setting env var so the app uses the temp DB
    from app.database import engine, init_db
    from app.migrations import upgrade

    upgrade(engine)
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
    from app.models import ApiKey
    session = SessionLocal()
    try:
        crud.reset_application_data(session)
        session.query(ApiKey).delete(synchronize_session=False)
        session.commit()
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
