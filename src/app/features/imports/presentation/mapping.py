from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import cast

from app.features.imports.application.documents.detail_view import ImportDocumentDetailView
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappedRow,
    UnknownStatementMappingCommand,
    UnknownStatementMappingPreview,
    UnknownStatementMappingWarning,
)
from app.features.imports.application.unknown_statement_mappings.preview import (
    preview_unknown_statement_mapping,
)
from app.features.imports.application.unknown_statement_mappings.raw_tables import (
    compatible_mapping_table_count,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    compatible_mapping_templates,
)
from app.features.imports.application.unknown_statement_mappings.ui_defaults import (
    default_mapping_command,
    preview_table_options,
)
from app.features.imports.models import ImportMappingTemplate, UploadedDocumentStatus


class MappingPresentationError(ValueError):
    pass


@dataclass(frozen=True)
class MappingDocumentVM:
    status_label: str
    filename: str
    detail_url: str
    preview_url: str
    import_url: str


@dataclass(frozen=True)
class MappingNextStepVM:
    title: str
    message: str
    primary_href: str
    primary_label: str
    primary_icon: str
    secondary_href: str | None = None
    secondary_label: str | None = None
    secondary_icon: str | None = None


@dataclass(frozen=True)
class MappingTableOptionVM:
    value: str
    page_label: str
    table_label: str | None
    is_selected: bool


@dataclass(frozen=True)
class MappingColumnOptionVM:
    index: int
    label: str


@dataclass(frozen=True)
class MappingSuggestionReasonVM:
    message: str


@dataclass(frozen=True)
class MappingSuggestionWarningVM:
    message: str


@dataclass(frozen=True)
class MappingSuggestionVM:
    title: str
    reasons: list[MappingSuggestionReasonVM]
    warnings: list[MappingSuggestionWarningVM]


@dataclass(frozen=True)
class MappingColumnCandidateVM:
    message: str


@dataclass(frozen=True)
class MappingSelectedTableRowVM:
    cells: list[str]


@dataclass(frozen=True)
class MappingSelectedTableVM:
    title: str
    picker_meta: str
    size_meta: str
    import_scope_meta: str
    column_options: list[MappingColumnOptionVM]
    mapping_suggestion: MappingSuggestionVM | None
    column_candidates: list[MappingColumnCandidateVM]
    rows: list[MappingSelectedTableRowVM]


@dataclass(frozen=True)
class MappingWarningVM:
    message: str
    severity: str


@dataclass(frozen=True)
class MappingImportActionVM:
    form_action: str
    label: str
    icon: str


@dataclass(frozen=True)
class MappingSummaryMetricVM:
    label: str
    value: int
    class_name: str


@dataclass(frozen=True)
class MappingPreviewSummaryVM:
    metrics: list[MappingSummaryMetricVM]


@dataclass(frozen=True)
class MappingPreviewRowVM:
    source_row_number: int
    status: str
    status_label: str
    status_badge_class: str
    operation_date: str
    posting_date: str
    amount: str
    amount_class: str
    currency: str
    description: str
    error: str


@dataclass(frozen=True)
class MappingFormOptionVM:
    value: str
    label: str
    is_selected: bool


@dataclass(frozen=True)
class MappingFormSelectFieldVM:
    field_id: str
    name: str
    label: str
    options: list[MappingFormOptionVM]


@dataclass(frozen=True)
class MappingFormInputFieldVM:
    field_id: str
    name: str
    label: str
    value: str
    input_type: str
    min_value: str | None = None


@dataclass(frozen=True)
class MappingFormVM:
    select_fields: list[MappingFormSelectFieldVM]
    first_data_row: MappingFormInputFieldVM
    default_currency: MappingFormInputFieldVM


@dataclass(frozen=True)
class MappingPageContext:
    document: MappingDocumentVM
    next_step: MappingNextStepVM
    form: MappingFormVM
    selected_table_vm: MappingSelectedTableVM
    table_picker_options: list[MappingTableOptionVM]
    has_preview: bool
    warnings: list[MappingWarningVM]
    import_action: MappingImportActionVM | None
    preview_summary: MappingPreviewSummaryVM | None
    preview_rows: list[MappingPreviewRowVM]
    mapping_templates: list[ImportMappingTemplate]

    def template_values(
        self,
        *,
        app_name: str,
        workspace: object,
    ) -> dict[str, object]:
        return {
            "app_name": app_name,
            "document": self.document,
            "mapping_next_step": self.next_step,
            "mapping_form": self.form,
            "selected_table_vm": self.selected_table_vm,
            "table_picker_options": self.table_picker_options,
            "mapping_has_preview": self.has_preview,
            "mapping_warnings": self.warnings,
            "mapping_import_action": self.import_action,
            "mapping_preview_summary": self.preview_summary,
            "mapping_preview_rows": self.preview_rows,
            "mapping_templates": self.mapping_templates,
            "workspace": workspace,
        }


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


