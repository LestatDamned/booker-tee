from uuid import UUID, uuid4

import pytest
from workspaces_support import (
    workspace_invitations_app,
    workspace_members_app,
    workspace_ownership_app,
    workspace_settings_app,
    workspaces_app,
)

from api_client import ApiTestClient as TestClient
from app.api.v1.auth.dependencies import get_identity_email_sender
from app.features.users.email_delivery import IdentityEmail
from app.features.workspaces.commands import (
    CreateWorkspaceCommand,
    LeaveWorkspaceCommand,
    TransferWorkspaceOwnershipCommand,
    TransitionWorkspaceLifecycleCommand,
    TransitionWorkspaceMemberCommand,
    UpdateWorkspaceMemberRoleApiCommand,
    UpdateWorkspaceSettingsCommand,
)
from app.features.workspaces.domain.types import WorkspaceRole, WorkspaceType
from app.features.workspaces.errors import (
    WorkspaceIdempotencyConflictError,
    WorkspaceInvitationConflictError,
    WorkspaceInvitationNotFoundError,
    WorkspaceInvitationTransitionError,
    WorkspaceLifecycleConflictError,
    WorkspaceLifecycleTransitionError,
    WorkspaceMemberConflictError,
    WorkspaceMemberTransitionError,
    WorkspaceNotFoundError,
    WorkspaceSettingsForbiddenError,
    WorkspaceSwitchConflictError,
    WorkspaceUpdateConflictError,
)
from app.main import create_app


def test_workspace_directory_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/workspaces")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_workspace_directory_returns_camel_case_server_capabilities() -> None:
    app, reader, _, _ = workspaces_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/workspaces")

    assert response.status_code == 200
    payload = response.json()
    assert payload["currentWorkspaceId"] == str(reader.directory.current_workspace_id)
    assert payload["capabilities"] == {"canCreate": True}
    assert payload["items"][0]["isCurrent"] is True
    assert payload["items"][0]["blockingReasonCodes"] == ["workspace_current"]
    assert payload["items"][1]["capabilities"]["canSelect"] is True
    assert payload["workspaceTypeOptions"][0] == {
        "value": "personal",
        "label": "Личное",
    }
    assert len(reader.calls) == 1
    assert reader.calls[0][0] != reader.directory.current_workspace_id
    assert reader.calls[0][1] == reader.directory.current_workspace_id


def test_workspace_create_normalizes_and_dispatches_idempotent_command() -> None:
    app, _, creator, _ = workspaces_app()
    idempotency_key = uuid4()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces",
            headers={"Idempotency-Key": str(idempotency_key)},
            json={
                "name": "  Семейный   бюджет ",
                "workspaceType": "family",
                "defaultCurrency": " rub ",
            },
        )

    assert response.status_code == 201
    assert isinstance(creator.calls[0][1], UUID)
    assert creator.calls[0][2:] == (
        CreateWorkspaceCommand(
            name="Семейный бюджет",
            workspace_type=WorkspaceType.FAMILY,
            default_currency="RUB",
        ),
        idempotency_key,
    )
    payload = response.json()
    assert payload["workspace"]["isCurrent"] is True
    assert payload["session"]["workspace"]["id"] == payload["workspace"]["id"]
    assert payload["navigationOutcome"] == {
        "kind": "workspace_changed",
        "href": "/app/workspaces",
        "boundary": "hard_reload",
    }


def test_workspace_create_requires_key_and_returns_workspace_field_errors() -> None:
    app, _, creator, _ = workspaces_app()

    with TestClient(app) as client:
        missing_key = client.post(
            "/api/v1/workspaces",
            json={"name": "Дом", "workspaceType": "personal"},
        )
        invalid = client.post(
            "/api/v1/workspaces",
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": " ", "workspaceType": "personal"},
        )

    assert missing_key.status_code == 422
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "workspace_validation_error"
    assert invalid.json()["error"]["fieldErrors"] == {
        "name": ["Название пространства обязательно."]
    }
    assert creator.calls == []


def test_workspace_create_maps_idempotency_conflict() -> None:
    app, _, creator, _ = workspaces_app()
    creator.error = WorkspaceIdempotencyConflictError("Ключ уже использован.")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces",
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": "Дом", "workspaceType": "personal"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_conflict"


