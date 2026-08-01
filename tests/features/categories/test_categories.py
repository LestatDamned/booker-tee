from datetime import date
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

import app.features.categories.router as categories_router
from app.features.categories.models import CategoryKind
from app.features.categories.presentation.presenter import (
    CategoryPagePresenter,
    categories_url,
    category_detail_url,
    category_form_error_message,
    category_form_state,
    category_recent_url,
    split_category_rows,
)
from app.features.categories.service import (
    DEFAULT_CATEGORY_SEEDS,
    PROPERTY_MANAGEMENT_CATEGORY_SEEDS,
    SYSTEM_CATEGORY_SEEDS,
    CategoryError,
    CategoryManagementRow,
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


def test_category_presenter_builds_page_state_for_current_view() -> None:
    active_user = category_row(is_active=True, is_system=False)
    archived_user = category_row(is_active=False, is_system=False)
    system = category_row(is_active=True, is_system=True)

    page = CategoryPagePresenter.build_index(
        [active_user, archived_user, system],
        category_view="archived",
        create_form=category_form_state(
            error="Введите название категории.",
            name="",
            kind=CategoryKind.EXPENSE,
            notes="Супермаркеты",
        ),
    )

    assert page.view == "archived"
    assert [row.category for row in page.user_category_rows] == [archived_user.category]
    assert page.system_category_rows == []
    assert page.create_form.error == "Введите название категории."
    assert page.create_form.kind == CategoryKind.EXPENSE
    assert page.create_form_id == "category-create-form"
    assert page.create_label == "создать категорию"
    assert page.create_panel_open
    assert page.create_submit_action.form_id == "category-create-form"
    archived_vm = page.user_category_rows[0]
    assert archived_vm.title == archived_user.category.name
    assert archived_vm.kind_label == "расход"
    assert archived_vm.status_label == "архив"
    assert archived_vm.operation_count_label == "3 операций"
    assert archived_vm.rule_count_label == "2 правил"
    assert archived_vm.detail_action.url == f"/categories/{archived_user.category.id}"
    assert page.view_options[0].url == "/categories"
    assert [option.value for option in page.view_options if option.is_active] == ["archived"]


def test_category_presenter_keeps_create_panel_closed_for_existing_clean_list() -> None:
    active_user = category_row(is_active=True, is_system=False)

    page = CategoryPagePresenter.build_index(
        [active_user],
        category_view="active",
    )

    assert not page.create_panel_open


def test_category_presenter_marks_recent_category_when_visible() -> None:
    active_user = category_row(is_active=True, is_system=False)

    page = CategoryPagePresenter.build_index(
        [active_user],
        category_view="active",
        recent_category_id=active_user.category.id,
    )

    assert page.recent_category is not None
    assert page.recent_category.category == active_user.category
    assert page.recent_category.is_recent
    assert page.recent_category_id == active_user.category.id


def test_category_presenter_builds_detail_action_policy() -> None:
    category_id = uuid4()

    page = CategoryPagePresenter.build_detail(
        cast(
            Any,
            SimpleNamespace(
                category=SimpleNamespace(
                    id=category_id,
                    name="Продукты",
                    kind=CategoryKind.EXPENSE,
                    is_active=False,
                    is_system=False,
                    notes="Супермаркеты",
                ),
                operations=[],
                rules=[],
            ),
        )
    )

    assert page.header.title == "Продукты"
    assert page.header.kind_label == "расход"
    assert page.header.status_label == "архив"
    assert page.header.operation_count_label == "0 операций"
    assert page.header.rule_count_label == "0 правил"
    assert page.edit_toggle_action is not None
    assert page.edit_toggle_action.panel_id == f"category-edit-toggle-{category_id}"
    assert page.lifecycle_action is not None
    assert page.lifecycle_action.url == f"/categories/{category_id}/restore"
    assert page.delete_action is not None
    assert page.delete_action.url == f"/categories/{category_id}/delete"
    assert page.save_action.form_id == f"category-form-{category_id}"


def test_category_presenter_builds_period_context() -> None:
    category_id = uuid4()

    page = CategoryPagePresenter.build_detail(
        cast(
            Any,
            SimpleNamespace(
                category=SimpleNamespace(
                    id=category_id,
                    name="Продукты",
                    kind=CategoryKind.EXPENSE,
                    is_active=True,
                    is_system=False,
                    notes=None,
                ),
                operations=[],
                rules=[],
            ),
        ),
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
    )

    assert page.period_label == "01.06.2026 — 30.06.2026"
    assert page.has_period_filter is True
    assert page.reset_period_url == f"/categories/{category_id}"


def test_category_presenter_preserves_report_drilldown_context() -> None:
    category_id = uuid4()
    return_to = "/app/reports?date_from=2026-06-01&currency=USD"

    page = CategoryPagePresenter.build_detail(
        cast(
            Any,
            SimpleNamespace(
                category=SimpleNamespace(
                    id=category_id,
                    name="Аренда",
                    kind=CategoryKind.INCOME,
                    is_active=True,
                    is_system=False,
                    notes=None,
                ),
                operations=[],
                rules=[],
            ),
        ),
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        currency="USD",
        operation_type=OperationType.INCOME,
        return_to=return_to,
    )

    assert page.back_url == return_to
    assert page.back_label == "вернуться в отчёт"
    assert page.currency == "USD"
    assert page.flow_label == "только доходы"
    reset_url = page.reset_period_url
    assert "?date_from=" not in reset_url
    assert "currency=USD" in reset_url
    assert "type=income" in reset_url
    assert "return_to=%2Fapp%2Freports" in reset_url


def test_category_presenter_keeps_system_detail_readonly() -> None:
    page = CategoryPagePresenter.build_detail(
        cast(
            Any,
            SimpleNamespace(
                category=SimpleNamespace(
                    id=uuid4(),
                    name="Прочий расход",
                    kind=CategoryKind.EXPENSE,
                    is_active=True,
                    is_system=True,
                    notes=None,
                ),
                operations=[],
                rules=[],
            ),
        )
    )

    assert page.header.status_label == "системная"
    assert page.edit_toggle_action is None
    assert page.lifecycle_action is None
    assert page.delete_action is None


def test_categories_url_preserves_non_default_view() -> None:
    assert categories_url("active") == "/categories"
    assert categories_url("archived") == "/categories?view=archived"
    assert categories_url("nope") == "/categories"


def test_category_recent_url_targets_created_category_anchor() -> None:
    category_id = uuid4()

    assert category_recent_url(category_id, "active") == (
        f"/categories?recent_category_id={category_id}#category-{category_id}"
    )
    assert category_recent_url(category_id, "all") == (
        f"/categories?view=all&recent_category_id={category_id}#category-{category_id}"
    )
    assert category_recent_url(category_id, "archived") == (
        f"/categories?recent_category_id={category_id}#category-{category_id}"
    )


def test_category_detail_url_targets_category_detail() -> None:
    category_id = uuid4()

    assert category_detail_url(category_id) == f"/categories/{category_id}"
    assert (
        category_detail_url(
            category_id,
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 30),
        )
        == f"/categories/{category_id}?date_from=2026-06-01&date_to=2026-06-30"
    )

    drilldown = category_detail_url(
        category_id,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        currency="USD",
        operation_type=OperationType.EXPENSE,
        return_to="/app/reports?currency=USD",
    )
    assert "currency=USD" in drilldown
    assert "type=expense" in drilldown
    assert "return_to=%2Fapp%2Freports%3Fcurrency%3DUSD" in drilldown


