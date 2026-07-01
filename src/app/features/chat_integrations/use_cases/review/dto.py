from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


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
    document_label: str | None = None


@dataclass(frozen=True)
class StartedChatReviewItem:
    action_token: str
    item: ChatReviewQueueItem


@dataclass(frozen=True)
class ChatReviewDocumentChoice:
    id: UUID
    label: str
    reviewable_count: int


@dataclass(frozen=True)
class StartedChatReviewDocumentSelection:
    action_token: str
    document_choices: tuple[ChatReviewDocumentChoice, ...]


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
