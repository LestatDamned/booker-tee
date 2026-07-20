from types import SimpleNamespace
from typing import Any, cast

from app.features.workspaces.models import WorkspaceRole
from app.templating import create_templates


def test_base_header_hides_write_actions_for_viewer() -> None:
    html = render_template(
        "base.html",
        current_user=SimpleNamespace(email="viewer@example.com"),
        current_workspace=SimpleNamespace(name="Family"),
        current_membership=SimpleNamespace(role=WorkspaceRole.VIEWER),
        workspace_permissions=permissions(
            can_write_financial_data=False,
            can_manage_imports=False,
        ),
    )

    assert "наблюдатель" in html
    assert 'href="/reports"' in html
    assert 'href="/imports/upload"' not in html
    assert 'href="/app/ledger/manual"' in html


def test_accounts_template_hides_create_form_for_viewer() -> None:
    html = render_template(
        "accounts/index.html",
        account_details=[],
        account_types=[],
        current_user=SimpleNamespace(email="viewer@example.com"),
        current_workspace=SimpleNamespace(name="Family"),
        workspace=SimpleNamespace(name="Family", default_currency="RUB"),
        workspace_permissions=permissions(can_write_financial_data=False),
    )

    assert 'action="/accounts"' not in html
    assert "Попросите редактора" not in html


def test_accounts_template_shows_create_form_for_editor() -> None:
    html = render_template(
        "accounts/index.html",
        account_details=[],
        account_types=[],
        current_user=SimpleNamespace(email="editor@example.com"),
        current_workspace=SimpleNamespace(name="Family"),
        workspace=SimpleNamespace(name="Family", default_currency="RUB"),
        workspace_permissions=permissions(can_write_financial_data=True),
    )

    assert 'action="/accounts"' in html


def render_template(template_name: str, **context: object) -> str:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    context.setdefault("app_name", "Booker Tee")
    context.setdefault("css_version", "test-css-version")
    return templates.env.get_template(template_name).render(**context)


def permissions(**overrides: bool) -> SimpleNamespace:
    values = {
        "can_read_workspace": True,
        "can_write_financial_data": False,
        "can_manage_imports": False,
        "can_manage_members": False,
        "can_manage_workspace": False,
    }
    values.update(overrides)
    return SimpleNamespace(role=WorkspaceRole.VIEWER, **values)
