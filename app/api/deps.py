"""API authentication dependencies."""

from __future__ import annotations



from typing import Callable, Generator



from fastapi import Depends, HTTPException, Request

from fastapi.security import APIKeyHeader

from sqlalchemy.orm import Session



from app.api.keys import get_active_api_key, touch_api_key_usage

from app.api.principal import ApiPrincipal

from app.api.rate_limit import enforce_ip_rate_limit, enforce_key_rate_limit

from app.database import SessionLocal, get_api_read_session



api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)



_INVALID_KEY_HEADERS = {"WWW-Authenticate": "APIKey"}





def _invalid_key_exception() -> HTTPException:

    return HTTPException(

        status_code=401,

        detail="Invalid API key",

        headers=_INVALID_KEY_HEADERS,

    )





def _authenticate(raw_key: str | None) -> ApiPrincipal:

    if not raw_key:

        raise _invalid_key_exception()



    auth_session = SessionLocal()

    try:

        record = get_active_api_key(auth_session, raw_key)

        if record is None:

            raise _invalid_key_exception()

        principal = ApiPrincipal(key_id=record.id, scopes=tuple(record.scope_list()))

        touch_api_key_usage(auth_session, record)

    finally:

        auth_session.close()



    enforce_key_rate_limit(principal.key_id)

    return principal





def require_api_key(

    request: Request,

    raw_key: str | None = Depends(api_key_header),

) -> ApiPrincipal:

    """Validate X-API-Key header; never accept browser session cookies."""

    enforce_ip_rate_limit(request)

    principal = _authenticate(raw_key)

    request.state.api_key_id = principal.key_id

    request.state.api_scopes = principal.scopes

    return principal





def require_scope(required: str) -> Callable:

    def _dependency(principal: ApiPrincipal = Depends(require_api_key)) -> ApiPrincipal:

        if not principal.grants(required):

            raise HTTPException(status_code=403, detail=f"Insufficient scope; requires {required}")

        return principal



    return _dependency





def require_any_v1_scope(principal: ApiPrincipal = Depends(require_api_key)) -> ApiPrincipal:
    from app.api.scopes import V1_RESOURCES

    if not any(principal.grants(f"v1:{resource}") for resource in V1_RESOURCES):
        raise HTTPException(status_code=403, detail="At least one v1 scope is required")
    return principal


def require_v1_advance_detail(principal: ApiPrincipal = Depends(require_api_key)) -> ApiPrincipal:
    if not principal.grants("v1:advances") or not principal.grants("v1:advance-repayments"):
        raise HTTPException(
            status_code=403,
            detail="Advance detail requires v1:advances and v1:advance-repayments scopes",
        )
    return principal


def require_any_v2_scope(principal: ApiPrincipal = Depends(require_api_key)) -> ApiPrincipal:
    from app.api.scopes import V2_RESOURCES

    if not any(principal.grants(f"v2:{resource}") for resource in V2_RESOURCES):
        raise HTTPException(status_code=403, detail="At least one v2 scope is required")
    return principal


def api_read_db() -> Generator[Session, None, None]:

    yield from get_api_read_session()


