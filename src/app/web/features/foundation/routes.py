from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.core.settings import Settings
from app.web.features.foundation.presenter import FoundationPreviewPresenter
from app.web.templating import create_web_templates

router = APIRouter(prefix="/_next/foundation", tags=["web-foundation"])
templates = create_web_templates()


@router.get("", response_class=HTMLResponse)
async def foundation_preview(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    edit: bool = False,
) -> HTMLResponse:
    require_non_production(settings)
    return templates.TemplateResponse(
        request,
        "features/foundation/index.html",
        {
            "app_name": settings.app_name,
            "page_title": "Frontend Next foundation",
            "preview": FoundationPreviewPresenter.present(edit_panel_open=edit),
        },
    )


@router.get("/panel", response_class=HTMLResponse)
async def foundation_panel(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    require_non_production(settings)
    return templates.TemplateResponse(
        request,
        "features/foundation/_panel.html",
        {},
    )


def require_non_production(settings: Settings) -> None:
    if settings.is_production:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
