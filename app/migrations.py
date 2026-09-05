"""Versioned database migrations with advisory locking."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Callable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

SCHEMA_VERSION = 15

MigrationFn = Callable[[Connection, Engine], None]


def _table_exists(conn: Connection, name: str) -> bool:
    return name in inspect(conn).get_table_names()


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    cols = {c["name"] for c in inspect(conn).get_columns(table)}
    return column in cols


def _add_column(conn: Connection, table: str, ddl: str) -> None:
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def _migration_001_bootstrap(conn: Connection, engine: Engine) -> None:
    from app.database import Base
    from app import models  # noqa: F401
    from app.auth import User  # noqa: F401

    Base.metadata.create_all(bind=conn, checkfirst=True)


def _migration_002_legacy_columns(conn: Connection, engine: Engine) -> None:
    is_postgres = engine.dialect.name == "postgresql"
    datetime_type = "TIMESTAMP" if is_postgres else "DATETIME"

    if _table_exists(conn, "users"):
        if _column_exists(conn, "users", "is_active"):
            conn.execute(text("ALTER TABLE users DROP COLUMN is_active"))
        if not _column_exists(conn, "users", "role"):
            _add_column(conn, "users", "role VARCHAR(50) NOT NULL DEFAULT 'user'")
        conn.execute(text("UPDATE users SET role = 'admin' WHERE username = 'admin' AND role != 'admin'"))
        conn.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL"))
        if not _column_exists(conn, "users", "is_locked"):
            _add_column(conn, "users", "is_locked BOOLEAN NOT NULL DEFAULT false")
            _add_column(conn, "users", f"locked_until {datetime_type}")
            _add_column(conn, "users", "failed_login_count INTEGER NOT NULL DEFAULT 0")
            _add_column(conn, "users", f"last_failed_login {datetime_type}")

    if _table_exists(conn, "payouts") and not _column_exists(conn, "payouts", "status"):
        _add_column(conn, "payouts", "status VARCHAR(20) NOT NULL DEFAULT 'not_paid'")

    if _table_exists(conn, "models") and not _column_exists(conn, "models", "crypto_wallet"):
        _add_column(conn, "models", "crypto_wallet VARCHAR(200)")


def _migration_003_compensation_seed(conn: Connection, engine: Engine) -> None:
    from datetime import date

    from app.models import Model, ModelCompensationAdjustment

    if not _table_exists(conn, "model_compensation_adjustments"):
        ModelCompensationAdjustment.__table__.create(bind=conn, checkfirst=True)

    rows = conn.execute(text("SELECT id, start_date, amount_monthly FROM models")).fetchall()
    for model_id, start_date, amount_monthly in rows:
        existing = conn.execute(
            text("SELECT id FROM model_compensation_adjustments WHERE model_id = :mid LIMIT 1"),
            {"mid": model_id},
        ).first()
        if existing:
            continue
        effective = start_date or date.today().isoformat()
        conn.execute(
            text(
                """
                INSERT INTO model_compensation_adjustments
                (model_id, effective_date, amount_monthly, notes, created_at)
                VALUES (:mid, :eff, :amt, :notes, :created)
                """
            ),
            {
                "mid": model_id,
                "eff": effective,
                "amt": amount_monthly,
                "notes": "Seeded from existing model record",
                "created": datetime.utcnow().isoformat(sep=" "),
            },
        )


def _migration_004_api_keys(conn: Connection, engine: Engine) -> None:
    from app.models import ApiKey

    ApiKey.__table__.create(bind=conn, checkfirst=True)


def _migration_005_session_version(conn: Connection, engine: Engine) -> None:
    if _table_exists(conn, "users") and not _column_exists(conn, "users", "session_version"):
        _add_column(conn, "users", "session_version INTEGER NOT NULL DEFAULT 1")


def _migration_006_api_key_scopes(conn: Connection, engine: Engine) -> None:
    if not _table_exists(conn, "api_keys"):
        return
    is_postgres = engine.dialect.name == "postgresql"
    datetime_type = "TIMESTAMP" if is_postgres else "DATETIME"
    if not _column_exists(conn, "api_keys", "expires_at"):
        _add_column(conn, "api_keys", f"expires_at {datetime_type}")
    if not _column_exists(conn, "api_keys", "scopes"):
        _add_column(conn, "api_keys", "scopes TEXT NOT NULL DEFAULT '[\"v1:*\"]'")
    if not _column_exists(conn, "api_keys", "revoked_by"):
        _add_column(conn, "api_keys", "revoked_by VARCHAR(100)")
    if not _column_exists(conn, "api_keys", "revoke_reason"):
        _add_column(conn, "api_keys", "revoke_reason TEXT")
    conn.execute(text("UPDATE api_keys SET scopes = '[\"v1:*\"]' WHERE scopes IS NULL OR scopes = ''"))


def _migration_007_sync_state(conn: Connection, engine: Engine) -> None:
    from app.models import SyncState

    SyncState.__table__.create(bind=conn, checkfirst=True)
    existing = conn.execute(text("SELECT id FROM sync_state WHERE id = 1")).first()
    if not existing:
        conn.execute(text("INSERT INTO sync_state (id, revision) VALUES (1, 0)"))


def _migration_008_admin_nonces(conn: Connection, engine: Engine) -> None:
    from app.models import AdminActionNonce

    AdminActionNonce.__table__.create(bind=conn, checkfirst=True)


def _migration_009_rate_windows(conn: Connection, engine: Engine) -> None:
    from app.models import ApiRateWindow

    ApiRateWindow.__table__.create(bind=conn, checkfirst=True)


def _migration_010_payout_financials(conn: Connection, engine: Engine) -> None:
    if not _table_exists(conn, "payouts"):
        return
    is_postgres = engine.dialect.name == "postgresql"
    datetime_type = "TIMESTAMP" if is_postgres else "DATETIME"
    for col, ddl in [
        ("gross_amount", "NUMERIC(12, 2)"),
        ("advance_deduction_amount", "NUMERIC(12, 2)"),
        ("net_amount", "NUMERIC(12, 2)"),
        ("breakdown_source", "VARCHAR(40)"),
        ("superseded_at", datetime_type),
    ]:
        if not _column_exists(conn, "payouts", col):
            _add_column(conn, "payouts", f"{col} {ddl}")


def _migration_011_backfill_payout_financials(conn: Connection, engine: Engine) -> None:
    if not _table_exists(conn, "payouts"):
        return
    conn.execute(
        text(
            """
            UPDATE payouts
            SET net_amount = amount,
                gross_amount = amount,
                advance_deduction_amount = 0,
                breakdown_source = 'legacy_net_only'
            WHERE net_amount IS NULL
            """
        )
    )
    rows = conn.execute(
        text(
            """
            SELECT p.id, p.amount,
                   COALESCE((
                       SELECT SUM(r.amount) FROM advance_repayments r WHERE r.payout_id = p.id
                   ), 0) AS repayment_total,
                   COALESCE((
                       SELECT SUM(a.planned_amount) FROM payout_advance_allocations a WHERE a.payout_id = p.id
                   ), 0) AS alloc_total
            FROM payouts p
            WHERE p.breakdown_source = 'legacy_net_only'
            """
        )
    ).fetchall()
    for payout_id, amount, repayment_total, alloc_total in rows:
        net = float(amount or 0)
        repayment = float(repayment_total or 0)
        alloc = float(alloc_total or 0)
        if repayment > 0:
            gross = net + repayment
            deduction = repayment
            source = "backfilled_repayment"
        elif alloc > 0:
            gross = net + alloc
            deduction = alloc
            source = "backfilled_allocation"
        else:
            gross = net
            deduction = 0
            source = "legacy_net_only"
        conn.execute(
            text(
                """
                UPDATE payouts
                SET gross_amount = :gross,
                    advance_deduction_amount = :deduction,
                    net_amount = :net,
                    breakdown_source = :source
                WHERE id = :pid
                """
            ),
            {"gross": gross, "deduction": deduction, "net": net, "source": source, "pid": payout_id},
        )


def _migration_012_filter_indexes(conn: Connection, engine: Engine) -> None:
    indexes = [
        ("ix_payouts_pay_date", "payouts", "pay_date"),
        ("ix_payouts_status", "payouts", "status"),
        ("ix_payouts_model_id", "payouts", "model_id"),
        ("ix_payouts_schedule_run_id", "payouts", "schedule_run_id"),
        ("ix_adhoc_payments_pay_date", "adhoc_payments", "pay_date"),
        ("ix_adhoc_payments_model_id", "adhoc_payments", "model_id"),
    ]
    existing = {idx["name"] for idx in inspect(conn).get_indexes("payouts")} if _table_exists(conn, "payouts") else set()
    for name, table, column in indexes:
        if not _table_exists(conn, table):
            continue
        table_indexes = {idx["name"] for idx in inspect(conn).get_indexes(table)}
        if name in table_indexes or name in existing:
            continue
        try:
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})"))
        except Exception:
            pass


def _migration_013_payout_unique_key(conn: Connection, engine: Engine) -> None:
    if not _table_exists(conn, "payouts"):
        return
    dupes = conn.execute(
        text(
            """
            SELECT schedule_run_id, code, pay_date, GROUP_CONCAT(id) AS ids
            FROM payouts
            GROUP BY schedule_run_id, code, pay_date
            HAVING COUNT(*) > 1
            """
        )
        if engine.dialect.name == "postgresql"
        else text(
            """
            SELECT schedule_run_id, code, pay_date, GROUP_CONCAT(id) AS ids
            FROM payouts
            GROUP BY schedule_run_id, code, pay_date
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if dupes:
        details = [
            f"run={r[0]} code={r[1]} pay_date={r[2]} ids={r[3]}"
            for r in dupes
        ]
        raise RuntimeError(
            "Duplicate payout keys (schedule_run_id, code, pay_date) must be resolved before migration: "
            + "; ".join(details)
        )
    try:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_payouts_run_code_pay_date "
                "ON payouts (schedule_run_id, code, pay_date)"
            )
        )
    except Exception as exc:
        if "already exists" not in str(exc).lower():
            raise


