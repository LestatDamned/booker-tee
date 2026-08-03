from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest

from api_client import ApiTestClient as TestClient
from app.core.config import get_settings
from app.db.session import get_session
from app.main import create_app


@pytest.mark.parametrize(
    ("path", "form"),
    [
        ("/workspaces", {"name": "Family"}),
        (
            "/workspaces/{workspace_id}",
            {"name": "Family", "workspace_type": "personal", "default_currency": "RUB"},
        ),
        ("/workspaces/{workspace_id}/select", {}),
        ("/workspaces/{workspace_id}/invitations", {"role": "viewer"}),
        ("/workspaces/{workspace_id}/invitations/{resource_id}/revoke", {}),
        ("/workspaces/{workspace_id}/members/{resource_id}/role", {"role": "viewer"}),
        ("/workspaces/{workspace_id}/members/{resource_id}/disable", {}),
        ("/workspaces/{workspace_id}/members/{resource_id}/reactivate", {}),
        ("/workspaces/invitations/invitation-token/accept", {}),
    ],
)
def test_authenticated_workspace_post_routes_reject_missing_csrf(
    path: str,
    form: dict[str, str],
) -> None:
    app = create_app()
    settings = get_settings()
    workspace_id = uuid4()
    resource_id = uuid4()

    async def session_override() -> AsyncIterator[Any]:
        yield object()

    app.dependency_overrides[get_session] = session_override

    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, "workspace-security-session")
        response = client.post(
            path.format(workspace_id=workspace_id, resource_id=resource_id),
            data=form,
            follow_redirects=False,
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Недействительный CSRF токен."}
