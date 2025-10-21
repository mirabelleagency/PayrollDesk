import os
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up SQLite test database and initialize schema."""
    db_path = "./data/test_payroll.db"
    os.environ["PAYROLL_DATABASE_URL"] = f"sqlite:///{db_path}"
    
    # Import all models AFTER setting env var to ensure they use test DB
    from app import auth  # noqa: F401
    from app import models  # noqa: F401
    
    # Recreate engine with proper SQLite config
    from app.database import Base, engine, SessionLocal, init_db
    
    # For SQLite in testing, we need to enable foreign keys and use proper threading
    if "sqlite" in str(engine.url):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    
    # Create all tables
    Base.metadata.drop_all(bind=engine)  # Clean slate for tests
    Base.metadata.create_all(bind=engine)
    
    # Initialize database (creates admin user if not exists)
    init_db()
    
    yield
    
    # Cleanup after tests
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db():
    """Pytest configuration and fixtures for testing."""
    import os
    import pytest
    from sqlalchemy import event

    # Test database URL (file-based SQLite)
    TEST_DATABASE_URL = "sqlite:///./data/test_payroll.db"


    @pytest.fixture(scope="session", autouse=True)
    def setup_test_database():
        """Set the test database URL and initialize schema before tests run."""
        os.environ["PAYROLL_DATABASE_URL"] = TEST_DATABASE_URL

        # Import after setting env var so the app uses the test DB
        from app.database import Base, engine, init_db

        # For SQLite in testing, enable foreign keys
        if "sqlite" in str(engine.url):
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        # Create all tables and initialize default data
        Base.metadata.create_all(bind=engine)
        init_db()

        yield

        # Optionally drop tables after tests (commented out for inspection)
        # Base.metadata.drop_all(bind=engine)


    @pytest.fixture
    def test_db():
        """Provide a database session for each test."""
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()
