"""Run a live HTTP smoke test against a running PayrollDesk dev server."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "payroll_v4.db"


def _configure_env(db_path: Path) -> None:
    os.environ.setdefault("PAYROLL_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("API_RATE_SECRET", "dev-rate-secret-for-local-testing-32c")
    os.environ.setdefault("API_CURSOR_SECRET", "dev-cursor-secret-for-local-test-32c")


def _run_smoke(base_url: str, api_key: str) -> int:
    import httpx

    headers = {"X-API-Key": api_key}
    results: list[tuple[str, int, bool, str]] = []

    def check(name: str, response: httpx.Response, *, expect: int | None = None) -> dict | None:
        code = response.status_code
        ok = code == (expect if expect is not None else 200)
        try:
            body = response.json()
            count = len(body.get("data") or body.get("items") or [])
            rev = body.get("revision", body.get("snapshot_revision", "-"))
            extra = f"count={count} rev={rev}"
        except Exception:
            body = None
            extra = response.text[:80]
        results.append((name, code, ok, extra))
        return body if isinstance(body, dict) else None

    with httpx.Client(base_url=base_url, headers=headers, timeout=15) as client:
        snap = check("snapshot", client.get("/api/v2/snapshot"))
        rev = 0
        if snap:
            rev = snap.get("revision", snap.get("snapshot_revision", 0))
        check("models", client.get(f"/api/v2/models?snapshot_revision={rev}"))
        check(
            "schedule-runs",
            client.get(f"/api/v2/schedule-runs?year=2026&month=9&snapshot_revision={rev}"),
        )
        check("payouts", client.get(f"/api/v2/payouts?snapshot_revision={rev}"))
        check("advances", client.get(f"/api/v2/advances?snapshot_revision={rev}"))
        check("adhoc-payments", client.get(f"/api/v2/adhoc-payments?snapshot_revision={rev}"))
        check("validation-issues", client.get(f"/api/v2/validation-issues?snapshot_revision={rev}"))
        check("adjustments", client.get(f"/api/v2/adjustments?snapshot_revision={rev}"))
        check("v1 catalog", client.get("/api/v1"), expect=403)
        check("no auth", httpx.get(f"{base_url}/api/v2/snapshot", timeout=10), expect=401)

    print(f"=== API smoke test ({base_url}) ===")
    failed = 0
    for name, code, ok, extra in results:
        status = "OK" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"{status:4} {name}: HTTP {code} ({extra})")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--key-prefix",
        help="Verify an existing active key prefix (e.g. pd_ZcjWvvXGB) before testing",
    )
    args = parser.parse_args()

    _configure_env(args.db)
    sys.path.insert(0, str(ROOT))

    from app.api.keys import create_api_key_record, hash_api_key, revoke_api_key, validate_raw_key_format
    from app.database import SessionLocal

    raw_key = os.environ.get("PD_API_KEY", "").strip()
    ephemeral = False

    if raw_key:
        if not validate_raw_key_format(raw_key):
            print("PD_API_KEY is not a valid PayrollDesk API key format", file=sys.stderr)
            return 1
        with SessionLocal() as db:
            key_hash = hash_api_key(raw_key)
            record = (
                db.query(__import__("app.models", fromlist=["ApiKey"]).ApiKey)
                .filter_by(key_hash=key_hash)
                .filter_by(revoked_at=None)
                .first()
            )
            if record is None:
                print("PD_API_KEY does not match an active key in the local database", file=sys.stderr)
                return 1
            print(f"Using existing key prefix {record.key_prefix}")
    else:
        with SessionLocal() as db:
            record, raw_key = create_api_key_record(
                db,
                name="smoke-test-ephemeral",
                created_by="smoke_api_live",
                scopes=["v2:*"],
            )
            db.commit()
            ephemeral = True
            print(f"Created ephemeral key prefix {record.key_prefix}")

    if args.key_prefix:
        with SessionLocal() as db:
            from app.models import ApiKey

            match = (
                db.query(ApiKey)
                .filter(ApiKey.key_prefix.startswith(args.key_prefix[:12]))
                .filter(ApiKey.revoked_at.is_(None))
                .first()
            )
            if match is None:
                print(f"No active key found with prefix {args.key_prefix[:12]}", file=sys.stderr)
                return 1
            print(f"Verified active key in DB: {match.key_prefix} ({match.name})")

    try:
        return _run_smoke(args.base_url.rstrip("/"), raw_key)
    finally:
        if ephemeral:
            with SessionLocal() as db:
                revoke_api_key(db, record.id, revoked_by="smoke_api_live", revoke_reason="ephemeral")
                db.commit()


if __name__ == "__main__":
    raise SystemExit(main())
