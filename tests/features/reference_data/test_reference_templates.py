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
from app.features.properties.models import PropertyStatus
from app.features.properties.presentation.presenter import (
    PropertiesPagePresenter,
    property_form_state,
)
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
    assert "почему деньги пришли или ушли" in html
    assert "влияет на отчеты" in html
    assert "filter-tab-active" in html
    assert "entity-card-readonly" in html
    assert "category-edit-details" not in html
    assert "badge-expense" in html
    assert "системная" in html
    assert "архив" in html
    assert "10 операций" in html
    assert "4 правил" in html
    assert "отчет" in html
    assert "Супермаркеты и доставка" in html
    assert f'href="/categories/{custom_category_id}"' in html
    assert f'action="/categories/{custom_category_id}/restore"' not in html
    assert '<input type="hidden" name="view" value="all">' in html
    assert "<summary>ID</summary>" in html
    assert f"ID {system_category_id}" in html


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
    assert "управление категорией" in html
    assert f'action="/categories/{category_id}"' in html
    assert f'action="/categories/{category_id}/archive"' in html
    assert "GREEN HOUSE" in html
    assert "Экспобанк карта" in html
    assert "-890.00 RUB" in html
    assert f"/reports?category_id={category_id}" in html
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

    assert 'category-edit-details" open' in html
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

    assert 'category-edit-details" open' in html
    assert 'role="alert"' in html
    assert "Нельзя удалить категорию, у которой есть операции." in html
    assert f'action="/categories/{category_id}/restore"' in html
    assert f'action="/categories/{category_id}/delete"' not in html


def test_properties_template_uses_inline_card_editing() -> None:
    property_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("properties/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        property_page=PropertiesPagePresenter.build_index(
            cast(
                Any,
                [
                    SimpleNamespace(
                        id=property_id,
                        name="9 Maya 20",
                        short_name="9M20",
                        address="Krasnoyarsk",
                        status=PropertyStatus.ACTIVE,
                    )
                ],
            )
        ),
    )

    assert "form-panel" in html
    assert "к чему относится операция" in html
    assert "квартира" in html
    assert "семейная цель" in html
    assert "entity-card" in html
    assert "financial-row" in html
    assert "row-actions" in html
    assert "row-drawer" in html
    assert "property-card__edit" in html
    assert "badge-active" in html
    assert "изменить объект" in html
    assert "сохранить" in html
    assert "Еще действия" in html
    assert f"ID {property_id}" in html
    assert f'id="property-{property_id}"' in html


def test_properties_template_shows_create_error_and_keeps_values() -> None:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("properties/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        property_page=PropertiesPagePresenter.build_index(
            [],
            create_form=property_form_state(
                error="Название объекта обязательно.",
                name="Дом",
                short_name="D",
                address="Красноярск",
            ),
        ),
    )

    assert 'role="alert"' in html
    assert "Название объекта обязательно." in html
    assert 'value="Дом"' in html
    assert 'value="D"' in html
    assert 'value="Красноярск"' in html


def test_properties_template_shows_edit_error_and_keeps_row_values() -> None:
    property_id = uuid4()
    other_property_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("properties/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        property_page=PropertiesPagePresenter.build_index(
            cast(
                Any,
                [
                    SimpleNamespace(
                        id=property_id,
                        name="9 Maya 20",
                        short_name="9M20",
                        address="Krasnoyarsk",
                        status=PropertyStatus.ACTIVE,
                    ),
                    SimpleNamespace(
                        id=other_property_id,
                        name="Office",
                        short_name="OFF",
                        address="Moscow",
                        status=PropertyStatus.ACTIVE,
                    ),
                ],
            ),
            edit_forms_by_property_id={
                property_id: property_form_state(
                    error="Название объекта обязательно.",
                    name="Дом",
                    short_name="D",
                    address="Красноярск",
                ),
            },
        ),
    )

    assert html.count('role="alert"') == 1
    assert 'property-card__edit" open' in html
    assert "Название объекта обязательно." in html
    assert f'id="name-{property_id}" name="name" value="Дом"' in html
    assert f'id="short-name-{property_id}" name="short_name" value="D"' in html
    assert f'id="address-{property_id}" name="address" value="Красноярск"' in html
    assert f'id="name-{other_property_id}" name="name" value="Office"' in html


def test_properties_template_shows_lifecycle_error() -> None:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("properties/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        property_page=PropertiesPagePresenter.build_index(
            [],
            lifecycle_error="Объект не найден в этом workspace.",
        ),
    )

    assert 'role="alert"' in html
    assert "Объект не найден в этом workspace." in html
