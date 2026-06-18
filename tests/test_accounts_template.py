from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.templating import create_templates


def test_accounts_template_makes_balance_primary() -> None:
    account_id = uuid4()
    account = SimpleNamespace(
        id=account_id,
        name="Экспобанк карта",
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
    )
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")

    html = templates.env.get_template("accounts/index.html").render(
        account_details=[
            SimpleNamespace(
                account=account,
                balance=Decimal("23140.76"),
                entries=[object(), object()],
            )
        ],
        account_types=list(AccountType),
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
    )

    assert "account-balance" in html
    assert "money-value money-income" in html
    assert "23140.76" in html
    assert "<small>RUB</small>" in html
