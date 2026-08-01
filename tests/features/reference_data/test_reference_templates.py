from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.categories.models import CategoryKind
from app.features.categories.presentation.presenter import (
    CategoryPagePresenter,
    category_form_state,
)
from app.features.ledger.models import OperationType
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.templating import create_templates


def test_categories_template_uses_compact_cards() -> None:
    system_category_id = uuid4()
    custom_category_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    category_rows = [
        SimpleNamespace(
            category=SimpleNamespace(
                id=custom_category_id,
                name="Продукты",
                kind=CategoryKind.EXPENSE,
                is_active=False,
                is_system=False,
                system_key=None,
                notes="Супермаркеты и доставка",
            ),
            operation_count=10,
            rule_count=4,
        ),
        SimpleNamespace(
            category=SimpleNamespace(
                id=system_category_id,
                name="Прочий расход",
                kind=CategoryKind.EXPENSE,
                is_active=True,
                is_system=True,
                system_key="expense",
                notes=None,
            ),
            operation_count=2,
            rule_count=0,
        ),
    ]

    html = templates.env.get_template("categories/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        category_page=CategoryPagePresenter.build_index(
            cast(Any, category_rows),
            category_view="all",
        ),
    )

    assert "form-panel" in html
    assert "category-create-details" in html
    assert 'category-create-details" open' not in html
    assert "создать категорию" in html
    assert "почему деньги пришли или ушли" in html
    assert "влияет на отчеты" in html
    assert "filter-tab-active" in html
    assert "категория готова" not in html
    assert "financial-row" in html
    assert "row-actions" in html
    assert 'data-entity-working="true"' in html
    assert "category-card--system" in html
    assert "category-edit-details" not in html
    assert "badge-expense" in html
    assert "системная" in html
    assert "архив" in html
    assert "10 операций" in html
    assert "4 правил" in html
    assert "открыть категорию" in html
    assert "Еще действия" not in html
    assert f"/reports?category_id={custom_category_id}" not in html
    assert "Супермаркеты и доставка" in html
    assert f'href="/categories/{custom_category_id}"' in html
    assert f'id="category-{custom_category_id}"' in html
    assert f'action="/categories/{custom_category_id}/restore"' not in html
    assert '<input type="hidden" name="view" value="all">' in html
    assert "Показать ID" not in html
    assert f"ID {system_category_id}" not in html


def test_categories_template_shows_recent_created_feedback() -> None:
    category_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("categories/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        category_page=CategoryPagePresenter.build_index(
            cast(
                Any,
                [
                    SimpleNamespace(
                        category=SimpleNamespace(
                            id=category_id,
                            name="Продукты",
                            kind=CategoryKind.EXPENSE,
                            is_active=True,
                            is_system=False,
                            system_key=None,
                            notes="Супермаркеты",
                        ),
                        operation_count=0,
                        rule_count=0,
                    )
                ],
            ),
            category_view="active",
            recent_category_id=category_id,
        ),
    )

    assert "категория готова" in html
    assert "Продукты" in html
    assert "расход" in html
    assert "Супермаркеты" in html
    assert "Показать в списке" in html
    assert f'href="#category-{category_id}"' in html
    assert "category-card--recent" in html


def test_categories_template_empty_state_points_to_creation_form() -> None:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("categories/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        category_page=CategoryPagePresenter.build_index([], category_view="active"),
    )

    assert "Категорий не найдено" in html
    assert "добавьте категорию для будущих операций и правил" in html
    assert 'category-create-details" open' in html
    assert 'href="#name"' in html


def test_categories_template_shows_create_error_and_keeps_values() -> None:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("categories/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        category_page=CategoryPagePresenter.build_index(
            [],
            category_view="active",
            create_form=category_form_state(
                error="Категория с таким названием уже есть.",
                name="Продукты",
                kind=CategoryKind.EXPENSE,
                notes="Супермаркеты",
            ),
        ),
    )

    assert 'role="alert"' in html
    assert 'category-create-details" open' in html
    assert "Категория с таким названием уже есть." in html
    assert 'value="Продукты"' in html
    assert f'<option value="{CategoryKind.EXPENSE.value}" selected>' in html
    assert 'value="Супермаркеты"' in html


