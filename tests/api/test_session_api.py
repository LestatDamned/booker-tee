from uuid import uuid4

import pytest
from fastapi import FastAPI, Query, Request

from api_client import ApiTestClient as TestClient
from app.api.dependencies import ApiRequestContext, get_api_request_context, verify_api_csrf
from app.api.errors import ApiError, install_api_exception_handlers
from app.core.security import csrf_token_for_session
from app.core.settings import Settings
from app.features.users.models import User
from app.features.workspaces.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


def test_session_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/session")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Требуется вход.",
        }
    }


def test_session_exposes_workspace_and_capabilities_in_camel_case() -> None:
    app = create_app()
    user_id = uuid4()
    workspace_id = uuid4()

    async def context_override() -> ApiRequestContext:
        user = User(id=user_id, email="max@example.test", name="Max", password_hash="hash")
        workspace = Workspace(
            id=workspace_id,
            owner_id=user_id,
            name="Personal ledger",
            type=WorkspaceType.PERSONAL,
            default_currency="RUB",
        )
        membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        )
        return ApiRequestContext(
            workspace=WorkspaceContext(
                user=user,
                workspace=workspace,
                membership=membership,
            ),
            csrf_token="signed-csrf-token",
        )

    app.dependency_overrides[get_api_request_context] = context_override

    with TestClient(app) as client:
        response = client.get("/api/v1/session")

    assert response.status_code == 200
    assert response.json() == {
        "user": {
            "id": str(user_id),
            "email": "max@example.test",
            "name": "Max",
        },
        "workspace": {
            "id": str(workspace_id),
            "name": "Personal ledger",
            "type": "personal",
            "defaultCurrency": "RUB",
        },
        "membership": {"role": "owner", "status": "active"},
        "capabilities": {
            "canReadWorkspace": True,
            "canWriteFinancialData": True,
            "canManageImports": True,
            "canViewRawImportData": True,
            "canViewMemberDirectory": True,
            "canManageMembers": True,
            "canViewWorkspaceActivity": True,
            "canManageWorkspace": True,
        },
        "csrfToken": "signed-csrf-token",
    }


def test_api_validation_errors_use_stable_envelope() -> None:
    app = FastAPI()
    install_api_exception_handlers(app)

    @app.get("/api/v1/example")
    async def example(count: int = Query(ge=1)) -> dict[str, int]:
        return {"count": count}

    with TestClient(app) as client:
        response = client.get("/api/v1/example", params={"count": 0})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "count" in response.json()["error"]["fieldErrors"]


def test_exception_handlers_do_not_change_non_api_errors() -> None:
    app = FastAPI()
    install_api_exception_handlers(app)

    with TestClient(app) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_api_csrf_accepts_token_bound_to_session() -> None:
    settings = Settings(environment="test", auth_secret_key="test-secret")
    session_token = "session-token"
    csrf_token = csrf_token_for_session(session_token, settings)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [(b"x-csrf-token", csrf_token.encode())],
        }
    )

    verify_api_csrf(request, session_token=session_token, settings=settings)


def test_api_csrf_rejects_missing_token() -> None:
    request = Request({"type": "http", "method": "POST", "headers": []})

    with pytest.raises(ApiError) as error:
        verify_api_csrf(
            request,
            session_token="session-token",
            settings=Settings(environment="test", auth_secret_key="test-secret"),
        )

    assert error.value.status_code == 403
    assert error.value.code == "invalid_csrf"


def test_openapi_describes_runtime_api_error_envelope() -> None:
    openapi = create_app().openapi()

    session_unauthorized = openapi["paths"]["/api/v1/session"]["get"]["responses"]["401"]
    list_validation = openapi["paths"]["/api/v1/operations"]["get"]["responses"]["422"]
    create_validation = openapi["paths"]["/api/v1/manual-ledger"]["post"]["responses"]["422"]

    for response in (session_unauthorized, list_validation, create_validation):
        schema = response["content"]["application/json"]["schema"]
        assert schema["$ref"] == "#/components/schemas/ApiErrorEnvelope"
