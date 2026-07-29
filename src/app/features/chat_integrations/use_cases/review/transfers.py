from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.accounts.service import AccountService
from app.features.chat_integrations.actions.review import (
    ChatReviewTransferAccountSelection,
    ChatReviewTransferConfirmationSelection,
    ChatReviewTransferExistingSelection,
    ChatReviewTransferPairSelection,
)
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.models import ChatConversationFlow, ChatConversationState
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.use_cases.action_tokens import ChatActionTokenBuilder
from app.features.chat_integrations.use_cases.review.builders import (
    ChatReviewExistingTransferChoiceBuilder,
    ChatReviewTransferAccountChoiceBuilder,
    ChatReviewTransferCommandBuilder,
    ChatReviewTransferLabelBuilder,
    ChatReviewTransferPairChoiceBuilder,
)
from app.features.chat_integrations.use_cases.review.config import CHAT_REVIEW_ACTION_TTL
from app.features.chat_integrations.use_cases.review.dto import (
    ChatReviewActionResult,
    ChatReviewContinuationAnchor,
    ChatReviewExistingTransferChoice,
    ChatReviewQueueItem,
    ChatReviewTransferPairChoice,
    ChatReviewTransferPreviewEntry,
    StartedChatReviewTransferConfirmation,
    StartedChatReviewTransferSelection,
)
from app.features.chat_integrations.use_cases.review.queue import ChatReviewQueueReader
from app.features.chat_integrations.use_cases.review.state import (
    ChatReviewStateClaimer,
    ChatReviewStateReader,
)
from app.features.import_review.application.commands.transfers import ImportReviewTransferActor
from app.features.import_review.application.queries.transfer_suggestions import (
    TransferSuggestionUseCase,
)
from app.features.import_review.repository import ImportReviewRepository
from app.features.imports.errors import RawTransactionReviewError
from app.features.ledger.errors import LedgerPostingError
from app.features.workspaces.service import WorkspaceContext


