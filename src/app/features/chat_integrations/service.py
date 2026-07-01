from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.application import (
    BoundChatWorkspace,
    ChatAccountBalanceReader,
    ChatDocumentUploadService,
    ChatManualOperationConfirmation,
    ChatManualOperationService,
    ChatMonthlySummaryReader,
    ChatPrivateStatus,
    ChatPrivateStatusReader,
    ChatReviewActionService,
    ChatReviewCategoryActionResult,
    ChatReviewConfirmationService,
    ChatReviewContinuationAnchor,
    ChatReviewNavigationBoundary,
    ChatReviewQueueService,
    ChatReviewRuleSuggestionService,
    ChatReviewTransferService,
    ChatReviewUrlBuilder,
    ChatWorkspaceSwitcher,
    StartedChatManualAccountSelection,
    StartedChatManualAmountInput,
    StartedChatManualCategorySelection,
    StartedChatManualCorrectionSelection,
    StartedChatManualDateInput,
    StartedChatManualDateSelection,
    StartedChatManualDescriptionInput,
    WorkspaceChatResolver,
)
from app.features.chat_integrations.commands import (
    ChatManualAccountCallbackData,
    ChatManualAccountSelection,
    ChatManualCategoryCallbackData,
    ChatManualCategorySelection,
    ChatManualConfirmationCallbackData,
    ChatManualConfirmationSelection,
    ChatManualCorrectionCallbackData,
    ChatManualCorrectionSelection,
    ChatManualDateCallbackData,
    ChatManualDateSelection,
    ChatManualDescriptionCallbackData,
    ChatManualDescriptionSelection,
    ChatReviewActionConfirmationCallbackData,
    ChatReviewActionConfirmationSelection,
    ChatReviewActionSelection,
    ChatReviewCallbackData,
    ChatReviewCategoryCallbackData,
    ChatReviewCategoryPageCallbackData,
    ChatReviewCategoryPageSelection,
    ChatReviewCategorySelection,
    ChatReviewNavigationCallbackData,
    ChatReviewNavigationSelection,
    ChatReviewPropertyCallbackData,
    ChatReviewPropertySelection,
    ChatReviewReturnCallbackData,
    ChatReviewReturnSelection,
    ChatReviewRulePatternCallbackData,
    ChatReviewRulePatternSelection,
    ChatReviewRuleSuggestionCallbackData,
    ChatReviewRuleSuggestionSelection,
    ChatReviewTransferAccountSelection,
    ChatReviewTransferCallbackData,
    ChatReviewTransferConfirmationCallbackData,
    ChatReviewTransferConfirmationSelection,
    ChatReviewTransferPairCallbackData,
    ChatReviewTransferPairSelection,
    ChatSummaryCallbackData,
    ChatSummaryPeriodSelection,
    ChatUploadAccountSelection,
    ChatUploadCallbackData,
    ChatWorkspaceCallbackData,
    ChatWorkspaceSelection,
)
from app.features.chat_integrations.errors import (
    ChatDocumentUploadError,
    ChatManualOperationError,
    ChatReviewActionError,
    ChatWorkspaceResolutionError,
    ChatWorkspaceSwitchError,
)
from app.features.chat_integrations.notifications.dispatcher import (
    ChatNotificationProviderRegistry,
    ChatSharedFeedNotificationService,
)
from app.features.chat_integrations.presenters import TelegramMainMenuPresenter
from app.features.chat_integrations.providers.base import ChatDocumentDownloader, ChatProvider
from app.features.chat_integrations.schemas import (
    ChatConversationType,
    InboundChatEvent,
    InboundChatEventType,
    OutboundChatMessage,
)
from app.features.imports.models import UploadedDocument
from app.features.ledger.models import OperationType


