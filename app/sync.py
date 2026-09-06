"""Domain revision tracking for external API snapshot consistency."""
from __future__ import annotations

from sqlalchemy import event, inspect as sa_inspect, text, update
from sqlalchemy.orm import Session

_SYNC_MARKER = "_sync_domain_changed"
_events_registered = False


def _exposed_models():
    from app.models import (
        AdhocPayment,
        AdvanceRepayment,
        Model,
        ModelAdvance,
        ModelCompensationAdjustment,
        Payout,
        PayoutAdvanceAllocation,
        ScheduleRun,
        SyncState,
        ValidationIssue,
    )

    return (
        Model,
        ScheduleRun,
        Payout,
        ValidationIssue,
        ModelCompensationAdjustment,
        AdhocPayment,
        ModelAdvance,
        AdvanceRepayment,
        PayoutAdvanceAllocation,
    )


def _exposed_table_names() -> set[str]:
    return {model.__tablename__ for model in _exposed_models()}


def _is_exposed(instance) -> bool:
    return isinstance(instance, _exposed_models())


def _should_bump_dirty_object(obj) -> bool:
    """Skip revision bumps for progress-only schedule run updates."""
    from app.models import ScheduleRun

    if not _is_exposed(obj):
        return False
    if isinstance(obj, ScheduleRun):
        insp = sa_inspect(obj)
        changed = {
            attr.key
            for attr in insp.mapper.column_attrs
            if insp.attrs[attr.key].history.has_changes()
        }
        if changed and changed <= {"processing_progress"}:
            return False
    return True


def mark_sync_changed(session: Session) -> None:
    """Explicit marker for Core SQL mutations that bypass ORM events."""
    setattr(session, _SYNC_MARKER, True)


def _mark(session: Session) -> None:
    setattr(session, _SYNC_MARKER, True)


def _clear(session: Session) -> None:
    if hasattr(session, _SYNC_MARKER):
        delattr(session, _SYNC_MARKER)


def _ensure_sync_state_row(session: Session) -> None:
    existing = session.execute(text("SELECT id FROM sync_state WHERE id = 1")).first()
    if existing is None:
        session.execute(text("INSERT INTO sync_state (id, revision) VALUES (1, 0)"))


def _bump_revision(session: Session) -> None:
    from app.models import SyncState

    _ensure_sync_state_row(session)
    result = session.execute(
        update(SyncState)
        .where(SyncState.id == 1)
        .values(revision=SyncState.revision + 1)
    )
    if result.rowcount != 1:
        raise RuntimeError("sync_state row missing or revision bump failed")


def get_sync_revision(session: Session) -> int:
    value = session.execute(text("SELECT revision FROM sync_state WHERE id = 1")).scalar_one_or_none()
    if value is None:
        return 0
    return int(value)


def register_sync_events() -> None:
    global _events_registered
    if _events_registered:
        return
    _events_registered = True

    @event.listens_for(Session, "before_flush")
    def _before_flush(session, flush_context, instances):
        if session.info.get("read_only_api"):
            return
        for obj in session.new:
            if _is_exposed(obj):
                _mark(session)
                return
        for obj in session.dirty:
            if _should_bump_dirty_object(obj):
                _mark(session)
                return
        for obj in session.deleted:
            if _is_exposed(obj):
                _mark(session)
                return

    @event.listens_for(Session, "do_orm_execute")
    def _do_orm_execute(execute_state):
        if not execute_state.is_update and not execute_state.is_delete:
            return
        session = execute_state.session
        if session.info.get("read_only_api"):
            return
        statement = execute_state.statement
        table_name = getattr(getattr(statement, "table", None), "name", None)
        if table_name in _exposed_table_names():
            _mark(session)

    @event.listens_for(Session, "before_commit")
    def _before_commit(session):
        if not getattr(session, _SYNC_MARKER, False):
            return
        session.flush()
        _bump_revision(session)

    @event.listens_for(Session, "after_commit")
    def _after_commit(session):
        _clear(session)

    @event.listens_for(Session, "after_rollback")
    def _after_rollback(session):
        _clear(session)