class ChatReviewTransferService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.accounts = AccountService(session)
        self.chat_integrations = ChatIntegrationRepository(session)
        self.review_queue = ChatReviewQueueReader(session)
        self.transfer_suggestions = TransferSuggestionUseCase(session)
        self.transfers = ImportReviewTransferActor(session)

    async def start_transfer_selection(
        self,
        *,
        context: WorkspaceContext,
        action_token: str,
    ) -> StartedChatReviewTransferSelection:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")

        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(state.state_payload)
        item = await self.review_queue.read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")
        if item.source_account_id is None:
            raise ChatReviewActionError("Raw transaction row has no source account.")
        if item.amount is None:
            raise ChatReviewActionError("Raw transaction row has no amount.")

        accounts = await self.accounts.list_active_accounts(context.workspace.id)
        account_choices = ChatReviewTransferAccountChoiceBuilder.build_choices(
            item=item,
            accounts=accounts,
        )
        pair_choices = await self._build_transfer_pair_choices(
            context=context,
            item=item,
        )
        existing_transfer_choices = await self._build_existing_transfer_choices(
            context=context,
            item=item,
        )
        if not existing_transfer_choices and not pair_choices and not account_choices:
            raise ChatReviewActionError("No transfer account is available.")

        next_action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            step="choose_transfer_target",
            action_token=next_action_token,
            state_payload={
                "document_id": str(document_id),
                "raw_transaction_id": str(raw_transaction_id),
                "matched_raw_transaction_ids": [str(choice.id) for choice in pair_choices],
                "matched_raw_transaction_labels": [
                    ChatReviewTransferLabelBuilder.pair_label(choice) for choice in pair_choices
                ],
                "matched_raw_transaction_account_names": [
                    choice.account_name or "счет?" for choice in pair_choices
                ],
                "matched_raw_transaction_amounts": [str(choice.amount) for choice in pair_choices],
                "matched_raw_transaction_currencies": [choice.currency for choice in pair_choices],
                "matched_operation_ids": [str(choice.id) for choice in existing_transfer_choices],
                "matched_operation_labels": [
                    ChatReviewTransferLabelBuilder.existing_label(choice)
                    for choice in existing_transfer_choices
                ],
                "matched_operation_account_names": [
                    choice.account_name or "счет строки" for choice in existing_transfer_choices
                ],
                "matched_operation_account_amounts": [
                    str(choice.account_amount) for choice in existing_transfer_choices
                ],
                "matched_operation_account_currencies": [
                    choice.account_currency for choice in existing_transfer_choices
                ],
                "matched_operation_counterparty_names": [
                    choice.counterparty_account_name or "второй счет"
                    for choice in existing_transfer_choices
                ],
                "matched_operation_counterparty_amounts": [
                    str(choice.counterparty_amount) for choice in existing_transfer_choices
                ],
                "matched_operation_counterparty_currencies": [
                    choice.counterparty_currency for choice in existing_transfer_choices
                ],
                "account_ids": [str(choice.id) for choice in account_choices],
                "account_labels": [
                    ChatReviewTransferLabelBuilder.account_label(choice)
                    for choice in account_choices
                ],
                "account_names": [choice.name for choice in account_choices],
                "account_currencies": [choice.currency for choice in account_choices],
            },
            expires_at=utc_now() + CHAT_REVIEW_ACTION_TTL,
        )
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return StartedChatReviewTransferSelection(
            action_token=next_action_token,
            item=item,
            pair_choices=pair_choices,
            account_choices=account_choices,
            existing_transfer_choices=existing_transfer_choices,
        )

    async def start_transfer_confirmation_with_account(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewTransferAccountSelection,
    ) -> StartedChatReviewTransferConfirmation:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        if state.step != "choose_transfer_target":
            raise ChatReviewActionError("Stored review action is invalid.")

        account_id = ChatReviewStateReader.read_transfer_account_id(
            state.state_payload,
            selection.account_index,
        )
        target_label = ChatReviewStateReader.read_transfer_account_label(
            state.state_payload,
            selection.account_index,
        )
        item = await self._read_transfer_item(context=context, state=state)
        source_preview_entry = self._source_preview_entry(item)
        preview_entries = (
            source_preview_entry,
            ChatReviewStateReader.read_transfer_account_preview_entry(
                state.state_payload,
                selection.account_index,
                -source_preview_entry.amount,
            ),
        )
        return await self._start_transfer_confirmation(
            context=context,
            state=state,
            item=item,
            target_label=target_label,
            preview_entries=preview_entries,
            counterparty_account_id=account_id,
            matched_raw_transaction_id=None,
        )

    async def start_transfer_confirmation_with_pair(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewTransferPairSelection,
    ) -> StartedChatReviewTransferConfirmation:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        if state.step != "choose_transfer_target":
            raise ChatReviewActionError("Stored review action is invalid.")

        matched_raw_transaction_id = ChatReviewStateReader.read_matched_raw_transaction_id(
            state.state_payload,
            selection.pair_index,
        )
        target_label = ChatReviewStateReader.read_matched_raw_transaction_label(
            state.state_payload,
            selection.pair_index,
        )
        item = await self._read_transfer_item(context=context, state=state)
        preview_entries = (
            self._source_preview_entry(item),
            ChatReviewStateReader.read_matched_raw_transaction_preview_entry(
                state.state_payload,
                selection.pair_index,
            ),
        )
        return await self._start_transfer_confirmation(
            context=context,
            state=state,
            item=item,
            target_label=target_label,
            preview_entries=preview_entries,
            counterparty_account_id=None,
            matched_raw_transaction_id=matched_raw_transaction_id,
            matched_operation_id=None,
        )

    async def start_transfer_confirmation_with_existing(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewTransferExistingSelection,
    ) -> StartedChatReviewTransferConfirmation:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        if state.step != "choose_transfer_target":
            raise ChatReviewActionError("Stored review action is invalid.")

        matched_operation_id = ChatReviewStateReader.read_matched_operation_id(
            state.state_payload,
            selection.transfer_index,
        )
        target_label = ChatReviewStateReader.read_matched_operation_label(
            state.state_payload,
            selection.transfer_index,
        )
        item = await self._read_transfer_item(context=context, state=state)
        return await self._start_transfer_confirmation(
            context=context,
            state=state,
            item=item,
            target_label=target_label,
            preview_entries=ChatReviewStateReader.read_matched_operation_preview_entries(
                state.state_payload,
                selection.transfer_index,
            ),
            counterparty_account_id=None,
            matched_raw_transaction_id=None,
            matched_operation_id=matched_operation_id,
        )

    async def confirm_transfer(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewTransferConfirmationSelection,
    ) -> ChatReviewActionResult:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        if state.step != "confirm_transfer":
            raise ChatReviewActionError("Stored review action is invalid.")

        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        item = await self.review_queue.read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=ChatReviewStateReader.read_raw_transaction_id(
                state.state_payload,
            ),
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")

        command = ChatReviewTransferCommandBuilder.build_command(
            state.state_payload,
            idempotency_key=state.id,
        )
        await ChatReviewStateClaimer.claim_once(self.chat_integrations, state)
        try:
            await self.transfers.apply(
                context=context,
                command=command,
            )
        except (LedgerPostingError, RawTransactionReviewError, ValueError) as exc:
            await self.session.rollback()
            raise ChatReviewActionError(str(exc)) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.commit()
        return ChatReviewActionResult(
            action_label=ChatReviewStateReader.read_transfer_action_label(state.state_payload),
            continuation_anchor=ChatReviewContinuationAnchor(
                document_id=document_id,
                row_index=item.row_index,
            ),
        )

    async def _start_transfer_confirmation(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        item: ChatReviewQueueItem,
        target_label: str,
        preview_entries: tuple[ChatReviewTransferPreviewEntry, ...],
        counterparty_account_id: UUID | None,
        matched_raw_transaction_id: UUID | None,
        matched_operation_id: UUID | None = None,
    ) -> StartedChatReviewTransferConfirmation:
        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(state.state_payload)

        next_action_token = ChatActionTokenBuilder.build_token()
        payload: dict[str, object] = {
            "document_id": str(document_id),
            "raw_transaction_id": str(raw_transaction_id),
            "target_label": target_label,
        }
        if counterparty_account_id is not None:
            payload["counterparty_account_id"] = str(counterparty_account_id)
            payload["action_label"] = "перевод подтвержден"
        if matched_raw_transaction_id is not None:
            payload["matched_raw_transaction_id"] = str(matched_raw_transaction_id)
            payload["action_label"] = "парный перевод подтвержден"
        if matched_operation_id is not None:
            payload["matched_operation_id"] = str(matched_operation_id)
            payload["action_label"] = "строка привязана к ручному переводу"

        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            step="confirm_transfer",
            action_token=next_action_token,
            state_payload=payload,
            expires_at=utc_now() + CHAT_REVIEW_ACTION_TTL,
        )
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return StartedChatReviewTransferConfirmation(
            action_token=next_action_token,
            item=item,
            target_label=target_label,
            preview_entries=preview_entries,
        )

    async def _read_transfer_item(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
    ) -> ChatReviewQueueItem:
        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(state.state_payload)
        item = await self.review_queue.read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")
        if item.amount is None:
            raise ChatReviewActionError("Raw transaction row has no amount.")
        return item

    @staticmethod
    def _source_preview_entry(item: ChatReviewQueueItem) -> ChatReviewTransferPreviewEntry:
        if item.amount is None:
            raise ChatReviewActionError("Raw transaction row has no amount.")
        return ChatReviewTransferPreviewEntry(
            account_name=item.account_name or "счет строки",
            amount=item.amount,
            currency=item.currency,
        )

    async def _build_transfer_pair_choices(
        self,
        *,
        context: WorkspaceContext,
        item: ChatReviewQueueItem,
    ) -> tuple[ChatReviewTransferPairChoice, ...]:
        raw_transaction = await ImportReviewRepository(self.session).get_review_raw_transaction(
            workspace_id=context.workspace.id,
            document_id=item.document_id,
            raw_transaction_id=item.raw_transaction_id,
        )
        if raw_transaction is None:
            return ()
        suggestions = await self.transfer_suggestions.list_for_document(
            workspace_id=context.workspace.id,
            raw_transactions=[raw_transaction],
        )
        return ChatReviewTransferPairChoiceBuilder.build_choices(
            suggestions.get(raw_transaction.id, [])
        )

    async def _build_existing_transfer_choices(
        self,
        *,
        context: WorkspaceContext,
        item: ChatReviewQueueItem,
    ) -> tuple[ChatReviewExistingTransferChoice, ...]:
        raw_transaction = await ImportReviewRepository(self.session).get_review_raw_transaction(
            workspace_id=context.workspace.id,
            document_id=item.document_id,
            raw_transaction_id=item.raw_transaction_id,
        )
        if raw_transaction is None:
            return ()
        suggestions = await self.transfer_suggestions.list_existing_manual_for_document(
            workspace_id=context.workspace.id,
            raw_transactions=[raw_transaction],
        )
        return ChatReviewExistingTransferChoiceBuilder.build_choices(
            suggestions.get(raw_transaction.id, [])
        )
