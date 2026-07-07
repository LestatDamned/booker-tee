from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.presentation.mapping.models import (
    MappingColumnOptionVM,
    MappingFormInputFieldVM,
    MappingFormOptionVM,
    MappingFormSelectFieldVM,
    MappingFormVM,
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
