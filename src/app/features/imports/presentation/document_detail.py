from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from app.features.accounts.models import AccountType
from app.features.imports.mapping.dto import (
    ImportDocumentDetailView,
    ImportParseAttemptView,
    ImportRawTransactionRow,
)
from app.features.imports.models import (
    ParseAttemptStatus,
    RawTransactionStatus,
    UploadedDocumentStatus,
)


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


class DocumentDetailPresenter:
    def build(
        self,
        view: ImportDocumentDetailView,
        *,
        can_manage_imports: bool,
    ) -> DocumentDetailPageVM:
        validation = self.validation(view.validation)
        return DocumentDetailPageVM(
            title="Документ",
            status_label=document_status_label(view.status),
            document_name=view.original_filename,
            workflow=self.workflow(view, validation),
            next_step=self.next_step(view, validation, can_manage_imports=can_manage_imports),
            actions=self.actions(view, can_manage_imports=can_manage_imports),
            validation=validation,
            account=self.account(view),
            raw_transactions=self.raw_transactions(view.raw_transactions),
            parse_attempts=self.parse_attempts(view.parse_attempts),
            technical_details=self.technical_details(view),
        )

    def workflow(
        self,
        view: ImportDocumentDetailView,
        validation: DocumentDetailValidationVM | None,
    ) -> DocumentDetailWorkflowVM:
        if view.status == UploadedDocumentStatus.IMPORTED:
            return DocumentDetailWorkflowVM("done", "done", "skipped", "done", "done")
        if validation is not None and validation.needs_mapping:
            return DocumentDetailWorkflowVM("done", "done", "current", "pending", "pending")
        if view.raw_transactions:
            return DocumentDetailWorkflowVM("done", "done", "skipped", "current", "pending")
        if view.status == UploadedDocumentStatus.FAILED_TO_PARSE:
            return DocumentDetailWorkflowVM("done", "blocked", "pending", "pending", "pending")
        return DocumentDetailWorkflowVM("done", "current", "pending", "pending", "pending")

    def next_step(
        self,
        view: ImportDocumentDetailView,
        validation: DocumentDetailValidationVM | None,
        *,
        can_manage_imports: bool,
    ) -> DocumentDetailNextStepVM:
        if validation is not None and validation.needs_mapping and can_manage_imports:
            return DocumentDetailNextStepVM(
                title="Настройте колонки",
                message=(
                    "Файл выписки прочитан, но системе нужно понять, где дата, описание и сумма."
                ),
                primary_href=f"/imports/documents/{view.id}/mapping",
                primary_label="настроить колонки",
                primary_icon="settings",
            )
        if view.raw_transactions and can_manage_imports:
            return DocumentDetailNextStepVM(
                title="Проверьте строки",
                message=(
                    "Сырые строки извлечены. Подтвердите операции, отметьте переводы "
                    "и игнорируйте дубли."
                ),
                primary_href=f"/imports/documents/{view.id}/review",
                primary_label="открыть проверку",
                primary_icon="clipboard-check",
            )
        if view.status == UploadedDocumentStatus.FAILED_TO_PARSE and can_manage_imports:
            return DocumentDetailNextStepVM(
                title="Загрузите другую выписку",
                message=(
                    "Этот файл не удалось разобрать. Исходный документ сохранен, "
                    "можно попробовать другой файл."
                ),
                primary_href="/imports/upload",
                primary_label="загрузить заново",
                primary_icon="upload",
            )
        return DocumentDetailNextStepVM(
            title="Дождитесь извлечения",
            message="Когда строки появятся, Booker Tee предложит перейти к проверке.",
            primary_href="/imports",
            primary_label="к списку импортов",
            primary_icon="import",
        )

    def actions(
        self,
        view: ImportDocumentDetailView,
        *,
        can_manage_imports: bool,
    ) -> list[DocumentDetailActionVM]:
        if not can_manage_imports:
            return []
        document_url = f"/imports/documents/{view.id}"
        return [
            DocumentDetailActionVM(
                label="перепарсить",
                icon="refresh",
                action_url=f"{document_url}/reparse",
            ),
            DocumentDetailActionVM(
                label="игнорировать",
                icon="ignore",
                action_url=f"{document_url}/ignore",
            ),
            DocumentDetailActionVM(
                label="удалить",
                icon="trash",
                action_url=f"{document_url}/delete",
                tone="danger",
            ),
        ]

    def validation(self, validation: dict[str, object] | None) -> DocumentDetailValidationVM | None:
        if validation is None:
            return None
        status = string_value(validation.get("status"))
        if status == "needs_mapping":
            return DocumentDetailValidationVM(
                status=status,
                message=string_value(validation.get("message")),
                metrics=[
                    DocumentDetailMetricVM(
                        "банк",
                        string_value(validation.get("detected_bank_name"), fallback="не определен"),
                    ),
                    DocumentDetailMetricVM(
                        "тип",
                        statement_type_label(validation.get("detected_statement_type")),
                    ),
                    DocumentDetailMetricVM(
                        "извлечение",
                        "текстовый" if validation.get("text_based") else "нужен OCR",
                    ),
                    DocumentDetailMetricVM("таблицы", validation.get("table_count", "")),
                ],
                needs_mapping=True,
                table_previews=self.table_previews(validation),
            )
        return DocumentDetailValidationVM(
            status=status,
            message=string_value(validation.get("message")),
            metrics=[
                DocumentDetailMetricVM("строки", validation.get("extracted_count", "")),
                DocumentDetailMetricVM(
                    "приход",
                    money_value(
                        validation.get("calculated_total_inflow"),
                        validation.get("currency"),
                    ),
                    "income",
                ),
                DocumentDetailMetricVM(
                    "расход",
                    money_value(
                        validation.get("calculated_total_outflow"),
                        validation.get("currency"),
                    ),
                    "expense",
                ),
                DocumentDetailMetricVM("проверка", validation_status_label(status)),
            ],
            needs_mapping=False,
            table_previews=[],
        )

    def table_previews(
        self,
        validation: dict[str, object],
    ) -> list[DocumentDetailTablePreviewVM]:
        previews = validation.get("table_previews")
        if not isinstance(previews, list):
            return []
        return [
            self.table_preview(cast(Mapping[str, object], preview))
            for preview in previews
            if isinstance(preview, Mapping)
        ]

    def table_preview(
        self,
        preview: Mapping[str, object],
    ) -> DocumentDetailTablePreviewVM:
        is_continuation = bool(preview.get("is_continuation"))
        return DocumentDetailTablePreviewVM(
            meta=self.table_preview_meta(preview),
            rows=table_rows(preview.get("rows")),
            is_continuation=is_continuation,
            continuation_summary=self.continuation_summary(preview),
            continuation_fields=self.continuation_fields(preview),
            primary_mapping_suggestion=self.primary_mapping_suggestion(preview),
            column_candidates=[] if is_continuation else self.column_candidates(preview),
        )

    def table_preview_meta(self, preview: Mapping[str, object]) -> list[str]:
        page_number = int_value(preview.get("page_number"))
        table_index = int_value(preview.get("table_index"))
        row_count = int_value(preview.get("row_count"))
        column_count = int_value(preview.get("column_count"))
        return [
            f"страница {page_number}",
            table_source_label(preview.get("source_type"), table_index),
            table_row_count_label(
                row_count=row_count,
                preview_row_count=optional_int_value(preview.get("preview_row_count")),
            ),
            f"{column_count} колонок",
        ]

    def continuation_summary(self, preview: Mapping[str, object]) -> str:
        if not preview.get("is_continuation"):
            return ""
        page_number = int_value(preview.get("continued_from_page_number"))
        table_index = int_value(preview.get("continued_from_table_index"))
        return f"Продолжение таблицы · страница {page_number} · таблица {table_index + 1}"

    def continuation_fields(
        self,
        preview: Mapping[str, object],
    ) -> list[DocumentDetailContinuationFieldVM]:
        fields = preview.get("continuation_mapping_fields")
        if not isinstance(fields, list):
            return []
        result: list[DocumentDetailContinuationFieldVM] = []
        for field in fields:
            if not isinstance(field, Mapping):
                continue
            result.append(
                DocumentDetailContinuationFieldVM(
                    label=mapping_field_label(field.get("field")),
                    column_number=int_value(field.get("column_index")) + 1,
                )
            )
        return result

    def primary_mapping_suggestion(self, preview: Mapping[str, object]) -> object | None:
        suggestions = preview.get("mapping_suggestions")
        if not isinstance(suggestions, list) or not suggestions:
            return None
        return suggestions[0]

    def column_candidates(
        self,
        preview: Mapping[str, object],
    ) -> list[DocumentDetailColumnCandidateVM]:
        candidates = preview.get("column_candidates")
        if not isinstance(candidates, list):
            return []
        result: list[DocumentDetailColumnCandidateVM] = []
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            result.append(
                DocumentDetailColumnCandidateVM(
                    field=string_value(candidate.get("field")),
                    column_number=int_value(candidate.get("column_index")) + 1,
                    header=string_value(candidate.get("header")),
                )
            )
        return result

    def account(self, view: ImportDocumentDetailView) -> DocumentDetailAccountVM | None:
        if view.account is None:
            return None
        return DocumentDetailAccountVM(
            id=view.account.id,
            name=view.account.name,
            type_label=account_type_label(view.account.type),
            currency=view.account.currency,
        )

    def parse_attempts(
        self,
        attempts: Sequence[ImportParseAttemptView],
    ) -> list[DocumentDetailParseAttemptVM]:
        return [self.parse_attempt(attempt) for attempt in attempts]

    def parse_attempt(
        self,
        attempt: ImportParseAttemptView,
    ) -> DocumentDetailParseAttemptVM:
        return DocumentDetailParseAttemptVM(
            id=attempt.id,
            status_label=parse_attempt_status_label(attempt.status),
            parser_label=parser_label(attempt.parser_name, attempt.parser_version),
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            message=attempt.message,
        )

    def raw_transactions(
        self,
        rows: Sequence[ImportRawTransactionRow],
    ) -> list[DocumentDetailRawTransactionVM]:
        return [self.raw_transaction(row) for row in rows]

    def raw_transaction(
        self,
        row: ImportRawTransactionRow,
    ) -> DocumentDetailRawTransactionVM:
        return DocumentDetailRawTransactionVM(
            row_index=row.row_index,
            status_label=raw_transaction_status_label(row.status),
            status_css_class=f"badge-{row.status.value}",
            parse_attempt_id=row.parse_attempt_id,
            display_date=row.display_date,
            amount_label=row.amount if row.amount is not None else row.amount_raw or "",
            amount_tone=money_tone(row.amount),
            currency=row.currency or "",
            description=row.description,
            normalization_error=row.normalization_error,
        )

    def technical_details(self, view: ImportDocumentDetailView) -> DocumentDetailTechnicalVM:
        document_items = [
            DocumentDetailValueVM("ID", view.id),
            DocumentDetailValueVM("SHA-256", view.sha256_hash),
            DocumentDetailValueVM("Ключ хранения", view.storage_key),
        ]
        if view.account is not None:
            document_items.append(DocumentDetailValueVM("ID счета", view.account.id))
        return DocumentDetailTechnicalVM(
            document_items=document_items,
            parse_attempts=[self.parse_attempt_debug(attempt) for attempt in view.parse_attempts],
        )

    def parse_attempt_debug(
        self,
        attempt: ImportParseAttemptView,
    ) -> DocumentDetailParseAttemptDebugVM:
        status_label = parse_attempt_status_label(attempt.status)
        return DocumentDetailParseAttemptDebugVM(
            id=attempt.id,
            title=f"Попытка парсинга {status_label}",
            status_label=status_label,
            parser_label=parser_label(attempt.parser_name, attempt.parser_version),
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            error_message=attempt.error_message,
            validation_report=attempt.validation_report,
            raw_tables=attempt.raw_tables,
            raw_text_by_page=attempt.raw_text_by_page,
        )


