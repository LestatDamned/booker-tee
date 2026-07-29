from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.categories.service import CategoryService
from app.features.chat_integrations.actions.review import (
    ChatReviewCategoryPageSelection,
    ChatReviewCategorySelection,
    ChatReviewPropertySelection,
)
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.models import ChatConversationFlow, ChatConversationState
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.use_cases.action_tokens import ChatActionTokenBuilder
from app.features.chat_integrations.use_cases.review.builders import (
    ChatReviewCategoryChoiceBuilder,
    ChatReviewCategoryPageBuilder,
    ChatReviewPropertyChoiceBuilder,
    ChatReviewRulePatternBuilder,
)
from app.features.chat_integrations.use_cases.review.config import CHAT_REVIEW_ACTION_TTL
from app.features.chat_integrations.use_cases.review.dto import (
    ChatReviewActionResult,
    ChatReviewCategoryActionResult,
    ChatReviewContinuationAnchor,
    ChatReviewQueueItem,
    StartedChatReviewCategorySelection,
    StartedChatReviewPropertySelection,
    StartedChatReviewRuleSuggestion,
)
from app.features.chat_integrations.use_cases.review.queue import ChatReviewQueueReader
from app.features.chat_integrations.use_cases.review.state import (
    ChatReviewStateClaimer,
    ChatReviewStateReader,
)
from app.features.import_review.application.confirmation import (
    ConfirmImportReviewItemCommand,
    ImportReviewConfirmationActor,
)
from app.features.import_review.repository import ImportReviewRepository
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.errors import RawTransactionReviewError
from app.features.ledger.errors import LedgerPostingError
from app.features.properties.service import PropertyService
from app.features.workspaces.service import WorkspaceContext


class ChatReviewConfirmationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.categories = CategoryService(session)
        self.properties = PropertyService(session)
        self.chat_integrations = ChatIntegrationRepository(session)
        self.review_queue = ChatReviewQueueReader(session)
        self.confirmations = ImportReviewConfirmationActor(session)

    async def start_category_selection(
        self,
        *,
        context: WorkspaceContext,
        action_token: str,
    ) -> StartedChatReviewCategorySelection:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        if state.step not in {"review_item", "confirm_transfer"}:
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

        categories = await self.categories.list_or_seed_defaults(
            context.workspace.id,
            getattr(context.workspace, "type", None),
            include_inactive=False,
        )
        category_choices = ChatReviewCategoryChoiceBuilder.build_choices(
            item=item,
            categories=categories,
        )
        if not category_choices:
            raise ChatReviewActionError("No active categories are available.")

        next_action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            step="choose_category",
            action_token=next_action_token,
            state_payload={
                "document_id": str(document_id),
                "raw_transaction_id": str(raw_transaction_id),
                "category_ids": [str(choice.id) for choice in category_choices],
                "category_names": [choice.name for choice in category_choices],
            },
            expires_at=utc_now() + CHAT_REVIEW_ACTION_TTL,
        )
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return ChatReviewCategoryPageBuilder.build_selection(
            action_token=next_action_token,
            item=item,
            category_choices=category_choices,
            page_index=0,
        )

    async def change_category_page(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewCategoryPageSelection,
    ) -> StartedChatReviewCategorySelection:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        if state.step != "choose_category":
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

        return ChatReviewCategoryPageBuilder.build_selection(
            action_token=selection.action_token,
            item=item,
            category_choices=ChatReviewStateReader.read_category_choices(state.state_payload),
            page_index=selection.page_index,
        )

    async def confirm_with_suggestion(
        self,
        *,
        context: WorkspaceContext,
        action_token: str,
    ) -> ChatReviewCategoryActionResult:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
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
        if item.suggested_category_id is None:
            raise ChatReviewActionError("У этой строки нет предложения категории.")

        categories = await self.categories.list_or_seed_defaults(
            context.workspace.id,
            getattr(context.workspace, "type", None),
            include_inactive=False,
        )
        suggested_choice = next(
            (
                choice
                for choice in ChatReviewCategoryChoiceBuilder.build_choices(
                    item=item,
                    categories=categories,
                )
                if choice.id == item.suggested_category_id
            ),
            None,
        )
        if suggested_choice is None:
            raise ChatReviewActionError("Предложенная категория больше недоступна.")

        return await self._finish_category_confirmation(
            context=context,
            state=state,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            item=item,
            category_id=suggested_choice.id,
            category_name=suggested_choice.name,
            offer_rule_suggestion=False,
        )

    async def confirm_with_category(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewCategorySelection,
    ) -> ChatReviewCategoryActionResult:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        if state.step != "choose_category":
            raise ChatReviewActionError("Stored review action is invalid.")

        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(state.state_payload)
        category_id = ChatReviewStateReader.read_category_id(
            state.state_payload,
            selection.category_index,
        )
        item = await self.review_queue.read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")

        return await self._finish_category_confirmation(
            context=context,
            state=state,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            item=item,
            category_id=category_id,
            category_name=ChatReviewStateReader.read_category_name(
                state.state_payload,
                selection.category_index,
            ),
            offer_rule_suggestion=True,
        )

    async def _finish_category_confirmation(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        document_id: UUID,
        raw_transaction_id: UUID,
        item: ChatReviewQueueItem,
        category_id: UUID,
        category_name: str,
        offer_rule_suggestion: bool,
    ) -> ChatReviewCategoryActionResult:
        properties = await self.properties.list_active(context.workspace.id)
        if not properties:
            await ChatReviewStateClaimer.claim_once(self.chat_integrations, state)
            result = await self._confirm_transaction(
                context=context,
                state=state,
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                item=item,
                category_id=category_id,
                property_id=None,
            )
            rule_suggestion = None
            if offer_rule_suggestion:
                rule_suggestion = await self._maybe_start_rule_suggestion(
                    context=context,
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    category_id=category_id,
                    property_id=None,
                    category_name=category_name,
                    action_label=result.action_label,
                )
            await self.session.commit()
            return ChatReviewCategoryActionResult(
                action_result=result,
                rule_suggestion=rule_suggestion,
            )

        property_choices = ChatReviewPropertyChoiceBuilder.build_choices(properties)
        next_action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            step="choose_property",
            action_token=next_action_token,
            state_payload={
                "document_id": str(document_id),
                "raw_transaction_id": str(raw_transaction_id),
                "category_id": str(category_id),
                "category_name": category_name,
                "offer_rule_suggestion": offer_rule_suggestion,
                "property_ids": [
                    str(choice.id) if choice.id is not None else None for choice in property_choices
                ],
            },
            expires_at=utc_now() + CHAT_REVIEW_ACTION_TTL,
        )
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return ChatReviewCategoryActionResult(
            property_selection=StartedChatReviewPropertySelection(
                action_token=next_action_token,
                item=item,
                category_name=category_name,
                property_choices=property_choices,
            )
        )

    async def confirm_with_property(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewPropertySelection,
    ) -> ChatReviewCategoryActionResult:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatReviewActionError("This review action expired. Open the next row again.")
        if state.step != "choose_property":
            raise ChatReviewActionError("Stored review action is invalid.")

        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(state.state_payload)
        category_id = ChatReviewStateReader.read_confirm_category_id(state.state_payload)
        property_id = ChatReviewStateReader.read_property_id(
            state.state_payload,
            selection.property_index,
        )
        item = await self.review_queue.read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")

        await ChatReviewStateClaimer.claim_once(self.chat_integrations, state)
        result = await self._confirm_transaction(
            context=context,
            state=state,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            item=item,
            category_id=category_id,
            property_id=property_id,
        )

        rule_suggestion = None
        if ChatReviewStateReader.read_offer_rule_suggestion(state.state_payload):
            rule_suggestion = await self._maybe_start_rule_suggestion(
                context=context,
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                category_id=category_id,
                property_id=property_id,
                category_name=ChatReviewStateReader.read_confirm_category_name(state.state_payload),
                action_label=result.action_label,
            )
        await self.session.commit()
        return ChatReviewCategoryActionResult(
            action_result=result,
            rule_suggestion=rule_suggestion,
        )

    async def _maybe_start_rule_suggestion(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        category_id: UUID,
        property_id: UUID | None,
        category_name: str,
        action_label: str,
    ) -> StartedChatReviewRuleSuggestion | None:
        raw_transaction = await ImportReviewRepository(self.session).get_review_raw_transaction(
            workspace_id=context.workspace.id,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
        if raw_transaction is None:
            return None

        pattern_choices = ChatReviewRulePatternBuilder.build_choices(raw_transaction)
        if not pattern_choices:
            return None

        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            step="suggest_rule",
            action_token=action_token,
            state_payload={
                "document_id": str(document_id),
                "raw_transaction_id": str(raw_transaction_id),
                "category_id": str(category_id),
                "property_id": str(property_id) if property_id is not None else None,
                "category_name": category_name,
                "patterns": list(pattern_choices),
            },
            expires_at=utc_now() + CHAT_REVIEW_ACTION_TTL,
        )
        return StartedChatReviewRuleSuggestion(
            action_token=action_token,
            action_label=action_label,
            pattern=pattern_choices[0],
            alternative_patterns=pattern_choices[1:],
            category_name=category_name,
        )

    async def _confirm_transaction(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        document_id: UUID,
        raw_transaction_id: UUID,
        item: ChatReviewQueueItem,
        category_id: UUID,
        property_id: UUID | None,
    ) -> ChatReviewActionResult:
        try:
            await self.confirmations.apply(
                context=context,
                command=ConfirmImportReviewItemCommand(
                    document_id=document_id,
                    item_id=raw_transaction_id,
                    operation_type=None,
                    category_id=category_id,
                    property_id=property_id,
                    expected_status=RawTransactionStatus(item.status),
                    remember_rule=False,
                    rule_pattern=None,
                    idempotency_key=state.id,
                ),
            )
        except (LedgerPostingError, RawTransactionReviewError, ValueError) as exc:
            await self.session.rollback()
            raise ChatReviewActionError(str(exc)) from exc
        except Exception:
            await self.session.rollback()
            raise

        return ChatReviewActionResult(
            action_label="операция подтверждена",
            continuation_anchor=ChatReviewContinuationAnchor(
                document_id=document_id,
                row_index=item.row_index,
            ),
        )
