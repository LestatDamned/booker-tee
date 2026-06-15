from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.ledger.models import OperationType
from app.templating import create_templates


def test_reports_template_marks_financial_tones() -> None:
    account_id = uuid4()
    operation = SimpleNamespace(
        operation_date="2026-06-13",
        type=OperationType.EXPENSE,
        description="Без категории",
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("reports/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        filters=SimpleNamespace(
            date_from=None,
            date_to=None,
            account_id=None,
            category_id=None,
            property_id=None,
        ),
        accounts=[SimpleNamespace(id=account_id, name="Карта")],
        categories=[],
        properties=[],
        overview=SimpleNamespace(
            summary=SimpleNamespace(
                income=Decimal("100.00"),
                expense=Decimal("40.00"),
                profit=Decimal("60.00"),
            ),
            account_balances=[
                SimpleNamespace(
                    account=SimpleNamespace(id=account_id, name="Карта", currency="RUB"),
                    balance=Decimal("60.00"),
                )
            ],
            categories=[
                SimpleNamespace(
                    category_name="Продукты",
                    income=Decimal("0.00"),
                    expense=Decimal("40.00"),
                    profit=Decimal("-40.00"),
                )
            ],
            properties=[],
            uncategorized=[SimpleNamespace(operation=operation, total=Decimal("-5.00"))],
        ),
    )

    assert "metric-income" in html
    assert "metric-expense" in html
    assert "metric-profit" in html
    assert "amount-income" in html
    assert "amount-expense" in html
    assert "type-badge tone-expense" in html