def build_mapping_page_context(
    *,
    view: ImportDocumentDetailView,
    default_currency: str,
    mapping_templates: list[ImportMappingTemplate],
) -> MappingPageContext:
    raw_tables = latest_raw_tables(view)
    compatible_templates = compatible_mapping_templates(mapping_templates, raw_tables)
    command = default_mapping_command(
        view.validation,
        default_currency=default_currency,
        templates=compatible_templates,
    )
    return mapping_page_context_from_command(
        view=view,
        command=command,
        preview=None,
        mapping_templates=compatible_templates,
    )


def preview_mapping_page_context(
    *,
    view: ImportDocumentDetailView,
    command: UnknownStatementMappingCommand,
    mapping_templates: list[ImportMappingTemplate],
) -> MappingPageContext:
    raw_tables = latest_raw_tables(view)
    preview = preview_unknown_statement_mapping(raw_tables, command)
    compatible_templates = compatible_mapping_templates(mapping_templates, raw_tables)
    return mapping_page_context_from_command(
        view=view,
        command=command,
        preview=preview,
        mapping_templates=compatible_templates,
    )


def mapping_page_context_from_command(
    *,
    view: ImportDocumentDetailView,
    command: UnknownStatementMappingCommand,
    preview: UnknownStatementMappingPreview | None,
    mapping_templates: list[ImportMappingTemplate],
) -> MappingPageContext:
    raw_tables = latest_raw_tables(view)
    table_options = preview_table_options(view.validation)
    selected_table = selected_mapping_table(table_options, command)
    compatible_table_count = compatible_mapping_table_count(raw_tables, command)
    document = mapping_document(view)
    selected_table_vm = mapping_selected_table(
        selected_table,
        compatible_table_count=compatible_table_count,
    )
    return MappingPageContext(
        document=document,
        next_step=mapping_next_step(
            document=document,
            preview=preview,
            table_options=table_options,
        ),
        form=mapping_form(command, selected_table_vm.column_options),
        selected_table_vm=selected_table_vm,
        table_picker_options=mapping_table_options(table_options, command),
        has_preview=preview is not None,
        warnings=mapping_warnings(preview),
        import_action=mapping_import_action(
            document=document,
            preview=preview,
            compatible_table_count=compatible_table_count,
        ),
        preview_summary=mapping_preview_summary(preview),
        preview_rows=mapping_preview_rows(preview),
        mapping_templates=mapping_templates,
    )


def mapping_form(
    command: UnknownStatementMappingCommand,
    column_options: list[MappingColumnOptionVM],
) -> MappingFormVM:
    return MappingFormVM(
        select_fields=[
            mapping_select_field(
                field_id="operation_date_column",
                label="Дата",
                column_options=column_options,
                selected_index=command.operation_date_column,
            ),
            mapping_select_field(
                field_id="posting_date_column",
                label="Дата проводки",
                column_options=column_options,
                selected_index=command.posting_date_column,
                empty_label="не используется",
            ),
            mapping_select_field(
                field_id="description_column",
                label="Описание",
                column_options=column_options,
                selected_index=command.description_column,
            ),
            mapping_select_field(
                field_id="amount_column",
                label="Сумма",
                column_options=column_options,
                selected_index=command.amount_column,
                empty_label="нет единой колонки",
            ),
            mapping_select_field(
                field_id="debit_amount_column",
                label="Списание",
                column_options=column_options,
                selected_index=command.debit_amount_column,
                empty_label="не используется",
            ),
            mapping_select_field(
                field_id="credit_amount_column",
                label="Зачисление",
                column_options=column_options,
                selected_index=command.credit_amount_column,
                empty_label="не используется",
            ),
            mapping_select_field(
                field_id="currency_column",
                label="Валюта",
                column_options=column_options,
                selected_index=command.currency_column,
                empty_label="по умолчанию",
            ),
            mapping_select_field(
                field_id="balance_after_column",
                label="Остаток после",
                column_options=column_options,
                selected_index=command.balance_after_column,
                empty_label="не используется",
            ),
        ],
        first_data_row=MappingFormInputFieldVM(
            field_id="first_data_row",
            name="first_data_row",
            label="Первая строка данных",
            value=str(command.first_data_row),
            input_type="number",
            min_value="0",
        ),
        default_currency=MappingFormInputFieldVM(
            field_id="default_currency",
            name="default_currency",
            label="Валюта по умолчанию",
            value=command.default_currency,
            input_type="text",
        ),
    )


