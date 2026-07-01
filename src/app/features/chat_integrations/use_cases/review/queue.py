from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.chat_integrations.actions.review import (
    ChatReviewDocumentSelection,
    ChatReviewNavigationSelection,
    ChatReviewReturnSelection,
)
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.models import ChatConversationFlow
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.use_cases.action_tokens import ChatActionTokenBuilder
from app.features.chat_integrations.use_cases.review.config import CHAT_REVIEW_ACTION_TTL
from app.features.chat_integrations.use_cases.review.dto import (
    ChatReviewContinuationAnchor,
    ChatReviewDocumentChoice,
    ChatReviewNavigationBoundary,
    ChatReviewQueueItem,
    StartedChatReviewDocumentSelection,
    StartedChatReviewItem,
)
from app.features.chat_integrations.use_cases.review.state import ChatReviewStateReader
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.imports.query_repository import ImportQueryRepository
from app.features.workspaces.service import WorkspaceContext

CHAT_REVIEW_DOCUMENT_SELECTION_LIMIT = 8


class ChatReviewQueueReader:
    def __init__(self, session: AsyncSession) -> None:
        self.imports = ImportQueryRepository(session)

    async def read_document_choices(
        self,
        context: WorkspaceContext,
    ) -> tuple[ChatReviewDocumentChoice, ...]:
        documents = await self.imports.list_reviewable_documents_with_counts(
            workspace_id=context.workspace.id,
            limit=CHAT_REVIEW_DOCUMENT_SELECTION_LIMIT,
        )
        return tuple(
            ChatReviewDocumentChoice(
                id=document.id,
                label=ChatReviewDocumentLabelBuilder.from_document(document),
                reviewable_count=reviewable_count,
            )
            for document, reviewable_count in documents
        )

    async def read_next_item(self, context: WorkspaceContext) -> ChatReviewQueueItem | None:
        raw_transaction = await self.imports.get_next_review_raw_transaction(context.workspace.id)
        if raw_transaction is None:
            return None

        return await self._map_raw_transaction(context, raw_transaction)

    async def read_next_item_for_document(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
    ) -> ChatReviewQueueItem | None:
        raw_transaction = await self.imports.get_next_review_raw_transaction_for_document(
            workspace_id=context.workspace.id,
            document_id=document_id,
        )
        if raw_transaction is None:
            return None

        return await self._map_raw_transaction(context, raw_transaction)

    async def read_next_item_after(
        self,
        *,
        context: WorkspaceContext,
        anchor: ChatReviewContinuationAnchor,
    ) -> ChatReviewQueueItem | None:
        raw_transaction = await self.imports.get_next_review_raw_transaction_after(
            workspace_id=context.workspace.id,
            document_id=anchor.document_id,
            current_row_index=anchor.row_index,
        )
        if raw_transaction is None:
            return await self.read_next_item_for_document(
                context=context,
                document_id=anchor.document_id,
            )

        return await self._map_raw_transaction(context, raw_transaction)

    async def read_item(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
    ) -> ChatReviewQueueItem | None:
        raw_transaction = await self.imports.get_review_raw_transaction(
            workspace_id=context.workspace.id,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
        if raw_transaction is None:
            return None

        return await self._map_raw_transaction(context, raw_transaction)

    async def read_adjacent_item(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        current_row_index: int,
        direction: str,
    ) -> ChatReviewQueueItem | None:
        raw_transaction = await self.imports.get_adjacent_review_raw_transaction(
            workspace_id=context.workspace.id,
            document_id=document_id,
            current_row_index=current_row_index,
            direction=direction,
        )
        if raw_transaction is None:
            return None

        return await self._map_raw_transaction(context, raw_transaction)

    async def _map_raw_transaction(
        self,
        context: WorkspaceContext,
        raw_transaction: RawTransaction,
    ) -> ChatReviewQueueItem:
        document_row_count = await self.imports.count_raw_transactions_for_document(
            workspace_id=context.workspace.id,
            document_id=raw_transaction.uploaded_document_id,
        )
        document_reviewable_count = (
            await self.imports.count_reviewable_raw_transactions_for_document(
                workspace_id=context.workspace.id,
                document_id=raw_transaction.uploaded_document_id,
            )
        )
        return ChatReviewQueueItemMapper.from_raw_transaction(
            raw_transaction,
            document_row_count=document_row_count,
            document_reviewable_count=document_reviewable_count,
        )


class ChatReviewQueueItemMapper:
    @staticmethod
    def from_raw_transaction(
        raw_transaction: RawTransaction,
        *,
        document_row_count: int | None = None,
        document_reviewable_count: int | None = None,
    ) -> ChatReviewQueueItem:
        account_name = raw_transaction.account.name if raw_transaction.account is not None else None
        suggested_operation_type = (
            raw_transaction.suggested_operation_type.value
            if raw_transaction.suggested_operation_type is not None
            else None
        )
        return ChatReviewQueueItem(
            document_id=raw_transaction.uploaded_document_id,
            raw_transaction_id=raw_transaction.id,
            row_index=raw_transaction.row_index,
            document_row_count=document_row_count,
            document_reviewable_count=document_reviewable_count,
            status=raw_transaction.status.value,
            account_name=account_name,
            document_label=ChatReviewDocumentLabelBuilder.from_document(
                raw_transaction.uploaded_document,
            ),
            operation_date=raw_transaction.operation_date,
            amount=raw_transaction.amount,
            amount_raw=raw_transaction.amount_raw,
            currency=raw_transaction.currency or raw_transaction.currency_raw,
            description=raw_transaction.description_normalized or raw_transaction.description_raw,
            suggested_operation_type=suggested_operation_type,
            normalization_error=raw_transaction.normalization_error,
            suggested_category_id=raw_transaction.suggested_category_id,
            suggested_category_name=raw_transaction.suggested_category.name
            if raw_transaction.suggested_category is not None
            else None,
            source_account_id=raw_transaction.account_id,
        )


class ChatReviewDocumentLabelBuilder:
    @staticmethod
    def from_document(document: UploadedDocument) -> str:
        parts = [
            document.bank_name,
            document.statement_type,
            ChatReviewDocumentLabelBuilder._period_label(document),
        ]
        details = " / ".join(part for part in parts if part)
        if details:
            return f"{document.original_filename} ({details})"
        return document.original_filename

    @staticmethod
    def _period_label(document: UploadedDocument) -> str | None:
        if document.statement_period_start is None and document.statement_period_end is None:
            return None
        if document.statement_period_start is None:
            return f"по {document.statement_period_end:%d.%m.%Y}"
        if document.statement_period_end is None:
            return f"с {document.statement_period_start:%d.%m.%Y}"
        return (
            f"{document.statement_period_start:%d.%m.%Y}-{document.statement_period_end:%d.%m.%Y}"
        )


class ChatReviewQueueService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.review_queue = ChatReviewQueueReader(session)

    async def start_document_selection(
        self,
        context: WorkspaceContext,
    ) -> StartedChatReviewDocumentSelection | None:
        document_choices = await self.review_queue.read_document_choices(context)
        if not document_choices:
            return None

        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            step="choose_document",
            action_token=action_token,
            state_payload={
                "document_ids": [str(choice.id) for choice in document_choices],
            },
            expires_at=utc_now() + CHAT_REVIEW_ACTION_TTL,
        )
        await self.session.commit()
        return StartedChatReviewDocumentSelection(
            action_token=action_token,
            document_choices=document_choices,
        )

    async def start_next_review_item(
        self,
        context: WorkspaceContext,
    ) -> StartedChatReviewItem | None:
        item = await self.review_queue.read_next_item(context)
        if item is None:
            return None

        started_item = await self._start_review_item(context=context, item=item)
        await self.session.commit()
        return started_item

    async def start_next_review_item_for_document(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
    ) -> StartedChatReviewItem | None:
        item = await self.review_queue.read_next_item_for_document(
            context=context,
            document_id=document_id,
        )
        if item is None:
            return None

        started_item = await self._start_review_item(context=context, item=item)
        await self.session.commit()
        return started_item

    async def start_selected_document_review_item(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewDocumentSelection,
    ) -> StartedChatReviewItem | None:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open statements again.")
        if state.step != "choose_document":
            raise ChatReviewActionError("Stored review action is invalid.")

        document_id = ChatReviewStateReader.read_review_document_id(
            state.state_payload,
            selection.document_index,
        )
        item = await self.review_queue.read_next_item_for_document(
            context=context,
            document_id=document_id,
        )
        if item is None:
            await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
            await self.session.commit()
            return None

        started_item = await self._start_review_item(context=context, item=item)
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return started_item

    async def start_next_review_item_after(
        self,
        *,
        context: WorkspaceContext,
        anchor: ChatReviewContinuationAnchor,
    ) -> StartedChatReviewItem | None:
        item = await self.review_queue.read_next_item_after(context=context, anchor=anchor)
        if item is None:
            return None

        started_item = await self._start_review_item(context=context, item=item)
        await self.session.commit()
        return started_item

    async def start_adjacent_review_item(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewNavigationSelection,
    ) -> StartedChatReviewItem | ChatReviewNavigationBoundary:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        if state.step != "review_item":
            raise ChatReviewActionError("Stored review action is invalid.")

        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        current_item = await self.review_queue.read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=ChatReviewStateReader.read_raw_transaction_id(
                state.state_payload,
            ),
        )
        if current_item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")

        adjacent_item = await self.review_queue.read_adjacent_item(
            context=context,
            document_id=document_id,
            current_row_index=current_item.row_index,
            direction=selection.direction,
        )
        if adjacent_item is None:
            return ChatReviewNavigationBoundary(direction=selection.direction)

        started_item = await self._start_review_item(context=context, item=adjacent_item)
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return started_item

    async def return_to_review_item(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewReturnSelection,
    ) -> StartedChatReviewItem:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the row again.")
        if state.step not in {
            "choose_category",
            "choose_property",
            "choose_transfer_target",
            "confirm_review_action",
            "confirm_transfer",
        }:
            raise ChatReviewActionError("Stored review action is invalid.")

        item = await self.review_queue.read_item(
            context=context,
            document_id=ChatReviewStateReader.read_document_id(state.state_payload),
            raw_transaction_id=ChatReviewStateReader.read_raw_transaction_id(
                state.state_payload,
            ),
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")

        started_item = await self._start_review_item(context=context, item=item)
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return started_item

    async def _start_review_item(
        self,
        *,
        context: WorkspaceContext,
        item: ChatReviewQueueItem,
    ) -> StartedChatReviewItem:
        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            step="review_item",
            action_token=action_token,
            state_payload={
                "document_id": str(item.document_id),
                "raw_transaction_id": str(item.raw_transaction_id),
            },
            expires_at=utc_now() + CHAT_REVIEW_ACTION_TTL,
        )
        return StartedChatReviewItem(action_token=action_token, item=item)