class ChatEventService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        settings: Settings | None = None,
        document_downloader: ChatDocumentDownloader | None = None,
        chat_provider: ChatProvider | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.document_downloader = document_downloader
        self.chat_provider = chat_provider

    async def receive_inbound_event(self, event: InboundChatEvent) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        bound_workspace = await self._resolve_bound_workspace(event)
        if bound_workspace is not None:
            return await self._answer_bound_event(event, bound_workspace)

        if self._is_start_message(event):
            return TelegramMainMenuPresenter.show_welcome_menu(event.conversation)

        if event.event_type == InboundChatEventType.CALLBACK_QUERY:
            return self._answer_unbound_callback_query(event)

        return TelegramMainMenuPresenter.show_safe_fallback(event.conversation)

    @staticmethod
    def _is_start_message(event: InboundChatEvent) -> bool:
        return event.event_type == InboundChatEventType.MESSAGE and event.text == "/start"

    async def _resolve_bound_workspace(self, event: InboundChatEvent) -> BoundChatWorkspace | None:
        if self.session is None or event.actor is None:
            return None
        try:
            return await WorkspaceChatResolver(self.session).require_bound_workspace(event)
        except ChatWorkspaceResolutionError:
            return None

    async def _answer_bound_event(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        if event.conversation.conversation_type != ChatConversationType.PRIVATE:
            return TelegramMainMenuPresenter.show_group_private_actions_notice(event.conversation)

        if event.event_type == InboundChatEventType.DOCUMENT:
            return await self._start_document_upload(event, bound_workspace)

        account_selection = ChatUploadCallbackData.parse_account_selection(event.callback_data)
        if account_selection is not None:
            return await self._complete_document_upload(event, bound_workspace, account_selection)

        review_navigation = ChatReviewNavigationCallbackData.parse_navigation_selection(
            event.callback_data
        )
        if review_navigation is not None:
            return await self._navigate_review_item(event, bound_workspace, review_navigation)

        manual_confirmation = ChatManualConfirmationCallbackData.parse_confirm_action(
            event.callback_data
        )
        if manual_confirmation is not None:
            return await self._confirm_manual_operation(
                event,
                bound_workspace,
                manual_confirmation,
            )

        manual_correction_selection = ChatManualCorrectionCallbackData.parse_correction_selection(
            event.callback_data
        )
        if manual_correction_selection is not None:
            return await self._select_manual_correction(
                event,
                bound_workspace,
                manual_correction_selection,
            )

        manual_account_selection = ChatManualAccountCallbackData.parse_account_selection(
            event.callback_data
        )
        if manual_account_selection is not None:
            return await self._select_manual_account(
                event,
                bound_workspace,
                manual_account_selection,
            )

        manual_category_selection = ChatManualCategoryCallbackData.parse_category_selection(
            event.callback_data
        )
        if manual_category_selection is not None:
            return await self._select_manual_category(
                event,
                bound_workspace,
                manual_category_selection,
            )

        manual_date_selection = ChatManualDateCallbackData.parse_date_selection(event.callback_data)
        if manual_date_selection is not None:
            return await self._select_manual_date(
                event,
                bound_workspace,
                manual_date_selection,
            )

        manual_description_selection = (
            ChatManualDescriptionCallbackData.parse_description_selection(event.callback_data)
        )
        if manual_description_selection is not None:
            return await self._skip_manual_description(
                event,
                bound_workspace,
                manual_description_selection,
            )

        rule_pattern_selection = ChatReviewRulePatternCallbackData.parse_pattern_selection(
            event.callback_data
        )
        if rule_pattern_selection is not None:
            return await self._save_review_rule_pattern(
                event,
                bound_workspace,
                rule_pattern_selection,
            )

        rule_suggestion_action = ChatReviewRuleSuggestionCallbackData.parse_action(
            event.callback_data
        )
        if rule_suggestion_action is not None:
            return await self._apply_review_rule_suggestion_action(
                event,
                bound_workspace,
                rule_suggestion_action,
            )

        transfer_confirmation = (
            ChatReviewTransferConfirmationCallbackData.parse_confirmation_selection(
                event.callback_data
            )
        )
        if transfer_confirmation is not None:
            return await self._confirm_review_transfer(
                event,
                bound_workspace,
                transfer_confirmation,
            )

        transfer_pair_selection = ChatReviewTransferPairCallbackData.parse_pair_selection(
            event.callback_data
        )
        if transfer_pair_selection is not None:
            return await self._complete_review_transfer_pair(
                event,
                bound_workspace,
                transfer_pair_selection,
            )

        transfer_account_selection = ChatReviewTransferCallbackData.parse_account_selection(
            event.callback_data
        )
        if transfer_account_selection is not None:
            return await self._complete_review_transfer(
                event,
                bound_workspace,
                transfer_account_selection,
            )

        property_selection = ChatReviewPropertyCallbackData.parse_property_selection(
            event.callback_data
        )
        if property_selection is not None:
            return await self._complete_review_property_confirmation(
                event,
                bound_workspace,
                property_selection,
            )

        action_confirmation = ChatReviewActionConfirmationCallbackData.parse_confirmation_selection(
            event.callback_data
        )
        if action_confirmation is not None:
            return await self._confirm_review_action(
                event,
                bound_workspace,
                action_confirmation,
            )

        review_return_selection = ChatReviewReturnCallbackData.parse_return_selection(
            event.callback_data
        )
        if review_return_selection is not None:
            return await self._return_to_review_item(
                event,
                bound_workspace,
                review_return_selection,
            )

        category_page_selection = ChatReviewCategoryPageCallbackData.parse_page_selection(
            event.callback_data
        )
        if category_page_selection is not None:
            return await self._change_review_category_page(
                event,
                bound_workspace,
                category_page_selection,
            )

        category_selection = ChatReviewCategoryCallbackData.parse_category_selection(
            event.callback_data
        )
        if category_selection is not None:
            return await self._complete_review_confirmation(
                event,
                bound_workspace,
                category_selection,
            )

        review_action = ChatReviewCallbackData.parse_action(event.callback_data)
        if review_action is not None:
            return await self._apply_review_action(event, bound_workspace, review_action)

        workspace_selection = ChatWorkspaceCallbackData.parse_workspace_selection(
            event.callback_data
        )
        if workspace_selection is not None:
            return await self._select_chat_workspace(event, bound_workspace, workspace_selection)

        summary_period_selection = ChatSummaryCallbackData.parse_period_selection(
            event.callback_data
        )
        if summary_period_selection is not None:
            return await self._show_monthly_summary_for_period(
                event,
                bound_workspace,
                summary_period_selection,
            )

        category_summary_selection = ChatSummaryCallbackData.parse_category_selection(
            event.callback_data
        )
        if category_summary_selection is not None:
            return await self._show_category_summary_for_period(
                event,
                bound_workspace,
                category_summary_selection,
            )

        if event.event_type == InboundChatEventType.MESSAGE and not self._is_start_message(event):
            manual_response = await self._answer_manual_amount_message(event, bound_workspace)
            if manual_response is not None:
                return manual_response

            rule_pattern_response = await self._answer_review_rule_pattern_message(
                event,
                bound_workspace,
            )
            if rule_pattern_response is not None:
                return rule_pattern_response

        status = await ChatPrivateStatusReader(self.session).read_status(bound_workspace.context)

        if self._is_start_message(event):
            return TelegramMainMenuPresenter.show_bound_menu(
                event.conversation,
                bound_workspace.context,
                status,
                ChatReviewUrlBuilder.build_imports_url(self.settings),
            )

        if event.event_type == InboundChatEventType.CALLBACK_QUERY:
            return await self._answer_bound_callback_query(event, bound_workspace, status)

        return TelegramMainMenuPresenter.show_bound_menu(
            event.conversation,
            bound_workspace.context,
            status,
            ChatReviewUrlBuilder.build_imports_url(self.settings),
        )

    async def _answer_bound_callback_query(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        status: ChatPrivateStatus,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        match event.callback_data:
            case "main:menu":
                return TelegramMainMenuPresenter.show_bound_menu(
                    event.conversation,
                    bound_workspace.context,
                    status,
                    ChatReviewUrlBuilder.build_imports_url(self.settings),
                )
            case "status:show":
                return TelegramMainMenuPresenter.show_private_status(
                    event.conversation,
                    bound_workspace.context,
                    status,
                    ChatReviewUrlBuilder.build_imports_url(self.settings),
                )
            case "summary:show":
                return await self._show_monthly_summary(event, bound_workspace)
            case "balances:show":
                return await self._show_account_balances(event, bound_workspace)
            case "review:next":
                return await self._show_next_review_item(event, bound_workspace)
            case "upload:start":
                return TelegramMainMenuPresenter.show_upload_instructions(event.conversation)
            case "manual:start":
                return TelegramMainMenuPresenter.show_manual_operation_type_menu(event.conversation)
            case "workspace:choose":
                return await self._start_chat_workspace_selection(event, bound_workspace)
            case "manual:expense":
                return await self._start_manual_income_expense(
                    event,
                    bound_workspace,
                    OperationType.EXPENSE,
                )
            case "manual:income":
                return await self._start_manual_income_expense(
                    event,
                    bound_workspace,
                    OperationType.INCOME,
                )
            case "manual:transfer":
                return await self._start_manual_transfer(event, bound_workspace)
            case "help:show":
                return TelegramMainMenuPresenter.show_help(event.conversation)
            case _:
                return TelegramMainMenuPresenter.show_bound_menu(
                    event.conversation,
                    bound_workspace.context,
                    status,
                    ChatReviewUrlBuilder.build_imports_url(self.settings),
                )

    async def _start_chat_workspace_selection(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        try:
            selection = await ChatWorkspaceSwitcher(self.session).start_workspace_selection(
                bound_workspace
            )
        except ChatWorkspaceSwitchError as exc:
            return TelegramMainMenuPresenter.show_workspace_switch_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_workspace_menu(event.conversation, selection)

    async def _show_monthly_summary(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        summary = await ChatMonthlySummaryReader(self.session).read_current_month_summary(
            bound_workspace.context
        )
        return TelegramMainMenuPresenter.show_monthly_summary(
            event.conversation,
            bound_workspace.context,
            summary,
        )

    async def _show_monthly_summary_for_period(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatSummaryPeriodSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        summary = await ChatMonthlySummaryReader(self.session).read_month_summary(
            context=bound_workspace.context,
            month_start=selection.month_start,
        )
        return TelegramMainMenuPresenter.show_monthly_summary(
            event.conversation,
            bound_workspace.context,
            summary,
        )

    async def _show_category_summary_for_period(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatSummaryPeriodSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        summary = await ChatMonthlySummaryReader(self.session).read_category_summary(
            context=bound_workspace.context,
            month_start=selection.month_start,
        )
        return TelegramMainMenuPresenter.show_category_summary(
            event.conversation,
            bound_workspace.context,
            summary,
        )

    async def _show_account_balances(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        balances = await ChatAccountBalanceReader(self.session).read_account_balances(
            bound_workspace.context
        )
        return TelegramMainMenuPresenter.show_account_balances(
            event.conversation,
            bound_workspace.context,
            balances,
        )

    async def _select_chat_workspace(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        workspace_selection: ChatWorkspaceSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        try:
            selected = await ChatWorkspaceSwitcher(self.session).select_workspace(
                bound_workspace=bound_workspace,
                selection=workspace_selection,
            )
        except ChatWorkspaceSwitchError as exc:
            return TelegramMainMenuPresenter.show_workspace_switch_error(
                event.conversation,
                str(exc),
            )

        status = await ChatPrivateStatusReader(self.session).read_status(
            selected.bound_workspace.context
        )
        return TelegramMainMenuPresenter.show_bound_menu(
            event.conversation,
            selected.bound_workspace.context,
            status,
            ChatReviewUrlBuilder.build_imports_url(self.settings),
            callback_notification="Готово: пространство переключено",
        )

    async def _start_manual_income_expense(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        operation_type: OperationType,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            selection = await ChatManualOperationService(self.session).start_income_expense(
                context=bound_workspace.context,
                operation_type=operation_type,
            )
        except ChatManualOperationError as exc:
            return TelegramMainMenuPresenter.show_manual_operation_error(
                event.conversation,
                str(exc),
            )
        return TelegramMainMenuPresenter.show_manual_account_menu(event.conversation, selection)

    async def _start_manual_transfer(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            selection = await ChatManualOperationService(self.session).start_transfer(
                context=bound_workspace.context,
            )
        except ChatManualOperationError as exc:
            return TelegramMainMenuPresenter.show_manual_operation_error(
                event.conversation,
                str(exc),
            )
        return TelegramMainMenuPresenter.show_manual_account_menu(event.conversation, selection)

    async def _select_manual_account(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualAccountSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            result = await ChatManualOperationService(self.session).select_account(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramMainMenuPresenter.show_manual_operation_error(
                event.conversation,
                str(exc),
            )
        if isinstance(result, StartedChatManualAccountSelection):
            return TelegramMainMenuPresenter.show_manual_account_menu(
                event.conversation,
                result,
            )
        return TelegramMainMenuPresenter.show_manual_amount_prompt(event.conversation, result)

    async def _select_manual_category(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualCategorySelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            next_step = await ChatManualOperationService(self.session).select_category(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramMainMenuPresenter.show_manual_operation_error(
                event.conversation,
                str(exc),
            )
        return self._show_manual_next_step(event, next_step)

    async def _select_manual_correction(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualCorrectionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            next_step = await ChatManualOperationService(self.session).select_correction(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramMainMenuPresenter.show_manual_operation_error(
                event.conversation,
                str(exc),
            )
        return self._show_manual_next_step(event, next_step)

    async def _skip_manual_description(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualDescriptionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            confirmation = await ChatManualOperationService(self.session).skip_description(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramMainMenuPresenter.show_manual_operation_error(
                event.conversation,
                str(exc),
            )
        return TelegramMainMenuPresenter.show_manual_confirmation(
            event.conversation,
            confirmation,
        )

    async def _select_manual_date(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualDateSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            next_step = await ChatManualOperationService(self.session).select_date(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramMainMenuPresenter.show_manual_operation_error(
                event.conversation,
                str(exc),
            )
        return self._show_manual_next_step(event, next_step)

    async def _answer_manual_amount_message(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            next_step = await ChatManualOperationService(
                self.session,
            ).continue_from_text_input(
                context=bound_workspace.context,
                text=event.text,
            )
        except ChatManualOperationError as exc:
            if "дат" in str(exc).casefold():
                return TelegramMainMenuPresenter.show_manual_date_error(
                    event.conversation,
                    str(exc),
                )
            return TelegramMainMenuPresenter.show_manual_amount_error(
                event.conversation,
                str(exc),
            )
        if next_step is None:
            return None
        return self._show_manual_next_step(event, next_step)

    @staticmethod
    def _show_manual_next_step(
        event: InboundChatEvent,
        next_step: (
            ChatManualOperationConfirmation
            | StartedChatManualAmountInput
            | StartedChatManualCategorySelection
            | StartedChatManualCorrectionSelection
            | StartedChatManualDateInput
            | StartedChatManualDateSelection
            | StartedChatManualDescriptionInput
        ),
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        if isinstance(next_step, StartedChatManualAmountInput):
            return TelegramMainMenuPresenter.show_manual_amount_prompt(
                event.conversation,
                next_step,
            )
        if isinstance(next_step, StartedChatManualDateSelection):
            return TelegramMainMenuPresenter.show_manual_date_menu(event.conversation, next_step)
        if isinstance(next_step, StartedChatManualDateInput):
            return TelegramMainMenuPresenter.show_manual_date_input_prompt(
                event.conversation,
                next_step,
            )
        if isinstance(next_step, StartedChatManualCategorySelection):
            return TelegramMainMenuPresenter.show_manual_category_menu(
                event.conversation,
                next_step,
            )
        if isinstance(next_step, StartedChatManualDescriptionInput):
            return TelegramMainMenuPresenter.show_manual_description_prompt(
                event.conversation,
                next_step,
            )
        if isinstance(next_step, StartedChatManualCorrectionSelection):
            return TelegramMainMenuPresenter.show_manual_correction_menu(
                event.conversation,
                next_step,
            )
        return TelegramMainMenuPresenter.show_manual_confirmation(event.conversation, next_step)

    async def _confirm_manual_operation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualConfirmationSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            result = await ChatManualOperationService(self.session).confirm(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramMainMenuPresenter.show_manual_operation_error(
                event.conversation,
                str(exc),
            )
        return TelegramMainMenuPresenter.show_manual_operation_completed(event.conversation, result)

    async def _start_document_upload(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        if self.session is None or self.settings is None or self.document_downloader is None:
            return TelegramMainMenuPresenter.show_upload_not_ready(event.conversation)

        try:
            upload = await ChatDocumentUploadService(
                self.session,
                self.settings,
                self.document_downloader,
            ).start_document_upload(
                context=bound_workspace.context,
                document=event.document,
            )
        except ChatDocumentUploadError as exc:
            return TelegramMainMenuPresenter.show_document_upload_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_document_upload_account_menu(
            event.conversation,
            upload,
        )

    async def _complete_document_upload(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        account_selection: ChatUploadAccountSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        if self.session is None or self.settings is None or self.document_downloader is None:
            return TelegramMainMenuPresenter.show_upload_not_ready(event.conversation)

        try:
            document = await ChatDocumentUploadService(
                self.session,
                self.settings,
                self.document_downloader,
            ).complete_document_upload(
                context=bound_workspace.context,
                action_token=account_selection.action_token,
                account_index=account_selection.account_index,
            )
        except ChatDocumentUploadError as exc:
            return TelegramMainMenuPresenter.show_document_upload_error(
                event.conversation,
                str(exc),
            )

        await self._notify_shared_feed_about_uploaded_document(event, bound_workspace, document)
        return TelegramMainMenuPresenter.show_document_upload_completed(
            event.conversation,
            document,
            ChatReviewUrlBuilder.build_document_review_url(self.settings, document.id),
        )

    async def _show_next_review_item(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        started_item = await ChatReviewQueueService(self.session).start_next_review_item(
            bound_workspace.context
        )
        if started_item is None:
            return TelegramMainMenuPresenter.show_review_queue_empty(event.conversation)

        return TelegramMainMenuPresenter.show_next_review_item(
            event.conversation,
            started_item.item,
            started_item.action_token,
            ChatReviewUrlBuilder.build_raw_transaction_review_url(
                self.settings,
                document_id=started_item.item.document_id,
                raw_transaction_id=started_item.item.raw_transaction_id,
            ),
        )

    async def _show_next_review_item_after_success(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        action_label: str,
        continuation_anchor: ChatReviewContinuationAnchor | None = None,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        callback_notification = f"Готово: {action_label}"
        review_queue = ChatReviewQueueService(self.session)
        if continuation_anchor is None:
            started_item = await review_queue.start_next_review_item(bound_workspace.context)
        else:
            started_item = await review_queue.start_next_review_item_after(
                context=bound_workspace.context,
                anchor=continuation_anchor,
            )
        if started_item is None:
            return TelegramMainMenuPresenter.show_review_queue_empty(
                event.conversation,
                callback_notification=callback_notification,
            )

        return TelegramMainMenuPresenter.show_next_review_item(
            event.conversation,
            started_item.item,
            started_item.action_token,
            ChatReviewUrlBuilder.build_raw_transaction_review_url(
                self.settings,
                document_id=started_item.item.document_id,
                raw_transaction_id=started_item.item.raw_transaction_id,
            ),
            callback_notification=callback_notification,
        )

    async def _return_to_review_item(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewReturnSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        try:
            started_item = await ChatReviewQueueService(self.session).return_to_review_item(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_next_review_item(
            event.conversation,
            started_item.item,
            started_item.action_token,
            ChatReviewUrlBuilder.build_raw_transaction_review_url(
                self.settings,
                document_id=started_item.item.document_id,
                raw_transaction_id=started_item.item.raw_transaction_id,
            ),
        )

    async def _navigate_review_item(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewNavigationSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None
        try:
            result = await ChatReviewQueueService(self.session).start_adjacent_review_item(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )
        if isinstance(result, ChatReviewNavigationBoundary):
            return TelegramMainMenuPresenter.show_review_navigation_boundary(
                event.conversation,
                result,
            )
        return TelegramMainMenuPresenter.show_next_review_item(
            event.conversation,
            result.item,
            result.action_token,
            ChatReviewUrlBuilder.build_raw_transaction_review_url(
                self.settings,
                document_id=result.item.document_id,
                raw_transaction_id=result.item.raw_transaction_id,
            ),
        )

    async def _apply_review_action(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        if review_action.action == ChatReviewCallbackData.CONFIRM_ACTION:
            return await self._start_review_confirmation(event, bound_workspace, review_action)

        if review_action.action == ChatReviewCallbackData.ACCEPT_SUGGESTION_ACTION:
            return await self._accept_review_suggestion(event, bound_workspace, review_action)

        if review_action.action == ChatReviewCallbackData.TRANSFER_ACTION:
            return await self._start_review_transfer(event, bound_workspace, review_action)

        if review_action.action in {
            ChatReviewCallbackData.DUPLICATE_ACTION,
            ChatReviewCallbackData.IGNORE_ACTION,
        }:
            return await self._start_review_action_confirmation(
                event,
                bound_workspace,
                review_action,
            )

        try:
            result = await ChatReviewActionService(self.session).apply_action(
                context=bound_workspace.context,
                selection=review_action,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return await self._show_next_review_item_after_success(
            event,
            bound_workspace,
            result.action_label,
            result.continuation_anchor,
        )

    async def _start_review_action_confirmation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        try:
            confirmation = await ChatReviewActionService(
                self.session,
            ).start_action_confirmation(
                context=bound_workspace.context,
                selection=review_action,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_review_action_confirmation(
            event.conversation,
            confirmation,
        )

    async def _confirm_review_action(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        action_confirmation: ChatReviewActionConfirmationSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        try:
            result = await ChatReviewActionService(self.session).confirm_action(
                context=bound_workspace.context,
                selection=action_confirmation,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return await self._show_next_review_item_after_success(
            event,
            bound_workspace,
            result.action_label,
            result.continuation_anchor,
        )

    async def _start_review_transfer(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None or self.settings is None:
            return None

        try:
            selection = await ChatReviewTransferService(
                self.session,
                self.settings,
            ).start_transfer_selection(
                context=bound_workspace.context,
                action_token=review_action.action_token,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_review_transfer_account_menu(
            event.conversation,
            selection,
        )

    async def _start_review_confirmation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None or self.settings is None:
            return None

        try:
            selection = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).start_category_selection(
                context=bound_workspace.context,
                action_token=review_action.action_token,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_review_category_menu(
            event.conversation,
            selection,
        )

    async def _change_review_category_page(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        category_page_selection: ChatReviewCategoryPageSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None or self.settings is None:
            return None

        try:
            selection = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).change_category_page(
                context=bound_workspace.context,
                selection=category_page_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_review_category_menu(
            event.conversation,
            selection,
        )

    async def _accept_review_suggestion(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None or self.settings is None:
            return None

        try:
            category_result = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).confirm_with_suggestion(
                context=bound_workspace.context,
                action_token=review_action.action_token,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return await self._show_review_category_result(event, bound_workspace, category_result)

    async def _complete_review_confirmation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        category_selection: ChatReviewCategorySelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None or self.settings is None:
            return None

        try:
            category_result = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).confirm_with_category(
                context=bound_workspace.context,
                selection=category_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return await self._show_review_category_result(event, bound_workspace, category_result)

    async def _show_review_category_result(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        category_result: ChatReviewCategoryActionResult,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        if category_result.property_selection is not None:
            return TelegramMainMenuPresenter.show_review_property_menu(
                event.conversation,
                category_result.property_selection,
            )

        if category_result.action_result is None:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                "Stored review action is invalid.",
            )

        if category_result.rule_suggestion is not None:
            return TelegramMainMenuPresenter.show_review_rule_suggestion(
                event.conversation,
                category_result.rule_suggestion,
            )

        return await self._show_next_review_item_after_success(
            event,
            bound_workspace,
            category_result.action_result.action_label,
            category_result.action_result.continuation_anchor,
        )

    async def _complete_review_property_confirmation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        property_selection: ChatReviewPropertySelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None or self.settings is None:
            return None

        try:
            category_result = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).confirm_with_property(
                context=bound_workspace.context,
                selection=property_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return await self._show_review_category_result(event, bound_workspace, category_result)

    async def _apply_review_rule_suggestion_action(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        if selection.action == ChatReviewRuleSuggestionCallbackData.CHOOSE_PATTERN_ACTION:
            return await self._start_review_rule_pattern_selection(
                event,
                bound_workspace,
                selection,
            )

        if selection.action == ChatReviewRuleSuggestionCallbackData.ENTER_PATTERN_ACTION:
            return await self._start_review_rule_pattern_input(
                event,
                bound_workspace,
                selection,
            )

        try:
            if selection.action == ChatReviewRuleSuggestionCallbackData.SAVE_ACTION:
                result = await ChatReviewRuleSuggestionService(self.session).save_suggestion(
                    context=bound_workspace.context,
                    selection=selection,
                )
            else:
                result = await ChatReviewRuleSuggestionService(self.session).skip_suggestion(
                    context=bound_workspace.context,
                    selection=selection,
                )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return await self._show_next_review_item_after_success(
            event,
            bound_workspace,
            result.action_label,
            result.continuation_anchor,
        )

    async def _start_review_rule_pattern_selection(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        try:
            pattern_selection = await ChatReviewRuleSuggestionService(
                self.session,
            ).start_pattern_selection(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_review_rule_pattern_menu(
            event.conversation,
            pattern_selection,
        )

    async def _start_review_rule_pattern_input(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        try:
            pattern_input = await ChatReviewRuleSuggestionService(
                self.session,
            ).start_manual_pattern_input(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_review_rule_pattern_input(
            event.conversation,
            pattern_input,
        )

    async def _answer_review_rule_pattern_message(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        try:
            result = await ChatReviewRuleSuggestionService(self.session).save_manual_pattern(
                context=bound_workspace.context,
                text=event.text,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )
        if result is None:
            return None

        return await self._show_next_review_item_after_success(
            event,
            bound_workspace,
            result.action_label,
            result.continuation_anchor,
        )

    async def _save_review_rule_pattern(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewRulePatternSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        try:
            result = await ChatReviewRuleSuggestionService(self.session).save_pattern_selection(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return await self._show_next_review_item_after_success(
            event,
            bound_workspace,
            result.action_label,
            result.continuation_anchor,
        )

    async def _complete_review_transfer(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        transfer_account_selection: ChatReviewTransferAccountSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None or self.settings is None:
            return None

        try:
            confirmation = await ChatReviewTransferService(
                self.session,
                self.settings,
            ).start_transfer_confirmation_with_account(
                context=bound_workspace.context,
                selection=transfer_account_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_review_transfer_confirmation(
            event.conversation,
            confirmation,
        )

    async def _complete_review_transfer_pair(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        transfer_pair_selection: ChatReviewTransferPairSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None or self.settings is None:
            return None

        try:
            confirmation = await ChatReviewTransferService(
                self.session,
                self.settings,
            ).start_transfer_confirmation_with_pair(
                context=bound_workspace.context,
                selection=transfer_pair_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramMainMenuPresenter.show_review_transfer_confirmation(
            event.conversation,
            confirmation,
        )

    async def _confirm_review_transfer(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        transfer_confirmation: ChatReviewTransferConfirmationSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None or self.settings is None:
            return None

        try:
            result = await ChatReviewTransferService(
                self.session,
                self.settings,
            ).confirm_transfer(
                context=bound_workspace.context,
                selection=transfer_confirmation,
            )
        except ChatReviewActionError as exc:
            return TelegramMainMenuPresenter.show_review_action_error(
                event.conversation,
                str(exc),
            )

        return await self._show_next_review_item_after_success(
            event,
            bound_workspace,
            result.action_label,
            result.continuation_anchor,
        )

    async def _notify_shared_feed_about_uploaded_document(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        document: UploadedDocument,
    ) -> None:
        if self.session is None or self.chat_provider is None:
            return

        await ChatSharedFeedNotificationService(
            session=self.session,
            settings=self.settings,
            provider_registry=ChatNotificationProviderRegistry(
                {event.provider: self.chat_provider}
            ),
        ).notify_import_document_uploaded(
            context=bound_workspace.context,
            document=document,
        )

    @staticmethod
    def _answer_unbound_callback_query(event: InboundChatEvent) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        match event.callback_data:
            case "main:menu":
                return TelegramMainMenuPresenter.show_welcome_menu(event.conversation)
            case "help:show":
                return TelegramMainMenuPresenter.show_help(event.conversation)
            case "link:start":
                return TelegramMainMenuPresenter.show_unlinked_account_notice(
                    event.conversation,
                    event.actor,
                )
            case _:
                return TelegramMainMenuPresenter.show_unlinked_account_notice(
                    event.conversation,
                    event.actor,
                )