def mapping_select_field(
    *,
    field_id: str,
    label: str,
    column_options: list[MappingColumnOptionVM],
    selected_index: int | None,
    empty_label: str | None = None,
) -> MappingFormSelectFieldVM:
    options: list[MappingFormOptionVM] = []
    if empty_label is not None:
        options.append(
            MappingFormOptionVM(
                value="-1",
                label=empty_label,
                is_selected=selected_index is None,
            )
        )
    options.extend(mapping_form_column_options(column_options, selected_index))
    return MappingFormSelectFieldVM(
        field_id=field_id,
        name=field_id,
        label=label,
        options=options,
    )


def mapping_form_column_options(
    column_options: list[MappingColumnOptionVM],
    selected_index: int | None,
) -> list[MappingFormOptionVM]:
    return [
        MappingFormOptionVM(
            value=str(option.index),
            label=option.label,
            is_selected=selected_index == option.index,
        )
        for option in column_options
    ]


def mapping_next_step(
    *,
    document: MappingDocumentVM,
    preview: UnknownStatementMappingPreview | None,
    table_options: list[dict[str, object]],
) -> MappingNextStepVM:
    if preview is not None and preview.rows:
        return MappingNextStepVM(
            title="Импортируйте строки",
            message=(
                "Предпросмотр готов. После импорта строки попадут в проверку, "
                "но еще не станут подтвержденным учетом."
            ),
            primary_href="#mapping-import-actions",
            primary_label="к импорту строк",
            primary_icon="import",
        )
    if table_options:
        return MappingNextStepVM(
            title="Настройте колонки",
            message=(
                "Выберите дату, описание и сумму, затем посмотрите предпросмотр перед импортом."
            ),
            primary_href="#mapping-form",
            primary_label="к настройке",
            primary_icon="settings",
        )
    return MappingNextStepVM(
        title="Вернитесь к документу",
        message=(
            "Таблицы для настройки не найдены. Проверьте детали парсинга "
            "или загрузите выписку заново."
        ),
        primary_href=document.detail_url,
        primary_label="открыть документ",
        primary_icon="file-text",
        secondary_href="/imports/upload",
        secondary_label="загрузить заново",
        secondary_icon="upload",
    )


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


def mapping_table_options(
    table_options: Sequence[Mapping[str, object]],
    command: UnknownStatementMappingCommand,
) -> list[MappingTableOptionVM]:
    return [mapping_table_option(table, command) for table in table_options]


def mapping_table_option(
    table: Mapping[str, object],
    command: UnknownStatementMappingCommand,
) -> MappingTableOptionVM:
    page_number = int_table_value(table, "page_number", default=1)
    table_index = int_table_value(table, "table_index", default=0)
    return MappingTableOptionVM(
        value=f"{page_number}:{table_index}",
        page_label=str(page_number),
        table_label=str(table_index + 1) if table_index else None,
        is_selected=page_number == command.page_number and table_index == command.table_index,
    )


