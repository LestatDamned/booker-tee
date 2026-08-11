from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from api_client import ApiTestClient as TestClient
from app.api.dependencies import get_api_request_context
from app.api.v1.workspaces.dependencies import get_workspace_activity_service
from app.features.workspaces.domain.types import WorkspaceAuditEventType, WorkspaceRole
from app.features.workspaces.errors import (
    WorkspaceActivityForbiddenError,
    WorkspaceNotFoundError,
)
from app.features.workspaces.schemas import (
    WorkspaceActivityActorDto,
    WorkspaceActivityCursorDto,
    WorkspaceActivityDetailsDto,
    WorkspaceActivityDto,
    WorkspaceActivityItemDto,
    WorkspaceActivityItemScope,
    WorkspaceActivityScope,
    WorkspaceActivitySummaryCode,
)
from app.main import create_app


def test_workspace_activity_returns_keyset_page_and_no_store() -> None:
    app, service, actor_id, workspace_id, activity = activity_app()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/workspaces/{workspace_id}/activity?limit=1")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert activity.next_cursor is not None
    assert service.read.await_args.kwargs == {
        "actor_user_id": actor_id,
        "workspace_id": workspace_id,
        "limit": 1,
        "scope": WorkspaceActivityScope.ALL,
        "before_created_at": None,
        "before_id": None,
    }
    assert response.json()["items"][0]["summaryCode"] == "member_role_changed"
    assert response.json()["items"][0]["scope"] == "team"
    assert response.json()["nextCursor"]["beforeId"] == str(activity.next_cursor.before_id)
    assert response.json()["nextCursor"]["scope"] == "all"


def test_workspace_activity_passes_explicit_finance_scope() -> None:
    app, service, _, workspace_id, _ = activity_app()

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/workspaces/{workspace_id}/activity?scope=finance"
        )

    assert response.status_code == 200
    assert service.read.await_args.kwargs["scope"] == WorkspaceActivityScope.FINANCE


def test_workspace_activity_validates_cursor_pair() -> None:
    app, service, _, workspace_id, _ = activity_app()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/workspaces/{workspace_id}/activity?beforeId={uuid4()}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_activity_cursor"
    service.read.assert_not_awaited()


def test_workspace_activity_maps_forbidden_and_not_found() -> None:
    app, service, _, workspace_id, _ = activity_app()

    with TestClient(app) as client:
        service.read.side_effect = WorkspaceActivityForbiddenError("forbidden")
        forbidden = client.get(f"/api/v1/workspaces/{workspace_id}/activity")
        service.read.side_effect = WorkspaceNotFoundError("foreign")
        missing = client.get(f"/api/v1/workspaces/{workspace_id}/activity")

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "workspace_activity_forbidden"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "workspace_not_found"


def activity_app() -> tuple[FastAPI, AsyncMock, UUID, UUID, WorkspaceActivityDto]:
    context = api_context(role=WorkspaceRole.OWNER)
    workspace_id = uuid4()
    created_at = datetime(2026, 8, 10, 10, 30, tzinfo=UTC)
    activity = WorkspaceActivityDto(
        workspace_id=workspace_id,
        items=[
            WorkspaceActivityItemDto(
                id=uuid4(),
                event_type=WorkspaceAuditEventType.MEMBER_ROLE_CHANGED,
                scope=WorkspaceActivityItemScope.TEAM,
                actor=WorkspaceActivityActorDto(
                    id=context.workspace.user.id,
                    display_name="Max",
                ),
                target=WorkspaceActivityActorDto(id=uuid4(), display_name="Anna"),
                entity=None,
                summary_code=WorkspaceActivitySummaryCode.MEMBER_ROLE_CHANGED,
                details=WorkspaceActivityDetailsDto(
                    old_role=WorkspaceRole.VIEWER,
                    new_role=WorkspaceRole.EDITOR,
                ),
                created_at=created_at,
            )
        ],
        next_cursor=WorkspaceActivityCursorDto(
            before_created_at=created_at,
            before_id=uuid4(),
            scope=WorkspaceActivityScope.ALL,
        ),
    )
    service = AsyncMock()
    service.read.return_value = activity
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_workspace_activity_service] = lambda: service
    return app, service, context.workspace.user.id, workspace_id, activity
