from datetime import date
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import CategoryKind
from app.features.categories.repository import CategoryRepository
from app.features.categories.service import (
    DEFAULT_CATEGORY_SEEDS,
    PROPERTY_MANAGEMENT_CATEGORY_SEEDS,
    SYSTEM_CATEGORY_SEEDS,
    CategoryError,
    CategoryService,
    clean_optional_text,
)
from app.features.ledger.domain.types import OperationType
from app.features.workspaces.models import WorkspaceType


def test_system_categories_are_specific_fallbacks_and_financial_controls() -> None:
    categories_by_key = {seed.system_key: seed for seed in SYSTEM_CATEGORY_SEEDS}

    assert categories_by_key["income"].name == "Прочий доход"
    assert categories_by_key["income"].kind == CategoryKind.INCOME
    assert categories_by_key["expense"].name == "Прочий расход"
    assert categories_by_key["expense"].kind == CategoryKind.EXPENSE
    assert categories_by_key["rent"].name == "Арендный доход"
    assert categories_by_key["rent"].kind == CategoryKind.INCOME
    assert "Аренда" not in {seed.name for seed in SYSTEM_CATEGORY_SEEDS}


def test_default_categories_cover_common_import_review_choices() -> None:
    default_names = {seed.name for seed in DEFAULT_CATEGORY_SEEDS}

    assert {
        "Продукты",
        "Кафе и рестораны",
        "Такси",
        "Маркетплейсы",
        "Аренда жилья/помещения",
        "Ипотека и кредиты",
        "Связь и интернет",
        "Подписки и сервисы",
        "Красота и здоровье",
        "Комиссия банка",
    } <= default_names


def test_property_management_categories_are_seeded_only_for_property_workspace() -> None:
    personal_names = {
        seed.name for seed in CategoryService._default_category_seeds(WorkspaceType.PERSONAL)
    }
    property_names = {
        seed.name
        for seed in CategoryService._default_category_seeds(WorkspaceType.PROPERTY_MANAGEMENT)
    }
    property_only_names = {seed.name for seed in PROPERTY_MANAGEMENT_CATEGORY_SEEDS}

    assert property_only_names.isdisjoint(personal_names)
    assert property_only_names <= property_names


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(
            "  супермаркеты   и доставка  ",
            "супермаркеты и доставка",
            id="normalized",
        ),
        pytest.param("   ", None, id="blank"),
        pytest.param(None, None, id="missing"),
    ],
)
def test_clean_optional_text(value: str | None, expected: str | None) -> None:
    assert clean_optional_text(value) == expected


async def test_category_lookup_is_workspace_scoped() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: None),
    )

    result = await CategoryRepository(
        cast(AsyncSession, SimpleNamespace(execute=execute))
    ).get_for_workspace(workspace_id, category_id)

    assert result is None
    assert execute.await_args is not None
    compiled = execute.await_args.args[0].compile()
    sql = str(compiled)
    assert "categories.id" in sql
    assert "categories.workspace_id" in sql
    assert {workspace_id, category_id} <= set(compiled.params.values())


async def test_category_detail_forwards_currency_and_flow_to_ledger() -> None:
    category = SimpleNamespace(id=uuid4())
    captured: dict[str, object] = {}

    class Categories:
        async def get_for_workspace(self, *_args: object) -> object:
            return category

    class Ledger:
        async def list_confirmed_operations(self, **kwargs: object) -> list[object]:
            captured.update(kwargs)
            return []

    class Rules:
        async def list_for_category(self, **_kwargs: object) -> list[object]:
            return []

    service = CategoryService(cast(Any, SimpleNamespace()))
    service.categories = cast(Any, Categories())
    service.ledger = cast(Any, Ledger())
    service.rules = cast(Any, Rules())
    workspace_id = uuid4()

    await service.get_detail(
        workspace_id,
        category.id,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        currency="USD",
        operation_type=OperationType.EXPENSE,
    )

    assert captured == {
        "workspace_id": workspace_id,
        "category_id": category.id,
        "date_from": date(2026, 6, 1),
        "date_to": date(2026, 6, 30),
        "currency": "USD",
        "operation_type": OperationType.EXPENSE,
    }


async def test_category_name_uniqueness_is_case_insensitive() -> None:
    category_id = uuid4()
    service = CategoryService(cast(Any, SimpleNamespace(commit=noop_async)))
    service.categories = cast(
        Any,
        SimpleNamespace(
            get_by_name_for_workspace=existing_category(category_id),
        ),
    )

    with pytest.raises(CategoryError, match="Категория с таким названием уже есть"):
        await service._ensure_name_available(
            workspace_id=uuid4(),
            name="продукты",
        )


async def test_active_category_must_be_archived_before_delete() -> None:
    category_id = uuid4()
    category = SimpleNamespace(
        id=category_id,
        name="Продукты",
        is_active=True,
        is_system=False,
    )
    repository = SimpleNamespace(
        get_for_workspace=AsyncMock(return_value=category),
        delete=AsyncMock(),
    )
    session = SimpleNamespace(commit=AsyncMock())
    service = CategoryService(cast(Any, session))
    service.categories = cast(Any, repository)

    with pytest.raises(CategoryError, match="Сначала перенесите категорию в архив"):
        await service.delete_archived_custom(
            workspace_id=uuid4(),
            category_id=category_id,
        )

    repository.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


async def noop_async() -> None:
    return None


def existing_category(category_id: object) -> object:
    async def get_by_name_for_workspace(_workspace_id: object, _name: str) -> object:
        return SimpleNamespace(id=category_id)

    return get_by_name_for_workspace
