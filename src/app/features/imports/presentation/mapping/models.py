from dataclasses import dataclass

from app.features.imports.presentation.mapping_suggestions import MappingSuggestionVM


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
class MappingTemplateNoticeVM:
    title: str
    message: str


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
    template_notice: MappingTemplateNoticeVM | None
    form: MappingFormVM
    selected_table_vm: MappingSelectedTableVM
    table_picker_options: list[MappingTableOptionVM]
    has_preview: bool
    warnings: list[MappingWarningVM]
    import_action: MappingImportActionVM | None
    preview_summary: MappingPreviewSummaryVM | None
    preview_rows: list[MappingPreviewRowVM]

    def template_values(
        self,
        *,
        app_name: str,
        workspace: object,
    ) -> dict[str, object]:
        return {
            "app_name": app_name,
            "page": self,
            "workspace": workspace,
        }