def test_workspace_select_dispatches_expected_current_and_returns_session() -> None:
    app, reader, _, switcher = workspaces_app()
    target_id = reader.directory.items[1].id

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{target_id}/select",
            json={"expectedCurrentWorkspaceId": str(reader.directory.current_workspace_id)},
        )

    assert response.status_code == 200
    assert isinstance(switcher.calls[0][1], UUID)
    assert switcher.calls[0][2:] == (
        target_id,
        reader.directory.current_workspace_id,
    )
    assert response.json()["session"]["workspace"]["id"] == str(target_id)
    assert response.json()["navigationOutcome"]["boundary"] == "hard_reload"


def test_workspace_select_masks_missing_and_reports_stale_current() -> None:
    app, reader, _, switcher = workspaces_app()
    target_id = reader.directory.items[1].id
    payload = {"expectedCurrentWorkspaceId": str(reader.directory.current_workspace_id)}

    with TestClient(app) as client:
        switcher.error = WorkspaceNotFoundError("foreign")
        missing = client.post(f"/api/v1/workspaces/{target_id}/select", json=payload)
        new_current_id = uuid4()
        switcher.error = WorkspaceSwitchConflictError(current_workspace_id=new_current_id)
        conflict = client.post(f"/api/v1/workspaces/{target_id}/select", json=payload)

    assert missing.status_code == 404
    assert missing.json()["error"] == {
        "code": "workspace_not_found",
        "message": "Пространство больше недоступно.",
    }
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "workspace_switch_conflict"
    assert conflict.json()["error"]["details"] == {"currentWorkspaceId": str(new_current_id)}


def test_workspace_settings_read_is_target_scoped_and_returns_impact() -> None:
    app, service, _, actor_id, workspace_id = workspace_settings_app()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert response.status_code == 200
    assert service.read_calls == [(actor_id, workspace_id)]
    payload = response.json()
    assert payload["workspace"]["name"] == "Семейный бюджет"
    assert payload["workspace"]["capabilities"]["canUpdate"] is True
    assert payload["lifecycleImpact"] == {
        "financialHistoryPreserved": True,
        "currentSessionCount": 2,
        "pendingInvitationCount": 1,
        "activeIntegrationConnectionCount": 1,
        "activeChatIdentityBindingCount": 2,
    }


def test_workspace_settings_masks_missing_and_foreign_identically() -> None:
    app, service, _, _, workspace_id = workspace_settings_app()
    service.read_error = WorkspaceNotFoundError("foreign")

    with TestClient(app) as client:
        response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "workspace_not_found",
        "message": "Пространство не найдено.",
    }


def test_workspace_settings_update_dispatches_expected_snapshot() -> None:
    app, service, _, actor_id, workspace_id = workspace_settings_app()
    expected = service.settings.workspace.updated_at

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/workspaces/{workspace_id}",
            json={
                "name": "  Новый   дом ",
                "workspaceType": "personal",
                "defaultCurrency": " usd ",
                "expectedUpdatedAt": expected.isoformat(),
            },
        )

    assert response.status_code == 200
    assert service.update_calls == [
        (
            actor_id,
            workspace_id,
            UpdateWorkspaceSettingsCommand(
                name="Новый дом",
                workspace_type=WorkspaceType.PERSONAL,
                default_currency="USD",
                expected_updated_at=expected,
            ),
        )
    ]


def test_workspace_settings_update_maps_authority_conflict_and_validation() -> None:
    app, service, _, _, workspace_id = workspace_settings_app()
    payload = {
        "name": "Дом",
        "workspaceType": "personal",
        "defaultCurrency": "RUB",
        "expectedUpdatedAt": service.settings.workspace.updated_at.isoformat(),
    }

    with TestClient(app) as client:
        service.update_error = WorkspaceSettingsForbiddenError("forbidden")
        forbidden = client.put(f"/api/v1/workspaces/{workspace_id}", json=payload)
        service.update_error = WorkspaceUpdateConflictError("stale")
        conflict = client.put(f"/api/v1/workspaces/{workspace_id}", json=payload)
        service.update_error = None
        invalid = client.put(
            f"/api/v1/workspaces/{workspace_id}",
            json={**payload, "name": " "},
        )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "workspace_forbidden"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "workspace_update_conflict"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "workspace_validation_error"
    assert invalid.json()["error"]["fieldErrors"] == {
        "name": ["Название пространства обязательно."]
    }


