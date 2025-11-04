"""FastAPI entry point for the payroll application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app import __version__
from app.routers import admin, analytics, auth, dashboard, models, profile, schedules

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Payroll Desk", version=__version__, lifespan=lifespan)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(analytics.router)
app.include_router(admin.router)
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