def test_category_detail_template_shows_operations_and_rules() -> None:
    category_id = uuid4()
    account_id = uuid4()
    rule_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("categories/detail.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        category_page=CategoryPagePresenter.build_detail(
            cast(
                Any,
                SimpleNamespace(
                    category=SimpleNamespace(
                        id=category_id,
                        name="Кафе и рестораны",
                        kind=CategoryKind.EXPENSE,
                        is_active=True,
                        is_system=False,
                        notes="Еда вне дома",
                    ),
                    summary=SimpleNamespace(
                        income=Decimal("0.00"),
                        expense=Decimal("12254.60"),
                        profit=Decimal("-12254.60"),
                    ),
                    operations=[
                        SimpleNamespace(
                            operation=SimpleNamespace(
                                operation_date=date(2026, 6, 19),
                                type=OperationType.EXPENSE,
                                description="GREEN HOUSE",
                                property=None,
                                money_entries=[
                                    SimpleNamespace(
                                        account=SimpleNamespace(
                                            id=account_id,
                                            name="Экспобанк карта",
                                        ),
                                        amount=Decimal("-890.00"),
                                        currency="RUB",
                                    )
                                ],
                            ),
                            total=Decimal("-890.00"),
                        )
                    ],
                    rules=[
                        SimpleNamespace(
                            id=rule_id,
                            pattern="GREEN HOUSE",
                            is_active=True,
                            match_type=TransactionRuleMatchType.CONTAINS,
                            application_mode=TransactionRuleApplicationMode.AUTO_APPLY,
                            direction=MoneyDirection.OUTFLOW,
                            target_operation_type=OperationType.EXPENSE,
                        )
                    ],
                ),
            )
        ),
    )

    assert "Кафе и рестораны" in html
    assert "financial-row" in html
    assert "row-actions" in html
    assert "изменить категорию" in html
    assert "Еще действия" not in html
    assert "Показать ID" not in html
    assert f'action="/categories/{category_id}"' in html
    assert f'action="/categories/{category_id}/archive"' in html
    assert "GREEN HOUSE" in html
    assert "Экспобанк карта" in html
    assert "-890.00 RUB" in html
    assert f"/reports?category_id={category_id}" not in html
    assert f"/rules#rule-{rule_id}" in html


def test_category_detail_template_shows_edit_error_and_keeps_values() -> None:
    category_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("categories/detail.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        category_page=CategoryPagePresenter.build_detail(
            cast(
                Any,
                SimpleNamespace(
                    category=SimpleNamespace(
                        id=category_id,
                        name="Кафе",
                        kind=CategoryKind.EXPENSE,
                        is_active=True,
                        is_system=False,
                        notes="Старое описание",
                    ),
                    summary=SimpleNamespace(
                        income=Decimal("0.00"),
                        expense=Decimal("0.00"),
                        profit=Decimal("0.00"),
                    ),
                    operations=[],
                    rules=[],
                ),
            ),
            edit_form=category_form_state(
                error="Категория с таким названием уже есть.",
                name="Продукты",
                kind=CategoryKind.INCOME,
                notes="Новое описание",
            ),
        ),
    )

    assert 'category-detail-card__edit" open' in html
    assert 'role="alert"' in html
    assert "Категория с таким названием уже есть." in html
    assert 'name="name" value="Продукты"' in html
    assert f'<option value="{CategoryKind.INCOME.value}" selected>' in html
    assert 'name="notes" value="Новое описание"' in html


def test_category_detail_template_shows_lifecycle_error() -> None:
    category_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("categories/detail.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        category_page=CategoryPagePresenter.build_detail(
            cast(
                Any,
                SimpleNamespace(
                    category=SimpleNamespace(
                        id=category_id,
                        name="Архивная категория",
                        kind=CategoryKind.EXPENSE,
                        is_active=False,
                        is_system=False,
                        notes=None,
                    ),
                    summary=SimpleNamespace(
                        income=Decimal("0.00"),
                        expense=Decimal("0.00"),
                        profit=Decimal("0.00"),
                    ),
                    operations=[
                        SimpleNamespace(
                            operation=SimpleNamespace(
                                operation_date=date(2026, 6, 19),
                                type=OperationType.EXPENSE,
                                description="GREEN HOUSE",
                                property=None,
                                money_entries=[
                                    SimpleNamespace(
                                        account=SimpleNamespace(name="Экспобанк карта"),
                                        amount=Decimal("-890.00"),
                                        currency="RUB",
                                    )
                                ],
                            ),
                            total=Decimal("-890.00"),
                        )
                    ],
                    rules=[],
                ),
            ),
            lifecycle_error="Нельзя удалить категорию, у которой есть операции.",
        ),
    )

    assert 'category-detail-card__edit" open' in html
    assert 'role="alert"' in html
    assert "Нельзя удалить категорию, у которой есть операции." in html
    assert f'action="/categories/{category_id}/restore"' in html
    assert f'action="/categories/{category_id}/delete"' not in html
