from uuid import UUID

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

router = APIRouter(include_in_schema=False)


def redirect_to_react(request: Request, target: str) -> RedirectResponse:
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(
        url=target,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/ledger/manual")
async def historical_manual_ledger(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/ledger/manual")


@router.get("/accounts")
async def historical_accounts(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/accounts")


@router.get("/accounts/{account_id}")
async def historical_account_detail(
    request: Request,
    account_id: UUID,
) -> RedirectResponse:
    return redirect_to_react(request, f"/app/accounts/{account_id}")


@router.get("/imports")
async def historical_imports(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/imports")


@router.get("/imports/upload")
async def historical_import_upload(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/imports/upload")


@router.get("/imports/documents/{document_id}")
async def historical_import_document(
    request: Request,
    document_id: UUID,
) -> RedirectResponse:
    return redirect_to_react(request, f"/app/imports/documents/{document_id}")


@router.get("/imports/documents/{document_id}/mapping")
async def historical_import_mapping(
    request: Request,
    document_id: str,
) -> RedirectResponse:
    return redirect_to_react(
        request,
        f"/app/imports/documents/{document_id}/mapping",
    )


@router.get("/imports/documents/{document_id}/review")
async def historical_import_review(
    request: Request,
    document_id: str,
) -> RedirectResponse:
    return redirect_to_react(
        request,
        f"/app/imports/documents/{document_id}/review",
    )
