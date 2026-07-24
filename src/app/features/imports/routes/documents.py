from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

router = APIRouter()


@router.get("/upload")
async def upload_form(
    request: Request,
) -> Response:
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(
        url=f"/app/imports/upload{query}",
        status_code=307,
    )


@router.get("/documents/{document_id}")
async def document_detail(
    request: Request,
    document_id: UUID,
) -> Response:
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(
        url=f"/app/imports/documents/{document_id}{query}",
        status_code=307,
    )
