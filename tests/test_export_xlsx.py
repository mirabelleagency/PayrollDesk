from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_session
from app.auth import User
from app.routers.auth import get_current_user


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


@contextmanager
def _override_dependencies(session, user):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_export_xlsx_requires_admin():
    session = _make_db()

    # create a non-admin user and a fake dependency
    user = User.create_user("normal", "password", role="user")
    session.add(user)
    session.commit()

    with _override_dependencies(session, user):
        client = TestClient(app)
        resp = client.get("/dashboard/export-xlsx")
        assert resp.status_code == 403


def test_export_xlsx_admin():
    session = _make_db()

    user = User.create_user("admin", "password", role="admin")
    session.add(user)
    session.commit()

    with _override_dependencies(session, user):
        client = TestClient(app)
        resp = client.get("/dashboard/export-xlsx")
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
