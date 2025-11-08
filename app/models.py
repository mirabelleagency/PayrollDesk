"""SQLAlchemy models for the payroll application."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

STATUS_ENUM = ("Active", "Inactive")
FREQUENCY_ENUM = ("weekly", "biweekly", "monthly")
PAYOUT_STATUS_ENUM = ("paid", "approved", "on_hold", "not_paid")
ADHOC_PAYMENT_STATUS_ENUM = ("pending", "paid", "cancelled")


class Model(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    real_name: Mapped[str] = mapped_column(String(200), nullable=False)
    working_name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_monthly: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    crypto_wallet: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    payouts: Mapped[list["Payout"]] = relationship(back_populates="model", cascade="all, delete-orphan")
    validations: Mapped[list["ValidationIssue"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )
    compensation_adjustments: Mapped[list["ModelCompensationAdjustment"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
        order_by="ModelCompensationAdjustment.effective_date",
    )
    adhoc_payments: Mapped[list["AdhocPayment"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("amount_monthly > 0", name="ck_models_amount_positive"),
    )


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_year: Mapped[int] = mapped_column(Integer, nullable=False)
    target_month: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    include_inactive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    summary_models_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_total_payout: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    summary_frequency_counts: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    export_path: Mapped[str] = mapped_column(String(255), nullable=False, default="exports")

    payouts: Mapped[list["Payout"]] = relationship(back_populates="schedule_run", cascade="all, delete-orphan")
    validations: Mapped[list["ValidationIssue"]] = relationship(
        back_populates="schedule_run", cascade="all, delete-orphan"
    )


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_run_id: Mapped[int] = mapped_column(ForeignKey("schedule_runs.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="SET NULL"), nullable=True)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    real_name: Mapped[str] = mapped_column(String(200), nullable=False)
    working_name: Mapped[str] = mapped_column(String(200), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_paid")

    schedule_run: Mapped[ScheduleRun] = relationship(back_populates="payouts")
    model: Mapped[Model] = relationship(back_populates="payouts")


class ValidationIssue(Base):
    __tablename__ = "validation_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_run_id: Mapped[int] = mapped_column(ForeignKey("schedule_runs.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="SET NULL"), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    issue: Mapped[str] = mapped_column(Text, nullable=False)

    schedule_run: Mapped[ScheduleRun] = relationship(back_populates="validations")
    model: Mapped[Model] = relationship(back_populates="validations")


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(default=False, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index("idx_failed_attempts", "username", "success", "attempted_at"),
    )


class ModelCompensationAdjustment(Base):
    __tablename__ = "model_compensation_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_monthly: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    model: Mapped[Model] = relationship(back_populates="compensation_adjustments")

    __table_args__ = (
        UniqueConstraint("model_id", "effective_date", name="uq_adjustment_model_date"),
        CheckConstraint("amount_monthly > 0", name="ck_adjustment_amount_positive"),
    )


class AdhocPayment(Base):
    __tablename__ = "adhoc_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    model: Mapped[Model] = relationship(back_populates="adhoc_payments")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_adhoc_payments_amount_positive"),
        CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled')",
            name="ck_adhoc_payments_status_valid",
        ),
    )

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


# --- Cash advance feature models -------------------------------------------

class ModelAdvance(Base):
    __tablename__ = "model_advances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)

    # Principal and remaining balance
    amount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_remaining: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Workflow status: requested -> approved -> active -> closed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")

    # Deduction strategy
    strategy: Mapped[str] = mapped_column(String(20), nullable=False, default="fixed")  # fixed | percent
    fixed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    percent_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)  # 0-100

    # Policy knobs (per-advance overrides)
    min_net_floor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=500)
    max_per_run: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=600)
    cap_multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=1.0)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    model: Mapped[Model] = relationship(back_populates="advances")
    repayments: Mapped[list["AdvanceRepayment"]] = relationship(
        back_populates="advance", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("amount_total > 0", name="ck_advances_total_positive"),
        CheckConstraint("amount_remaining >= 0", name="ck_advances_remaining_nonnegative"),
        CheckConstraint("strategy IN ('fixed', 'percent')", name="ck_advances_strategy_valid"),
        CheckConstraint("percent_rate IS NULL OR (percent_rate >= 0 AND percent_rate <= 100)", name="ck_advances_percent_range"),
        CheckConstraint("min_net_floor >= 0", name="ck_advances_floor_nonnegative"),
        CheckConstraint("max_per_run >= 0", name="ck_advances_max_per_run_nonnegative"),
        CheckConstraint("cap_multiplier >= 0", name="ck_advances_cap_multiplier_nonnegative"),
    )


class AdvanceRepayment(Base):
    __tablename__ = "advance_repayments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    advance_id: Mapped[int] = mapped_column(ForeignKey("model_advances.id", ondelete="CASCADE"), nullable=False, index=True)
    payout_id: Mapped[int | None] = mapped_column(ForeignKey("payouts.id", ondelete="SET NULL"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")  # auto | manual
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    advance: Mapped[ModelAdvance] = relationship(back_populates="repayments")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_advance_repayment_amount_positive"),
    )


class PayoutAdvanceAllocation(Base):
    __tablename__ = "payout_advance_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_run_id: Mapped[int] = mapped_column(ForeignKey("schedule_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    payout_id: Mapped[int] = mapped_column(ForeignKey("payouts.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    advance_id: Mapped[int] = mapped_column(ForeignKey("model_advances.id", ondelete="CASCADE"), nullable=False, index=True)
    planned_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        CheckConstraint("planned_amount > 0", name="ck_payout_allocation_amount_positive"),
    )


# Back-populate relationships added after class definitions
Model.advances = relationship(
    "ModelAdvance", back_populates="model", cascade="all, delete-orphan"
)
