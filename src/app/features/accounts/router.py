from uuid import UUID

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/{account_id}", response_class=HTMLResponse)
async def account_detail(
    request: Request,
    account_id: UUID,
) -> RedirectResponse:
    query = request.url.query
    target = f"/app/accounts/{account_id}"
    return RedirectResponse(
        url=f"{target}?{query}" if query else target,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