def _migration_014_schedule_run_unique(conn: Connection, engine: Engine) -> None:
    if not _table_exists(conn, "schedule_runs"):
        return
    dupes = conn.execute(
        text(
            """
            SELECT target_year, target_month, COUNT(*) AS cnt
            FROM schedule_runs
            GROUP BY target_year, target_month
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if dupes:
        raise RuntimeError(
            "Duplicate schedule runs for year/month must be resolved: "
            + ", ".join(f"{y}-{m:02d} ({c} runs)" for y, m, c in dupes)
        )
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_schedule_runs_year_month "
            "ON schedule_runs (target_year, target_month)"
        )
    )


def _migration_015_allocation_uniqueness(conn: Connection, engine: Engine) -> None:
    if not _table_exists(conn, "payout_advance_allocations"):
        return
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_payout_advance_alloc_payout_advance "
            "ON payout_advance_allocations (payout_id, advance_id)"
        )
    )
    if _table_exists(conn, "advance_repayments"):
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_advance_repayment_payout_advance "
                "ON advance_repayments (payout_id, advance_id) "
                "WHERE payout_id IS NOT NULL"
            )
            if engine.dialect.name == "postgresql"
            else text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_advance_repayment_payout_advance "
                "ON advance_repayments (payout_id, advance_id) "
                "WHERE payout_id IS NOT NULL"
            )
        )


MIGRATIONS: list[tuple[int, str, MigrationFn]] = [
    (1, "bootstrap_core_tables", _migration_001_bootstrap),
    (2, "legacy_column_patches", _migration_002_legacy_columns),
    (3, "compensation_adjustments_seed", _migration_003_compensation_seed),
    (4, "api_keys_table", _migration_004_api_keys),
    (5, "user_session_version", _migration_005_session_version),
    (6, "api_key_scopes_expiry", _migration_006_api_key_scopes),
    (7, "sync_state", _migration_007_sync_state),
    (8, "admin_action_nonces", _migration_008_admin_nonces),
    (9, "api_rate_windows", _migration_009_rate_windows),
    (10, "payout_financial_columns", _migration_010_payout_financials),
    (11, "backfill_payout_financials", _migration_011_backfill_payout_financials),
    (12, "payout_filter_indexes", _migration_012_filter_indexes),
    (13, "payout_unique_run_code_date", _migration_013_payout_unique_key),
    (14, "schedule_run_unique_year_month", _migration_014_schedule_run_unique),
    (15, "allocation_uniqueness", _migration_015_allocation_uniqueness),
]


def _ensure_ledger(conn: Connection) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                applied_at TIMESTAMP NOT NULL
            )
            """
        )
    )


