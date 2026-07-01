from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.chat_integrations.errors import ChatManualOperationError
from app.features.chat_integrations.models import ChatConversationFlow, ChatConversationState
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.use_cases.action_tokens import ChatActionTokenBuilder
from app.features.chat_integrations.use_cases.manual.config import (
    CHAT_MANUAL_OPERATION_FLOWS,
    CHAT_MANUAL_OPERATION_TTL,
)
from app.features.workspaces.service import WorkspaceContext


class ChatManualOperationStateStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)

    async def create(
        self,
        *,
        context: WorkspaceContext,
        flow: ChatConversationFlow,
        step: str,
        payload: dict[str, object],
    ) -> str:
        action_token = await self._create_state(
            context=context,
            flow=flow,
            step=step,
            payload=payload,
        )
        await self.session.commit()
        return action_token

    async def get_latest_active(
        self,
        *,
        context: WorkspaceContext,
    ) -> ChatConversationState | None:
        return await self.chat_integrations.get_latest_active_conversation_state_for_flows(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flows=CHAT_MANUAL_OPERATION_FLOWS,
            now=utc_now(),
        )

    async def get_by_token(
        self,
        *,
        context: WorkspaceContext,
        action_token: str,
    ) -> ChatConversationState:
        state = await self.chat_integrations.get_active_conversation_state_for_flows(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flows=CHAT_MANUAL_OPERATION_FLOWS,
            action_token=action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatManualOperationError("Действие устарело. Начни операцию заново.")
        return state

    async def replace(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        flow: ChatConversationFlow,
        step: str,
        payload: dict[str, object],
    ) -> str:
        action_token = await self._create_state(
            context=context,
            flow=flow,
            step=step,
            payload=payload,
        )
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return action_token

    async def consume(self, state: ChatConversationState) -> None:
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()

    async def _create_state(
        self,
        *,
        context: WorkspaceContext,
        flow: ChatConversationFlow,
        step: str,
        payload: dict[str, object],
    ) -> str:
        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=flow,
            step=step,
            action_token=action_token,
            state_payload=payload,
            expires_at=utc_now() + CHAT_MANUAL_OPERATION_TTL,
        )
        return action_token
