"""Reset admin password to 'admin' for development."""
from app.auth import User
from app.database import SessionLocal

db = SessionLocal()

# Find admin user
admin_user = db.query(User).filter(User.username == 'admin').first()

if admin_user:
    # Reset password to 'admin'
    admin_user.password_hash = User.hash_password('admin')
    admin_user.is_locked = False
    admin_user.failed_login_count = 0
    admin_user.locked_until = None
    db.commit()
    print(f"✓ Reset admin password to 'admin'")
    print(f"  Username: admin")
    print(f"  Password: admin")
    print(f"  Locked: {admin_user.is_locked}")
else:
    # Create admin user
    admin_user = User(
        username='admin',
        password_hash=User.hash_password('admin'),
        role='admin',
        is_locked=False,
        failed_login_count=0
    )
    db.add(admin_user)
    db.commit()
    print("✓ Created admin user")
    print("  Username: admin")
    print("  Password: admin")

db.close()