def mapping_selected_table(
    table: Mapping[str, object],
    *,
    compatible_table_count: int,
) -> MappingSelectedTableVM:
    if not table:
        return MappingSelectedTableVM(
            title="",
            picker_meta="",
            size_meta="",
            import_scope_meta="",
            column_options=[],
            mapping_suggestion=None,
            column_candidates=[],
            rows=[],
        )

    page_number = int_table_value(table, "page_number", default=1)
    table_index = int_table_value(table, "table_index", default=0)
    row_count = int_table_value(table, "row_count", default=0)
    column_count = int_table_value(table, "column_count", default=0)

    if table.get("source_type") == "text_candidate":
        title = f"Выбранные строки из текста: страница {page_number}"
        picker_meta = f"выбрана страница {page_number} · строки из текста"
    else:
        title = f"Выбранная таблица: страница {page_number} · таблица {table_index + 1}"
        picker_meta = f"выбрана страница {page_number} · таблица {table_index + 1}"

    import_scope_meta = (
        f"импорт: {compatible_table_count} таблиц по этой схеме"
        if compatible_table_count > 1
        else "импорт: только выбранная таблица"
    )
    return MappingSelectedTableVM(
        title=title,
        picker_meta=picker_meta,
        size_meta=f"{row_count} строк · {column_count} колонок",
        import_scope_meta=import_scope_meta,
        column_options=mapping_column_options(table),
        mapping_suggestion=mapping_table_suggestion(table),
        column_candidates=mapping_column_candidates(table),
        rows=mapping_table_rows(table),
    )


def mapping_table_suggestion(table: Mapping[str, object]) -> MappingSuggestionVM | None:
    suggestions = table.get("mapping_suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        return None
    suggestion = string_key_mapping(suggestions[0])
    if suggestion is None:
        return None
    return mapping_suggestion(suggestion)


def mapping_suggestion(suggestion: Mapping[str, object]) -> MappingSuggestionVM:
    confidence = float_table_value(suggestion, "confidence", default=0)
    return MappingSuggestionVM(
        title=f"Предложение маппинга · {int(round(confidence * 100))}%",
        reasons=mapping_suggestion_reasons(suggestion),
        warnings=mapping_suggestion_warnings(suggestion),
    )


def mapping_suggestion_reasons(
    suggestion: Mapping[str, object],
) -> list[MappingSuggestionReasonVM]:
    reasons = suggestion.get("reasons")
    if not isinstance(reasons, list):
        return []
    return [
        MappingSuggestionReasonVM(mapping_suggestion_reason_message(reason)) for reason in reasons
    ]


def mapping_suggestion_reason_message(reason: object) -> str:
    reason_mapping = string_key_mapping(reason)
    if reason_mapping is None or "field" not in reason_mapping:
        return str(reason)

    field_label = mapping_field_label(reason_mapping.get("field"))
    column_number = int_table_value(reason_mapping, "column_index", default=0) + 1
    evidence = string_table_value(reason_mapping, "evidence")

    if evidence == "header_match":
        return (
            f"{field_label}: колонка {column_number} выбрана по заголовку "
            f"«{string_table_value(reason_mapping, 'header')}»."
        )
    if evidence == "date_like_values":
        return mapping_profile_reason_message(field_label, column_number, reason_mapping, "дату")
    if evidence == "money_like_values":
        return mapping_profile_reason_message(field_label, column_number, reason_mapping, "суммы")
    if evidence == "currency_like_values":
        return mapping_profile_reason_message(field_label, column_number, reason_mapping, "валюту")
    if evidence == "description_like_values":
        return (
            f"{field_label}: колонка {column_number} содержит "
            f"{string_table_value(reason_mapping, 'matched_count')}/"
            f"{string_table_value(reason_mapping, 'sample_count')} текстовых значений."
        )
    return f"{field_label}: колонка {column_number}."


def mapping_profile_reason_message(
    field_label: str,
    column_number: int,
    reason: Mapping[str, object],
    value_label: str,
) -> str:
    return (
        f"{field_label}: колонка {column_number} содержит "
        f"{string_table_value(reason, 'matched_count')}/"
        f"{string_table_value(reason, 'sample_count')} значений, похожих на {value_label}."
    )


def mapping_suggestion_warnings(
    suggestion: Mapping[str, object],
) -> list[MappingSuggestionWarningVM]:
    warnings = suggestion.get("warnings")
    if not isinstance(warnings, list):
        return []
    return [
        MappingSuggestionWarningVM(mapping_suggestion_warning_message(warning))
        for warning in warnings
    ]


def mapping_suggestion_warning_message(warning: object) -> str:
    warning_mapping = string_key_mapping(warning)
    if warning_mapping is None:
        return str(warning)
    code = string_table_value(warning_mapping, "code")
    if code == "partial_debit_credit_columns":
        return (
            "Найдена только одна колонка списания/зачисления. Проверьте знак суммы перед импортом."
        )
    return code


def mapping_column_candidates(table: Mapping[str, object]) -> list[MappingColumnCandidateVM]:
    candidates = table.get("column_candidates")
    if not isinstance(candidates, list):
        return []
    candidate_vms: list[MappingColumnCandidateVM] = []
    for candidate in candidates:
        candidate_mapping = string_key_mapping(candidate)
        if candidate_mapping is not None:
            candidate_vms.append(
                MappingColumnCandidateVM(mapping_column_candidate_message(candidate_mapping))
            )
    return candidate_vms


def mapping_column_candidate_message(candidate: Mapping[str, object]) -> str:
    column_number = int_table_value(candidate, "column_index", default=0) + 1
    return (
        f"{string_table_value(candidate, 'field')}: колонка {column_number} · "
        f"{string_table_value(candidate, 'header')}"
    )


def mapping_table_rows(table: Mapping[str, object]) -> list[MappingSelectedTableRowVM]:
    rows = table.get("rows")
    if not isinstance(rows, list):
        return []
    return [MappingSelectedTableRowVM(cells=mapping_table_row_cells(row)) for row in rows]


def mapping_table_row_cells(row: object) -> list[str]:
    if isinstance(row, list):
        return [str(cell) for cell in row]
    return [str(row)]


def mapping_column_options(table: Mapping[str, object]) -> list[MappingColumnOptionVM]:
    column_count = int_table_value(table, "column_count", default=0)
    return [
        MappingColumnOptionVM(
            index=index,
            label=f"{index + 1} · {mapping_column_header(table, index)}",
        )
        for index in range(column_count)
    ]


def mapping_column_header(table: Mapping[str, object], index: int) -> str:
    rows = table.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], list) and len(rows[0]) > index:
        return str(rows[0][index])
    return f"Колонка {index + 1}"