def test_workspace_deactivate_dispatches_snapshot_and_returns_boundary_impact() -> None:
    app, settings, lifecycle_service, actor_id, workspace_id = workspace_settings_app()
    expected_current_id = lifecycle_service.result.workspace.id
    expected_updated_at = settings.settings.workspace.updated_at

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/deactivate",
            json={
                "expectedCurrentWorkspaceId": str(expected_current_id),
                "expectedWorkspaceUpdatedAt": expected_updated_at.isoformat(),
            },
        )

    assert response.status_code == 200
    assert isinstance(lifecycle_service.calls[0][2], UUID)
    assert lifecycle_service.calls[0][:2] == ("deactivate", actor_id)
    assert lifecycle_service.calls[0][3:] == (
        workspace_id,
        TransitionWorkspaceLifecycleCommand(
            expected_workspace_updated_at=expected_updated_at,
            expected_current_workspace_id=expected_current_id,
        ),
    )
    assert response.json()["impact"] == {
        "movedSessionCount": 2,
        "revokedInvitationCount": 1,
        "disabledIntegrationConnectionCount": 1,
        "disabledChatConversationBindingCount": 1,
        "disabledChatIdentityBindingCount": 2,
        "consumedChatConversationStateCount": 1,
        "failedIntegrationDeliveryCount": 1,
    }
    assert response.json()["navigationOutcome"] == {
        "kind": "workspace_changed",
        "href": "/app/workspaces",
        "boundary": "hard_reload",
    }


def test_workspace_lifecycle_masks_target_and_maps_stale_and_blocking_reasons() -> None:
    app, settings, lifecycle_service, _, workspace_id = workspace_settings_app()
    payload = {
        "expectedCurrentWorkspaceId": str(lifecycle_service.result.workspace.id),
        "expectedWorkspaceUpdatedAt": settings.settings.workspace.updated_at.isoformat(),
    }

    with TestClient(app) as client:
        lifecycle_service.error = WorkspaceNotFoundError("foreign")
        missing = client.post(f"/api/v1/workspaces/{workspace_id}/restore", json=payload)
        lifecycle_service.error = WorkspaceLifecycleConflictError("stale")
        conflict = client.post(f"/api/v1/workspaces/{workspace_id}/restore", json=payload)
        lifecycle_service.error = WorkspaceLifecycleTransitionError(
            "fallback",
            reason_codes=["workspace_fallback_required"],
        )
        blocked = client.post(f"/api/v1/workspaces/{workspace_id}/deactivate", json=payload)

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "workspace_not_found"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "workspace_lifecycle_conflict"
    assert blocked.status_code == 422
    assert blocked.json()["error"] == {
        "code": "workspace_lifecycle_blocked",
        "message": "fallback",
        "details": {"reasonCodes": ["workspace_fallback_required"]},
    }


def test_workspace_members_read_returns_server_capabilities() -> None:
    app, service, actor_id, workspace_id = workspace_members_app()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/workspaces/{workspace_id}/members")

    assert response.status_code == 200
    assert service.read_calls == [(actor_id, workspace_id)]
    assert response.json()["items"][0]["capabilities"] == {
        "canUpdateRole": True,
        "canDisable": True,
        "canLeave": False,
        "canReactivate": False,
        "canTransferOwnership": True,
        "assignableRoles": ["admin", "editor", "viewer"],
    }


