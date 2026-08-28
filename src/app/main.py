import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.api.errors import install_api_exception_handlers
from app.api.router import router as api_router
from app.core.config import get_settings
from app.core.middleware import install_security_middleware
from app.db.session import session_factory
from app.features.chat_integrations.router import router as chat_integrations_router
from app.features.imports.parsers.sidecar.client import StatementParserSidecarClient
from app.legacy_frontend_redirects import router as legacy_frontend_redirects_router
from app.react_frontend import install_react_frontend


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    parser = StatementParserSidecarClient.from_settings(settings)
    if parser is not None:
        deadline = (
            asyncio.get_running_loop().time() + settings.statement_parser_startup_timeout_seconds
        )
        while True:
            try:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError("Parser startup timed out")
                await asyncio.wait_for(parser.ping(), timeout=remaining)
                break
            except (RuntimeError, TimeoutError):
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise
                await asyncio.sleep(min(0.25, remaining))
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_runtime()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    install_security_middleware(app, settings)
    install_api_exception_handlers(app)
    app.include_router(api_router)
    app.include_router(legacy_frontend_redirects_router)
    app.include_router(chat_integrations_router)

    @app.get("/", include_in_schema=False)
    async def home() -> RedirectResponse:
        return RedirectResponse(
            url="/app",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    @app.get("/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    @app.get("/health/db")
    async def database_healthcheck() -> dict[str, str]:
        async with session_factory() as session:
            await session.execute(text("select 1"))
        return {"status": "ok", "database": "reachable"}

    install_react_frontend(app)

    return app


app = create_app()
