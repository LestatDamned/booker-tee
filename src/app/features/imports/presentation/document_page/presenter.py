from collections.abc import Mapping, Sequence
from typing import cast

from app.features.imports.application.documents.detail_view import (
    ImportDocumentDetailView,
    ImportParseAttemptView,
    ImportRawTransactionRow,
)
from app.features.imports.models import UploadedDocumentStatus
from app.features.imports.presentation.document_page.formatting import (
    account_type_label,
    document_status_label,
    int_value,
    money_tone,
    money_value,
    optional_int_value,
    parse_attempt_status_label,
    parser_label,
    raw_transaction_status_label,
    statement_type_label,
    string_value,
    table_row_count_label,
    table_rows,
    table_source_label,
    validation_status_label,
)
from app.features.imports.presentation.document_page.models import (
    DocumentDetailAccountVM,
    DocumentDetailActionVM,
    DocumentDetailColumnCandidateVM,
    DocumentDetailContinuationFieldVM,
    DocumentDetailMetricVM,
    DocumentDetailNextStepVM,
    DocumentDetailPageVM,
    DocumentDetailParseAttemptDebugVM,
    DocumentDetailParseAttemptVM,
    DocumentDetailRawTransactionVM,
    DocumentDetailTablePreviewVM,
    DocumentDetailTechnicalVM,
    DocumentDetailValidationVM,
    DocumentDetailValueVM,
    DocumentDetailWorkflowVM,
)
from app.features.imports.presentation.field_labels import (
    mapping_column_candidate_message,
    mapping_field_label,
)
from app.features.imports.presentation.mapping_suggestions import (
    MappingSuggestionVM,
    first_mapping_suggestion_from_raw,
)


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

    def primary_mapping_suggestion(
        self,
        preview: Mapping[str, object],
    ) -> MappingSuggestionVM | None:
        return first_mapping_suggestion_from_raw(preview.get("mapping_suggestions"))

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
            field = string_value(candidate.get("field"))
            column_number = int_value(candidate.get("column_index")) + 1
            header = string_value(candidate.get("header"))
            result.append(
                DocumentDetailColumnCandidateVM(
                    field=field,
                    column_number=column_number,
                    header=header,
                    message=mapping_column_candidate_message(
                        field=field,
                        column_number=column_number,
                        header=header,
                    ),
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
