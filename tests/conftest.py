import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api_client import ApiTestClient
from app.main import create_app


@pytest.fixture
async def postgres_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        os.environ["BOOKER_TEE_TEST_DATABASE_URL"],
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest.fixture
def postgres_sessions(
    postgres_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(postgres_engine, expire_on_commit=False)


@pytest.fixture
async def postgres_rollback_sessions(
    postgres_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with postgres_engine.connect() as connection:
        transaction = await connection.begin()
        yield async_sessionmaker(
            connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        await transaction.rollback()


@pytest.fixture(scope="module")
def canonical_app() -> FastAPI:
    return create_app()


@pytest.fixture(scope="session")
def canonical_openapi_schema() -> dict[str, Any]:
    return create_app().openapi()


@pytest.fixture
def app(canonical_app: FastAPI) -> Iterator[FastAPI]:
    canonical_app.dependency_overrides = {}
    yield canonical_app
    canonical_app.dependency_overrides = {}


@pytest.fixture
def client(app: FastAPI) -> Iterator[ApiTestClient]:
    with ApiTestClient(app) as test_client:
        yield test_client
