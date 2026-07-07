from collections.abc import Sequence
from dataclasses import dataclass

from app.features.imports.mapping.dto import ImportDocumentDetailView
from app.features.imports.models import UploadedDocumentStatus


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
class DocumentDetailValidationVM:
    status: str
    message: str
    metrics: Sequence[DocumentDetailMetricVM]
    needs_mapping: bool


@dataclass(frozen=True)
class DocumentDetailPageVM:
    title: str
    status_label: str
    document_name: str
    workflow: DocumentDetailWorkflowVM
    next_step: DocumentDetailNextStepVM
    actions: Sequence[DocumentDetailActionVM]
    validation: DocumentDetailValidationVM | None


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


def statement_type_label(value: object) -> str:
    labels = {
        "card_statement": "карточная выписка",
        "account_statement": "выписка по счету",
        "deposit_statement": "выписка по вкладу",
    }
    status = string_value(value)
    return labels.get(status, status)


def money_value(value: object, currency: object) -> str:
    if value in {None, ""}:
        return ""
    currency_label = string_value(currency)
    if not currency_label:
        return str(value)
    return f"{value} {currency_label}"


def string_value(value: object, *, fallback: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return fallback
    return str(value)
