import os
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import hash_session_token
from app.db.base import utc_now
from app.features.categories.models import Category, CategoryKind
from app.features.chat_integrations.models import (
    ChatConversationBinding,
    ChatConversationBindingMode,
    ChatConversationFlow,
    ChatConversationState,
    ChatIdentityBinding,
    IntegrationConnection,
    IntegrationConnectionStatus,
    IntegrationDeliveryStatus,
    IntegrationEventDelivery,
)
from app.features.chat_integrations.schemas import ChatConversationType, ChatProviderCode
from app.features.users.models import User, UserSession
from app.features.workspaces.application.lifecycle import WorkspaceLifecycleService
from app.features.workspaces.commands import TransitionWorkspaceLifecycleCommand
from app.features.workspaces.domain.types import (
    WorkspaceInvitationStatus,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceInvitation, WorkspaceMember
from app.features.workspaces.tokens import hash_invitation_token

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL lifecycle tests.",
)


async def test_deactivate_is_atomic_and_restore_does_not_resurrect_runtime(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    user_id = uuid4()
    target_id = uuid4()
    fallback_id = uuid4()
    session_id = uuid4()
    invitation_id = uuid4()
    category_id = uuid4()
    connection_id = uuid4()
    conversation_binding_id = uuid4()
    identity_binding_id = uuid4()
    state_id = uuid4()
    delivery_id = uuid4()
    session_token = f"workspace-lifecycle-{uuid4()}"

    async with sessions() as session:
        user = User(
            id=user_id,
            email=f"workspace-lifecycle-{user_id}@example.test",
            password_hash="hash",
            name="Lifecycle owner",
        )
        target = Workspace(
            id=target_id,
            owner_id=user_id,
            name="Lifecycle target",
            type=WorkspaceType.FAMILY,
            default_currency="RUB",
        )
        fallback = Workspace(
            id=fallback_id,
            owner_id=user_id,
            name="Lifecycle fallback",
            type=WorkspaceType.PERSONAL,
            default_currency="RUB",
        )
        session.add_all(
            [
                user,
                target,
                fallback,
                WorkspaceMember(
                    workspace_id=target_id,
                    user_id=user_id,
                    role=WorkspaceRole.OWNER,
                    status=WorkspaceMemberStatus.ACTIVE,
                ),
                WorkspaceMember(
                    workspace_id=fallback_id,
                    user_id=user_id,
                    role=WorkspaceRole.OWNER,
                    status=WorkspaceMemberStatus.ACTIVE,
                ),
                UserSession(
                    id=session_id,
                    user_id=user_id,
                    current_workspace_id=target_id,
                    session_token_hash=hash_session_token(session_token),
                    expires_at=utc_now() + timedelta(hours=1),
                ),
                WorkspaceInvitation(
                    id=invitation_id,
                    workspace_id=target_id,
                    role=WorkspaceRole.VIEWER,
                    status=WorkspaceInvitationStatus.PENDING,
                    token_hash=hash_invitation_token(f"invite-{uuid4()}"),
                    invited_by_user_id=user_id,
                    expires_at=utc_now() + timedelta(hours=1),
                ),
                Category(
                    id=category_id,
                    workspace_id=target_id,
                    name="Preserved category",
                    kind=CategoryKind.EXPENSE,
                ),
            ]
        )
        await session.flush()
        connection = IntegrationConnection(
            id=connection_id,
            workspace_id=target_id,
            provider=ChatProviderCode.FAKE,
            status=IntegrationConnectionStatus.ACTIVE,
            display_name="Lifecycle connection",
            created_by_user_id=user_id,
        )
        conversation_binding = ChatConversationBinding(
            id=conversation_binding_id,
            workspace_id=target_id,
            connection_id=connection_id,
            provider=ChatProviderCode.FAKE,
            external_chat_id=f"lifecycle-{uuid4()}",
            conversation_type=ChatConversationType.PRIVATE,
            mode=ChatConversationBindingMode.PERSONAL_INPUT,
            is_active=True,
        )
        session.add(connection)
        await session.flush()
        session.add(conversation_binding)
        await session.flush()
        session.add_all(
            [
                ChatIdentityBinding(
                    id=identity_binding_id,
                    workspace_id=target_id,
                    user_id=user_id,
                    connection_id=connection_id,
                    provider=ChatProviderCode.FAKE,
                    external_user_id=f"lifecycle-{uuid4()}",
                    display_name="Lifecycle owner",
                    is_active=True,
                ),
                ChatConversationState(
                    id=state_id,
                    workspace_id=target_id,
                    binding_id=conversation_binding_id,
                    user_id=user_id,
                    flow=ChatConversationFlow.MAIN_MENU,
                    step="idle",
                    action_token=f"lifecycle-{uuid4()}",
                    state_payload={},
                    expires_at=utc_now() + timedelta(hours=1),
                ),
                IntegrationEventDelivery(
                    id=delivery_id,
                    workspace_id=target_id,
                    connection_id=connection_id,
                    binding_id=conversation_binding_id,
                    event_type="lifecycle.test",
                    idempotency_key=f"lifecycle-{uuid4()}",
                    status=IntegrationDeliveryStatus.PENDING,
                ),
            ]
        )
        await session.commit()
        await session.refresh(target)
        expected_updated_at = target.updated_at

    async with sessions() as session:
        actor = await session.get(User, user_id)
        assert actor is not None
        result = await WorkspaceLifecycleService(session).deactivate(
            actor=actor,
            session_token=session_token,
            workspace_id=target_id,
            command=TransitionWorkspaceLifecycleCommand(
                expected_workspace_updated_at=expected_updated_at,
                expected_current_workspace_id=target_id,
            ),
        )
        assert result.impact.model_dump() == {
            "moved_session_count": 1,
            "revoked_invitation_count": 1,
            "disabled_integration_connection_count": 1,
            "disabled_chat_conversation_binding_count": 1,
            "disabled_chat_identity_binding_count": 1,
            "consumed_chat_conversation_state_count": 1,
            "failed_integration_delivery_count": 1,
        }

    async with sessions() as session:
        target = await session.get(Workspace, target_id)
        user_session = await session.get(UserSession, session_id)
        invitation = await session.get(WorkspaceInvitation, invitation_id)
        connection = await session.get(IntegrationConnection, connection_id)
        conversation = await session.get(ChatConversationBinding, conversation_binding_id)
        identity = await session.get(ChatIdentityBinding, identity_binding_id)
        state = await session.get(ChatConversationState, state_id)
        delivery = await session.get(IntegrationEventDelivery, delivery_id)
        assert target is not None
        assert user_session is not None
        assert invitation is not None
        assert connection is not None
        assert conversation is not None
        assert identity is not None
        assert state is not None
        assert delivery is not None
        assert target.is_active is False and target.archived_at is not None
        assert user_session.current_workspace_id == fallback_id
        assert invitation.status == WorkspaceInvitationStatus.REVOKED
        assert connection.status == IntegrationConnectionStatus.DISABLED
        assert conversation.is_active is False
        assert identity.is_active is False
        assert state.consumed_at is not None
        assert delivery.status == IntegrationDeliveryStatus.FAILED
        assert await session.get(Category, category_id) is not None
        deactivated_updated_at = target.updated_at

    async with sessions() as session:
        actor = await session.get(User, user_id)
        assert actor is not None
        await WorkspaceLifecycleService(session).restore(
            actor=actor,
            session_token=session_token,
            workspace_id=target_id,
            command=TransitionWorkspaceLifecycleCommand(
                expected_workspace_updated_at=deactivated_updated_at,
                expected_current_workspace_id=fallback_id,
            ),
        )

    async with sessions() as session:
        target = await session.get(Workspace, target_id)
        user_session = await session.get(UserSession, session_id)
        invitation = await session.get(WorkspaceInvitation, invitation_id)
        connection = await session.get(IntegrationConnection, connection_id)
        conversation = await session.get(ChatConversationBinding, conversation_binding_id)
        identity = await session.get(ChatIdentityBinding, identity_binding_id)
        state = await session.get(ChatConversationState, state_id)
        delivery = await session.get(IntegrationEventDelivery, delivery_id)
        assert target is not None
        assert user_session is not None
        assert invitation is not None
        assert connection is not None
        assert conversation is not None
        assert identity is not None
        assert state is not None
        assert delivery is not None
        assert target.is_active is True and target.archived_at is None
        assert user_session.current_workspace_id == fallback_id
        assert invitation.status == WorkspaceInvitationStatus.REVOKED
        assert connection.status == IntegrationConnectionStatus.DISABLED
        assert conversation.is_active is False
        assert identity.is_active is False
        assert state.consumed_at is not None
        assert delivery.status == IntegrationDeliveryStatus.FAILED
        assert await session.get(Category, category_id) is not None
