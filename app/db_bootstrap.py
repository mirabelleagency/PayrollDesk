"""Bring the database schema up to date before the app starts.

Run by entrypoint.sh as `python -m app.db_bootstrap`. Three cases:

- Empty database (no tables at all): create the whole schema from the models
  and stamp Alembic at head. The baseline migration (0001) is a no-op that
  assumes the tables already exist, so `alembic upgrade head` cannot build a
  database from nothing — it fails on the first ALTER and, before this script,
  left a fresh environment with no alembic_version, failing every migration on
  every later deploy.
- Database with alembic_version: `alembic upgrade head`, as before.
- Tables but no alembic_version: created by an older startup that never
  stamped. Which migrations it already has can't be guessed safely, so this
  reports it loudly and leaves the schema alone; stamp the right revision by
  hand (`alembic stamp <rev>`), after which upgrades run normally.

Exits non-zero when a migration fails, so a deploy with a broken migration
stops before the server starts instead of running on a half-migrated schema.
"""
from __future__ import annotations

import logging
import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import Base, engine
from app import models  # noqa: F401 - registers domain tables with Base.metadata
from app.auth import User  # noqa: F401 - registers users table

logger = logging.getLogger("db_bootstrap")

ALEMBIC_INI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[db_bootstrap] %(message)s")
    config = Config(ALEMBIC_INI)
    tables = set(inspect(engine).get_table_names())

    if "alembic_version" in tables:
        logger.info("Running alembic upgrade head")
        command.upgrade(config, "head")
        return 0

    if not tables:
        logger.info("Empty database: creating schema from models and stamping head")
        Base.metadata.create_all(bind=engine)
        command.stamp(config, "head")
        return 0

    logger.error(
        "Database has %d tables but no alembic_version, so its migration state is "
        "unknown and migrations were NOT run. Stamp the revision the schema matches "
        "(`alembic stamp <revision>`); later deploys will then upgrade normally.",
        len(tables),
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("Schema migration failed")
        sys.exit(1)