def document_status_label(status: UploadedDocumentStatus) -> str:
    labels = {
        UploadedDocumentStatus.UPLOADED: "загружен",
        UploadedDocumentStatus.PENDING_PARSE: "ожидает парсинга",
        UploadedDocumentStatus.PARSING: "парсится",
        UploadedDocumentStatus.PARSED: "распознан",
        UploadedDocumentStatus.REQUIRES_REVIEW: "нужна проверка",
        UploadedDocumentStatus.FAILED_TO_PARSE: "ошибка парсинга",
        UploadedDocumentStatus.IMPORTED: "импортирован",
        UploadedDocumentStatus.IGNORED: "игнорируется",
    }
    return labels.get(status, status.value)


def validation_status_label(status: str) -> str:
    labels = {
        "valid": "сошлось",
        "mismatch": "не совпадает",
        "unavailable": "нет итогов",
        "needs_review": "нужна проверка",
        "needs_mapping": "нужна настройка",
        "failed": "ошибка",
        "failed_to_parse": "ошибка парсинга",
    }
    return labels.get(status, status)


def parse_attempt_status_label(status: ParseAttemptStatus) -> str:
    labels = {
        ParseAttemptStatus.RUNNING: "в процессе",
        ParseAttemptStatus.SUCCESS: "успешно",
        ParseAttemptStatus.REQUIRES_REVIEW: "нужна проверка",
        ParseAttemptStatus.FAILED: "ошибка",
    }
    return labels.get(status, status.value)


