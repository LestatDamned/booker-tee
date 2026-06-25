from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.features.ledger.models import OperationType
from app.templating import create_templates


def test_account_detail_template_uses_compact_entry_cards() -> None:
    account_id = uuid4()
    operation_id = uuid4()
    account = SimpleNamespace(
        id=account_id,
        name="Экспобанк карта",
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    operation = SimpleNamespace(
        id=operation_id,
        operation_date="2026-06-05",
        type=OperationType.EXPENSE,
        category=SimpleNamespace(name="Продукты"),
        property=None,
        description='Списание средств по платежу СБП | ООО "ЛЕНТА"',
        money_entries=[],
    )
    entry = SimpleNamespace(
        operation=operation,
        operation_id=operation_id,
        amount=Decimal("-2438.87"),
        currency="RUB",
        account=account,
    )
    operation.money_entries = [entry]
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("accounts/detail.html").render(
        app_name="Booker Tee",
        detail=SimpleNamespace(
            account=account,
            balance=Decimal("32080.66"),
            entries=[entry],
        ),
        account_types=list(AccountType),
    )

    assert "entry-list" in html
    assert "entry-item" in html
    assert "tone-expense" in html
    assert "amount-expense" in html
    assert "badge-expense" in html
    assert "Экспобанк карта" in html
    assert "Продукты" in html
    assert "Технические детали" in html
    assert f"ID {operation_id}" in html
    assert "<th>операция</th>" not in html