def _current_version(conn: Connection) -> int:
    _ensure_ledger(conn)
    row = conn.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar_one_or_none()
    return int(row or 0)


def _acquire_lock(conn: Connection, engine: Engine) -> None:
    if engine.dialect.name == "postgresql":
        conn.execute(text("SELECT pg_advisory_lock(42424242)"))


def _release_lock(conn: Connection, engine: Engine) -> None:
    if engine.dialect.name == "postgresql":
        conn.execute(text("SELECT pg_advisory_unlock(42424242)"))


def _apply_migration(conn: Connection, engine: Engine, version: int, name: str, fn: MigrationFn) -> None:
    fn(conn, engine)
    conn.execute(
        text("INSERT INTO schema_migrations (version, name, applied_at) VALUES (:v, :n, :t)"),
        {"v": version, "n": name, "t": datetime.utcnow()},
    )


def upgrade(engine: Engine | None = None) -> int:
    if engine is None:
        from app.database import engine as default_engine

        engine = default_engine

    with engine.begin() as conn:
        _acquire_lock(conn, engine)
        current = _current_version(conn)
        for version, name, fn in MIGRATIONS:
            if version <= current:
                continue
            _apply_migration(conn, engine, version, name, fn)
            current = version
        _release_lock(conn, engine)
        return current


def verify_schema(engine: Engine | None = None) -> None:
    if engine is None:
        from app.database import engine as default_engine

        engine = default_engine
    with engine.connect() as conn:
        current = _current_version(conn)
    if current != SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {current} != expected {SCHEMA_VERSION}. "
            "Run: python -m app.migrations upgrade"
        )


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    if command == "upgrade":
        version = upgrade()
        print(f"Schema at version {version}")
        return 0
    if command == "verify":
        verify_schema()
        print(f"Schema verified at version {SCHEMA_VERSION}")
        return 0
    print(f"Unknown command: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