def test_workspace_member_role_dispatches_expected_snapshot_and_maps_stale() -> None:
    app, service, actor_id, workspace_id = workspace_members_app()
    member = service.members.items[0]
    payload = {"role": "viewer", "expectedUpdatedAt": member.updated_at.isoformat()}

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/workspaces/{workspace_id}/members/{member.id}/role",
            json=payload,
        )
        service.error = WorkspaceMemberConflictError("stale")
        conflict = client.put(
            f"/api/v1/workspaces/{workspace_id}/members/{member.id}/role",
            json=payload,
        )

    assert response.status_code == 200
    assert service.role_calls[0] == (
        actor_id,
        workspace_id,
        UpdateWorkspaceMemberRoleApiCommand(
            member_id=member.id,
            role=WorkspaceRole.VIEWER,
            expected_updated_at=member.updated_at,
        ),
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "member_role_conflict"


def test_workspace_member_disable_maps_reason_codes_without_existence_leak() -> None:
    app, service, actor_id, workspace_id = workspace_members_app()
    member = service.members.items[0]
    payload = {"expectedUpdatedAt": member.updated_at.isoformat()}

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/members/{member.id}/disable",
            json=payload,
        )
        service.error = WorkspaceMemberTransitionError("blocked", reason_codes=["member_owner"])
        blocked = client.post(
            f"/api/v1/workspaces/{workspace_id}/members/{member.id}/disable",
            json=payload,
        )
        service.error = WorkspaceNotFoundError("foreign")
        hidden = client.post(
            f"/api/v1/workspaces/{workspace_id}/members/{uuid4()}/disable",
            json=payload,
        )

    assert response.status_code == 200
    assert service.transition_calls[0] == (
        "disable",
        actor_id,
        workspace_id,
        TransitionWorkspaceMemberCommand(
            member_id=member.id,
            expected_updated_at=member.updated_at,
        ),
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["details"] == {"reasonCodes": ["member_owner"]}
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "workspace_not_found"


def test_workspace_invitations_return_metadata_without_credentials() -> None:
    app, service, actor_id, workspace_id = workspace_invitations_app()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/workspaces/{workspace_id}/invitations")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert service.read_calls == [(actor_id, workspace_id)]
    payload = response.json()
    assert payload["capabilities"]["assignableRoles"] == ["editor", "viewer"]
    assert "token" not in response.text.lower()
    assert "hash" not in response.text.lower()


def test_workspace_team_directories_are_forbidden_outside_owner_and_admin() -> None:
    members_app, members, _, members_workspace_id = workspace_members_app(WorkspaceRole.EDITOR)
    invitations_app, invitations, _, invitations_workspace_id = workspace_invitations_app(
        WorkspaceRole.EDITOR
    )

    with TestClient(members_app) as client:
        members_response = client.get(f"/api/v1/workspaces/{members_workspace_id}/members")
    with TestClient(invitations_app) as client:
        invitations_response = client.get(
            f"/api/v1/workspaces/{invitations_workspace_id}/invitations"
        )

    assert members_response.status_code == 403
    assert invitations_response.status_code == 403
    assert members_response.json()["error"]["code"] == "member_directory_forbidden"
    assert invitations_response.json()["error"]["code"] == "member_directory_forbidden"
    assert members.read_calls == []
    assert invitations.read_calls == []


def test_workspace_invitation_create_returns_transient_share_url() -> None:
    app, service, actor_id, workspace_id = workspace_invitations_app()
    idempotency_key = uuid4()
    sent: list[IdentityEmail] = []

    async def capture_email(message: IdentityEmail) -> None:
        sent.append(message)

    app.dependency_overrides[get_identity_email_sender] = lambda: capture_email

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers={"Idempotency-Key": str(idempotency_key)},
            json={"email": "invitee@example.test", "role": "viewer"},
        )

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    assert service.create_calls == [
        (
            actor_id,
            workspace_id,
            "invitee@example.test",
            WorkspaceRole.VIEWER,
            idempotency_key,
        )
    ]
    payload = response.json()
    assert payload["shareUrl"].endswith(
        "/app/workspaces/invitation#token=one-time-invitation-token"
    )
    assert payload["invitation"]["inviteeEmail"] == "invitee@example.test"
    assert "shareUrl" not in payload["invitations"]
    assert len(sent) == 1
    assert sent[0].recipient == "invitee@example.test"
    assert payload["shareUrl"] in sent[0].text


