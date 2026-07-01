import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from secrets import token_urlsafe
from typing import cast
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.accounts.models import Account
from app.features.accounts.service import AccountService
from app.features.categories.models import Category, CategoryKind
from app.features.categories.service import CategoryService
from app.features.chat_integrations.commands import (
    BindChatIdentityCommand,
    ChatManualAccountSelection,
    ChatManualCategorySelection,
    ChatManualConfirmationSelection,
    ChatManualCorrectionCallbackData,
    ChatManualCorrectionSelection,
    ChatManualDateCallbackData,
    ChatManualDateSelection,
    ChatManualDescriptionSelection,
    ChatReviewActionConfirmationSelection,
    ChatReviewActionSelection,
    ChatReviewCallbackData,
    ChatReviewCategoryPageSelection,
    ChatReviewCategorySelection,
    ChatReviewNavigationSelection,
    ChatReviewPropertySelection,
    ChatReviewReturnSelection,
    ChatReviewRulePatternSelection,
    ChatReviewRuleSuggestionSelection,
    ChatReviewTransferAccountSelection,
    ChatReviewTransferConfirmationSelection,
    ChatReviewTransferPairSelection,
    ChatWorkspaceSelection,
)
from app.features.chat_integrations.errors import (
    ChatDocumentUploadError,
    ChatIdentityBindingError,
    ChatManualOperationError,
    ChatReviewActionError,
    ChatWorkspaceResolutionError,
    ChatWorkspaceSwitchError,
)
from app.features.chat_integrations.models import (
    ChatConversationFlow,
    ChatConversationState,
    ChatIdentityBinding,
)
from app.features.chat_integrations.providers.base import ChatDocumentDownloader
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.schemas import (
    ChatDocument,
    ChatDownloadedFile,
    InboundChatEvent,
)
from app.features.imports.application.documents.upload import StatementUploadUseCase
from app.features.imports.application.review.actions import (
    RawTransactionReviewCommand,
    RawTransactionReviewUseCase,
)
from app.features.imports.application.review.status import RawTransactionReviewStatusUseCase
from app.features.imports.errors import RawTransactionReviewError, UploadValidationError
from app.features.imports.infrastructure.extraction.resolver import SUPPORTED_STATEMENT_EXTENSIONS
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.imports.query_repository import ImportQueryRepository
from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
)
from app.features.ledger.application.transfer_suggestions import (
    TransferSuggestion,
    TransferSuggestionUseCase,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import OperationType
from app.features.ledger.service import LedgerPostingService
from app.features.properties.models import Property
from app.features.properties.service import PropertyService
from app.features.reports.service import ReportFilters, ReportsService
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.transaction_rules.domain.patterns import infer_rule_pattern
from app.features.transaction_rules.domain.text import clean_rule_pattern, normalized_text
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.users.repository import UserRepository
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.service import WorkspaceContext

TELEGRAM_DOCUMENT_DOWNLOAD_LIMIT_BYTES = 20 * 1024 * 1024
CHAT_DOCUMENT_UPLOAD_TTL = timedelta(minutes=30)
CHAT_REVIEW_ACTION_TTL = timedelta(minutes=30)
CHAT_DOCUMENT_UPLOAD_MAX_ACCOUNT_CHOICES = 8
CHAT_REVIEW_CATEGORY_PAGE_SIZE = 7
CHAT_REVIEW_PROPERTY_MAX_CHOICES = 8
CHAT_REVIEW_TRANSFER_ACCOUNT_MAX_CHOICES = 8
CHAT_REVIEW_TRANSFER_PAIR_MAX_CHOICES = 5
CHAT_MANUAL_OPERATION_TTL = timedelta(minutes=30)
CHAT_MANUAL_ACCOUNT_MAX_CHOICES = 8
CHAT_MANUAL_CATEGORY_MAX_CHOICES = 8
CHAT_MANUAL_OPERATION_FLOWS = (
    ChatConversationFlow.RECORD_EXPENSE,
    ChatConversationFlow.RECORD_INCOME,
    ChatConversationFlow.RECORD_TRANSFER,
)
CHAT_WORKSPACE_SWITCH_TTL = timedelta(minutes=10)


@dataclass(frozen=True)
class BoundChatWorkspace:
    identity_binding: ChatIdentityBinding
    context: WorkspaceContext


@dataclass(frozen=True)
class ChatWorkspaceChoice:
    id: UUID
    name: str
    is_current: bool


@dataclass(frozen=True)
class StartedChatWorkspaceSelection:
    action_token: str
    workspace_choices: tuple[ChatWorkspaceChoice, ...]


@dataclass(frozen=True)
class SelectedChatWorkspace:
    bound_workspace: BoundChatWorkspace


@dataclass(frozen=True)
class ChatPrivateStatus:
    documents_needing_attention: int
    raw_transactions_needing_attention: int

    @property
    def total_needing_attention(self) -> int:
        return self.documents_needing_attention + self.raw_transactions_needing_attention


@dataclass(frozen=True)
class ChatMonthlySummary:
    date_from: date
    date_to: date
    currency: str
    income: Decimal
    expense: Decimal
    profit: Decimal
    documents_needing_attention: int
    raw_transactions_needing_attention: int

    @property
    def total_needing_attention(self) -> int:
        return self.documents_needing_attention + self.raw_transactions_needing_attention


@dataclass(frozen=True)
class ChatCategorySummaryRow:
    category_name: str
    income: Decimal
    expense: Decimal
    profit: Decimal


@dataclass(frozen=True)
class ChatCategorySummary:
    date_from: date
    date_to: date
    currency: str
    rows: tuple[ChatCategorySummaryRow, ...]


@dataclass(frozen=True)
class ChatAccountBalanceRow:
    account_name: str
    currency: str
    balance: Decimal


@dataclass(frozen=True)
class ChatCurrencyBalanceTotal:
    currency: str
    balance: Decimal


@dataclass(frozen=True)
class ChatAccountBalances:
    rows: tuple[ChatAccountBalanceRow, ...]
    totals: tuple[ChatCurrencyBalanceTotal, ...]


@dataclass(frozen=True)
class ChatReviewQueueItem:
    document_id: UUID
    raw_transaction_id: UUID
    row_index: int
    status: str
    account_name: str | None
    operation_date: date | None
    amount: Decimal | None
    amount_raw: str | None
    currency: str | None
    description: str | None
    suggested_operation_type: str | None
    normalization_error: str | None
    suggested_category_id: UUID | None = None
    suggested_category_name: str | None = None
    document_row_count: int | None = None
    document_reviewable_count: int | None = None
    source_account_id: UUID | None = None


@dataclass(frozen=True)
class StartedChatReviewItem:
    action_token: str
    item: ChatReviewQueueItem


@dataclass(frozen=True)
class StartedChatReviewActionConfirmation:
    action_token: str
    item: ChatReviewQueueItem
    action: str
    action_label: str


@dataclass(frozen=True)
class ChatReviewNavigationBoundary:
    direction: str


@dataclass(frozen=True)
class ChatReviewCategoryChoice:
    id: UUID
    name: str


@dataclass(frozen=True)
class StartedChatReviewCategorySelection:
    action_token: str
    item: ChatReviewQueueItem
    category_choices: tuple[ChatReviewCategoryChoice, ...]
    page_index: int = 0
    page_count: int = 1
    page_start_index: int = 0


@dataclass(frozen=True)
class ChatReviewPropertyChoice:
    id: UUID | None
    name: str


@dataclass(frozen=True)
class StartedChatReviewPropertySelection:
    action_token: str
    item: ChatReviewQueueItem
    category_name: str
    property_choices: tuple[ChatReviewPropertyChoice, ...]


@dataclass(frozen=True)
class ChatReviewContinuationAnchor:
    document_id: UUID
    row_index: int


@dataclass(frozen=True)
class ChatReviewActionResult:
    action_label: str
    continuation_anchor: ChatReviewContinuationAnchor | None = None


@dataclass(frozen=True)
class StartedChatReviewRuleSuggestion:
    action_token: str
    action_label: str
    pattern: str
    alternative_patterns: tuple[str, ...]
    category_name: str


@dataclass(frozen=True)
class StartedChatReviewRulePatternSelection:
    action_token: str
    pattern_choices: tuple[str, ...]
    category_name: str


@dataclass(frozen=True)
class StartedChatReviewRulePatternInput:
    action_token: str
    category_name: str


@dataclass(frozen=True)
class ChatReviewCategoryActionResult:
    action_result: ChatReviewActionResult | None = None
    property_selection: StartedChatReviewPropertySelection | None = None
    rule_suggestion: StartedChatReviewRuleSuggestion | None = None


@dataclass(frozen=True)
class ChatReviewRuleActionResult:
    action_label: str
    continuation_anchor: ChatReviewContinuationAnchor | None = None


@dataclass(frozen=True)
class ChatReviewTransferAccountChoice:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class ChatReviewTransferPairChoice:
    id: UUID
    account_name: str | None
    operation_date: date | None
    amount: Decimal | None
    currency: str | None
    description: str | None
    day_distance: int


@dataclass(frozen=True)
class StartedChatReviewTransferSelection:
    action_token: str
    item: ChatReviewQueueItem
    pair_choices: tuple[ChatReviewTransferPairChoice, ...]
    account_choices: tuple[ChatReviewTransferAccountChoice, ...]


@dataclass(frozen=True)
class StartedChatReviewTransferConfirmation:
    action_token: str
    item: ChatReviewQueueItem
    target_label: str


@dataclass(frozen=True)
class ChatAccountChoice:
    name: str
    currency: str


@dataclass(frozen=True)
class StartedChatDocumentUpload:
    action_token: str
    account_choices: tuple[ChatAccountChoice, ...]


@dataclass(frozen=True)
class ChatManualAccountChoice:
    name: str
    currency: str


@dataclass(frozen=True)
class StartedChatManualAccountSelection:
    action_token: str
    operation_type: OperationType
    account_choices: tuple[ChatManualAccountChoice, ...]
    source_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualAmountInput:
    operation_type: OperationType
    account_name: str
    currency: str
    destination_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualDateSelection:
    action_token: str
    operation_type: OperationType
    amount: Decimal
    currency: str
    account_name: str
    destination_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualDateInput:
    operation_type: OperationType
    amount: Decimal
    currency: str
    account_name: str
    destination_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualDescriptionInput:
    action_token: str
    operation_type: OperationType
    amount: Decimal
    operation_date: date
    currency: str
    account_name: str
    category_name: str | None = None
    destination_account_name: str | None = None


@dataclass(frozen=True)
class ChatManualCategoryChoice:
    id: UUID | None
    name: str


@dataclass(frozen=True)
class StartedChatManualCategorySelection:
    action_token: str
    operation_type: OperationType
    amount: Decimal
    currency: str
    account_name: str
    category_choices: tuple[ChatManualCategoryChoice, ...]


@dataclass(frozen=True)
class ChatManualOperationConfirmation:
    action_token: str
    operation_type: OperationType
    amount: Decimal
    operation_date: date
    account_name: str
    currency: str
    category_name: str | None = None
    description: str | None = None
    destination_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualCorrectionSelection:
    action_token: str
    confirmation: ChatManualOperationConfirmation


@dataclass(frozen=True)
class ChatManualOperationResult:
    operation_id: UUID
    operation_type: OperationType
    amount: Decimal
    currency: str
    operation_date: date


class ChatActionTokenBuilder:
    @staticmethod
    def build_token() -> str:
        return token_urlsafe(12)


class ChatReviewUrlBuilder:
    @staticmethod
    def build_imports_url(settings: Settings | None) -> str | None:
        if settings is None or settings.public_base_url is None:
            return None
        return f"{settings.public_base_url.rstrip('/')}/imports"

    @staticmethod
    def build_document_review_url(
        settings: Settings | None,
        document_id: UUID,
    ) -> str | None:
        if settings is None or settings.public_base_url is None:
            return None
        base_url = settings.public_base_url.rstrip("/")
        return f"{base_url}/imports/documents/{document_id}/review"

    @staticmethod
    def build_raw_transaction_review_url(
        settings: Settings | None,
        *,
        document_id: UUID,
        raw_transaction_id: UUID,
    ) -> str | None:
        document_url = ChatReviewUrlBuilder.build_document_review_url(settings, document_id)
        if document_url is None:
            return None
        return f"{document_url}#raw-{raw_transaction_id}"


class ChatIdentityBinder:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def bind_chat_identity(self, command: BindChatIdentityCommand) -> ChatIdentityBinding:
        membership = await self.workspaces.get_active_membership(
            user_id=command.user_id,
            workspace_id=command.workspace_id,
        )
        if membership is None:
            raise ChatIdentityBindingError("User is not an active member of this workspace.")

        existing_binding = await self.chat_integrations.get_active_identity_binding(
            workspace_id=command.workspace_id,
            provider=command.provider,
            external_user_id=command.external_user_id,
        )
        if existing_binding is not None:
            if existing_binding.user_id != command.user_id:
                raise ChatIdentityBindingError("This chat identity is already linked.")
            existing_binding.display_name = command.display_name
            await self.session.commit()
            return existing_binding

        binding = await self.chat_integrations.create_identity_binding(
            workspace_id=command.workspace_id,
            user_id=command.user_id,
            provider=command.provider,
            external_user_id=command.external_user_id,
            display_name=command.display_name,
        )
        await self.session.commit()
        return binding


class WorkspaceChatResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def require_bound_workspace(self, event: InboundChatEvent) -> BoundChatWorkspace:
        if event.actor is None:
            raise ChatWorkspaceResolutionError("Chat event does not include an actor.")

        bindings = await self.chat_integrations.list_active_identity_bindings_for_external_user(
            provider=event.actor.provider,
            external_user_id=event.actor.external_user_id,
        )
        if not bindings:
            raise ChatWorkspaceResolutionError("Chat identity is not linked to Booker Tee.")
        if len(bindings) > 1:
            raise ChatWorkspaceResolutionError("Chat identity is linked to multiple workspaces.")

        binding = bindings[0]
        user = await self.users.get_active(binding.user_id)
        if user is None:
            raise ChatWorkspaceResolutionError("Linked Booker Tee user is not active.")

        membership = await self.workspaces.get_active_membership(
            user_id=binding.user_id,
            workspace_id=binding.workspace_id,
        )
        if membership is None:
            raise ChatWorkspaceResolutionError("Linked workspace membership is not active.")

        return BoundChatWorkspace(
            identity_binding=binding,
            context=WorkspaceContext(
                user=user,
                workspace=membership.workspace,
                membership=membership,
            ),
        )


class ChatWorkspaceSwitcher:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def start_workspace_selection(
        self,
        bound_workspace: BoundChatWorkspace,
    ) -> StartedChatWorkspaceSelection:
        workspaces = await self.workspaces.list_active_for_user(bound_workspace.context.user.id)
        if not workspaces:
            raise ChatWorkspaceSwitchError("Нет доступных рабочих пространств.")

        choices = tuple(
            ChatWorkspaceChoice(
                id=workspace.id,
                name=workspace.name,
                is_current=workspace.id == bound_workspace.context.workspace.id,
            )
            for workspace in workspaces
        )
        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=bound_workspace.context.workspace.id,
            user_id=bound_workspace.context.user.id,
            flow=ChatConversationFlow.MAIN_MENU,
            step="choose_workspace",
            action_token=action_token,
            state_payload={
                "workspace_ids": [str(choice.id) for choice in choices],
                "workspace_names": [choice.name for choice in choices],
            },
            expires_at=utc_now() + CHAT_WORKSPACE_SWITCH_TTL,
        )
        await self.session.commit()
        return StartedChatWorkspaceSelection(
            action_token=action_token,
            workspace_choices=choices,
        )

    async def select_workspace(
        self,
        *,
        bound_workspace: BoundChatWorkspace,
        selection: ChatWorkspaceSelection,
    ) -> SelectedChatWorkspace:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=bound_workspace.context.workspace.id,
            user_id=bound_workspace.context.user.id,
            flow=ChatConversationFlow.MAIN_MENU,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatWorkspaceSwitchError(
                "Выбор рабочего пространства устарел. Открой меню снова."
            )
        if state.step != "choose_workspace":
            raise ChatWorkspaceSwitchError("Сохраненный шаг выбора workspace некорректен.")

        workspace_id = ChatWorkspaceSwitchStateReader.read_workspace_id(
            state.state_payload,
            selection.workspace_index,
        )
        membership = await self.workspaces.get_active_membership(
            user_id=bound_workspace.context.user.id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise ChatWorkspaceSwitchError("Это рабочее пространство больше недоступно.")

        target_binding = await self._get_or_create_target_binding(
            bound_workspace=bound_workspace,
            workspace_id=workspace_id,
        )
        target_binding.is_active = True
        target_binding.display_name = bound_workspace.identity_binding.display_name
        await self.chat_integrations.deactivate_other_identity_bindings(
            keep_binding_id=target_binding.id,
            provider=bound_workspace.identity_binding.provider,
            external_user_id=bound_workspace.identity_binding.external_user_id,
        )
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return SelectedChatWorkspace(
            bound_workspace=BoundChatWorkspace(
                identity_binding=target_binding,
                context=WorkspaceContext(
                    user=bound_workspace.context.user,
                    workspace=membership.workspace,
                    membership=membership,
                ),
            )
        )

    async def _get_or_create_target_binding(
        self,
        *,
        bound_workspace: BoundChatWorkspace,
        workspace_id: UUID,
    ) -> ChatIdentityBinding:
        target_binding = await self.chat_integrations.get_identity_binding(
            workspace_id=workspace_id,
            provider=bound_workspace.identity_binding.provider,
            external_user_id=bound_workspace.identity_binding.external_user_id,
        )
        if target_binding is not None:
            if target_binding.user_id != bound_workspace.context.user.id:
                raise ChatWorkspaceSwitchError("Этот чат уже привязан к другому пользователю.")
            return target_binding

        return await self.chat_integrations.create_identity_binding(
            workspace_id=workspace_id,
            user_id=bound_workspace.context.user.id,
            provider=bound_workspace.identity_binding.provider,
            external_user_id=bound_workspace.identity_binding.external_user_id,
            display_name=bound_workspace.identity_binding.display_name,
        )


class ChatPrivateStatusReader:
    def __init__(self, session: AsyncSession) -> None:
        self.imports = ImportQueryRepository(session)

    async def read_status(self, context: WorkspaceContext) -> ChatPrivateStatus:
        raw_transactions_count = await self.imports.count_raw_transactions_needing_attention(
            context.workspace.id
        )
        return ChatPrivateStatus(
            documents_needing_attention=await self.imports.count_documents_needing_attention(
                context.workspace.id
            ),
            raw_transactions_needing_attention=raw_transactions_count,
        )


class ChatMonthlySummaryReader:
    def __init__(self, session: AsyncSession) -> None:
        self.imports = ImportQueryRepository(session)
        self.reports = ReportsService(session)

    async def read_current_month_summary(self, context: WorkspaceContext) -> ChatMonthlySummary:
        today = utc_now().date()
        return await self.read_month_summary(
            context=context,
            month_start=today.replace(day=1),
        )

    async def read_month_summary(
        self,
        *,
        context: WorkspaceContext,
        month_start: date,
    ) -> ChatMonthlySummary:
        date_from = month_start.replace(day=1)
        date_to = ChatMonthRange.next_month_start(date_from) - timedelta(days=1)
        overview = await self.reports.build_overview(
            workspace_id=context.workspace.id,
            filters=ReportFilters(date_from=date_from, date_to=date_to),
        )
        return ChatMonthlySummary(
            date_from=date_from,
            date_to=date_to,
            currency=getattr(context.workspace, "default_currency", "RUB"),
            income=overview.summary.income,
            expense=overview.summary.expense,
            profit=overview.summary.profit,
            documents_needing_attention=await self.imports.count_documents_needing_attention(
                context.workspace.id
            ),
            raw_transactions_needing_attention=(
                await self.imports.count_raw_transactions_needing_attention(context.workspace.id)
            ),
        )

    async def read_category_summary(
        self,
        *,
        context: WorkspaceContext,
        month_start: date,
    ) -> ChatCategorySummary:
        date_from = month_start.replace(day=1)
        date_to = ChatMonthRange.next_month_start(date_from) - timedelta(days=1)
        overview = await self.reports.build_overview(
            workspace_id=context.workspace.id,
            filters=ReportFilters(date_from=date_from, date_to=date_to),
        )
        return ChatCategorySummary(
            date_from=date_from,
            date_to=date_to,
            currency=getattr(context.workspace, "default_currency", "RUB"),
            rows=tuple(
                ChatCategorySummaryRow(
                    category_name=row.category_name,
                    income=row.income,
                    expense=row.expense,
                    profit=row.profit,
                )
                for row in overview.categories
            ),
        )


class ChatAccountBalanceReader:
    def __init__(self, session: AsyncSession) -> None:
        self.reports = ReportsService(session)

    async def read_account_balances(self, context: WorkspaceContext) -> ChatAccountBalances:
        overview = await self.reports.build_overview(
            workspace_id=context.workspace.id,
            filters=ReportFilters(),
        )
        rows = tuple(
            ChatAccountBalanceRow(
                account_name=balance_row.account.name,
                currency=balance_row.account.currency,
                balance=balance_row.balance,
            )
            for balance_row in overview.account_balances
        )
        return ChatAccountBalances(
            rows=rows,
            totals=ChatAccountBalanceTotalBuilder.build_totals(rows),
        )


class ChatAccountBalanceTotalBuilder:
    @staticmethod
    def build_totals(
        rows: tuple[ChatAccountBalanceRow, ...],
    ) -> tuple[ChatCurrencyBalanceTotal, ...]:
        grouped: dict[str, Decimal] = {}
        for row in rows:
            grouped[row.currency] = grouped.get(row.currency, Decimal("0.00")) + row.balance
        return tuple(
            ChatCurrencyBalanceTotal(currency=currency, balance=balance.quantize(Decimal("0.01")))
            for currency, balance in sorted(grouped.items())
        )


class ChatMonthRange:
    @staticmethod
    def next_month_start(month_start: date) -> date:
        if month_start.month == 12:
            return month_start.replace(year=month_start.year + 1, month=1)
        return month_start.replace(month=month_start.month + 1)


class ChatReviewQueueReader:
    def __init__(self, session: AsyncSession) -> None:
        self.imports = ImportQueryRepository(session)

    async def read_next_item(self, context: WorkspaceContext) -> ChatReviewQueueItem | None:
        raw_transaction = await self.imports.get_next_review_raw_transaction(context.workspace.id)
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
            return None

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


class ChatReviewQueueService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.review_queue = ChatReviewQueueReader(session)

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

    async def start_next_review_item_after(
        self,
        *,
        context: WorkspaceContext,
        anchor: ChatReviewContinuationAnchor,
    ) -> StartedChatReviewItem | None:
        item = await self.review_queue.read_next_item_after(context=context, anchor=anchor)
        if item is None:
            item = await self.review_queue.read_next_item(context)
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


class ChatReviewActionService:
    CONFIRMABLE_ACTIONS = {
        ChatReviewCallbackData.DUPLICATE_ACTION,
        ChatReviewCallbackData.IGNORE_ACTION,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.review_queue = ChatReviewQueueReader(session)
        self.review_status = RawTransactionReviewStatusUseCase(session)

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

        review_action = ChatReviewActionMapper.to_review_status_action(action)
        await ChatReviewStateClaimer.claim_once(self.chat_integrations, state)
        try:
            await self.review_status.set_status(
                workspace_id=context.workspace.id,
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                action=review_action,
            )
        except RawTransactionReviewError as exc:
            raise ChatReviewActionError(str(exc)) from exc

        await self.session.commit()
        return ChatReviewActionResult(
            action_label=ChatReviewActionMapper.to_action_label(action),
            continuation_anchor=ChatReviewContinuationAnchor(
                document_id=document_id,
                row_index=item.row_index,
            ),
        )


class ChatReviewConfirmationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.categories = CategoryService(session)
        self.properties = PropertyService(session)
        self.chat_integrations = ChatIntegrationRepository(session)
        self.review_queue = ChatReviewQueueReader(session)

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
        raw_transaction = await ImportQueryRepository(self.session).get_review_raw_transaction(
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
        document_id: UUID,
        raw_transaction_id: UUID,
        item: ChatReviewQueueItem,
        category_id: UUID,
        property_id: UUID | None,
    ) -> ChatReviewActionResult:
        try:
            await RawTransactionReviewUseCase(self.session, self.settings).handle(
                context=context,
                command=RawTransactionReviewCommand(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    action="confirm",
                    category_id=category_id,
                    property_id=property_id,
                ),
            )
        except (LedgerPostingError, RawTransactionReviewError, ValueError) as exc:
            raise ChatReviewActionError(str(exc)) from exc

        return ChatReviewActionResult(
            action_label="операция подтверждена",
            continuation_anchor=ChatReviewContinuationAnchor(
                document_id=document_id,
                row_index=item.row_index,
            ),
        )


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
        except TransactionRuleError as exc:
            raise ChatReviewActionError(str(exc)) from exc
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


class ChatReviewTransferService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.accounts = AccountService(session)
        self.chat_integrations = ChatIntegrationRepository(session)
        self.review_queue = ChatReviewQueueReader(session)
        self.transfer_suggestions = TransferSuggestionUseCase(session)

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
        if not pair_choices and not account_choices:
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
                "account_ids": [str(choice.id) for choice in account_choices],
                "account_labels": [
                    ChatReviewTransferLabelBuilder.account_label(choice)
                    for choice in account_choices
                ],
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
        return await self._start_transfer_confirmation(
            context=context,
            state=state,
            target_label=target_label,
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
        return await self._start_transfer_confirmation(
            context=context,
            state=state,
            target_label=target_label,
            counterparty_account_id=None,
            matched_raw_transaction_id=matched_raw_transaction_id,
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

        command = ChatReviewTransferCommandBuilder.build_command(state.state_payload)
        await ChatReviewStateClaimer.claim_once(self.chat_integrations, state)
        try:
            await RawTransactionReviewUseCase(self.session, self.settings).handle(
                context=context,
                command=command,
            )
        except (LedgerPostingError, RawTransactionReviewError, ValueError) as exc:
            raise ChatReviewActionError(str(exc)) from exc

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
        target_label: str,
        counterparty_account_id: UUID | None,
        matched_raw_transaction_id: UUID | None,
    ) -> StartedChatReviewTransferConfirmation:
        document_id = ChatReviewStateReader.read_document_id(state.state_payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(state.state_payload)
        item = await self.review_queue.read_item(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
        if item is None:
            raise ChatReviewActionError("Raw transaction row was not found.")

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
        )

    async def _build_transfer_pair_choices(
        self,
        *,
        context: WorkspaceContext,
        item: ChatReviewQueueItem,
    ) -> tuple[ChatReviewTransferPairChoice, ...]:
        raw_transaction = await ImportQueryRepository(self.session).get_review_raw_transaction(
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


class ChatManualOperationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountService(session)
        self.categories = CategoryService(session)
        self.chat_integrations = ChatIntegrationRepository(session)
        self.ledger = LedgerPostingService(session)

    async def start_income_expense(
        self,
        *,
        context: WorkspaceContext,
        operation_type: OperationType,
    ) -> StartedChatManualAccountSelection:
        if operation_type not in {OperationType.INCOME, OperationType.EXPENSE}:
            raise ChatManualOperationError("Manual operation must be income or expense.")

        accounts = await self.accounts.list_active_accounts(context.workspace.id)
        account_choices = ChatManualAccountChoiceBuilder.build_choices(accounts)
        if not account_choices:
            raise ChatManualOperationError("Сначала создай счет в Booker Tee.")

        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatManualOperationFlowMapper.to_flow(operation_type),
            step="choose_account",
            action_token=action_token,
            state_payload=ChatManualOperationPayloadBuilder.accounts_payload(accounts),
            expires_at=utc_now() + CHAT_MANUAL_OPERATION_TTL,
        )
        await self.session.commit()
        return StartedChatManualAccountSelection(
            action_token=action_token,
            operation_type=operation_type,
            account_choices=account_choices,
        )

    async def start_transfer(
        self,
        *,
        context: WorkspaceContext,
    ) -> StartedChatManualAccountSelection:
        accounts = await self.accounts.list_active_accounts(context.workspace.id)
        account_choices = ChatManualAccountChoiceBuilder.build_choices(accounts)
        if len(account_choices) < 2:
            raise ChatManualOperationError("Для перевода нужны минимум два активных счета.")

        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.RECORD_TRANSFER,
            step="choose_source_account",
            action_token=action_token,
            state_payload=ChatManualOperationPayloadBuilder.accounts_payload(accounts),
            expires_at=utc_now() + CHAT_MANUAL_OPERATION_TTL,
        )
        await self.session.commit()
        return StartedChatManualAccountSelection(
            action_token=action_token,
            operation_type=OperationType.TRANSFER,
            account_choices=account_choices,
        )

    async def select_account(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualAccountSelection,
    ) -> StartedChatManualAccountSelection | StartedChatManualAmountInput:
        state = await self._get_state_by_token(context, selection.action_token)
        if state.step == "choose_account":
            account = ChatManualOperationStateReader.read_account(
                state.state_payload,
                selection.account_index,
            )
            flow = state.flow
            await self._consume_and_create_state(
                context=context,
                state=state,
                flow=flow,
                step="enter_amount",
                payload={
                    "operation_type": ChatManualOperationFlowMapper.to_operation_type(flow).value,
                    "account_id": str(account.id),
                    "account_name": account.name,
                    "currency": account.currency,
                },
            )
            return StartedChatManualAmountInput(
                operation_type=ChatManualOperationFlowMapper.to_operation_type(flow),
                account_name=account.name,
                currency=account.currency,
            )

        if state.step == "choose_source_account":
            source_account = ChatManualOperationStateReader.read_account(
                state.state_payload,
                selection.account_index,
            )
            accounts = await self.accounts.list_active_accounts(context.workspace.id)
            destination_accounts = [
                account
                for account in accounts
                if account.id != source_account.id and account.currency == source_account.currency
            ]
            account_choices = ChatManualAccountChoiceBuilder.build_choices(destination_accounts)
            if not account_choices:
                raise ChatManualOperationError("Нет второго счета в той же валюте.")

            action_token = await self._consume_and_create_state(
                context=context,
                state=state,
                flow=ChatConversationFlow.RECORD_TRANSFER,
                step="choose_destination_account",
                payload={
                    "source_account_id": str(source_account.id),
                    "source_account_name": source_account.name,
                    "currency": source_account.currency,
                    **ChatManualOperationPayloadBuilder.accounts_payload(destination_accounts),
                },
            )
            return StartedChatManualAccountSelection(
                action_token=action_token,
                operation_type=OperationType.TRANSFER,
                account_choices=account_choices,
                source_account_name=source_account.name,
            )

        if state.step == "choose_destination_account":
            destination_account = ChatManualOperationStateReader.read_account(
                state.state_payload,
                selection.account_index,
            )
            source_account_name = ChatManualOperationStateReader.read_required_string(
                state.state_payload,
                "source_account_name",
            )
            source_account_id = ChatManualOperationStateReader.read_required_uuid(
                state.state_payload,
                "source_account_id",
            )
            currency = ChatManualOperationStateReader.read_required_string(
                state.state_payload,
                "currency",
            )
            await self._consume_and_create_state(
                context=context,
                state=state,
                flow=ChatConversationFlow.RECORD_TRANSFER,
                step="enter_amount",
                payload={
                    "operation_type": OperationType.TRANSFER.value,
                    "source_account_id": str(source_account_id),
                    "source_account_name": source_account_name,
                    "destination_account_id": str(destination_account.id),
                    "destination_account_name": destination_account.name,
                    "currency": currency,
                },
            )
            return StartedChatManualAmountInput(
                operation_type=OperationType.TRANSFER,
                account_name=source_account_name,
                currency=currency,
                destination_account_name=destination_account.name,
            )

        raise ChatManualOperationError("Stored manual operation step is invalid.")

    async def continue_from_text_input(
        self,
        *,
        context: WorkspaceContext,
        text: str | None,
    ) -> (
        ChatManualOperationConfirmation
        | StartedChatManualCategorySelection
        | StartedChatManualDateSelection
        | StartedChatManualDescriptionInput
        | None
    ):
        state = await self.chat_integrations.get_latest_active_conversation_state_for_flows(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flows=CHAT_MANUAL_OPERATION_FLOWS,
            now=utc_now(),
        )
        if state is None:
            return None

        if state.step == "enter_amount":
            return await self._start_date_selection_from_amount(
                context=context,
                state=state,
                amount_text=text,
            )

        if state.step == "enter_custom_date":
            return await self._continue_after_operation_date(
                context=context,
                state=state,
                operation_date=ChatManualDateParser.parse(text),
            )

        if state.step == "enter_description":
            return await self._start_confirmation_from_description(
                context=context,
                state=state,
                description_text=text,
            )

        return None

    async def select_date(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualDateSelection,
    ) -> (
        StartedChatManualCategorySelection
        | StartedChatManualDateInput
        | StartedChatManualDescriptionInput
    ):
        state = await self._get_state_by_token(context, selection.action_token)
        if state.step != "choose_date":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        if selection.date_action == ChatManualDateCallbackData.CUSTOM_ACTION:
            action_token = await self._consume_and_create_state(
                context=context,
                state=state,
                flow=state.flow,
                step="enter_custom_date",
                payload=state.state_payload,
            )
            return ChatManualOperationStateReader.read_date_input(
                state.state_payload,
                action_token=action_token,
            )

        return await self._continue_after_operation_date(
            context=context,
            state=state,
            operation_date=ChatManualDateResolver.resolve(selection.date_action),
        )

    async def _start_date_selection_from_amount(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        amount_text: str | None,
    ) -> StartedChatManualDateSelection:
        amount = ChatManualAmountParser.parse_positive_amount(amount_text)
        payload = {
            **state.state_payload,
            "amount": str(amount),
        }
        action_token = await self._consume_and_create_state(
            context=context,
            state=state,
            flow=state.flow,
            step="choose_date",
            payload=payload,
        )
        return ChatManualOperationStateReader.read_date_selection(
            payload,
            action_token=action_token,
        )

    async def _continue_after_operation_date(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        operation_date: date,
    ) -> StartedChatManualCategorySelection | StartedChatManualDescriptionInput:
        operation_type = ChatManualOperationFlowMapper.to_operation_type(state.flow)
        payload = {
            **state.state_payload,
            "operation_date": operation_date.isoformat(),
        }
        if operation_type != OperationType.TRANSFER:
            categories = await self.categories.list_or_seed_defaults(
                context.workspace.id,
                getattr(context.workspace, "type", None),
                include_inactive=False,
            )
            category_choices = ChatManualCategoryChoiceBuilder.build_choices(
                operation_type=operation_type,
                categories=categories,
            )
            if category_choices:
                action_token = await self._consume_and_create_state(
                    context=context,
                    state=state,
                    flow=state.flow,
                    step="choose_category",
                    payload={
                        **payload,
                        "category_ids": [
                            str(choice.id) if choice.id is not None else None
                            for choice in category_choices
                        ],
                        "category_names": [choice.name for choice in category_choices],
                    },
                )
                return StartedChatManualCategorySelection(
                    action_token=action_token,
                    operation_type=operation_type,
                    amount=ChatManualOperationStateReader.read_amount(payload),
                    currency=ChatManualOperationStateReader.read_required_string(
                        payload,
                        "currency",
                    ),
                    account_name=ChatManualOperationStateReader.read_required_string(
                        payload,
                        "account_name",
                    ),
                    category_choices=category_choices,
                )

        return await self._start_description_input(
            context=context,
            state=state,
            flow=state.flow,
            payload=payload,
        )

    async def select_category(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualCategorySelection,
    ) -> StartedChatManualDescriptionInput:
        state = await self._get_state_by_token(context, selection.action_token)
        if state.step != "choose_category":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        category = ChatManualOperationStateReader.read_category(
            state.state_payload,
            selection.category_index,
        )
        payload = {
            **state.state_payload,
            "category_id": str(category.id) if category.id is not None else None,
            "category_name": category.name,
        }
        return await self._start_description_input(
            context=context,
            state=state,
            flow=state.flow,
            payload=payload,
        )

    async def skip_description(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualDescriptionSelection,
    ) -> ChatManualOperationConfirmation:
        state = await self._get_state_by_token(context, selection.action_token)
        if state.step != "enter_description":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        return await self._start_confirmation_from_description(
            context=context,
            state=state,
            description_text=None,
        )

    async def select_correction(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualCorrectionSelection,
    ) -> (
        StartedChatManualAmountInput
        | StartedChatManualCategorySelection
        | StartedChatManualCorrectionSelection
        | StartedChatManualDateSelection
        | StartedChatManualDescriptionInput
    ):
        state = await self._get_state_by_token(context, selection.action_token)
        if state.step != "confirm":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        confirmation = ChatManualOperationStateReader.read_confirmation(
            state.state_payload,
            action_token=selection.action_token,
        )
        operation_type = confirmation.operation_type

        if selection.correction_action == ChatManualCorrectionCallbackData.MENU_ACTION:
            return StartedChatManualCorrectionSelection(
                action_token=selection.action_token,
                confirmation=confirmation,
            )

        if selection.correction_action == ChatManualCorrectionCallbackData.AMOUNT_ACTION:
            await self._consume_and_create_state(
                context=context,
                state=state,
                flow=state.flow,
                step="enter_amount",
                payload=state.state_payload,
            )
            return StartedChatManualAmountInput(
                operation_type=operation_type,
                account_name=confirmation.account_name,
                currency=confirmation.currency,
                destination_account_name=confirmation.destination_account_name,
            )

        if selection.correction_action == ChatManualCorrectionCallbackData.DATE_ACTION:
            action_token = await self._consume_and_create_state(
                context=context,
                state=state,
                flow=state.flow,
                step="choose_date",
                payload=state.state_payload,
            )
            return ChatManualOperationStateReader.read_date_selection(
                state.state_payload,
                action_token=action_token,
            )

        if selection.correction_action == ChatManualCorrectionCallbackData.CATEGORY_ACTION:
            if operation_type == OperationType.TRANSFER:
                raise ChatManualOperationError("У перевода нет категории.")
            categories = await self.categories.list_or_seed_defaults(
                context.workspace.id,
                getattr(context.workspace, "type", None),
                include_inactive=False,
            )
            category_choices = ChatManualCategoryChoiceBuilder.build_choices(
                operation_type=operation_type,
                categories=categories,
            )
            action_token = await self._consume_and_create_state(
                context=context,
                state=state,
                flow=state.flow,
                step="choose_category",
                payload={
                    **state.state_payload,
                    "category_ids": [
                        str(choice.id) if choice.id is not None else None
                        for choice in category_choices
                    ],
                    "category_names": [choice.name for choice in category_choices],
                },
            )
            return StartedChatManualCategorySelection(
                action_token=action_token,
                operation_type=operation_type,
                amount=confirmation.amount,
                currency=confirmation.currency,
                account_name=confirmation.account_name,
                category_choices=category_choices,
            )

        if selection.correction_action == ChatManualCorrectionCallbackData.DESCRIPTION_ACTION:
            return await self._start_description_input(
                context=context,
                state=state,
                flow=state.flow,
                payload=state.state_payload,
            )

        raise ChatManualOperationError("Выбери, что исправить, кнопкой.")

    async def _start_description_input(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        flow: ChatConversationFlow,
        payload: dict[str, object],
    ) -> StartedChatManualDescriptionInput:
        action_token = await self._consume_and_create_state(
            context=context,
            state=state,
            flow=flow,
            step="enter_description",
            payload=payload,
        )
        return ChatManualOperationStateReader.read_description_input(
            payload,
            action_token=action_token,
        )

    async def _start_confirmation_from_description(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        description_text: str | None,
    ) -> ChatManualOperationConfirmation:
        payload = {
            **state.state_payload,
            "description": ChatManualDescriptionCleaner.clean(description_text),
        }
        action_token = await self._consume_and_create_state(
            context=context,
            state=state,
            flow=state.flow,
            step="confirm",
            payload=payload,
        )
        return ChatManualOperationStateReader.read_confirmation(
            payload,
            action_token=action_token,
        )

    async def confirm(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualConfirmationSelection,
    ) -> ChatManualOperationResult:
        state = await self._get_state_by_token(context, selection.action_token)
        if state.step != "confirm":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        confirmation = ChatManualOperationStateReader.read_confirmation(
            state.state_payload,
            action_token=selection.action_token,
        )
        try:
            if confirmation.operation_type == OperationType.TRANSFER:
                operation = await self.ledger.create_manual_transfer(
                    context=context,
                    command=CreateManualTransferCommand(
                        source_account_id=ChatManualOperationStateReader.read_required_uuid(
                            state.state_payload,
                            "source_account_id",
                        ),
                        destination_account_id=ChatManualOperationStateReader.read_required_uuid(
                            state.state_payload,
                            "destination_account_id",
                        ),
                        amount=confirmation.amount,
                        operation_date=confirmation.operation_date,
                        description=confirmation.description,
                    ),
                )
            else:
                operation = await self.ledger.create_manual_income_expense(
                    context=context,
                    command=CreateManualIncomeExpenseCommand(
                        operation_type=confirmation.operation_type,
                        account_id=ChatManualOperationStateReader.read_required_uuid(
                            state.state_payload,
                            "account_id",
                        ),
                        amount=confirmation.amount,
                        operation_date=confirmation.operation_date,
                        description=confirmation.description,
                        category_id=ChatManualOperationStateReader.read_optional_uuid(
                            state.state_payload,
                            "category_id",
                        ),
                        property_id=None,
                    ),
                )
        except (LedgerPostingError, ValueError) as exc:
            raise ChatManualOperationError(str(exc)) from exc

        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return ChatManualOperationResult(
            operation_id=operation.id,
            operation_type=confirmation.operation_type,
            amount=confirmation.amount,
            currency=confirmation.currency,
            operation_date=confirmation.operation_date,
        )

    async def _get_state_by_token(
        self,
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

    async def _consume_and_create_state(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
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
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return action_token


@dataclass(frozen=True)
class ChatManualStoredAccount:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class ChatManualStoredCategory:
    id: UUID | None
    name: str


class ChatManualAccountChoiceBuilder:
    @staticmethod
    def build_choices(accounts: list[Account]) -> tuple[ChatManualAccountChoice, ...]:
        return tuple(
            ChatManualAccountChoice(name=account.name, currency=account.currency)
            for account in accounts[:CHAT_MANUAL_ACCOUNT_MAX_CHOICES]
        )


class ChatManualOperationPayloadBuilder:
    @staticmethod
    def accounts_payload(accounts: list[Account]) -> dict[str, object]:
        limited_accounts = accounts[:CHAT_MANUAL_ACCOUNT_MAX_CHOICES]
        return {
            "account_ids": [str(account.id) for account in limited_accounts],
            "account_names": [account.name for account in limited_accounts],
            "account_currencies": [account.currency for account in limited_accounts],
        }


class ChatManualCategoryChoiceBuilder:
    @staticmethod
    def build_choices(
        *,
        operation_type: OperationType,
        categories: list[Category],
    ) -> tuple[ChatManualCategoryChoice, ...]:
        accepted_kinds = ChatManualCategoryChoiceBuilder._accepted_kinds(operation_type)
        excluded_system_keys = {"transfer", "adjustment", "duplicate", "ignore"}
        choices = [ChatManualCategoryChoice(id=None, name="Без категории")]

        for category in categories:
            if not category.is_active:
                continue
            if category.kind not in accepted_kinds:
                continue
            if category.system_key in excluded_system_keys:
                continue
            if category.system_key == "uncategorized":
                continue
            choices.append(ChatManualCategoryChoice(id=category.id, name=category.name))
            if len(choices) >= CHAT_MANUAL_CATEGORY_MAX_CHOICES:
                break

        return tuple(choices)

    @staticmethod
    def _accepted_kinds(operation_type: OperationType) -> set[CategoryKind]:
        match operation_type:
            case OperationType.INCOME:
                return {CategoryKind.INCOME, CategoryKind.MIXED}
            case OperationType.EXPENSE:
                return {CategoryKind.EXPENSE, CategoryKind.MIXED}
            case _:
                return set()


class ChatManualOperationFlowMapper:
    @staticmethod
    def to_flow(operation_type: OperationType) -> ChatConversationFlow:
        match operation_type:
            case OperationType.EXPENSE:
                return ChatConversationFlow.RECORD_EXPENSE
            case OperationType.INCOME:
                return ChatConversationFlow.RECORD_INCOME
            case OperationType.TRANSFER:
                return ChatConversationFlow.RECORD_TRANSFER
            case _:
                raise ChatManualOperationError("Manual operation type is not supported.")

    @staticmethod
    def to_operation_type(flow: ChatConversationFlow) -> OperationType:
        match flow:
            case ChatConversationFlow.RECORD_EXPENSE:
                return OperationType.EXPENSE
            case ChatConversationFlow.RECORD_INCOME:
                return OperationType.INCOME
            case ChatConversationFlow.RECORD_TRANSFER:
                return OperationType.TRANSFER
            case _:
                raise ChatManualOperationError("Stored manual operation flow is invalid.")


class ChatManualOperationStateReader:
    @staticmethod
    def read_account(payload: dict[str, object], account_index: int) -> ChatManualStoredAccount:
        account_ids = ChatManualOperationStateReader._read_list(payload, "account_ids")
        account_names = ChatManualOperationStateReader._read_list(payload, "account_names")
        account_currencies = ChatManualOperationStateReader._read_list(
            payload,
            "account_currencies",
        )
        if (
            account_index < 0
            or account_index >= len(account_ids)
            or account_index >= len(account_names)
            or account_index >= len(account_currencies)
        ):
            raise ChatManualOperationError("Selected account is no longer available.")
        try:
            account_id = UUID(str(account_ids[account_index]))
        except ValueError as exc:
            raise ChatManualOperationError("Stored account id is invalid.") from exc

        name = account_names[account_index]
        currency = account_currencies[account_index]
        if not isinstance(name, str) or not isinstance(currency, str):
            raise ChatManualOperationError("Stored account is invalid.")
        return ChatManualStoredAccount(id=account_id, name=name, currency=currency)

    @staticmethod
    def read_category(
        payload: dict[str, object],
        category_index: int,
    ) -> ChatManualStoredCategory:
        category_ids = ChatManualOperationStateReader._read_list(payload, "category_ids")
        category_names = ChatManualOperationStateReader._read_list(payload, "category_names")
        if (
            category_index < 0
            or category_index >= len(category_ids)
            or category_index >= len(category_names)
        ):
            raise ChatManualOperationError("Selected category is no longer available.")

        category_id = category_ids[category_index]
        parsed_category_id: UUID | None = None
        if category_id is not None:
            try:
                parsed_category_id = UUID(str(category_id))
            except ValueError as exc:
                raise ChatManualOperationError("Stored category id is invalid.") from exc

        category_name = category_names[category_index]
        if not isinstance(category_name, str):
            raise ChatManualOperationError("Stored category is invalid.")
        return ChatManualStoredCategory(id=parsed_category_id, name=category_name)

    @staticmethod
    def read_date_selection(
        payload: dict[str, object],
        *,
        action_token: str,
    ) -> StartedChatManualDateSelection:
        operation_type = OperationType(
            ChatManualOperationStateReader.read_required_string(payload, "operation_type")
        )
        return StartedChatManualDateSelection(
            action_token=action_token,
            operation_type=operation_type,
            amount=ChatManualOperationStateReader.read_amount(payload),
            currency=ChatManualOperationStateReader.read_required_string(payload, "currency"),
            account_name=ChatManualOperationStateReader.read_account_name_for_operation(
                payload,
                operation_type,
            ),
            destination_account_name=ChatManualOperationStateReader.read_optional_string(
                payload,
                "destination_account_name",
            ),
        )

    @staticmethod
    def read_date_input(
        payload: dict[str, object],
        *,
        action_token: str,
    ) -> StartedChatManualDateInput:
        date_selection = ChatManualOperationStateReader.read_date_selection(
            payload,
            action_token=action_token,
        )
        return StartedChatManualDateInput(
            operation_type=date_selection.operation_type,
            amount=date_selection.amount,
            currency=date_selection.currency,
            account_name=date_selection.account_name,
            destination_account_name=date_selection.destination_account_name,
        )

    @staticmethod
    def read_description_input(
        payload: dict[str, object],
        *,
        action_token: str,
    ) -> StartedChatManualDescriptionInput:
        operation_type = OperationType(
            ChatManualOperationStateReader.read_required_string(payload, "operation_type")
        )
        operation_date = date.fromisoformat(
            ChatManualOperationStateReader.read_required_string(payload, "operation_date")
        )
        return StartedChatManualDescriptionInput(
            action_token=action_token,
            operation_type=operation_type,
            amount=ChatManualOperationStateReader.read_amount(payload),
            operation_date=operation_date,
            currency=ChatManualOperationStateReader.read_required_string(payload, "currency"),
            account_name=ChatManualOperationStateReader.read_account_name_for_operation(
                payload,
                operation_type,
            ),
            category_name=ChatManualOperationStateReader.read_optional_string(
                payload,
                "category_name",
            ),
            destination_account_name=ChatManualOperationStateReader.read_optional_string(
                payload,
                "destination_account_name",
            ),
        )

    @staticmethod
    def read_confirmation(
        payload: dict[str, object],
        *,
        action_token: str,
    ) -> ChatManualOperationConfirmation:
        operation_type = OperationType(
            ChatManualOperationStateReader.read_required_string(payload, "operation_type")
        )
        operation_date = date.fromisoformat(
            ChatManualOperationStateReader.read_required_string(payload, "operation_date")
        )
        amount = Decimal(ChatManualOperationStateReader.read_required_string(payload, "amount"))
        currency = ChatManualOperationStateReader.read_required_string(payload, "currency")

        if operation_type == OperationType.TRANSFER:
            return ChatManualOperationConfirmation(
                action_token=action_token,
                operation_type=operation_type,
                amount=amount,
                operation_date=operation_date,
                account_name=ChatManualOperationStateReader.read_required_string(
                    payload,
                    "source_account_name",
                ),
                currency=currency,
                destination_account_name=ChatManualOperationStateReader.read_required_string(
                    payload,
                    "destination_account_name",
                ),
                description=ChatManualOperationStateReader.read_optional_string(
                    payload,
                    "description",
                ),
            )

        return ChatManualOperationConfirmation(
            action_token=action_token,
            operation_type=operation_type,
            amount=amount,
            operation_date=operation_date,
            account_name=ChatManualOperationStateReader.read_required_string(
                payload,
                "account_name",
            ),
            currency=currency,
            category_name=ChatManualOperationStateReader.read_optional_string(
                payload,
                "category_name",
            ),
            description=ChatManualOperationStateReader.read_optional_string(
                payload,
                "description",
            ),
        )

    @staticmethod
    def read_account_name_for_operation(
        payload: dict[str, object],
        operation_type: OperationType,
    ) -> str:
        if operation_type == OperationType.TRANSFER:
            return ChatManualOperationStateReader.read_required_string(
                payload,
                "source_account_name",
            )
        return ChatManualOperationStateReader.read_required_string(payload, "account_name")

    @staticmethod
    def read_amount(payload: dict[str, object]) -> Decimal:
        return Decimal(ChatManualOperationStateReader.read_required_string(payload, "amount"))

    @staticmethod
    def read_optional_uuid(payload: dict[str, object], key: str) -> UUID | None:
        value = payload.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ChatManualOperationError("Stored manual operation id is invalid.")
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatManualOperationError("Stored manual operation id is invalid.") from exc

    @staticmethod
    def read_required_uuid(payload: dict[str, object], key: str) -> UUID:
        value = ChatManualOperationStateReader.read_required_string(payload, key)
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatManualOperationError("Stored manual operation id is invalid.") from exc

    @staticmethod
    def read_required_string(payload: dict[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ChatManualOperationError("Stored manual operation is invalid.")
        return value

    @staticmethod
    def read_optional_string(payload: dict[str, object], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        return value if isinstance(value, str) else None

    @staticmethod
    def _read_list(payload: dict[str, object], key: str) -> list[object]:
        value = payload.get(key)
        if not isinstance(value, list):
            raise ChatManualOperationError("Stored manual operation is invalid.")
        return list(value)


class ChatManualAmountParser:
    @staticmethod
    def parse_positive_amount(raw_value: str | None) -> Decimal:
        if raw_value is None:
            raise ChatManualOperationError("Напиши сумму числом.")

        cleaned = raw_value.casefold().strip()
        cleaned = re.sub(r"\b(rub|rur|руб\.?|р)\b", "", cleaned)
        cleaned = cleaned.replace("₽", "")
        cleaned = cleaned.replace("\u00a0", "")
        cleaned = cleaned.replace(" ", "")
        cleaned = cleaned.replace(",", ".")
        try:
            amount = Decimal(cleaned).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise ChatManualOperationError("Не понял сумму. Напиши, например: 1250") from exc

        if amount <= Decimal("0"):
            raise ChatManualOperationError("Сумма должна быть больше нуля.")
        return amount


class ChatManualDateResolver:
    @staticmethod
    def resolve(date_action: str) -> date:
        match date_action:
            case ChatManualDateCallbackData.TODAY_ACTION:
                return date.today()
            case ChatManualDateCallbackData.YESTERDAY_ACTION:
                return date.today() - timedelta(days=1)
            case _:
                raise ChatManualOperationError("Выбери дату кнопкой.")


class ChatManualDateParser:
    @staticmethod
    def parse(raw_value: str | None) -> date:
        if raw_value is None:
            raise ChatManualOperationError("Напиши дату.")

        cleaned = raw_value.strip()
        if cleaned.casefold() == "сегодня":
            return date.today()
        if cleaned.casefold() == "вчера":
            return date.today() - timedelta(days=1)

        for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(cleaned, date_format).date()
            except ValueError:
                continue

        try:
            parsed_without_year = datetime.strptime(cleaned, "%d.%m").date()
        except ValueError as exc:
            raise ChatManualOperationError("Не понял дату. Напиши, например: 30.06.2026") from exc

        today = date.today()
        return parsed_without_year.replace(year=today.year)


class ChatManualDescriptionCleaner:
    @staticmethod
    def clean(raw_value: str | None) -> str | None:
        if raw_value is None:
            return None

        cleaned = " ".join(raw_value.split())
        if not cleaned:
            return None
        return cleaned[:255]


class ChatReviewCategoryChoiceBuilder:
    @staticmethod
    def build_choices(
        *,
        item: ChatReviewQueueItem,
        categories: list[Category],
    ) -> tuple[ChatReviewCategoryChoice, ...]:
        accepted_kinds = ChatReviewCategoryChoiceBuilder._accepted_kinds(item)
        excluded_system_keys = {"transfer", "adjustment", "duplicate", "ignore"}
        choices: list[Category] = []
        chosen_ids: set[UUID] = set()

        suggested = next(
            (category for category in categories if category.id == item.suggested_category_id),
            None,
        )
        if suggested is not None and ChatReviewCategoryChoiceBuilder._is_available_category(
            suggested,
            accepted_kinds,
            excluded_system_keys,
        ):
            choices.append(suggested)
            chosen_ids.add(suggested.id)

        for category in categories:
            if category.id in chosen_ids:
                continue
            if not ChatReviewCategoryChoiceBuilder._is_available_category(
                category,
                accepted_kinds,
                excluded_system_keys,
            ):
                continue
            choices.append(category)
            chosen_ids.add(category.id)

        return tuple(
            ChatReviewCategoryChoice(id=category.id, name=category.name) for category in choices
        )

    @staticmethod
    def _accepted_kinds(item: ChatReviewQueueItem) -> set[CategoryKind]:
        if item.suggested_operation_type == "income" or (
            item.suggested_operation_type is None
            and item.amount is not None
            and item.amount > Decimal("0")
        ):
            return {CategoryKind.INCOME, CategoryKind.MIXED}
        if item.suggested_operation_type == "expense" or (
            item.suggested_operation_type is None
            and item.amount is not None
            and item.amount < Decimal("0")
        ):
            return {CategoryKind.EXPENSE, CategoryKind.MIXED}
        return {CategoryKind.INCOME, CategoryKind.EXPENSE, CategoryKind.MIXED}

    @staticmethod
    def _is_available_category(
        category: Category,
        accepted_kinds: set[CategoryKind],
        excluded_system_keys: set[str],
    ) -> bool:
        return (
            category.is_active
            and category.kind in accepted_kinds
            and category.system_key not in excluded_system_keys
        )


class ChatReviewCategoryPageBuilder:
    @staticmethod
    def build_selection(
        *,
        action_token: str,
        item: ChatReviewQueueItem,
        category_choices: tuple[ChatReviewCategoryChoice, ...],
        page_index: int,
    ) -> StartedChatReviewCategorySelection:
        page_count = max(
            1,
            (len(category_choices) + CHAT_REVIEW_CATEGORY_PAGE_SIZE - 1)
            // CHAT_REVIEW_CATEGORY_PAGE_SIZE,
        )
        normalized_page_index = min(max(page_index, 0), page_count - 1)
        page_start_index = normalized_page_index * CHAT_REVIEW_CATEGORY_PAGE_SIZE
        page_end_index = page_start_index + CHAT_REVIEW_CATEGORY_PAGE_SIZE
        return StartedChatReviewCategorySelection(
            action_token=action_token,
            item=item,
            category_choices=category_choices[page_start_index:page_end_index],
            page_index=normalized_page_index,
            page_count=page_count,
            page_start_index=page_start_index,
        )


class ChatReviewPropertyChoiceBuilder:
    @staticmethod
    def build_choices(properties: list[Property]) -> tuple[ChatReviewPropertyChoice, ...]:
        choices = [ChatReviewPropertyChoice(id=None, name="Без объекта")]
        choices.extend(
            ChatReviewPropertyChoice(
                id=property_.id,
                name=property_.short_name or property_.name,
            )
            for property_ in properties[:CHAT_REVIEW_PROPERTY_MAX_CHOICES]
        )
        return tuple(choices)


class ChatReviewRulePatternBuilder:
    GENERIC_TOKENS = {
        "ao",
        "банк",
        "карта",
        "карте",
        "операция",
        "оплата",
        "перевод",
        "платеж",
        "покупка",
        "средств",
        "списание",
        "транзакции",
        "экспобанк",
    }

    @classmethod
    def build_choices(cls, raw_transaction: RawTransaction) -> tuple[str, ...]:
        try:
            inferred_pattern = infer_rule_pattern(raw_transaction)
        except TransactionRuleError:
            return ()

        choices: list[str] = []
        for candidate in (inferred_pattern, *cls._split_pattern(inferred_pattern)):
            cleaned = cls._clean_candidate(candidate)
            if cleaned is None or cleaned in choices:
                continue
            choices.append(cleaned)
        return tuple(choices[:4])

    @classmethod
    def clean_manual_pattern(cls, value: str | None) -> str:
        cleaned = cls._clean_candidate(value or "")
        if cleaned is None:
            raise ChatReviewActionError(
                "Напиши более точный признак: минимум 3 буквы или цифры, без номера карты."
            )
        return cleaned

    @classmethod
    def _split_pattern(cls, pattern: str) -> tuple[str, ...]:
        candidates = re.split(r"[&*/|,;]+|\s+", pattern)
        return tuple(candidate for candidate in candidates if candidate)

    @classmethod
    def _clean_candidate(cls, candidate: str) -> str | None:
        try:
            cleaned = clean_rule_pattern(candidate)
        except TransactionRuleError:
            return None
        if len(cleaned) < 3 or len(cleaned) > 80:
            return None
        normalized = normalized_text(cleaned)
        if len(normalized) < 3:
            return None
        tokens = set(normalized.split())
        if not tokens or tokens.issubset(cls.GENERIC_TOKENS):
            return None
        if "xxxx" in cleaned.casefold():
            return None
        return cleaned


class ChatReviewTransferAccountChoiceBuilder:
    @staticmethod
    def build_choices(
        *,
        item: ChatReviewQueueItem,
        accounts: list[Account],
    ) -> tuple[ChatReviewTransferAccountChoice, ...]:
        choices: list[ChatReviewTransferAccountChoice] = []
        for account in accounts:
            if account.id == item.source_account_id:
                continue
            if item.currency is not None and account.currency != item.currency:
                continue
            choices.append(
                ChatReviewTransferAccountChoice(
                    id=account.id,
                    name=account.name,
                    currency=account.currency,
                )
            )
            if len(choices) >= CHAT_REVIEW_TRANSFER_ACCOUNT_MAX_CHOICES:
                break
        return tuple(choices)


class ChatReviewTransferPairChoiceBuilder:
    @staticmethod
    def build_choices(
        suggestions: list[TransferSuggestion],
    ) -> tuple[ChatReviewTransferPairChoice, ...]:
        choices: list[ChatReviewTransferPairChoice] = []
        for suggestion in suggestions[:CHAT_REVIEW_TRANSFER_PAIR_MAX_CHOICES]:
            raw_transaction = suggestion.raw_transaction
            choices.append(
                ChatReviewTransferPairChoice(
                    id=raw_transaction.id,
                    account_name=raw_transaction.account.name
                    if raw_transaction.account is not None
                    else None,
                    operation_date=raw_transaction.operation_date,
                    amount=raw_transaction.amount,
                    currency=raw_transaction.currency,
                    description=(
                        raw_transaction.description_normalized or raw_transaction.description_raw
                    ),
                    day_distance=suggestion.day_distance,
                )
            )
        return tuple(choices)


class ChatReviewTransferLabelBuilder:
    @staticmethod
    def account_label(choice: ChatReviewTransferAccountChoice) -> str:
        return f"{choice.name} / {choice.currency}"

    @staticmethod
    def pair_label(choice: ChatReviewTransferPairChoice) -> str:
        date_label = (
            choice.operation_date.strftime("%d.%m.%Y")
            if choice.operation_date is not None
            else "дата?"
        )
        amount_label = "сумма?"
        if choice.amount is not None:
            amount_label = f"{choice.amount:.2f} {choice.currency or ''}".strip()
        account_label = choice.account_name or "счет?"
        return f"Пара: {account_label} / {date_label} / {amount_label}"


class ChatReviewTransferCommandBuilder:
    @staticmethod
    def build_command(payload: dict[str, object]) -> RawTransactionReviewCommand:
        document_id = ChatReviewStateReader.read_document_id(payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(payload)
        counterparty_account_id = ChatReviewStateReader.read_confirm_transfer_account_id(payload)
        if counterparty_account_id is not None:
            return RawTransactionReviewCommand(
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                action="transfer",
                counterparty_account_id=counterparty_account_id,
            )

        matched_raw_transaction_id = (
            ChatReviewStateReader.read_confirm_transfer_matched_raw_transaction_id(payload)
        )
        if matched_raw_transaction_id is not None:
            return RawTransactionReviewCommand(
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                action="transfer",
                matched_raw_transaction_id=matched_raw_transaction_id,
            )

        raise ChatReviewActionError("Stored transfer action is invalid.")


class ChatReviewActionMapper:
    @staticmethod
    def to_review_status_action(callback_action: str) -> str:
        match callback_action:
            case "dup":
                return "duplicate"
            case "ign":
                return "ignore"
            case "uniq":
                return "mark_unique"
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


class ChatReviewStateClaimer:
    @staticmethod
    async def claim_once(
        chat_integrations: ChatIntegrationRepository,
        state: ChatConversationState,
    ) -> None:
        claimed = await chat_integrations.try_consume_active_conversation_state(
            state,
            consumed_at=utc_now(),
        )
        if not claimed:
            raise ChatReviewActionError("Stored review action is invalid.")


class ChatWorkspaceSwitchStateReader:
    @staticmethod
    def read_workspace_id(payload: dict[str, object], workspace_index: int) -> UUID:
        if workspace_index < 0:
            raise ChatWorkspaceSwitchError("Выбранное рабочее пространство не найдено.")
        workspace_ids = ChatWorkspaceSwitchStateReader._read_list(payload, "workspace_ids")
        try:
            value = workspace_ids[workspace_index]
        except IndexError as exc:
            raise ChatWorkspaceSwitchError("Выбранное рабочее пространство не найдено.") from exc
        if not isinstance(value, str):
            raise ChatWorkspaceSwitchError("Сохраненный выбор workspace некорректен.")
        return UUID(value)

    @staticmethod
    def _read_list(payload: dict[str, object], key: str) -> list[object]:
        value = payload.get(key)
        if not isinstance(value, list):
            raise ChatWorkspaceSwitchError("Сохраненный выбор workspace некорректен.")
        return cast(list[object], value)


class ChatReviewStateReader:
    @staticmethod
    def read_document_id(payload: dict[str, object]) -> UUID:
        return ChatReviewStateReader._read_uuid(payload, "document_id")

    @staticmethod
    def read_raw_transaction_id(payload: dict[str, object]) -> UUID:
        return ChatReviewStateReader._read_uuid(payload, "raw_transaction_id")

    @staticmethod
    def read_category_id(payload: dict[str, object], category_index: int) -> UUID:
        category_ids = payload.get("category_ids")
        if not isinstance(category_ids, list):
            raise ChatReviewActionError("Stored review action does not include categories.")
        if category_index < 0 or category_index >= len(category_ids):
            raise ChatReviewActionError("Selected category is no longer available.")

        category_id = category_ids[category_index]
        if not isinstance(category_id, str):
            raise ChatReviewActionError("Stored category id is invalid.")
        try:
            return UUID(category_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored category id is invalid.") from exc

    @staticmethod
    def read_category_name(payload: dict[str, object], category_index: int) -> str:
        category_names = payload.get("category_names")
        if not isinstance(category_names, list):
            return "выбранная категория"
        if category_index < 0 or category_index >= len(category_names):
            return "выбранная категория"
        category_name = category_names[category_index]
        return category_name if isinstance(category_name, str) else "выбранная категория"

    @staticmethod
    def read_category_choices(
        payload: dict[str, object],
    ) -> tuple[ChatReviewCategoryChoice, ...]:
        category_ids = payload.get("category_ids")
        category_names = payload.get("category_names")
        if not isinstance(category_ids, list) or not isinstance(category_names, list):
            raise ChatReviewActionError("Stored review action does not include categories.")
        if len(category_ids) != len(category_names):
            raise ChatReviewActionError("Stored review categories are invalid.")

        choices: list[ChatReviewCategoryChoice] = []
        for category_id, category_name in zip(category_ids, category_names, strict=True):
            if not isinstance(category_id, str) or not isinstance(category_name, str):
                raise ChatReviewActionError("Stored review categories are invalid.")
            try:
                parsed_category_id = UUID(category_id)
            except ValueError as exc:
                raise ChatReviewActionError("Stored category id is invalid.") from exc
            choices.append(ChatReviewCategoryChoice(id=parsed_category_id, name=category_name))
        return tuple(choices)

    @staticmethod
    def read_confirm_category_id(payload: dict[str, object]) -> UUID:
        return ChatReviewStateReader._read_uuid(payload, "category_id")

    @staticmethod
    def read_confirm_category_name(payload: dict[str, object]) -> str:
        category_name = payload.get("category_name")
        return category_name if isinstance(category_name, str) else "выбранная категория"

    @staticmethod
    def read_offer_rule_suggestion(payload: dict[str, object]) -> bool:
        return payload.get("offer_rule_suggestion") is True

    @staticmethod
    def read_optional_property_id(payload: dict[str, object]) -> UUID | None:
        property_id = payload.get("property_id")
        if property_id is None:
            return None
        if not isinstance(property_id, str):
            raise ChatReviewActionError("Stored property id is invalid.")
        try:
            return UUID(property_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored property id is invalid.") from exc

    @staticmethod
    def read_rule_patterns(payload: dict[str, object]) -> tuple[str, ...]:
        patterns = payload.get("patterns")
        if not isinstance(patterns, list):
            raise ChatReviewActionError("Stored rule suggestion is invalid.")
        clean_patterns: list[str] = []
        for pattern in patterns:
            if not isinstance(pattern, str):
                raise ChatReviewActionError("Stored rule suggestion is invalid.")
            clean_patterns.append(pattern)
        if not clean_patterns:
            raise ChatReviewActionError("Stored rule suggestion is invalid.")
        return tuple(clean_patterns)

    @staticmethod
    def read_rule_pattern(payload: dict[str, object], pattern_index: int) -> str:
        patterns = ChatReviewStateReader.read_rule_patterns(payload)
        if pattern_index < 0 or pattern_index >= len(patterns):
            raise ChatReviewActionError("Selected rule pattern is no longer available.")
        return patterns[pattern_index]

    @staticmethod
    def read_review_action(payload: dict[str, object]) -> str:
        review_action = payload.get("review_action")
        if not isinstance(review_action, str):
            raise ChatReviewActionError("Stored review action is invalid.")
        if review_action not in {
            ChatReviewCallbackData.DUPLICATE_ACTION,
            ChatReviewCallbackData.IGNORE_ACTION,
            ChatReviewCallbackData.MARK_UNIQUE_ACTION,
        }:
            raise ChatReviewActionError("Stored review action is invalid.")
        return review_action

    @staticmethod
    def read_property_id(payload: dict[str, object], property_index: int) -> UUID | None:
        property_ids = payload.get("property_ids")
        if not isinstance(property_ids, list):
            raise ChatReviewActionError("Stored review action does not include properties.")
        if property_index < 0 or property_index >= len(property_ids):
            raise ChatReviewActionError("Selected property is no longer available.")

        property_id = property_ids[property_index]
        if property_id is None:
            return None
        if not isinstance(property_id, str):
            raise ChatReviewActionError("Stored property id is invalid.")
        try:
            return UUID(property_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored property id is invalid.") from exc

    @staticmethod
    def read_transfer_account_id(payload: dict[str, object], account_index: int) -> UUID:
        account_ids = payload.get("account_ids")
        if not isinstance(account_ids, list):
            raise ChatReviewActionError("Stored review action does not include accounts.")
        if account_index < 0 or account_index >= len(account_ids):
            raise ChatReviewActionError("Selected account is no longer available.")

        account_id = account_ids[account_index]
        if not isinstance(account_id, str):
            raise ChatReviewActionError("Stored account id is invalid.")
        try:
            return UUID(account_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored account id is invalid.") from exc

    @staticmethod
    def read_transfer_account_label(payload: dict[str, object], account_index: int) -> str:
        return ChatReviewStateReader._read_label(
            payload=payload,
            key="account_labels",
            index=account_index,
            fallback="выбранный счет",
        )

    @staticmethod
    def read_matched_raw_transaction_id(payload: dict[str, object], pair_index: int) -> UUID:
        raw_transaction_ids = payload.get("matched_raw_transaction_ids")
        if not isinstance(raw_transaction_ids, list):
            raise ChatReviewActionError("Stored review action does not include matched rows.")
        if pair_index < 0 or pair_index >= len(raw_transaction_ids):
            raise ChatReviewActionError("Selected matched row is no longer available.")

        raw_transaction_id = raw_transaction_ids[pair_index]
        if not isinstance(raw_transaction_id, str):
            raise ChatReviewActionError("Stored matched row id is invalid.")
        try:
            return UUID(raw_transaction_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored matched row id is invalid.") from exc

    @staticmethod
    def read_matched_raw_transaction_label(payload: dict[str, object], pair_index: int) -> str:
        return ChatReviewStateReader._read_label(
            payload=payload,
            key="matched_raw_transaction_labels",
            index=pair_index,
            fallback="выбранная парная строка",
        )

    @staticmethod
    def read_confirm_transfer_account_id(payload: dict[str, object]) -> UUID | None:
        value = payload.get("counterparty_account_id")
        if value is None:
            return None
        if not isinstance(value, str):
            raise ChatReviewActionError("Stored transfer account is invalid.")
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatReviewActionError("Stored transfer account is invalid.") from exc

    @staticmethod
    def read_confirm_transfer_matched_raw_transaction_id(
        payload: dict[str, object],
    ) -> UUID | None:
        value = payload.get("matched_raw_transaction_id")
        if value is None:
            return None
        if not isinstance(value, str):
            raise ChatReviewActionError("Stored matched row is invalid.")
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatReviewActionError("Stored matched row is invalid.") from exc

    @staticmethod
    def read_transfer_action_label(payload: dict[str, object]) -> str:
        action_label = payload.get("action_label")
        if not isinstance(action_label, str):
            return "перевод подтвержден"
        return action_label

    @staticmethod
    def _read_label(
        *,
        payload: dict[str, object],
        key: str,
        index: int,
        fallback: str,
    ) -> str:
        labels = payload.get(key)
        if not isinstance(labels, list):
            return fallback
        if index < 0 or index >= len(labels):
            return fallback
        label = labels[index]
        return label if isinstance(label, str) else fallback

    @staticmethod
    def _read_uuid(payload: dict[str, object], key: str) -> UUID:
        value = payload.get(key)
        if not isinstance(value, str):
            raise ChatReviewActionError("Stored review action is invalid.")
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatReviewActionError("Stored review action is invalid.") from exc


class ChatDocumentUploadService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        downloader: ChatDocumentDownloader,
    ) -> None:
        self.session = session
        self.settings = settings
        self.downloader = downloader
        self.accounts = AccountService(session)
        self.chat_integrations = ChatIntegrationRepository(session)

    async def start_document_upload(
        self,
        *,
        context: WorkspaceContext,
        document: ChatDocument | None,
    ) -> StartedChatDocumentUpload:
        if document is None:
            raise ChatDocumentUploadError("Document event does not include a file.")

        ChatDocumentUploadPolicy.ensure_supported_statement(document)
        accounts = await self.accounts.list_active_accounts(context.workspace.id)
        if not accounts:
            raise ChatDocumentUploadError("Create an account before uploading statements.")

        account_choices = tuple(
            ChatAccountChoice(name=account.name, currency=account.currency)
            for account in accounts[:CHAT_DOCUMENT_UPLOAD_MAX_ACCOUNT_CHOICES]
        )
        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.UPLOAD_DOCUMENT,
            step="choose_account",
            action_token=action_token,
            state_payload={
                "file_id": document.file_id,
                "file_unique_id": document.file_unique_id,
                "file_name": document.file_name,
                "mime_type": document.mime_type,
                "file_size": document.file_size,
                "account_ids": [str(account.id) for account in accounts],
            },
            expires_at=utc_now() + CHAT_DOCUMENT_UPLOAD_TTL,
        )
        await self.session.commit()
        return StartedChatDocumentUpload(
            action_token=action_token,
            account_choices=account_choices,
        )

    async def complete_document_upload(
        self,
        *,
        context: WorkspaceContext,
        action_token: str,
        account_index: int,
    ) -> UploadedDocument:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.UPLOAD_DOCUMENT,
            action_token=action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatDocumentUploadError("This upload action expired. Send the statement again.")

        document = ChatDocumentUploadStateReader.read_document(state.state_payload)
        account_id = ChatDocumentUploadStateReader.read_account_id(
            state.state_payload,
            account_index,
        )
        downloaded_file = await self.downloader.download_document(document)
        upload_file = ChatDownloadedFileUploadAdapter.to_upload_file(downloaded_file)

        try:
            uploaded_document = await StatementUploadUseCase(
                self.session,
                self.settings,
            ).upload_and_extract_statement(
                context=context,
                upload_file=upload_file,
                account_id=account_id,
            )
        except UploadValidationError as exc:
            raise ChatDocumentUploadError(str(exc)) from exc
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return uploaded_document


class ChatDocumentUploadPolicy:
    @staticmethod
    def ensure_supported_statement(document: ChatDocument) -> None:
        if (
            document.file_size is not None
            and document.file_size > TELEGRAM_DOCUMENT_DOWNLOAD_LIMIT_BYTES
        ):
            raise ChatDocumentUploadError("Telegram statement files must be 20 MB or smaller.")

        filename = document.file_name or ""
        extension = Path(filename).suffix.casefold()
        if extension not in SUPPORTED_STATEMENT_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_STATEMENT_EXTENSIONS))
            raise ChatDocumentUploadError(f"Only {allowed} statement files can be uploaded.")


class ChatDocumentUploadStateReader:
    @staticmethod
    def read_document(payload: dict[str, object]) -> ChatDocument:
        file_id = payload.get("file_id")
        if not isinstance(file_id, str) or not file_id:
            raise ChatDocumentUploadError("Stored upload state does not include a Telegram file.")

        return ChatDocument(
            file_id=file_id,
            file_unique_id=ChatDocumentUploadStateReader._optional_string(
                payload.get("file_unique_id")
            ),
            file_name=ChatDocumentUploadStateReader._optional_string(payload.get("file_name")),
            mime_type=ChatDocumentUploadStateReader._optional_string(payload.get("mime_type")),
            file_size=ChatDocumentUploadStateReader._optional_int(payload.get("file_size")),
        )

    @staticmethod
    def read_account_id(payload: dict[str, object], account_index: int) -> UUID:
        account_ids = payload.get("account_ids")
        if not isinstance(account_ids, list):
            raise ChatDocumentUploadError("Stored upload state does not include accounts.")
        if account_index < 0 or account_index >= len(account_ids):
            raise ChatDocumentUploadError("Selected account is no longer available.")

        account_id = account_ids[account_index]
        if not isinstance(account_id, str):
            raise ChatDocumentUploadError("Stored account id is invalid.")
        try:
            return UUID(account_id)
        except ValueError as exc:
            raise ChatDocumentUploadError("Stored account id is invalid.") from exc

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return value if isinstance(value, int) else None


class ChatDownloadedFileUploadAdapter:
    @staticmethod
    def to_upload_file(downloaded_file: ChatDownloadedFile) -> UploadFile:
        headers = Headers({"content-type": downloaded_file.content_type or ""})
        return UploadFile(
            BytesIO(downloaded_file.file_bytes),
            size=len(downloaded_file.file_bytes),
            filename=downloaded_file.filename,
            headers=headers,
        )
