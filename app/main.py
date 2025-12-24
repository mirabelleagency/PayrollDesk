"""FastAPI entry point for the payroll application."""
from __future__ import annotations

import re
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Response, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi import status, HTTPException
from fastapi.responses import JSONResponse
from urllib.parse import quote
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import init_db, get_session
from app import __version__
from app.routers import admin, auth, changelog, commissions, dashboard, models, profile, schedules


# Pattern for hashed static files (e.g., index-DnJkF9X2.js)
HASHED_FILE_PATTERN = re.compile(r"^/static/.*-[a-zA-Z0-9]{8,}\.(js|css|woff2?)$")


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

# Add cache-control middleware for static assets
app.add_middleware(CacheControlMiddleware)

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