def int_table_value(table: Mapping[str, object], key: str, *, default: int) -> int:
    value = table.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def float_table_value(table: Mapping[str, object], key: str, *, default: float) -> float:
    value = table.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def string_table_value(table: Mapping[str, object], key: str) -> str:
    value = table.get(key)
    return "" if value is None else str(value)


def string_key_mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return None


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
    field = "" if value is None else str(value)
    return labels.get(field, field)


def latest_raw_tables(view: ImportDocumentDetailView) -> list[dict[str, object]] | None:
    latest_attempt = view.parse_attempts[0] if view.parse_attempts else None
    return latest_attempt.raw_tables if latest_attempt else None


def mapping_document(view: ImportDocumentDetailView) -> MappingDocumentVM:
    document_url = f"/imports/documents/{view.id}"
    return MappingDocumentVM(
        status_label=mapping_document_status_label(view.status),
        filename=view.original_filename,
        detail_url=document_url,
        preview_url=f"{document_url}/mapping",
        import_url=f"{document_url}/mapping/import",
    )


def mapping_document_status_label(status: UploadedDocumentStatus) -> str:
    labels = {
        UploadedDocumentStatus.UPLOADED: "загружено",
        UploadedDocumentStatus.PENDING_PARSE: "ожидает парсинга",
        UploadedDocumentStatus.PARSING: "парсинг",
        UploadedDocumentStatus.PARSED: "распознано",
        UploadedDocumentStatus.REQUIRES_REVIEW: "требует проверки",
        UploadedDocumentStatus.FAILED_TO_PARSE: "ошибка парсинга",
        UploadedDocumentStatus.IMPORTED: "импортировано",
        UploadedDocumentStatus.IGNORED: "игнорируется",
    }
    return labels.get(status, status.value)


def parse_table_ref(value: str) -> tuple[int, int]:
    try:
        page_number, table_index = value.split(":", maxsplit=1)
        parsed_page_number = int(page_number)
        parsed_table_index = int(table_index)
        if parsed_page_number < 1 or parsed_table_index < 0:
            raise ValueError
        return parsed_page_number, parsed_table_index
    except ValueError as exc:
        raise MappingPresentationError("Invalid table reference.") from exc


def selected_mapping_table(
    table_options: list[dict[str, object]],
    command: UnknownStatementMappingCommand,
) -> dict[str, object]:
    for table in table_options:
        if (
            table.get("page_number") == command.page_number
            and table.get("table_index") == command.table_index
        ):
            return table
    return table_options[0] if table_options else {}
