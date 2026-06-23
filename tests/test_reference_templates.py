from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.categories.models import CategoryKind
from app.features.ledger.models import OperationType
from app.features.properties.models import PropertyStatus
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

    html = templates.env.get_template("categories/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        kinds=list(CategoryKind),
        category_view="archived",
        category_view_options=[
            ("active", "активные"),
            ("archived", "архив"),
            ("system", "системные"),
            ("all", "все"),
        ],
        user_category_rows=[
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
        ],
        system_category_rows=[
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
        ],
    )

    assert "form-panel" in html
    assert "filter-tab-active" in html
    assert "entity-card-readonly" in html
    assert "category-edit-details" in html
    assert "badge-expense" in html
    assert "системная" in html
    assert "архив" in html
    assert "10 операций" in html
    assert "4 правил" in html
    assert "Супермаркеты и доставка" in html
    assert f'action="/categories/{custom_category_id}"' in html
    assert f'action="/categories/{custom_category_id}/restore"' in html
    assert '<input type="hidden" name="view" value="archived">' in html
    assert "<summary>ID</summary>" in html
    assert str(system_category_id) in html


def test_category_detail_template_shows_operations_and_rules() -> None:
    category_id = uuid4()
    account_id = uuid4()
    rule_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("categories/detail.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        detail=SimpleNamespace(
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
                                account=SimpleNamespace(id=account_id, name="Экспобанк карта"),
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

    assert "Кафе и рестораны" in html
    assert "GREEN HOUSE" in html
    assert "Экспобанк карта" in html
    assert "-890.00 RUB" in html
    assert f"/reports?category_id={category_id}" in html
    assert f"/rules#rule-{rule_id}" in html


def test_properties_template_uses_inline_card_editing() -> None:
    property_id = uuid4()
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("properties/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        properties=[
            SimpleNamespace(
                id=property_id,
                name="9 Maya 20",
                short_name="9M20",
                address="Krasnoyarsk",
                status=PropertyStatus.ACTIVE,
            )
        ],
    )

    assert "form-panel" in html
    assert "entity-card" in html
    assert "form-panel-embedded" in html
    assert "badge-active" in html
    assert "сохранить" in html
    assert f"ID {str(property_id)[:8]}" in html
