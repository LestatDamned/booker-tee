from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.ledger.models import OperationType
from app.templating import create_templates


def test_reports_template_marks_financial_tones() -> None:
    account_id = uuid4()
    category_id = uuid4()
    operation = SimpleNamespace(
        operation_date="2026-06-13",
        type=OperationType.EXPENSE,
        description="Без категории",
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("reports/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
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
                    category_id=category_id,
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
    assert "money-value money-income" in html
    assert "money-value money-expense" in html
    assert "money-value money-profit" in html
    assert "<small>RUB</small>" in html
    assert "report-table" in html
    assert 'data-label="прибыль"' in html
    assert f'href="/categories/{category_id}"' in html
    assert "amount-income" in html
    assert "amount-expense" in html
    assert "badge-expense" in html


def test_reports_template_empty_state_points_to_accounts_without_accounts() -> None:
    html = render_reports(
        accounts=[],
        overview=empty_overview(account_balances=[]),
    )

    assert "Сначала создайте счет" in html
    assert "подтвержденные операции для отчетов" in html
    assert 'href="/accounts"' in html
    assert "Балансы счетов" not in html
    assert "По категориям" not in html


def test_reports_template_empty_state_points_to_imports_without_confirmed_operations() -> None:
    account_id = uuid4()
    html = render_reports(
        accounts=[SimpleNamespace(id=account_id, name="Карта")],
        overview=empty_overview(
            account_balances=[
                SimpleNamespace(
                    account=SimpleNamespace(id=account_id, name="Карта", currency="RUB"),
                    balance=Decimal("0.00"),
                )
            ]
        ),
    )

    assert "Отчет пока пуст" in html
    assert "Переводы между своими счетами в прибыль не входят" in html
    assert 'href="/imports"' in html
    assert 'href="/imports/upload"' in html
    assert "По категориям" not in html


def test_reports_template_empty_state_points_to_review_when_documents_need_review() -> None:
    account_id = uuid4()
    document_id = uuid4()
    html = render_reports(
        accounts=[SimpleNamespace(id=account_id, name="Карта")],
        documents_needing_review=[SimpleNamespace(id=document_id)],
        overview=empty_overview(
            account_balances=[
                SimpleNamespace(
                    account=SimpleNamespace(id=account_id, name="Карта", currency="RUB"),
                    balance=Decimal("0.00"),
                )
            ]
        ),
    )

    assert "Есть выписка со строками на проверке" in html
    assert "неподтвержденные строки не входят в доходы, расходы и прибыль" in html
    assert f'href="/imports/documents/{document_id}/review"' in html
    assert "проверить строки" in html
    assert 'href="/imports/upload"' not in html
    assert "По категориям" not in html


def render_reports(
    *,
    accounts: list[object],
    overview: object,
    documents_needing_review: list[object] | None = None,
) -> str:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    return templates.env.get_template("reports/index.html").render(
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        filters=SimpleNamespace(
            date_from=None,
            date_to=None,
            account_id=None,
            category_id=None,
            property_id=None,
        ),
        accounts=accounts,
        categories=[],
        documents_needing_review=documents_needing_review or [],
        properties=[],
        overview=overview,
    )


def empty_overview(*, account_balances: list[object]) -> SimpleNamespace:
    return SimpleNamespace(
        summary=SimpleNamespace(
            income=Decimal("0.00"),
            expense=Decimal("0.00"),
            profit=Decimal("0.00"),
        ),
        account_balances=account_balances,
        categories=[],
        properties=[],
        uncategorized=[],
    )
