from app.features.imports.application.documents.detail_view import ImportDocumentDetailView
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
    UnknownStatementMappingPreview,
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
from app.features.imports.presentation.mapping.form import mapping_form
from app.features.imports.presentation.mapping.models import (
    MappingDocumentVM,
    MappingNextStepVM,
    MappingPageContext,
    MappingPresentationError,
    MappingTemplateNoticeVM,
)
from app.features.imports.presentation.mapping.preview import (
    mapping_import_action,
    mapping_preview_rows,
    mapping_preview_summary,
    mapping_submit_actions,
    mapping_warnings,
)
from app.features.imports.presentation.mapping.tables import (
    mapping_selected_table_vm,
    mapping_table_picker_options,
)


class MappingPagePresenter:
    def build(
        self,
        *,
        view: ImportDocumentDetailView,
        default_currency: str,
        mapping_templates: list[ImportMappingTemplate],
    ) -> MappingPageContext:
        raw_tables = _latest_raw_tables(view)
        compatible_templates = compatible_mapping_templates(mapping_templates, raw_tables)
        command = default_mapping_command(
            view.validation,
            default_currency=default_currency,
            templates=compatible_templates,
        )
        return self._from_command(
            view=view,
            command=command,
            preview=None,
            mapping_templates=compatible_templates,
        )

    def preview(
        self,
        *,
        view: ImportDocumentDetailView,
        command: UnknownStatementMappingCommand,
        mapping_templates: list[ImportMappingTemplate],
    ) -> MappingPageContext:
        raw_tables = _latest_raw_tables(view)
        preview = preview_unknown_statement_mapping(raw_tables, command)
        compatible_templates = compatible_mapping_templates(mapping_templates, raw_tables)
        return self._from_command(
            view=view,
            command=command,
            preview=preview,
            mapping_templates=compatible_templates,
        )

    def _from_command(
        self,
        *,
        view: ImportDocumentDetailView,
        command: UnknownStatementMappingCommand,
        preview: UnknownStatementMappingPreview | None,
        mapping_templates: list[ImportMappingTemplate],
    ) -> MappingPageContext:
        raw_tables = _latest_raw_tables(view)
        table_options = preview_table_options(view.validation)
        selected_table = _selected_mapping_table(table_options, command)
        compatible_table_count = compatible_mapping_table_count(raw_tables, command)
        document = _mapping_document(view)
        selected_table_vm = mapping_selected_table_vm(
            selected_table,
            compatible_table_count=compatible_table_count,
        )
        import_action = mapping_import_action(
            document=document,
            compatible_table_count=compatible_table_count,
        )
        return MappingPageContext(
            document=document,
            next_step=_mapping_next_step(
                document=document,
                preview=preview,
                table_options=table_options,
            ),
            template_notice=_mapping_template_notice(mapping_templates),
            form=mapping_form(command, selected_table_vm.column_options),
            selected_table_vm=selected_table_vm,
            table_picker_options=mapping_table_picker_options(table_options, command),
            has_preview=preview is not None,
            warnings=mapping_warnings(preview),
            form_actions=mapping_submit_actions(
                document=document,
                import_action=import_action,
                preview_ready=preview is not None,
            ),
            preview_summary=mapping_preview_summary(preview),
            preview_rows=mapping_preview_rows(preview),
        )


def _mapping_template_notice(
    mapping_templates: list[ImportMappingTemplate],
) -> MappingTemplateNoticeVM | None:
    if not mapping_templates:
        return None
    template = mapping_templates[0]
    return MappingTemplateNoticeVM(
        title="Найден шаблон",
        message=(
            f"{template.name}. Поля ниже уже заполнены из последнего подходящего "
            "шаблона для этого банка и типа выписки."
        ),
    )


def _mapping_next_step(
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
        secondary_href="/app/imports/upload",
        secondary_label="загрузить заново",
        secondary_icon="upload",
    )


def _latest_raw_tables(view: ImportDocumentDetailView) -> list[dict[str, object]] | None:
    latest_attempt = view.parse_attempts[0] if view.parse_attempts else None
    return latest_attempt.raw_tables if latest_attempt else None


def _mapping_document(view: ImportDocumentDetailView) -> MappingDocumentVM:
    document_url = f"/imports/documents/{view.id}"
    return MappingDocumentVM(
        status_label=_mapping_document_status_label(view.status),
        filename=view.original_filename,
        detail_url=document_url,
        preview_url=f"{document_url}/mapping",
        import_url=f"{document_url}/mapping/import",
    )


def _mapping_document_status_label(status: UploadedDocumentStatus) -> str:
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


def _selected_mapping_table(
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
