from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from manual_ledger_support import (
    manual_expense,
    manual_ledger_app,
    workspace_context,
)

from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import OperationStatus
from app.features.workspaces.models import WorkspaceRole
from app.web.features.ledger.manual.query_state import (
    MANUAL_LEDGER_URL,
)


def test_cancel_replaces_row_with_restore_and_delete_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}/cancel",
            data={"return_to": "/_next/ledger/manual?page=1&per_page=50"},
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert "HX-Retarget" not in response.headers
    assert "отменено" in response.text
    assert f'action="/_next/ledger/manual/{operation.id}/restore"' in response.text
    assert f'action="/_next/ledger/manual/{operation.id}/delete"' in response.text
    assert 'name="csrf_token" value="test-csrf-token"' in response.text
    assert calls.cancelled_ids == [operation.id]


def test_cancel_that_leaves_status_filter_replaces_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.realistic_listing = True

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}/cancel",
            data={"return_to": "/_next/ledger/manual?status=confirmed&page=1&per_page=50"},
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#manual-ledger-results"
    assert f'id="next-operation-{operation.id}"' not in response.text
    assert "0 ручных операций" in response.text


def test_restore_replaces_cancelled_row(monkeypatch: pytest.MonkeyPatch) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = replace(manual_expense(), status=OperationStatus.IGNORED)
    calls.operations = [operation]

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}/restore",
            data={"return_to": MANUAL_LEDGER_URL},
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert "подтверждено" in response.text
    assert f'hx-post="/_next/ledger/manual/{operation.id}/cancel"' in response.text
    assert calls.restored_ids == [operation.id]


def test_delete_always_rebuilds_results_and_clears_operation_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = replace(manual_expense(), status=OperationStatus.IGNORED)
    calls.operations = [operation]
    calls.realistic_listing = True

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}/delete",
            data={
                "return_to": (
                    f"/_next/ledger/manual?operation_id={operation.id}&page=1&per_page=50"
                )
            },
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#manual-ledger-results"
    assert "operation_id" not in response.headers["HX-Replace-Url"]
    assert f'id="next-operation-{operation.id}"' not in response.text
    assert "0 ручных операций" in response.text
    assert calls.deleted_ids == [operation.id]


def test_lifecycle_actions_have_http_redirect_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}/cancel",
            data={"return_to": MANUAL_LEDGER_URL},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert f"operation_id={operation.id}" in response.headers["location"]
    assert response.headers["location"].endswith(f"#next-operation-{operation.id}")


def test_lifecycle_error_returns_localized_422_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.lifecycle_error = LedgerPostingError("Only confirmed manual operations can be cancelled.")

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}/cancel",
            data={"return_to": MANUAL_LEDGER_URL},
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 422
    assert "Отменить можно только подтверждённую ручную операцию" in response.text
    assert 'role="alert"' in response.text


def test_lifecycle_http_error_uses_technical_422_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.lifecycle_error = LedgerPostingError("Only confirmed manual operations can be cancelled.")

    with TestClient(app) as client:
        response = client.post(
            f"{MANUAL_LEDGER_URL}/{operation.id}/cancel",
            data={"return_to": MANUAL_LEDGER_URL},
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "Отменить можно только подтверждённую ручную операцию."}


def test_lifecycle_actions_require_financial_write_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.VIEWER)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]

    with TestClient(app) as client:
        response = client.post(f"/_next/ledger/manual/{operation.id}/cancel")

    assert response.status_code == 403
    assert calls.cancelled_ids == []
