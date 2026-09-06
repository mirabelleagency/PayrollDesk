import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "payroll.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print("tables:", [r[0] for r in cur.fetchall()])
cur.execute("PRAGMA table_info(schedule_runs)")
print("schedule_runs:", [r[1] for r in cur.fetchall()])
cur.execute("PRAGMA table_info(payouts)")
print("payouts:", [r[1] for r in cur.fetchall()])
cur.execute("PRAGMA table_info(models)")
print("models:", [r[1] for r in cur.fetchall()])
cur.execute("SELECT * FROM alembic_version")
print("alembic_version rows:", cur.fetchall())
conn.close()
