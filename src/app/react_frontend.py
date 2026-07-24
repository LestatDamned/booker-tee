from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

REACT_BUILD_ROOT = Path("frontend/build/client")


def install_react_frontend(
    app: FastAPI,
    *,
    build_root: Path = REACT_BUILD_ROOT,
) -> None:
    """Serve the compiled SPA without taking ownership of API or legacy routes."""
    assets_root = build_root / "assets"
    if assets_root.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_root), name="react_assets")

    async def spa_index() -> Response:
        index_path = build_root / "index.html"
        if not index_path.is_file():
            return HTMLResponse(
                "React frontend is not built. Run the frontend development server.",
                status_code=503,
            )
        return FileResponse(index_path)

    async def spa_fallback(client_path: str) -> Response:
        del client_path
        return await spa_index()

    async def historical_manual_ledger_redirect(request: Request) -> RedirectResponse:
        target = "/app/ledger/manual"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(
            url=target,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    async def historical_import_review_redirect(
        request: Request,
        document_id: str,
    ) -> RedirectResponse:
        target = f"/app/imports/documents/{document_id}/review"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(
            url=target,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    async def historical_import_mapping_redirect(
        request: Request,
        document_id: str,
    ) -> RedirectResponse:
        target = f"/app/imports/documents/{document_id}/mapping"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(
            url=target,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    async def historical_imports_redirect(request: Request) -> RedirectResponse:
        target = "/app/imports"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(
            url=target,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    app.add_api_route(
        "/ledger/manual",
        historical_manual_ledger_redirect,
        methods=["GET"],
        include_in_schema=False,
    )
    app.add_api_route(
        "/imports/documents/{document_id}/review",
        historical_import_review_redirect,
        methods=["GET"],
        include_in_schema=False,
    )
    app.add_api_route(
        "/imports/documents/{document_id}/mapping",
        historical_import_mapping_redirect,
        methods=["GET"],
        include_in_schema=False,
    )
    app.add_api_route(
        "/imports",
        historical_imports_redirect,
        methods=["GET"],
        include_in_schema=False,
    )
    app.add_api_route("/app", spa_index, methods=["GET"], include_in_schema=False)
    app.add_api_route(
        "/app/{client_path:path}",
        spa_fallback,
        methods=["GET"],
        include_in_schema=False,
    )