def test_workspace_invitation_revoke_dispatches_stale_snapshot_and_masks_id() -> None:
    app, service, actor_id, workspace_id = workspace_invitations_app()
    invitation = service.invitations.items[0]

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations/{invitation.id}/revoke",
            json={"expectedUpdatedAt": invitation.updated_at.isoformat()},
        )
        service.error = WorkspaceInvitationConflictError("stale")
        conflict = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations/{invitation.id}/revoke",
            json={"expectedUpdatedAt": invitation.updated_at.isoformat()},
        )
        service.error = WorkspaceInvitationNotFoundError("foreign")
        hidden = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations/{uuid4()}/revoke",
            json={"expectedUpdatedAt": invitation.updated_at.isoformat()},
        )

    assert response.status_code == 200
    assert service.revoke_calls[0] == (
        actor_id,
        workspace_id,
        invitation.id,
        invitation.updated_at,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "invitation_conflict"
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "invitation_not_found"


def test_workspace_invitation_maps_idempotency_and_role_reason() -> None:
    app, service, _, workspace_id = workspace_invitations_app()

    with TestClient(app) as client:
        service.error = WorkspaceIdempotencyConflictError("reused")
        conflict = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers={"Idempotency-Key": str(uuid4())},
            json={"email": "invitee@example.test", "role": "viewer"},
        )
        service.error = WorkspaceInvitationTransitionError(
            "forbidden",
            reason_codes=["invitation_role_forbidden"],
        )
        blocked = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers={"Idempotency-Key": str(uuid4())},
            json={"email": "invitee@example.test", "role": "admin"},
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert blocked.status_code == 422
    assert blocked.json()["error"]["details"] == {"reasonCodes": ["invitation_role_forbidden"]}


@pytest.mark.parametrize(
    "reason",
    ["member_limit_reached", "pending_invitation_limit_reached"],
)
def test_workspace_invitation_exposes_stable_limit_reason(reason: str) -> None:
    app, service, _, workspace_id = workspace_invitations_app()
    service.error = WorkspaceInvitationTransitionError(
        "limit reached",
        reason_codes=[reason],
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/invitations",
            headers={"Idempotency-Key": str(uuid4())},
            json={"email": "invitee@example.test", "role": "viewer"},
        )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": reason,
        "message": "limit reached",
        "details": {"reasonCodes": [reason]},
    }


def test_workspace_ownership_transfer_dispatches_both_stale_snapshots() -> None:
    app, service, actor_id, workspace_id, recipient_id = workspace_ownership_app()
    updated_at = service.transfer_result.workspace.updated_at

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/transfer-ownership",
            json={
                "recipientMemberId": str(recipient_id),
                "expectedWorkspaceUpdatedAt": updated_at.isoformat(),
                "expectedRecipientUpdatedAt": updated_at.isoformat(),
            },
        )

    assert response.status_code == 200
    assert isinstance(service.transfer_calls[0][1], UUID)
    assert service.transfer_calls[0][0] == actor_id
    assert service.transfer_calls[0][2:] == (
        workspace_id,
        TransferWorkspaceOwnershipCommand(
            recipient_member_id=recipient_id,
            expected_workspace_updated_at=updated_at,
            expected_recipient_updated_at=updated_at,
        ),
    )
    assert response.json()["navigationOutcome"] == {
        "kind": "workspace_authority_changed",
        "href": f"/app/workspaces/{workspace_id}/settings",
        "boundary": "hard_reload",
    }


def test_workspace_leave_dispatches_session_snapshot_and_returns_fallback() -> None:
    app, service, actor_id, workspace_id, _ = workspace_ownership_app()
    updated_at = service.transfer_result.workspace.updated_at

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/leave",
            json={
                "expectedMemberUpdatedAt": updated_at.isoformat(),
                "expectedCurrentWorkspaceId": str(workspace_id),
            },
        )

    assert response.status_code == 200
    assert isinstance(service.leave_calls[0][1], UUID)
    assert service.leave_calls[0][0] == actor_id
    assert service.leave_calls[0][2:] == (
        workspace_id,
        LeaveWorkspaceCommand(
            expected_member_updated_at=updated_at,
            expected_current_workspace_id=workspace_id,
        ),
    )
    assert response.json()["session"]["workspace"]["id"] == str(service.leave_result.workspace.id)
    assert response.json()["navigationOutcome"]["boundary"] == "hard_reload"