def raw_transaction_status_label(status: RawTransactionStatus) -> str:
    labels = {
        RawTransactionStatus.EXTRACTED: "извлечено",
        RawTransactionStatus.NORMALIZED: "нормализовано",
        RawTransactionStatus.SUGGESTED: "предложено",
        RawTransactionStatus.NEEDS_REVIEW: "нужна проверка",
        RawTransactionStatus.MATCHED: "связано",
        RawTransactionStatus.IGNORED: "игнор",
        RawTransactionStatus.DUPLICATE: "дубликат",
        RawTransactionStatus.POSSIBLE_DUPLICATE: "возможный дубль",
        RawTransactionStatus.FAILED: "ошибка",
        RawTransactionStatus.CONFIRMED: "подтверждено",
    }
    return labels.get(status, status.value)


def account_type_label(account_type: AccountType) -> str:
    labels = {
        AccountType.CASH: "наличные",
        AccountType.CARD: "карта",
        AccountType.DEPOSIT: "депозит",
        AccountType.CHECKING: "расчетный счет",
        AccountType.OTHER: "другое",
    }
    return labels.get(account_type, account_type.value)


def statement_type_label(value: object) -> str:
    labels = {
        "card_statement": "карточная выписка",
        "account_statement": "выписка по счету",
        "deposit_statement": "выписка по вкладу",
    }
    status = string_value(value)
    return labels.get(status, status)


