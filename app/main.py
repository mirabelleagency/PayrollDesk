"""FastAPI entry point for the payroll application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi import status
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app import __version__
from app.routers import admin, analytics, auth, changelog, dashboard, models, profile, schedules

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Payroll Desk", version=__version__, lifespan=lifespan)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(analytics.router)
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
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
