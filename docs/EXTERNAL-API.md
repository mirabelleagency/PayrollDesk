# PayrollDesk External API — Developer Guide

> **Version:** v2.52.0 · **Last updated:** 2026-09-07  
> **Audience:** Backend integrators pulling payroll data into downstream systems

PayrollDesk exposes a **read-only HTTP JSON API** for server-to-server integration. All endpoints are `GET` only. Browser session cookies are **not** accepted — use a scoped API key.

---

## Table of contents

1. [Quick start](#quick-start)
2. [Base URL and transport](#base-url-and-transport)
3. [Authentication](#authentication)
4. [Scopes](#scopes)
5. [API versions (v1 vs v2)](#api-versions-v1-vs-v2)
6. [Snapshot sync (v2)](#snapshot-sync-v2)
7. [Pagination](#pagination)
8. [Rate limits](#rate-limits)
9. [Data conventions](#data-conventions)
10. [Error reference](#error-reference)
11. [Endpoints — v2 (recommended)](#endpoints--v2-recommended)
12. [Endpoints — v1 (legacy)](#endpoints--v1-legacy)
13. [Resource schemas](#resource-schemas)
14. [Example sync workflow](#example-sync-workflow)
15. [Security notes](#security-notes)

---

## Quick start

1. **Obtain an API key** — Admin logs into PayrollDesk → **Admin → API Keys** → create a key. Copy the plaintext secret immediately; only a prefix is stored server-side.
2. **Call the snapshot endpoint** (v2) to get the current domain revision.
3. **Pull collections** using that `snapshot_revision`, paginating until `has_more` is false.
4. **On 409**, refresh the snapshot and restart the affected collection from page 1.

```bash
# Replace BASE_URL and YOUR_KEY
export BASE_URL="https://payroll.example.com"
export API_KEY="pd_your_key_here"

# 1. Current revision + authorized collections
curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/api/v2/snapshot" | jq .

# 2. First page of models (use revision from step 1)
curl -s -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v2/models?snapshot_revision=1&limit=100" | jq .

# 3. Next page (use next_cursor from previous response)
curl -s -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v2/models?cursor=...&limit=100" | jq .
```

For local development, see [README.md](../README.md#external-read-only-api-v1--v2) and `scripts/seed_api_demo.py` / `scripts/smoke_api_live.py`.

---

## Base URL and transport

| Item | Value |
|------|-------|
| Protocol | HTTPS in production |
| Content-Type | `application/json` |
| Auth header | `X-API-Key: pd_…` |
| Methods | `GET` only |
| CORS | Disabled — call from a backend, not browser JavaScript on another origin |
| Caching | Responses include `Cache-Control: no-store` |

Path prefixes:

- **v2 (recommended):** `/api/v2/…`
- **v1 (legacy):** `/api/v1/…`

---

## Authentication

Every request must include:

```http
X-API-Key: pd_<43-character-url-safe-token>
```

| Outcome | HTTP | Meaning |
|---------|------|---------|
| Missing or invalid key | **401** | `{"detail":"Invalid API key"}` |
| Valid key, wrong scope | **403** | `{"detail":"Insufficient scope; requires v2:models"}` (example) |
| Valid key, authorized | **200** | Normal response |

Keys are prefixed with `pd_` and are 46 characters total. Revoked or expired keys behave as invalid (401).

**Important:** Do not send PayrollDesk session cookies. The API ignores browser login state by design.

---

## Scopes

Each API key carries one or more scopes. Scopes are granted when an admin creates the key.

### Wildcard scopes

| Scope | Grants |
|-------|--------|
| `v2:*` | All v2 collections |
| `v1:*` | All v1 collections |

### Per-resource scopes

| Resource | v2 scope | v1 scope |
|----------|----------|----------|
| Models | `v2:models` | `v1:models` |
| Payouts | `v2:payouts` | `v1:payouts` |
| Schedule runs | `v2:schedule-runs` | `v1:schedule-runs` |
| Validation issues | `v2:validation-issues` | `v1:validation-issues` |
| Adhoc payments | `v2:adhoc-payments` | `v1:adhoc-payments` |
| Adjustments | `v2:adjustments` | `v1:adjustments` |
| Advances | `v2:advances` | `v1:advances` |
| Advance repayments | `v2:advance-repayments` | `v1:advance-repayments` |
| Advance allocations | `v2:advance-allocations` | `v1:advance-allocations` |

### Special scope rules

- **`GET /api/v1/advances/{id}`** requires **both** `v1:advances` **and** `v1:advance-repayments` (returns nested repayments).
- **`GET /api/v2/advances/{id}`** requires only `v2:advances`.
- **`GET /api/v2/snapshot`** requires at least one v2 resource scope; the response lists only collections your key may access.

Grant the minimum scopes needed. Keys with `v2:*` expose real names, notes, and crypto wallet addresses.

---

## API versions (v1 vs v2)

| Feature | v1 | v2 |
|---------|----|----|
| Snapshot revision | No | **Yes** — consistent reads across collections |
| Pagination cursor | Integer `after_id` | Signed opaque `cursor` (HMAC) |
| Timestamps | Local ISO (`2026-09-01T12:00:00`) | UTC with `Z` suffix (`2026-09-01T04:00:00Z`) |
| Payout breakdown | `amount` only | `gross_amount`, `advance_deduction_amount`, `net_amount`, `is_locked` |
| Schedule run | Includes `export_path` | Includes `run_status`, `pay_config_id` |
| Mid-sync conflict detection | No | **409** if domain revision changes during read |
| Recommendation | Legacy integrations | **New integrations** |

Use **v2** for all new work. v1 remains available for backward compatibility.

v2 can be disabled server-side with `API_V2_ENABLED=false` (returns **404** on v2 routes).

---

## Snapshot sync (v2)

PayrollDesk maintains a monotonic **domain revision** (`sync_state.revision`). Any create/update/delete on exposed payroll tables increments this counter.

### Why it matters

When pulling multiple collections (models, payouts, schedule runs, …), v2 guarantees that all pages were read against the **same revision**. If payroll data changes while you are syncing, the API returns **409 Conflict** so you can restart with a fresh snapshot instead of merging inconsistent data.

### Revision lifecycle

```
GET /api/v2/snapshot
        │
        ▼
   revision = N
        │
        ├──► GET /api/v2/models?snapshot_revision=N
        ├──► GET /api/v2/payouts?snapshot_revision=N
        └──► … other collections …
        │
        ▼ (payroll edited mid-sync)
   409 snapshot_changed
        │
        ▼
   Re-fetch snapshot → revision = N+1 → restart affected collection
```

### Snapshot response

```json
{
  "api_version": "2",
  "revision": 1,
  "collections": [
    "models",
    "payouts",
    "schedule-runs",
    "validation-issues",
    "adhoc-payments",
    "adjustments",
    "advances",
    "advance-repayments",
    "advance-allocations"
  ]
}
```

The `collections` array reflects your key's scopes, not necessarily every resource in the system.

---

## Pagination

### v2 — signed cursors

**First page** — `snapshot_revision` is required:

```
GET /api/v2/models?snapshot_revision=1&limit=100
```

**Subsequent pages** — pass `cursor` from the previous response (do not change filters or `limit`):

```
GET /api/v2/models?cursor=<opaque-token>&limit=100
```

Response envelope:

```json
{
  "api_version": "2",
  "data": [ /* … */ ],
  "pagination": {
    "limit": 100,
    "next_cursor": "…",
    "has_more": true
  },
  "snapshot_revision": 1
}
```

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `limit` | 100 | 1–500 | Must match across cursor pages |
| `cursor` | — | opaque | Expires after **1 hour**; bound to key, resource, filters, and revision |
| `snapshot_revision` | required on page 1 | ≥ 0 | Omit when using `cursor` |

Cursor rules:

- Changing any filter parameter invalidates the cursor (**400**).
- Using another key's cursor fails validation (**400**).
- Expired cursors return **400** — restart from page 1 with a fresh `snapshot_revision`.

### v1 — integer `after_id`

v1 uses stable ascending `id` ordering:

```
GET /api/v1/models?limit=100
GET /api/v1/models?limit=100&after_id=42
```

Response:

```json
{
  "data": [ /* … */ ],
  "pagination": {
    "limit": 100,
    "next_cursor": 42,
    "has_more": true
  }
}
```

Here `next_cursor` is an integer ID, not an opaque token.

---

## Rate limits

Two independent sliding windows, each **120 requests per 60 seconds**:

| Bucket | Key |
|--------|-----|
| Per client IP | Source IP address |
| Per API key | Internal key ID |

When exceeded:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 42
```

```json
{"detail": "Rate limit exceeded"}
```

Design integrations to backoff on 429 and respect `Retry-After`. Full sync jobs should paginate with modest concurrency (typically one in-flight request per key).

---

## Data conventions

### Money

All monetary fields are **decimal strings** with two fractional digits:

```json
"amount_monthly": "5000.00"
"gross_amount": "1250.00"
```

Never assume floating-point JSON numbers for currency.

### Dates

Calendar dates use ISO 8601 date form:

```json
"pay_date": "2026-09-15"
"start_date": "2025-01-01"
```

### Timestamps

| Version | Format | Example |
|---------|--------|---------|
| v1 | ISO 8601 (server local) | `"2026-09-01T12:00:00"` |
| v2 | UTC with `Z` | `"2026-09-01T04:00:00Z"` |

### Soft deletes

Records with a non-null `deleted_at` in the database are **excluded** from API list/detail responses.

### Enum values

Common status values (case-sensitive):

| Field | Values |
|-------|--------|
| Model status | `Active`, `Inactive` |
| Payment frequency | `weekly`, `biweekly`, `monthly` |
| Payout status | `paid`, `approved`, `on_hold`, `not_paid` |
| Adhoc status | `pending`, `paid`, `cancelled` |
| Payout breakdown source (v2) | `native`, `backfilled_repayment`, `backfilled_allocation`, `legacy_net_only` |

Unknown query filter values return **422**.

---

## Error reference

| HTTP | When | Response shape |
|------|------|----------------|
| **400** | Missing `snapshot_revision` on v2 page 1; invalid/expired cursor; invalid date range | `{"detail":"…"}` or structured object |
| **401** | Missing/invalid API key | `{"detail":"Invalid API key"}` |
| **403** | Insufficient scope | `{"detail":"Insufficient scope; requires …"}` |
| **404** | Resource not found; v2 disabled | `{"detail":"…"}` |
| **405** | POST/PUT/PATCH/DELETE | Method not allowed |
| **409** | v2 snapshot revision changed mid-read | `{"detail":{"code":"snapshot_changed","message":"Domain revision changed"}}` |
| **422** | Invalid query parameter (bad date format, unknown enum) | `{"detail":"Invalid date_from; use YYYY-MM-DD."}` |
| **429** | Rate limit | `{"detail":"Rate limit exceeded"}` + `Retry-After` header |
| **503** | Rate limiter backend unavailable | `{"detail":"Rate limiter unavailable"}` |

---

## Endpoints — v2 (recommended)

All paths are prefixed with `/api/v2`. Collection list endpoints share pagination parameters described above.

### `GET /api/v2/snapshot`

Returns current revision and authorized collection names.

**Scope:** At least one v2 resource scope.

---

### `GET /api/v2/models`

| Query param | Type | Description |
|-------------|------|-------------|
| `code` | string | Filter by model code |
| `status` | `Active` \| `Inactive` | Filter by status |
| `payment_frequency` | enum | `weekly`, `biweekly`, `monthly` |
| `payment_method` | string | Exact match |
| `snapshot_revision` | int | Required on first page |
| `cursor` | string | Opaque pagination token |
| `limit` | int | Page size (default 100) |

### `GET /api/v2/models/{model_id}`

| Query param | Type | Description |
|-------------|------|-------------|
| `snapshot_revision` | int | **Required** |

---

### `GET /api/v2/payouts`

| Query param | Type | Description |
|-------------|------|-------------|
| `date_from` | `YYYY-MM-DD` | Inclusive start |
| `date_to` | `YYYY-MM-DD` | Inclusive end (≥ `date_from`) |
| `status` | enum | `paid`, `approved`, `on_hold`, `not_paid` |
| `model_id` | int | Filter by model |
| `run_id` | int | Filter by schedule run |
| `snapshot_revision`, `cursor`, `limit` | | Pagination |

### `GET /api/v2/schedule-runs`

| Query param | Type | Description |
|-------------|------|-------------|
| `year` | int | Calendar year |
| `month` | int | 1–12 |
| `snapshot_revision`, `cursor`, `limit` | | Pagination |

### `GET /api/v2/schedule-runs/{run_id}`

Requires `snapshot_revision`.

### `GET /api/v2/validation-issues`

| Query param | Type | Description |
|-------------|------|-------------|
| `run_id` | int | Schedule run |
| `model_id` | int | Model |
| `severity` | string | e.g. `warning`, `error` |
| `snapshot_revision`, `cursor`, `limit` | | Pagination |

### `GET /api/v2/adhoc-payments`

| Query param | Type | Description |
|-------------|------|-------------|
| `date_from`, `date_to` | date | Pay date range |
| `status` | string | Adhoc status |
| `model_id` | int | Model filter |
| `snapshot_revision`, `cursor`, `limit` | | Pagination |

### `GET /api/v2/adjustments`

| Query param | Type | Description |
|-------------|------|-------------|
| `date_from`, `date_to` | date | Effective date range |
| `model_id` | int | Model filter |
| `snapshot_revision`, `cursor`, `limit` | | Pagination |

### `GET /api/v2/advances`

| Query param | Type | Description |
|-------------|------|-------------|
| `status` | string | Advance status |
| `model_id` | int | Model filter |
| `snapshot_revision`, `cursor`, `limit` | | Pagination |

### `GET /api/v2/advances/{advance_id}`

Requires `snapshot_revision`. Does not embed repayments (pull `/advance-repayments` separately).

### `GET /api/v2/advance-repayments`

| Query param | Type | Description |
|-------------|------|-------------|
| `advance_id` | int | Parent advance |
| `payout_id` | int | Linked payout |
| `snapshot_revision`, `cursor`, `limit` | | Pagination |

### `GET /api/v2/advance-allocations`

| Query param | Type | Description |
|-------------|------|-------------|
| `run_id` | int | Schedule run |
| `payout_id` | int | Payout |
| `model_id` | int | Model |
| `advance_id` | int | Advance |
| `snapshot_revision`, `cursor`, `limit` | | Pagination |

---

## Endpoints — v1 (legacy)

Prefix: `/api/v1`. Pagination uses integer `after_id`. No snapshot revision.

### `GET /api/v1`

Catalog of available v1 routes. Requires at least one v1 scope.

### Collection routes

Same resource names as v2, with these differences:

| Route | v1-only notes |
|-------|---------------|
| `GET /api/v1/advances/{id}` | Requires **both** `v1:advances` and `v1:advance-repayments`; includes nested `repayments` array |
| `GET /api/v1/schedule-runs/{id}` | Response includes `export_path` |
| All list routes | Use `after_id` instead of `cursor`; no `snapshot_revision` |

Full v1 route list (from catalog):

```
GET /api/v1/models
GET /api/v1/models/{id}
GET /api/v1/payouts
GET /api/v1/schedule-runs
GET /api/v1/schedule-runs/{id}
GET /api/v1/validation-issues
GET /api/v1/adhoc-payments
GET /api/v1/adjustments
GET /api/v1/advances
GET /api/v1/advances/{id}
GET /api/v1/advance-repayments
GET /api/v1/advance-allocations
```

---

## Resource schemas

### Model (v2)

```json
{
  "id": 1,
  "status": "Active",
  "code": "DEMO-001",
  "real_name": "Jane Doe",
  "working_name": "Jane",
  "start_date": "2025-01-01",
  "payment_method": "ACH",
  "payment_frequency": "monthly",
  "amount_monthly": "5000.00",
  "crypto_wallet": "0xabc…",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2026-09-01T04:00:00Z"
}
```

### Payout (v2)

```json
{
  "id": 10,
  "schedule_run_id": 2,
  "model_id": 1,
  "pay_date": "2026-09-15",
  "code": "DEMO-001",
  "real_name": "Jane Doe",
  "working_name": "Jane",
  "payment_method": "ACH",
  "payment_frequency": "monthly",
  "gross_amount": "5000.00",
  "advance_deduction_amount": "500.00",
  "net_amount": "4500.00",
  "amount": "4500.00",
  "breakdown_source": "native",
  "status": "approved",
  "notes": null,
  "superseded_at": null,
  "is_locked": false,
  "current_model_crypto_wallet": "0xabc…"
}
```

`amount` is an alias for `net_amount`. Legacy payouts without gross breakdown use `breakdown_source: "legacy_net_only"`.

### Schedule run (v2)

```json
{
  "id": 2,
  "target_year": 2026,
  "target_month": 9,
  "currency": "USD",
  "include_inactive": false,
  "summary_models_paid": 3,
  "summary_total_payout": "8750.00",
  "summary_frequency_counts": {"monthly": 3},
  "run_status": "ready",
  "pay_config_id": 1,
  "created_at": "2026-09-01T04:00:00Z"
}
```

### Advance (v2)

```json
{
  "id": 5,
  "model_id": 1,
  "amount_total": "2000.00",
  "amount_remaining": "1500.00",
  "status": "active",
  "strategy": "fixed",
  "fixed_amount": "500.00",
  "percent_rate": null,
  "min_net_floor": "0.00",
  "max_per_run": "500.00",
  "cap_multiplier": "1.00",
  "notes": null,
  "created_at": "2026-08-01T04:00:00Z",
  "updated_at": "2026-09-01T04:00:00Z",
  "activated_at": "2026-08-01T04:00:00Z"
}
```

Other resources follow the same field naming patterns; see OpenAPI at `/docs` on a running instance for machine-readable schemas.

---

## Example sync workflow

Pseudocode for a nightly v2 pull:

```python
import httpx

BASE = "https://payroll.example.com"
HEADERS = {"X-API-Key": "pd_…"}
COLLECTIONS = ["models", "payouts", "schedule-runs", "validation-issues"]

def fetch_collection(client, name, revision):
    rows = []
    params = {"snapshot_revision": revision, "limit": 500}
    while True:
        r = client.get(f"/api/v2/{name}", params=params, headers=HEADERS)
        if r.status_code == 409:
            raise SnapshotChanged()
        r.raise_for_status()
        body = r.json()
        rows.extend(body["data"])
        if not body["pagination"]["has_more"]:
            return rows, body["snapshot_revision"]
        params = {"cursor": body["pagination"]["next_cursor"], "limit": 500}

with httpx.Client(base_url=BASE, timeout=30) as client:
    snap = client.get("/api/v2/snapshot", headers=HEADERS).json()
    revision = snap["revision"]

    for name in COLLECTIONS:
        if name not in snap["collections"]:
            continue
        while True:
            try:
                data, rev = fetch_collection(client, name, revision)
                upsert_to_warehouse(name, data)
                break
            except SnapshotChanged:
                snap = client.get("/api/v2/snapshot", headers=HEADERS).json()
                revision = snap["revision"]
                # retry same collection from scratch
```

Recommended practices:

- Store the last successfully synced `revision` in your system for observability.
- Pull collections sequentially per sync job to stay under rate limits.
- Treat 409 as a normal retry signal, not a hard failure.
- Idempotently upsert by resource `id`.

---

## Security notes

| Topic | Guidance |
|-------|----------|
| Key storage | Treat keys like passwords; store in a secrets manager, never in source control |
| Key rotation | Revoke old keys in Admin → API Keys before deploying new ones |
| Scope minimization | Prefer `v2:models` + `v2:payouts` over `v2:*` when possible |
| PII | Responses include real names and optional crypto wallet addresses |
| Transport | HTTPS only in production |
| Logging | Do not log full API keys; prefix (`pd_ZcjWvvXGB`) is safe for support |
| Server secrets | Operators must set `API_RATE_SECRET` and `API_CURSOR_SECRET` (32+ chars) in production |

---

## Related documentation

- [README.md](../README.md) — Local setup and environment variables
- [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md) — Internal architecture and database schema
- OpenAPI — `GET /docs` on a running PayrollDesk instance (interactive explorer)

For questions or access requests, contact your PayrollDesk administrator.
