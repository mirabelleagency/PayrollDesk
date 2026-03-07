"""FastAPI entry point for the payroll application."""
from __future__ import annotations

import logging
import re
import time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Response, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi import status, HTTPException
from fastapi.responses import JSONResponse
from urllib.parse import quote
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import init_db, get_session
from app import __version__
from app.core.rate_limiter import limiter
from app.routers import admin, auth, changelog, commissions, dashboard, models, profile, schedules

logger = logging.getLogger(__name__)


# Pattern for hashed static files (e.g., index-DnJkF9X2.js)
HASHED_FILE_PATTERN = re.compile(r"^/static/.*-[a-zA-Z0-9]{8,}\.(js|css|woff2?)$")

# Paths exempt from CSRF validation
_CSRF_EXEMPT_PATHS = {"/health", "/health/db", "/login"}
_STATE_CHANGING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate Origin/Referer headers on state-changing requests to prevent CSRF."""

    async def dispatch(self, request: Request, call_next):
        if request.method in _STATE_CHANGING_METHODS:
            path = request.url.path.rstrip("/")
            if path not in _CSRF_EXEMPT_PATHS:
                host = request.headers.get("host", "")
                origin = request.headers.get("origin")
                referer = request.headers.get("referer")

                if origin:
                    parsed = urlparse(origin)
                    origin_host = parsed.netloc
                    if origin_host != host:
                        logger.warning(
                            "CSRF blocked: origin=%s host=%s path=%s",
                            origin, host, path,
                        )
                        return JSONResponse(
                            {"detail": "CSRF validation failed"},
                            status_code=403,
                        )
                elif referer:
                    parsed = urlparse(referer)
                    referer_host = parsed.netloc
                    if referer_host != host:
                        logger.warning(
                            "CSRF blocked: referer=%s host=%s path=%s",
                            referer, host, path,
                        )
                        return JSONResponse(
                            {"detail": "CSRF validation failed"},
                            status_code=403,
                        )
        return await call_next(request)


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Add cache-control headers for static assets."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        
        if path.startswith("/static/"):
            # Hashed files: immutable, 1 year cache
            if HASHED_FILE_PATTERN.match(path):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            # Non-hashed static files: 1 day cache with revalidation
            else:
                response.headers["Cache-Control"] = "public, max-age=86400, must-revalidate"
        
        return response

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Payroll Desk", version=__version__, lifespan=lifespan)

# Add rate limiter state to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add cache-control middleware for static assets
app.add_middleware(CacheControlMiddleware)

# CSRF protection: validate Origin/Referer on state-changing requests
app.add_middleware(CSRFMiddleware)

# Restrictive CORS: same-origin only (add allowed origins here if API access is opened)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=[],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(commissions.router)
app.include_router(admin.router)
app.include_router(changelog.router)
app.include_router(dashboard.router)
app.include_router(models.router)
app.include_router(schedules.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/login")


@app.get("/health")
def health() -> Response:
    """Simple health endpoint for load balancers and platform checks."""
    return Response(content='{"status":"ok"}', media_type="application/json")


@app.get("/health/db")
def health_db(db: Session = Depends(get_session)) -> dict[str, Any]:
    """Database health check endpoint with connection test and timing.
    
    Returns:
        JSON with database status, response time, and connection info.
        
    Example response:
        {
            "status": "healthy",
            "database": {
                "connected": true,
                "response_time_ms": 2.5,
                "engine": "postgresql"
            }
        }
    """
    start = time.perf_counter()
    try:
        # Execute a simple query to test the connection
        result = db.execute(text("SELECT 1")).scalar()
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        # Get database type from connection URL
        engine_url = str(db.get_bind().url)
        db_type = "postgresql" if "postgresql" in engine_url else "sqlite"
        
        return {
            "status": "healthy",
            "database": {
                "connected": result == 1,
                "response_time_ms": round(elapsed_ms, 2),
                "engine": db_type,
            },
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": {
                    "connected": False,
                    "response_time_ms": round(elapsed_ms, 2),
                    "error": str(e),
                },
            },
        )


# Custom handler: redirect unauthenticated HTML requests to /login instead of JSON 401
@app.exception_handler(HTTPException)
async def http_exception_redirect_login(request: Request, exc: HTTPException):
    """Redirect 401 HTML page requests to /login; preserve JSON for API calls.

    Logic:
    - If status != 401, fall back to normal JSON style.
    - If 401 and client likely expects HTML (Accept header includes text/html or navigating via browser), issue 303 redirect.
    - Otherwise return JSON (e.g. for fetch/XHR expecting application/json).
    """
    if exc.status_code != status.HTTP_401_UNAUTHORIZED:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    accept = request.headers.get("accept", "")
    wants_html = "text/html" in accept or "*/*" in accept  # browsers often send */*
    if wants_html:
        # Preserve original target so we can return after login
        original = request.url.path
        if request.url.query:
            original = f"{original}?{request.url.query}"
        login_url = f"/login?next={quote(original, safe='')}"
        return RedirectResponse(url=login_url, status_code=status.HTTP_303_SEE_OTHER)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