def parser_label(parser_name: str, parser_version: str | None) -> str:
    if not parser_version:
        return parser_name
    return f"{parser_name} {parser_version}"


def table_source_label(source_type: object, table_index: int) -> str:
    if source_type == "text_candidate":
        return "из текста"
    return f"таблица {table_index + 1}"


def table_row_count_label(*, row_count: int, preview_row_count: int | None) -> str:
    if preview_row_count is not None and preview_row_count < row_count:
        return f"показано {preview_row_count} из {row_count} строк"
    return f"{row_count} строк"


def mapping_field_label(value: object) -> str:
    labels = {
        "operation_date": "дата",
        "posting_date": "дата проводки",
        "description": "описание",
        "amount": "сумма",
        "debit_amount": "списание",
        "credit_amount": "зачисление",
        "currency": "валюта",
        "balance_after": "остаток после операции",
    }
    field = string_value(value)
    return labels.get(field, field)


def table_rows(value: object) -> Sequence[Sequence[object]]:
    if not isinstance(value, list):
        return []
    return cast(Sequence[Sequence[object]], value)


def int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return 0


def optional_int_value(value: object) -> int | None:
    if value is None:
        return None
    return int_value(value)


def money_value(value: object, currency: object) -> str:
    if value in {None, ""}:
        return ""
    currency_label = string_value(currency)
    if not currency_label:
        return str(value)
    return f"{value} {currency_label}"


def money_tone(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value > 0:
        return "income"
    if value < 0:
        return "expense"
    return None


def string_value(value: object, *, fallback: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return fallback
    return str(value)
