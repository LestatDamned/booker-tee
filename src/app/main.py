from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import session_factory
from app.features.accounts.router import router as accounts_router
from app.features.categories.router import router as categories_router
from app.features.imports.router import router as imports_router
from app.features.ledger.router import router as ledger_router
from app.features.properties.router import router as properties_router
from app.features.reports.router import router as reports_router
from app.features.transaction_rules.router import router as transaction_rules_router
from app.templating import create_templates

templates = create_templates()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = get_settings()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="src/app/static"), name="static")
    app.include_router(accounts_router)
    app.include_router(categories_router)
    app.include_router(imports_router)
    app.include_router(ledger_router)
    app.include_router(properties_router)
    app.include_router(reports_router)
    app.include_router(transaction_rules_router)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "home.html",
            {"app_name": settings.app_name},
        )

    @app.get("/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    @app.get("/health/db")
    async def database_healthcheck() -> dict[str, str]:
        async with session_factory() as session:
            await session.execute(text("select 1"))
        return {"status": "ok", "database": "reachable"}

    return app


app = create_app()
