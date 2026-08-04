from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations.models import (
    ChatConversationBinding,
    ChatConversationBindingMode,
    ChatConversationFlow,
    ChatConversationState,
    ChatIdentityBinding,
    ChatNotificationLevel,
    IntegrationConnection,
    IntegrationConnectionStatus,
    IntegrationDeliveryStatus,
    IntegrationEventDelivery,
)
from app.features.chat_integrations.schemas import ChatProviderCode


@dataclass(frozen=True)
class WorkspaceRuntimeDeactivationCounts:
    connection_count: int
    conversation_binding_count: int
    identity_binding_count: int
    conversation_state_count: int
    delivery_count: int


class ChatIntegrationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_active_connections_for_workspace(self, workspace_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(IntegrationConnection)
            .where(
                IntegrationConnection.workspace_id == workspace_id,
                IntegrationConnection.status == IntegrationConnectionStatus.ACTIVE,
            )
        )
        return result.scalar_one()

    async def count_active_identity_bindings_for_workspace(
        self,
        workspace_id: UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(ChatIdentityBinding)
            .where(
                ChatIdentityBinding.workspace_id == workspace_id,
                ChatIdentityBinding.is_active.is_(True),
            )
        )
        return result.scalar_one()

    async def deactivate_workspace_runtime(
        self,
        workspace_id: UUID,
        *,
        deactivated_at: datetime,
    ) -> WorkspaceRuntimeDeactivationCounts:
        connection_count = await self._update_count(
            update(IntegrationConnection)
            .where(
                IntegrationConnection.workspace_id == workspace_id,
                IntegrationConnection.status == IntegrationConnectionStatus.ACTIVE,
            )
            .values(status=IntegrationConnectionStatus.DISABLED)
        )
        conversation_binding_count = await self._update_count(
            update(ChatConversationBinding)
            .where(
                ChatConversationBinding.workspace_id == workspace_id,
                ChatConversationBinding.is_active.is_(True),
            )
            .values(is_active=False)
        )
        identity_binding_count = await self._update_count(
            update(ChatIdentityBinding)
            .where(
                ChatIdentityBinding.workspace_id == workspace_id,
                ChatIdentityBinding.is_active.is_(True),
            )
            .values(is_active=False)
        )
        conversation_state_count = await self._update_count(
            update(ChatConversationState)
            .where(
                ChatConversationState.workspace_id == workspace_id,
                ChatConversationState.consumed_at.is_(None),
            )
            .values(consumed_at=deactivated_at)
        )
        delivery_count = await self._update_count(
            update(IntegrationEventDelivery)
            .where(
                IntegrationEventDelivery.workspace_id == workspace_id,
                IntegrationEventDelivery.status == IntegrationDeliveryStatus.PENDING,
            )
            .values(
                status=IntegrationDeliveryStatus.FAILED,
                error_message="Workspace was deactivated before delivery.",
            )
        )
        await self.session.flush()
        return WorkspaceRuntimeDeactivationCounts(
            connection_count=connection_count,
            conversation_binding_count=conversation_binding_count,
            identity_binding_count=identity_binding_count,
            conversation_state_count=conversation_state_count,
            delivery_count=delivery_count,
        )

    async def _update_count(self, statement) -> int:
        result = cast(CursorResult, await self.session.execute(statement))
        return result.rowcount

    async def get_active_identity_binding(
        self,
        *,
        workspace_id: UUID,
        provider: ChatProviderCode,
        external_user_id: str,
    ) -> ChatIdentityBinding | None:
        result = await self.session.execute(
            select(ChatIdentityBinding)
            .where(
                ChatIdentityBinding.workspace_id == workspace_id,
                ChatIdentityBinding.provider == provider,
                ChatIdentityBinding.external_user_id == external_user_id,
                ChatIdentityBinding.is_active.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_identity_binding(
        self,
        *,
        workspace_id: UUID,
        provider: ChatProviderCode,
        external_user_id: str,
    ) -> ChatIdentityBinding | None:
        result = await self.session.execute(
            select(ChatIdentityBinding)
            .where(
                ChatIdentityBinding.workspace_id == workspace_id,
                ChatIdentityBinding.provider == provider,
                ChatIdentityBinding.external_user_id == external_user_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_active_identity_bindings_for_external_user(
        self,
        *,
        provider: ChatProviderCode,
        external_user_id: str,
    ) -> list[ChatIdentityBinding]:
        result = await self.session.execute(
            select(ChatIdentityBinding)
            .where(
                ChatIdentityBinding.provider == provider,
                ChatIdentityBinding.external_user_id == external_user_id,
                ChatIdentityBinding.is_active.is_(True),
            )
            .order_by(ChatIdentityBinding.created_at)
        )
        return list(result.scalars().all())

    async def create_identity_binding(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        provider: ChatProviderCode,
        external_user_id: str,
        display_name: str | None,
    ) -> ChatIdentityBinding:
        binding = ChatIdentityBinding(
            workspace_id=workspace_id,
            user_id=user_id,
            provider=provider,
            external_user_id=external_user_id,
            display_name=display_name,
            is_active=True,
        )
        self.session.add(binding)
        await self.session.flush()
        return binding

    async def deactivate_other_identity_bindings(
        self,
        *,
        keep_binding_id: UUID,
        provider: ChatProviderCode,
        external_user_id: str,
    ) -> None:
        await self.session.execute(
            update(ChatIdentityBinding)
            .where(
                ChatIdentityBinding.id != keep_binding_id,
                ChatIdentityBinding.provider == provider,
                ChatIdentityBinding.external_user_id == external_user_id,
                ChatIdentityBinding.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await self.session.flush()

    async def revoke_workspace_access_for_user(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        revoked_at: datetime,
    ) -> None:
        await self.session.execute(
            update(ChatIdentityBinding)
            .where(
                ChatIdentityBinding.workspace_id == workspace_id,
                ChatIdentityBinding.user_id == user_id,
                ChatIdentityBinding.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await self.session.execute(
            update(ChatConversationState)
            .where(
                ChatConversationState.workspace_id == workspace_id,
                ChatConversationState.user_id == user_id,
                ChatConversationState.consumed_at.is_(None),
            )
            .values(consumed_at=revoked_at)
        )
        await self.session.flush()

    async def revoke_all_access_for_user(
        self,
        *,
        user_id: UUID,
        revoked_at: datetime,
    ) -> None:
        await self.session.execute(
            update(ChatIdentityBinding)
            .where(
                ChatIdentityBinding.user_id == user_id,
                ChatIdentityBinding.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await self.session.execute(
            update(ChatConversationState)
            .where(
                ChatConversationState.user_id == user_id,
                ChatConversationState.consumed_at.is_(None),
            )
            .values(consumed_at=revoked_at)
        )
        await self.session.flush()

    async def create_conversation_state(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID | None,
        flow: ChatConversationFlow,
        step: str,
        action_token: str,
        state_payload: dict[str, object],
        expires_at: datetime,
    ) -> ChatConversationState:
        state = ChatConversationState(
            workspace_id=workspace_id,
            user_id=user_id,
            flow=flow,
            step=step,
            action_token=action_token,
            state_payload=state_payload,
            expires_at=expires_at,
        )
        self.session.add(state)
        await self.session.flush()
        return state

    async def get_active_conversation_state(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID | None,
        flow: ChatConversationFlow,
        action_token: str,
        now: datetime,
    ) -> ChatConversationState | None:
        result = await self.session.execute(
            select(ChatConversationState)
            .where(
                ChatConversationState.workspace_id == workspace_id,
                ChatConversationState.user_id == user_id,
                ChatConversationState.flow == flow,
                ChatConversationState.action_token == action_token,
                ChatConversationState.expires_at > now,
                ChatConversationState.consumed_at.is_(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_conversation_state_for_flows(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID | None,
        flows: tuple[ChatConversationFlow, ...],
        action_token: str,
        now: datetime,
    ) -> ChatConversationState | None:
        result = await self.session.execute(
            select(ChatConversationState)
            .where(
                ChatConversationState.workspace_id == workspace_id,
                ChatConversationState.user_id == user_id,
                ChatConversationState.flow.in_(flows),
                ChatConversationState.action_token == action_token,
                ChatConversationState.expires_at > now,
                ChatConversationState.consumed_at.is_(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_active_conversation_state_for_flows(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID | None,
        flows: tuple[ChatConversationFlow, ...],
        now: datetime,
    ) -> ChatConversationState | None:
        result = await self.session.execute(
            select(ChatConversationState)
            .where(
                ChatConversationState.workspace_id == workspace_id,
                ChatConversationState.user_id == user_id,
                ChatConversationState.flow.in_(flows),
                ChatConversationState.expires_at > now,
                ChatConversationState.consumed_at.is_(None),
            )
            .order_by(ChatConversationState.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def consume_conversation_state(
        self,
        state: ChatConversationState,
        *,
        consumed_at: datetime,
    ) -> None:
        state.consumed_at = consumed_at
        await self.session.flush()

    async def try_consume_active_conversation_state(
        self,
        state: ChatConversationState,
        *,
        consumed_at: datetime,
    ) -> bool:
        result = cast(
            CursorResult,
            await self.session.execute(
                update(ChatConversationState)
                .where(
                    ChatConversationState.id == state.id,
                    ChatConversationState.consumed_at.is_(None),
                )
                .values(consumed_at=consumed_at)
            ),
        )
        if result.rowcount != 1:
            await self.session.flush()
            return False

        state.consumed_at = consumed_at
        await self.session.flush()
        return True

    async def list_active_shared_feed_bindings(
        self,
        *,
        workspace_id: UUID,
    ) -> list[ChatConversationBinding]:
        result = await self.session.execute(
            select(ChatConversationBinding)
            .where(
                ChatConversationBinding.workspace_id == workspace_id,
                ChatConversationBinding.mode == ChatConversationBindingMode.SHARED_FEED,
                ChatConversationBinding.notification_level.in_(
                    [
                        ChatNotificationLevel.SAFE_ACTIVITY,
                        ChatNotificationLevel.REVIEW_ALERTS,
                    ]
                ),
                ChatConversationBinding.is_active.is_(True),
            )
            .order_by(ChatConversationBinding.created_at)
        )
        return list(result.scalars().all())

    async def get_event_delivery(
        self,
        *,
        workspace_id: UUID,
        connection_id: UUID,
        idempotency_key: str,
    ) -> IntegrationEventDelivery | None:
        result = await self.session.execute(
            select(IntegrationEventDelivery)
            .where(
                IntegrationEventDelivery.workspace_id == workspace_id,
                IntegrationEventDelivery.connection_id == connection_id,
                IntegrationEventDelivery.idempotency_key == idempotency_key,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_event_delivery(
        self,
        *,
        workspace_id: UUID,
        connection_id: UUID,
        binding_id: UUID | None,
        event_type: str,
        idempotency_key: str,
    ) -> IntegrationEventDelivery:
        delivery = IntegrationEventDelivery(
            workspace_id=workspace_id,
            connection_id=connection_id,
            binding_id=binding_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            status=IntegrationDeliveryStatus.PENDING,
        )
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def mark_event_delivery_sent(
        self,
        delivery: IntegrationEventDelivery,
        *,
        sent_at: datetime,
    ) -> None:
        delivery.status = IntegrationDeliveryStatus.SENT
        delivery.sent_at = sent_at
        delivery.error_message = None
        await self.session.flush()

    async def mark_event_delivery_failed(
        self,
        delivery: IntegrationEventDelivery,
        *,
        error_message: str,
    ) -> None:
        delivery.status = IntegrationDeliveryStatus.FAILED
        delivery.error_message = error_message
        await self.session.flush()
