"""FastAPI entry point for the payroll application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, Request
from fastapi.responses import RedirectResponse
from fastapi import status, HTTPException
from fastapi.responses import JSONResponse
from urllib.parse import quote
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app import __version__
from app.session_config import get_session_secret, session_cookie_secure
from app.routers import admin, admin_api_keys, analytics, auth, changelog, dashboard, models, profile, schedules
from app.api.v1 import router as api_v1_router
from app.api.v2 import router as api_v2_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Payroll Desk", version=__version__, lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=get_session_secret(),
    session_cookie="session",
    max_age=86400,
    same_site="lax",
    https_only=session_cookie_secure(),
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(admin_api_keys.router)
app.include_router(changelog.router)
app.include_router(dashboard.router)
app.include_router(models.router)
app.include_router(schedules.router)
app.include_router(api_v1_router, prefix="/api/v1", tags=["API"])
app.include_router(api_v2_router, prefix="/api/v2", tags=["API v2"])

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def api_security_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/admin/api-keys"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/login")


@app.get("/health")
def health() -> Response:
    """Simple health endpoint for load balancers and platform checks."""
    return Response(content='{"status":"ok"}', media_type="application/json")


def _json_exception_response(exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(HTTPException)
async def http_exception_redirect_login(request: Request, exc: HTTPException):
    """Redirect 401 HTML page requests to /login; preserve JSON for API calls."""
    if exc.status_code != status.HTTP_401_UNAUTHORIZED:
        return _json_exception_response(exc)

    if request.url.path.startswith("/api/"):
        return _json_exception_response(exc)

    accept = request.headers.get("accept", "")
    wants_html = "text/html" in accept or "*/*" in accept
    if wants_html:
        original = request.url.path
        if request.url.query:
            original = f"{original}?{request.url.query}"
        login_url = f"/login?next={quote(original, safe='')}"
        return RedirectResponse(url=login_url, status_code=status.HTTP_303_SEE_OTHER)
    return _json_exception_response(exc)
