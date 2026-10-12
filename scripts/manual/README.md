# Manual login checks

Scripts that drive a **running** PayrollDesk over HTTP (`http://127.0.0.1:8000`)
to exercise login, lockout and admin unlock. They run at import time and need a
live server, so they live outside `tests/` where pytest would collect them and
fail. Start the app, then run one directly:

    python scripts/manual/test_login.py
