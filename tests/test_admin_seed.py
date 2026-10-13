"""The default admin is only created when there is no admin at all."""
from app.auth import User
from app.database import SessionLocal, init_db


def test_renamed_admin_is_not_recreated():
    session = SessionLocal()
    try:
        admin = session.query(User).filter(User.username == "admin").one()
        admin.username = "owner"
        session.commit()
    finally:
        session.close()

    try:
        init_db()  # what every restart runs
        session = SessionLocal()
        try:
            # Before: a fresh "admin" account was created on the next start.
            assert session.query(User).filter(User.username == "admin").first() is None
            assert session.query(User).filter(User.role == "admin").count() == 1
        finally:
            session.close()
    finally:
        session = SessionLocal()
        try:
            owner = session.query(User).filter(User.username == "owner").one()
            owner.username = "admin"
            session.commit()
        finally:
            session.close()


def test_admin_is_created_when_there_is_none():
    session = SessionLocal()
    try:
        admins = session.query(User).filter(User.role == "admin").all()
        originals = {a.id: a.username for a in admins}
        for a in admins:
            a.role = "user"
            a.username = f"former-{a.username}"
        session.commit()
        ids = list(originals)
    finally:
        session.close()
    try:
        init_db()
        session = SessionLocal()
        try:
            created = session.query(User).filter(User.role == "admin").all()
            assert len(created) == 1
            new_admin_id = created[0].id
            session.delete(created[0])
            session.commit()
        finally:
            session.close()
    finally:
        session = SessionLocal()
        try:
            for user in session.query(User).filter(User.id.in_(ids)):
                user.role = "admin"
                user.username = originals[user.id]
            session.commit()
        finally:
            session.close()
