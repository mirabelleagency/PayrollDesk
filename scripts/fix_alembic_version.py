"""Script to fix alembic version and create the compensation alerts table."""
from sqlalchemy import create_engine, text

DATABASE_URL = "sqlite:///data/payroll.db"

def main():
    e = create_engine(DATABASE_URL)
    with e.connect() as conn:
        # First, clear any existing version entries
        conn.execute(text("DELETE FROM alembic_version"))
        
        # Insert the target version
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('fe8ae1eb2e95')"))
        conn.commit()
        
        print("Alembic version set to: fe8ae1eb2e95")
        print("Current version:", conn.execute(text("SELECT * FROM alembic_version")).fetchall())
        
        # Check if payout_compensation_alerts table exists
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='payout_compensation_alerts'"
        )).fetchone()
        
        if result:
            print("Table payout_compensation_alerts already exists")
        else:
            print("Creating payout_compensation_alerts table...")
            conn.execute(text("""
                CREATE TABLE payout_compensation_alerts (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    payout_id INTEGER NOT NULL,
                    model_id INTEGER NOT NULL,
                    schedule_run_id INTEGER NOT NULL,
                    original_amount NUMERIC(12, 2) NOT NULL,
                    new_amount NUMERIC(12, 2) NOT NULL,
                    prorated_amount NUMERIC(12, 2),
                    effective_date DATE NOT NULL,
                    alert_type VARCHAR(30) NOT NULL DEFAULT 'compensation_changed',
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    notes TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    resolved_at DATETIME,
                    resolved_by VARCHAR(100),
                    FOREIGN KEY(payout_id) REFERENCES payouts (id) ON DELETE CASCADE,
                    FOREIGN KEY(model_id) REFERENCES models (id) ON DELETE CASCADE,
                    FOREIGN KEY(schedule_run_id) REFERENCES schedule_runs (id) ON DELETE CASCADE,
                    UNIQUE (payout_id, effective_date),
                    CHECK (alert_type IN ('compensation_changed', 'new_adjustment')),
                    CHECK (status IN ('pending', 'acknowledged', 'applied', 'dismissed'))
                )
            """))
            
            # Create indexes
            conn.execute(text("CREATE INDEX ix_payout_compensation_alerts_payout_id ON payout_compensation_alerts (payout_id)"))
            conn.execute(text("CREATE INDEX ix_payout_compensation_alerts_model_id ON payout_compensation_alerts (model_id)"))
            conn.execute(text("CREATE INDEX ix_payout_compensation_alerts_schedule_run_id ON payout_compensation_alerts (schedule_run_id)"))
            conn.execute(text("CREATE INDEX ix_payout_compensation_alerts_status ON payout_compensation_alerts (status)"))
            
            conn.commit()
            print("Table payout_compensation_alerts created successfully")

if __name__ == "__main__":
    main()
