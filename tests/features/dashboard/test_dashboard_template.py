from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.templating import create_templates


def test_dashboard_review_action_opens_canonical_import_review() -> None:
    document_id = uuid4()
    html = render_dashboard_summary(
        documents_needing_review=[SimpleNamespace(id=document_id)],
    )

    assert f'href="/app/imports/documents/{document_id}/review"' in html


def render_dashboard_summary(
    *,
    documents_needing_review: list[object],
) -> str:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get(
        "path",
        "",
    )
    return templates.env.get_template("dashboard/summary.html").render(
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        overview=SimpleNamespace(
            month_start="01.06.2026",
            month_end="30.06.2026",
            documents_needing_review=documents_needing_review,
            recent_documents=[],
            reports=SimpleNamespace(
                summary=SimpleNamespace(
                    income=Decimal("0.00"),
                    expense=Decimal("0.00"),
                    profit=Decimal("0.00"),
                ),
                account_balances=[],
                categories=[],
                properties=[],
                uncategorized=[],
            ),
        ),
    )
