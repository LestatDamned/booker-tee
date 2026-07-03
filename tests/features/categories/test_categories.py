from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from app.features.categories.models import CategoryKind
from app.features.categories.router import categories_url, split_category_rows
from app.features.categories.service import (
    DEFAULT_CATEGORY_SEEDS,
    PROPERTY_MANAGEMENT_CATEGORY_SEEDS,
    SYSTEM_CATEGORY_SEEDS,
    CategoryError,
    CategoryManagementRow,
    CategoryService,
    clean_optional_text,
)
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


def test_clean_optional_text_normalizes_blank_category_notes() -> None:
    assert clean_optional_text("  супермаркеты   и доставка  ") == "супермаркеты и доставка"
    assert clean_optional_text("   ") is None
    assert clean_optional_text(None) is None


def test_category_view_filter_splits_user_archive_and_system_rows() -> None:
    active_user = category_row(is_active=True, is_system=False)
    archived_user = category_row(is_active=False, is_system=False)
    system = category_row(is_active=True, is_system=True)

    assert split_category_rows([active_user, archived_user, system], "active") == (
        [active_user],
        [],
    )
    assert split_category_rows([active_user, archived_user, system], "archived") == (
        [archived_user],
        [],
    )
    assert split_category_rows([active_user, archived_user, system], "system") == (
        [],
        [system],
    )
    assert split_category_rows([active_user, archived_user, system], "all") == (
        [active_user, archived_user],
        [system],
    )


def test_categories_url_preserves_non_default_view() -> None:
    assert categories_url("active") == "/categories"
    assert categories_url("archived") == "/categories?view=archived"
    assert categories_url("nope") == "/categories"


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_archived_category_without_links_can_be_deleted() -> None:
    category_id = uuid4()
    category = SimpleNamespace(id=category_id, is_active=False, is_system=False)
    repository = FakeCategoryRepository(category=category)
    service = CategoryService(cast(Any, SimpleNamespace(commit=repository.commit)))
    service.categories = cast(Any, repository)

    await service.delete_archived_custom(
        workspace_id=uuid4(),
        category_id=category_id,
    )

    assert repository.deleted == category
    assert repository.committed


@pytest.mark.asyncio
async def test_active_category_must_be_archived_before_delete() -> None:
    category_id = uuid4()
    category = SimpleNamespace(id=category_id, is_active=True, is_system=False)
    repository = FakeCategoryRepository(category=category)
    service = CategoryService(cast(Any, SimpleNamespace(commit=repository.commit)))
    service.categories = cast(Any, repository)

    with pytest.raises(CategoryError, match="Сначала перенесите категорию в архив"):
        await service.delete_archived_custom(
            workspace_id=uuid4(),
            category_id=category_id,
        )

    assert repository.deleted is None


@pytest.mark.asyncio
async def test_archived_category_with_operations_cannot_be_deleted() -> None:
    category_id = uuid4()
    category = SimpleNamespace(id=category_id, is_active=False, is_system=False)
    repository = FakeCategoryRepository(category=category, operation_count=1)
    service = CategoryService(cast(Any, SimpleNamespace(commit=repository.commit)))
    service.categories = cast(Any, repository)

    with pytest.raises(CategoryError, match="есть операции"):
        await service.delete_archived_custom(
            workspace_id=uuid4(),
            category_id=category_id,
        )

    assert repository.deleted is None


def category_row(*, is_active: bool, is_system: bool) -> CategoryManagementRow:
    return cast(
        CategoryManagementRow,
        SimpleNamespace(
            category=SimpleNamespace(
                id=uuid4(),
                is_active=is_active,
                is_system=is_system,
            )
        ),
    )


class FakeCategoryRepository:
    def __init__(
        self,
        *,
        category: Any,
        operation_count: int = 0,
        rule_count: int = 0,
    ) -> None:
        self.category = category
        self.operation_count = operation_count
        self.rule_count = rule_count
        self.deleted: object | None = None
        self.committed = False

    async def get_for_workspace(self, _workspace_id: object, _category_id: object) -> object:
        return self.category

    async def count_operations_by_category(self, _workspace_id: object) -> dict[object, int]:
        return {self.category.id: self.operation_count}

    async def count_rules_by_category(self, _workspace_id: object) -> dict[object, int]:
        return {self.category.id: self.rule_count}

    async def delete(self, category: object) -> None:
        self.deleted = category

    async def commit(self) -> None:
        self.committed = True


async def noop_async() -> None:
    return None


def existing_category(category_id: object) -> object:
    async def get_by_name_for_workspace(_workspace_id: object, _name: str) -> object:
        return SimpleNamespace(id=category_id)

    return get_by_name_for_workspace
