from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.chat_integrations.actions.review import (
    ChatReviewRulePatternSelection,
    ChatReviewRuleSuggestionSelection,
)
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.models import ChatConversationFlow, ChatConversationState
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.use_cases.action_tokens import ChatActionTokenBuilder
from app.features.chat_integrations.use_cases.review.builders import ChatReviewRulePatternBuilder
from app.features.chat_integrations.use_cases.review.config import CHAT_REVIEW_ACTION_TTL
from app.features.chat_integrations.use_cases.review.dto import (
    ChatReviewContinuationAnchor,
    ChatReviewRuleActionResult,
    StartedChatReviewRulePatternInput,
    StartedChatReviewRulePatternSelection,
)
from app.features.chat_integrations.use_cases.review.queue import ChatReviewQueueReader
from app.features.chat_integrations.use_cases.review.state import (
    ChatReviewStateClaimer,
    ChatReviewStateReader,
)
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.workspaces.service import WorkspaceContext


class ChatReviewRuleSuggestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)

    async def save_suggestion(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> ChatReviewRuleActionResult:
        state = await self._get_rule_suggestion_state(
            context=context,
            action_token=selection.action_token,
        )
        pattern = ChatReviewStateReader.read_rule_pattern(state.state_payload, 0)
        anchor = await self._create_rule_from_state(context=context, state=state, pattern=pattern)
        return ChatReviewRuleActionResult(
            action_label="правило сохранено",
            continuation_anchor=anchor,
        )

    async def skip_suggestion(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> ChatReviewRuleActionResult:
        state = await self._get_rule_suggestion_state(
            context=context,
            action_token=selection.action_token,
        )
        anchor = await self._build_continuation_anchor(context=context, state=state)
        await ChatReviewStateClaimer.claim_once(self.chat_integrations, state)
        await self.session.commit()
        return ChatReviewRuleActionResult(
            action_label="без правила",
            continuation_anchor=anchor,
        )

    async def start_pattern_selection(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> StartedChatReviewRulePatternSelection:
        state = await self._get_rule_suggestion_state(
            context=context,
            action_token=selection.action_token,
        )
        return StartedChatReviewRulePatternSelection(
            action_token=selection.action_token,
            pattern_choices=ChatReviewStateReader.read_rule_patterns(state.state_payload),
            category_name=ChatReviewStateReader.read_confirm_category_name(state.state_payload),
        )

    async def start_manual_pattern_input(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> StartedChatReviewRulePatternInput:
        state = await self._get_rule_suggestion_state(
            context=context,
            action_token=selection.action_token,
        )
        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.REVIEW,
            step="enter_rule_pattern",
            action_token=action_token,
            state_payload=state.state_payload,
            expires_at=utc_now() + CHAT_REVIEW_ACTION_TTL,
        )
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return StartedChatReviewRulePatternInput(
            action_token=action_token,
            category_name=ChatReviewStateReader.read_confirm_category_name(state.state_payload),
        )

    async def save_manual_pattern(
        self,
        *,
        context: WorkspaceContext,
        text: str | None,
    ) -> ChatReviewRuleActionResult | None:
        state = await self.chat_integrations.get_latest_active_conversation_state_for_flows(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flows=(ChatConversationFlow.REVIEW,),
            now=utc_now(),
        )
        if state is None or state.step != "enter_rule_pattern":
            return None

        pattern = ChatReviewRulePatternBuilder.clean_manual_pattern(text)
        anchor = await self._create_rule_from_state(context=context, state=state, pattern=pattern)
        return ChatReviewRuleActionResult(
            action_label="правило сохранено",
            continuation_anchor=anchor,
        )

    async def save_pattern_selection(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatReviewRulePatternSelection,
    ) -> ChatReviewRuleActionResult:
        state = await self._get_rule_suggestion_state(
            context=context,
            action_token=selection.action_token,
        )
        pattern = ChatReviewStateReader.read_rule_pattern(
            state.state_payload,
            selection.pattern_index,
        )
        anchor = await self._create_rule_from_state(context=context, state=state, pattern=pattern)
        return ChatReviewRuleActionResult(
            action_label="правило сохранено",
            continuation_anchor=anchor,
        )

    async def _get_rule_suggestion_state(
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
        if state.step not in {"suggest_rule", "enter_rule_pattern"}:
            raise ChatReviewActionError("Stored review action is invalid.")
        return state

    async def _create_rule_from_state(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        pattern: str,
    ) -> ChatReviewContinuationAnchor:
        anchor = await self._build_continuation_anchor(context=context, state=state)
        await ChatReviewStateClaimer.claim_once(self.chat_integrations, state)
        try:
            await TransactionRuleManagementUseCase(self.session).create_rule_from_raw_confirmation(
                context=context,
                document_id=ChatReviewStateReader.read_document_id(state.state_payload),
                raw_transaction_id=ChatReviewStateReader.read_raw_transaction_id(
                    state.state_payload,
                ),
                category_id=ChatReviewStateReader.read_confirm_category_id(state.state_payload),
                property_id=ChatReviewStateReader.read_optional_property_id(state.state_payload),
                pattern=pattern,
            )
            await TransactionRuleApplicationUseCase(self.session).apply_rules_to_document(
                workspace_id=context.workspace.id,
                document_id=ChatReviewStateReader.read_document_id(state.state_payload),
            )
            await self.session.commit()
        except TransactionRuleError as exc:
            await self.session.rollback()
            raise ChatReviewActionError(str(exc)) from exc
        except Exception:
            await self.session.rollback()
            raise
        return anchor

    async def _build_continuation_anchor(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
    ) -> ChatReviewContinuationAnchor:
        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        item = await ChatReviewQueueReader(self.session).read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=ChatReviewStateReader.read_raw_transaction_id(
                state.state_payload,
            ),
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")
        return ChatReviewContinuationAnchor(document_id=document_id, row_index=item.row_index)
