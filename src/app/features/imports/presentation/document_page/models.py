from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class DocumentDetailWorkflowVM:
    upload: str
    extract: str
    mapping: str
    review: str
    ledger: str


@dataclass(frozen=True)
class DocumentDetailNextStepVM:
    title: str
    message: str
    primary_href: str
    primary_label: str
    primary_icon: str


@dataclass(frozen=True)
class DocumentDetailActionVM:
    label: str
    icon: str
    action_url: str
    tone: str | None = None


@dataclass(frozen=True)
class DocumentDetailMetricVM:
    label: str
    value: object
    tone: str | None = None


@dataclass(frozen=True)
class DocumentDetailContinuationFieldVM:
    label: str
    column_number: int


@dataclass(frozen=True)
class DocumentDetailColumnCandidateVM:
    field: str
    column_number: int
    header: str


@dataclass(frozen=True)
class DocumentDetailTablePreviewVM:
    meta: Sequence[str]
    rows: Sequence[Sequence[object]]
    is_continuation: bool
    continuation_summary: str
    continuation_fields: Sequence[DocumentDetailContinuationFieldVM]
    primary_mapping_suggestion: object | None
    column_candidates: Sequence[DocumentDetailColumnCandidateVM]


@dataclass(frozen=True)
class DocumentDetailValidationVM:
    status: str
    message: str
    metrics: Sequence[DocumentDetailMetricVM]
    needs_mapping: bool
    table_previews: Sequence[DocumentDetailTablePreviewVM]


@dataclass(frozen=True)
class DocumentDetailAccountVM:
    id: UUID
    name: str
    type_label: str
    currency: str


@dataclass(frozen=True)
class DocumentDetailParseAttemptVM:
    id: UUID
    status_label: str
    parser_label: str
    started_at: datetime
    finished_at: datetime | None
    message: str


@dataclass(frozen=True)
class DocumentDetailRawTransactionVM:
    row_index: int
    status_label: str
    status_css_class: str
    parse_attempt_id: UUID
    display_date: object
    amount_label: object
    amount_tone: str | None
    currency: str
    description: str
    normalization_error: str


@dataclass(frozen=True)
class DocumentDetailValueVM:
    label: str
    value: object


@dataclass(frozen=True)
class DocumentDetailParseAttemptDebugVM:
    id: UUID
    title: str
    status_label: str
    parser_label: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    validation_report: dict[str, object] | None
    raw_tables: list[dict[str, object]] | None
    raw_text_by_page: list[str] | None


@dataclass(frozen=True)
class DocumentDetailTechnicalVM:
    document_items: Sequence[DocumentDetailValueVM]
    parse_attempts: Sequence[DocumentDetailParseAttemptDebugVM]


@dataclass(frozen=True)
class DocumentDetailPageVM:
    title: str
    status_label: str
    document_name: str
    workflow: DocumentDetailWorkflowVM
    next_step: DocumentDetailNextStepVM
    actions: Sequence[DocumentDetailActionVM]
    validation: DocumentDetailValidationVM | None
    account: DocumentDetailAccountVM | None
    raw_transactions: Sequence[DocumentDetailRawTransactionVM]
    parse_attempts: Sequence[DocumentDetailParseAttemptVM]
    technical_details: DocumentDetailTechnicalVM