def test_report_return_path_accepts_only_local_reports() -> None:
    target = "/app/reports?date_from=2026-06-01&currency=RUB"

    assert categories_router.safe_reports_return_path(target) == target
    assert categories_router.safe_reports_return_path("https://evil.example/reports") is None
    assert categories_router.safe_reports_return_path("//evil.example/app/reports") is None
    assert categories_router.safe_reports_return_path("/app/accounts") is None


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_category_update_redirect_keeps_detail_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    category_id = uuid4()
    monkeypatch.setattr(categories_router, "CategoryService", fake_category_service())

    response = await categories_router.update_category(
        category_id=category_id,
        request=cast(Any, SimpleNamespace()),
        session=cast(Any, SimpleNamespace()),
        settings=cast(Any, SimpleNamespace()),
        context=workspace_context(),
        name="Продукты",
        kind=CategoryKind.EXPENSE,
        notes=None,
    )

    assert response.status_code == 303
    assert response.headers["location"] == category_detail_url(category_id)


@pytest.mark.asyncio
async def test_category_lifecycle_redirect_keeps_detail_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    category_id = uuid4()
    monkeypatch.setattr(categories_router, "CategoryService", fake_category_service())

    archive_response = await categories_router.archive_category(
        category_id=category_id,
        request=cast(Any, SimpleNamespace()),
        session=cast(Any, SimpleNamespace()),
        settings=cast(Any, SimpleNamespace()),
        context=workspace_context(),
    )
    restore_response = await categories_router.restore_category(
        category_id=category_id,
        request=cast(Any, SimpleNamespace()),
        session=cast(Any, SimpleNamespace()),
        settings=cast(Any, SimpleNamespace()),
        context=workspace_context(),
    )

    assert archive_response.status_code == 303
    assert archive_response.headers["location"] == category_detail_url(category_id)
    assert restore_response.status_code == 303
    assert restore_response.headers["location"] == category_detail_url(category_id)


def test_category_form_error_message_uses_user_facing_required_name() -> None:
    assert category_form_error_message(CategoryError("Category name is required.")) == (
        "Введите название категории."
    )
    assert category_form_error_message(CategoryError("Категория с таким названием уже есть.")) == (
        "Категория с таким названием уже есть."
    )


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
    category_id = uuid4()
    return cast(
        CategoryManagementRow,
        SimpleNamespace(
            category=SimpleNamespace(
                id=category_id,
                name="Продукты",
                kind=CategoryKind.EXPENSE,
                is_active=is_active,
                is_system=is_system,
                system_key="expense" if is_system else None,
                notes="Супермаркеты",
            ),
            operation_count=3,
            rule_count=2,
        ),
    )


def fake_category_service() -> type:
    class FakeCategoryService:
        def __init__(self, _session: object) -> None:
            pass

        async def update_custom(self, **_kwargs: object) -> None:
            pass

        async def set_active(self, **_kwargs: object) -> None:
            pass

    return FakeCategoryService


def workspace_context() -> Any:
    return cast(Any, SimpleNamespace(workspace=SimpleNamespace(id=uuid4())))


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
