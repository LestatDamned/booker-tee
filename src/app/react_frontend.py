import base64
import hashlib
from html.parser import HTMLParser
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

REACT_BUILD_ROOT = Path("frontend/build/client")
CONTENT_SECURITY_POLICY = "Content-Security-Policy"


class _InlineScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.scripts: list[str] = []
        self._current_script: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and not any(name == "src" for name, _ in attrs):
            self._current_script = []

    def handle_data(self, data: str) -> None:
        if self._current_script is not None:
            self._current_script.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._current_script is not None:
            self.scripts.append("".join(self._current_script))
            self._current_script = None


def _build_spa_csp(index_html: str) -> str:
    collector = _InlineScriptCollector()
    collector.feed(index_html)
    script_sources = ["'self'"]
    script_sources.extend(
        f"'sha256-{base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()}'"
        for script in collector.scripts
    )
    return "; ".join(
        (
            "default-src 'none'",
            f"script-src {' '.join(script_sources)}",
            "style-src 'self'",
            "img-src 'self' data: blob:",
            "font-src 'self'",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
        )
    )


def install_react_frontend(
    app: FastAPI,
    *,
    build_root: Path = REACT_BUILD_ROOT,
) -> None:
    """Serve the compiled SPA without taking ownership of API or legacy routes."""
    assets_root = build_root / "assets"
    index_path = build_root / "index.html"
    csp = _build_spa_csp(index_path.read_text(encoding="utf-8")) if index_path.is_file() else None
    if assets_root.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_root), name="react_assets")

    async def spa_index() -> Response:
        if not index_path.is_file():
            return HTMLResponse(
                "React frontend is not built. Run the frontend development server.",
                status_code=503,
            )
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-store, no-transform",
                "Referrer-Policy": "no-referrer",
                CONTENT_SECURITY_POLICY: csp or "default-src 'none'",
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
