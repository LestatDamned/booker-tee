from fastapi import Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.web.features.ledger.manual.view_models import (
    ManualLedgerPageVM,
    ManualLedgerRowVM,
)


class ManualLedgerRenderer:
    def __init__(self, templates: Jinja2Templates) -> None:
        self._templates = templates

    def page(
        self,
        request: Request,
        page: ManualLedgerPageVM,
        *,
        app_name: str,
        response_status: int = status.HTTP_200_OK,
    ) -> HTMLResponse:
        return self._templates.TemplateResponse(
            request,
            "features/ledger/manual/index.html",
            {
                "app_name": app_name,
                "page_title": "Ручные операции",
                "page": page,
            },
            status_code=response_status,
        )

    def row(
        self,
        request: Request,
        row: ManualLedgerRowVM,
        *,
        response_status: int = status.HTTP_200_OK,
    ) -> HTMLResponse:
        return self._templates.TemplateResponse(
            request,
            "features/ledger/manual/_row.html",
            {"row": row},
            status_code=response_status,
        )

    def results(
        self,
        request: Request,
        page: ManualLedgerPageVM,
        *,
        replace_url: str,
    ) -> HTMLResponse:
        return self._templates.TemplateResponse(
            request,
            "features/ledger/manual/_results.html",
            {
                "page": page,
                "include_total_oob": True,
            },
            headers={
                "HX-Retarget": "#manual-ledger-results",
                "HX-Reswap": "outerHTML",
                "HX-Replace-Url": replace_url,
            },
        )

    def edit_panel(
        self,
        request: Request,
        row: ManualLedgerRowVM,
    ) -> HTMLResponse:
        return self._templates.TemplateResponse(
            request,
            "features/ledger/manual/_edit_panel.html",
            {"row": row},
        )
