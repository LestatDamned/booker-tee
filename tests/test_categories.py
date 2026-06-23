from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from app.features.categories.models import CategoryKind
from app.features.categories.router import categories_url, split_category_rows
from app.features.categories.service import (
    DEFAULT_CATEGORY_SEEDS,
    PROPERTY_MANAGEMENT_CATEGORY_SEEDS,
    SYSTEM_CATEGORY_SEEDS,
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
