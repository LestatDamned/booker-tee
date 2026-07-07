from datetime import date, datetime
from decimal import Decimal

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappedRow,
    UnknownStatementMappingPreview,
    UnknownStatementMappingWarning,
)
from app.features.imports.presentation.mapping.models import (
    MappingDocumentVM,
    MappingImportActionVM,
    MappingPreviewRowVM,
    MappingPreviewSummaryVM,
    MappingSummaryMetricVM,
    MappingWarningVM,
)

MAPPING_WARNING_MESSAGES = {
    "amount_and_split_columns": (
        "Выбрана единая сумма вместе со списанием/зачислением. Импорт использует единую сумму."
    ),
    "partial_debit_credit_columns": (
        "Выбрана только одна колонка списания/зачисления. Проверьте знак суммы перед импортом."
    ),
    "high_error_rate": (
        "В предпросмотре много строк с ошибками. "
        "Проверьте таблицу, первую строку данных и выбранные колонки."
    ),
    "no_valid_rows": "Нет валидных строк для импорта. Проверьте таблицу и выбранные колонки.",
    "balance_after_parse_errors": (
        "Часть остатков после операции не распознана. Импорт сохранит строки для проверки."
    ),
}


def mapping_warnings(
    preview: UnknownStatementMappingPreview | None,
) -> list[MappingWarningVM]:
    if preview is None:
        return []
    return [mapping_warning(warning) for warning in preview.warnings]


def mapping_warning(warning: UnknownStatementMappingWarning) -> MappingWarningVM:
    if warning.code == "duplicate_column_roles":
        message = (
            "Одна колонка выбрана для нескольких ролей. "
            f"Проверьте поля: {', '.join(warning.fields)}."
        )
    else:
        message = MAPPING_WARNING_MESSAGES.get(warning.code, warning.code)
    return MappingWarningVM(message=message, severity=warning.severity)


def mapping_import_action(
    *,
    document: MappingDocumentVM,
    preview: UnknownStatementMappingPreview | None,
    compatible_table_count: int,
) -> MappingImportActionVM | None:
    if preview is None or not preview.rows:
        return None
    label = "импортировать все страницы" if compatible_table_count > 1 else "импортировать строки"
    return MappingImportActionVM(
        form_action=document.import_url,
        label=label,
        icon="import",
    )


def mapping_preview_summary(
    preview: UnknownStatementMappingPreview | None,
) -> MappingPreviewSummaryVM | None:
    if preview is None:
        return None
    return MappingPreviewSummaryVM(
        metrics=[
            MappingSummaryMetricVM(
                label="строки",
                value=len(preview.rows),
                class_name="metric",
            ),
            MappingSummaryMetricVM(
                label="готово",
                value=preview.valid_count,
                class_name="metric metric-income",
            ),
            MappingSummaryMetricVM(
                label="ошибки",
                value=preview.error_count,
                class_name="metric metric-expense",
            ),
        ]
    )


def mapping_preview_rows(
    preview: UnknownStatementMappingPreview | None,
) -> list[MappingPreviewRowVM]:
    if preview is None:
        return []
    return [mapping_preview_row(row) for row in preview.rows]


def mapping_preview_row(row: UnknownStatementMappedRow) -> MappingPreviewRowVM:
    amount = row.amount
    description = row.description or row.description_raw
    return MappingPreviewRowVM(
        source_row_number=row.source_row_number,
        status=row.status,
        status_label=mapping_status_label(row.status),
        status_badge_class=f"badge-{row.status}",
        operation_date=mapping_date_label(
            row.operation_date,
            row.operation_date_raw,
        ),
        posting_date=mapping_date_label(
            row.posting_date,
            row.posting_date_raw,
        ),
        amount=str(amount or row.amount_raw),
        amount_class=mapping_amount_class(amount),
        currency=row.currency,
        description=str(description),
        error=row.error,
    )


def mapping_date_label(value: object, raw_value: object) -> str:
    formatted = mapping_date_ru(value)
    return formatted or str(raw_value)


def mapping_date_ru(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%d.%m.%Y")
    raw_value = str(value)
    try:
        return date.fromisoformat(raw_value).strftime("%d.%m.%Y")
    except ValueError:
        return raw_value


def mapping_amount_class(amount: object) -> str:
    if isinstance(amount, Decimal):
        if amount > 0:
            return "amount amount-income"
        if amount < 0:
            return "amount amount-expense"
    return "amount"


def mapping_status_label(status: str) -> str:
    labels = {
        "valid": "корректно",
        "error": "ошибка",
    }
    return labels.get(status, status)
