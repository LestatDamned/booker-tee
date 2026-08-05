from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
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
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
            },
        )

    async def spa_fallback(client_path: str) -> Response:
        del client_path
        return await spa_index()

    app.add_api_route(
        "/app",
        spa_index,
        methods=["GET"],
        include_in_schema=False,
        name="react_spa_index",
    )
    app.add_api_route(
        "/app/{client_path:path}",
        spa_fallback,
        methods=["GET"],
        include_in_schema=False,
        name="react_spa_path",
    )
