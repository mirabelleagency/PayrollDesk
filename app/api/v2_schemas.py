"""Pydantic models for API v2."""
from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class MoneyString(str):
    """Two-decimal money string."""


class ModelStatus(str, Enum):
    active = "Active"
    inactive = "Inactive"


class PaymentFrequency(str, Enum):
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"


class PayoutStatus(str, Enum):
    paid = "paid"
    approved = "approved"
    on_hold = "on_hold"
    not_paid = "not_paid"


class AdhocStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


class BreakdownSource(str, Enum):
    native = "native"
    backfilled_repayment = "backfilled_repayment"
    backfilled_allocation = "backfilled_allocation"
    legacy_net_only = "legacy_net_only"


class V2ErrorResponse(BaseModel):
    code: str
    message: str
    issues: list[str] | None = None


class V2Pagination(BaseModel):
    limit: int
    next_cursor: str | None = None
    has_more: bool


T = TypeVar("T")


class V2Page(BaseModel, Generic[T]):
    api_version: str = "2"
    data: list[T]
    pagination: V2Pagination
    snapshot_revision: int


class V2Detail(BaseModel, Generic[T]):
    api_version: str = "2"
    data: T
    snapshot_revision: int


class V2SnapshotResponse(BaseModel):
    api_version: str = "2"
    revision: int
    collections: list[str]


class V2Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ModelStatus
    code: str
    real_name: str
    working_name: str
    start_date: str
    payment_method: str
    payment_frequency: PaymentFrequency
    amount_monthly: str
    crypto_wallet: str | None = None
    created_at: str
    updated_at: str


class V2Payout(BaseModel):
    id: int
    schedule_run_id: int
    model_id: int | None
    pay_date: str
    code: str
    real_name: str
    working_name: str
    payment_method: str
    payment_frequency: PaymentFrequency
    gross_amount: str
    advance_deduction_amount: str
    net_amount: str
    amount: str
    breakdown_source: BreakdownSource | None = None
    status: PayoutStatus
    notes: str | None = None
    superseded_at: str | None = None
    is_locked: bool = False
    current_model_crypto_wallet: str | None = None


class V2ScheduleRun(BaseModel):
    id: int
    target_year: int
    target_month: int
    currency: str
    include_inactive: bool
    summary_models_paid: int
    summary_total_payout: str
    summary_frequency_counts: dict[str, int]
    run_status: str
    pay_config_id: int | None = None
    created_at: str


class V2ValidationIssue(BaseModel):
    id: int
    schedule_run_id: int
    model_id: int | None
    severity: str
    issue: str


class V2AdhocPayment(BaseModel):
    id: int
    model_id: int
    pay_date: str
    amount: str
    description: str | None = None
    notes: str | None = None
    status: AdhocStatus
    created_at: str
    updated_at: str


class V2Adjustment(BaseModel):
    id: int
    model_id: int
    effective_date: str
    amount_monthly: str
    notes: str | None = None
    created_at: str


class V2Advance(BaseModel):
    id: int
    model_id: int
    amount_total: str
    amount_remaining: str
    status: str
    strategy: str
    fixed_amount: str | None = None
    percent_rate: str | None = None
    min_net_floor: str
    max_per_run: str
    cap_multiplier: str
    notes: str | None = None
    created_at: str
    updated_at: str
    activated_at: str | None = None


class V2AdvanceRepayment(BaseModel):
    id: int
    advance_id: int
    payout_id: int | None
    amount: str
    source: str
    created_at: str


class V2AdvanceAllocation(BaseModel):
    id: int
    schedule_run_id: int
    payout_id: int
    model_id: int
    advance_id: int
    planned_amount: str
    created_at: str


class ModelsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = None
    status: ModelStatus | None = None
    payment_frequency: PaymentFrequency | None = None
    payment_method: str | None = None
    snapshot_revision: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class PayoutsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: str | None = None
    date_to: str | None = None
    status: PayoutStatus | None = None
    model_id: int | None = Field(default=None, ge=1)
    run_id: int | None = Field(default=None, ge=1)
    snapshot_revision: int | None = Field(default=None, ge=0)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=500)
