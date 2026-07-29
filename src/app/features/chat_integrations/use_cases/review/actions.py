from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.chat_integrations.actions.review import (
    ChatReviewActionConfirmationSelection,
    ChatReviewActionSelection,
    ChatReviewCallbackData,
)
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.models import ChatConversationFlow, ChatConversationState
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.use_cases.action_tokens import ChatActionTokenBuilder
from app.features.chat_integrations.use_cases.review.config import CHAT_REVIEW_ACTION_TTL
from app.features.chat_integrations.use_cases.review.dto import (
    ChatReviewActionResult,
    ChatReviewContinuationAnchor,
    StartedChatReviewActionConfirmation,
)
from app.features.chat_integrations.use_cases.review.queue import ChatReviewQueueReader
from app.features.chat_integrations.use_cases.review.state import (
    ChatReviewStateClaimer,
    ChatReviewStateReader,
)
from app.features.import_review.application.lifecycle import (
    ImportReviewLifecycleActor,
    ImportReviewLifecycleCommand,
)
from app.features.import_review.domain.lifecycle import (
    ImportReviewLifecycleAction,
    ImportReviewLifecycleError,
)
from app.features.imports.errors import RawTransactionReviewError
from app.features.imports.statements.types import RawTransactionStatus
from app.features.workspaces.service import WorkspaceContext


class ChatReviewActionService:
    CONFIRMABLE_ACTIONS = {
        ChatReviewCallbackData.DUPLICATE_ACTION,
        ChatReviewCallbackData.IGNORE_ACTION,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.review_queue = ChatReviewQueueReader(session)
        self.review_lifecycle = ImportReviewLifecycleActor(session)

    async def start_action_confirmation(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewActionSelection,
    ) -> StartedChatReviewActionConfirmation:
        if selection.action not in self.CONFIRMABLE_ACTIONS:
            raise ChatReviewActionError("This review action cannot be confirmed this way.")

        state = await self._get_active_review_state(
            context=context,
            action_token=selection.action_token,
        )
        if state.step != "review_item":
            raise ChatReviewActionError("Stored review action is invalid.")

        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(state.state_payload)
        item = await self.review_queue.read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")
        if (
            selection.action == ChatReviewCallbackData.DUPLICATE_ACTION
            and item.status != "possible_duplicate"
        ):
            raise ChatReviewActionError("Строка не помечена как возможный дубль.")

        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            step="confirm_review_action",
            action_token=action_token,
            state_payload={
                "document_id": str(document_id),
                "raw_transaction_id": str(raw_transaction_id),
                "review_action": selection.action,
            },
            expires_at=utc_now() + CHAT_REVIEW_ACTION_TTL,
        )
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return StartedChatReviewActionConfirmation(
            action_token=action_token,
            item=item,
            action=selection.action,
            action_label=ChatReviewActionMapper.to_action_label(selection.action),
        )

    async def confirm_action(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewActionConfirmationSelection,
    ) -> ChatReviewActionResult:
        state = await self._get_active_review_state(
            context=context,
            action_token=selection.action_token,
        )
        if state.step != "confirm_review_action":
            raise ChatReviewActionError("Stored review action is invalid.")

        return await self._apply_stored_action(
            context=context,
            state=state,
            action=ChatReviewStateReader.read_review_action(state.state_payload),
        )

    async def apply_action(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewActionSelection,
    ) -> ChatReviewActionResult:
        state = await self._get_active_review_state(
            context=context,
            action_token=selection.action_token,
        )
        if state.step != "review_item":
            raise ChatReviewActionError("Stored review action is invalid.")

        return await self._apply_stored_action(
            context=context,
            state=state,
            action=selection.action,
        )

    async def _get_active_review_state(
        self,
        *,
        context: WorkspaceContext,
        action_token: str,
    ) -> ChatConversationState:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        return state

    async def _apply_stored_action(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        action: str,
    ) -> ChatReviewActionResult:
        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(state.state_payload)
        item = await self.review_queue.read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")

        lifecycle_action = ChatReviewActionMapper.to_lifecycle_action(action)
        await ChatReviewStateClaimer.claim_once(self.chat_integrations, state)
        try:
            await self.review_lifecycle.apply(
                workspace_id=context.workspace.id,
                command=ImportReviewLifecycleCommand(
                    document_id=document_id,
                    item_id=raw_transaction_id,
                    action=lifecycle_action,
                    expected_status=RawTransactionStatus(item.status),
                ),
            )
        except (ImportReviewLifecycleError, RawTransactionReviewError) as exc:
            await self.session.rollback()
            raise ChatReviewActionError(str(exc)) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.commit()
        return ChatReviewActionResult(
            action_label=ChatReviewActionMapper.to_action_label(action),
            continuation_anchor=ChatReviewContinuationAnchor(
                document_id=document_id,
                row_index=item.row_index,
            ),
        )


class ChatReviewActionMapper:
    @staticmethod
    def to_lifecycle_action(callback_action: str) -> ImportReviewLifecycleAction:
        match callback_action:
            case "dup":
                return ImportReviewLifecycleAction.MARK_DUPLICATE
            case "ign":
                return ImportReviewLifecycleAction.IGNORE
            case "uniq":
                return ImportReviewLifecycleAction.MARK_UNIQUE
            case _:
                raise ChatReviewActionError("Unknown review action.")

    @staticmethod
    def to_action_label(callback_action: str) -> str:
        match callback_action:
            case "dup":
                return "строка помечена как дубль"
            case "ign":
                return "строка игнорируется"
            case "uniq":
                return "строка помечена как уникальная"
            case _:
                raise ChatReviewActionError("Unknown review action.")
