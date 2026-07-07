from dataclasses import dataclass

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
class MappingPageContext:
    document: MappingDocumentVM
    command: UnknownStatementMappingCommand
    preview: UnknownStatementMappingPreview | None
    selected_table: dict[str, object]
    table_options: list[dict[str, object]]
    compatible_table_count: int
    mapping_templates: list[ImportMappingTemplate]

    def template_values(
        self,
        *,
        app_name: str,
        workspace: object,
    ) -> dict[str, object]:
        return {
            "app_name": app_name,
            "command": self.command,
            "document": self.document,
            "preview": self.preview,
            "selected_table": self.selected_table,
            "table_options": self.table_options,
            "compatible_table_count": self.compatible_table_count,
            "mapping_templates": self.mapping_templates,
            "workspace": workspace,
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
    return MappingPageContext(
        document=mapping_document(view),
        command=command,
        preview=preview,
        selected_table=selected_mapping_table(table_options, command),
        table_options=table_options,
        compatible_table_count=compatible_mapping_table_count(raw_tables, command),
        mapping_templates=mapping_templates,
    )


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
