"""Routes for rendering the project changelog."""
from __future__ import annotations

from pathlib import Path

import markdown
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup

from app.auth import User
from app.dependencies import templates
from app.routers.auth import get_current_user

router = APIRouter(tags=["Changelog"])

_CHANGELOG_PATH = Path(__file__).resolve().parents[2] / "CHANGELOG.md"


def _render_changelog() -> Markup:
    if not _CHANGELOG_PATH.exists():
        raise HTTPException(status_code=404, detail="Changelog file not found")
    content = _CHANGELOG_PATH.read_text(encoding="utf-8")
    html = markdown.markdown(
        content,
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "sane_lists",
        ],
        output_format="html",
    )
    return Markup(html)


@router.get("/changelog", response_class=HTMLResponse)
def changelog(
    request: Request,
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    context = {
        "request": request,
        "user": user,
        "changelog_html": _render_changelog(),
    }
    return templates.TemplateResponse("changelog.html", context)
