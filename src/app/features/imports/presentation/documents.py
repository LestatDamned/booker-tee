from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.features.imports.application.documents.detail_view import ImportDocumentDetailView
from app.features.imports.models import UploadedDocumentStatus
from app.features.imports.presentation.document_page.formatting import document_status_label
from app.features.imports.presentation.document_page.presenter import (
    DocumentDetailPresenter,
)


@dataclass(frozen=True)
class ImportPageNextStepVM:
    title: str
    message: str
    primary_href: str
    primary_label: str
    primary_icon: str


@dataclass(frozen=True)
class ImportIndexDocumentVM:
    id: UUID
    filename: str
    status_label: str
    status_value: str
    created_at: object
    file_size_bytes: int
    detail_url: str
    review_url: str
    primary_href: str
    primary_label: str
    primary_icon: str
    primary_tone: str
    secondary_href: str
    secondary_label: str
    secondary_icon: str


@dataclass(frozen=True)
class ImportIndexPageVM:
    workspace_name: str
    title: str
    next_step: ImportPageNextStepVM | None
    documents: list[ImportIndexDocumentVM]
    can_import: bool


class ImportIndexPresenter:
    def build(
        self,
        *,
        documents: Sequence[object],
        workspace: object,
        can_import: bool,
    ) -> ImportIndexPageVM:
        document_vms = [self.document(document) for document in documents]
        return ImportIndexPageVM(
            workspace_name=str(getattr(workspace, "name", "")),
            title="Импорт выписок",
            next_step=self.next_step(document_vms, can_import=can_import),
            documents=document_vms,
            can_import=can_import,
        )

    def document(self, document: Any) -> ImportIndexDocumentVM:
        document_id = document.id
        status = document.status
        status_value = str(getattr(status, "value", status))
        detail_url = f"/imports/documents/{document_id}"
        review_url = f"{detail_url}/review"
        primary_href, primary_label, primary_icon, primary_tone = self.primary_action(
            status_value=status_value,
            detail_url=detail_url,
            review_url=review_url,
        )
        return ImportIndexDocumentVM(
            id=document_id,
            filename=str(getattr(document, "original_filename", "")),
            status_label=document_status_label(status),
            status_value=status_value,
            created_at=document.created_at,
            file_size_bytes=int(getattr(document, "file_size_bytes", None) or 0),
            detail_url=detail_url,
            review_url=review_url,
            primary_href=primary_href,
            primary_label=primary_label,
            primary_icon=primary_icon,
            primary_tone=primary_tone,
            secondary_href=detail_url,
            secondary_label="детали",
            secondary_icon="file-text",
        )

    def next_step(
        self,
        documents: list[ImportIndexDocumentVM],
        *,
        can_import: bool,
    ) -> ImportPageNextStepVM | None:
        if not can_import:
            return None
        attention_document = next(
            (
                document
                for document in documents
                if document.status_value
                in {
                    UploadedDocumentStatus.REQUIRES_REVIEW.value,
                    UploadedDocumentStatus.FAILED_TO_PARSE.value,
                    UploadedDocumentStatus.PENDING_PARSE.value,
                }
            ),
            None,
        )
        if attention_document is not None:
            return ImportPageNextStepVM(
                title="Проверьте выписку",
                message="Этот документ требует решения перед тем, как строки попадут в учет.",
                primary_href=attention_document.review_url,
                primary_label="открыть проверку",
                primary_icon="clipboard-check",
            )
        if documents:
            return ImportPageNextStepVM(
                title="Загрузите выписку",
                message=(
                    "Перед следующей загрузкой можно обновить правила: они ускорят "
                    "проверку строк и дадут подсказки по категориям."
                ),
                primary_href="/imports/upload",
                primary_label="загрузить выписку",
                primary_icon="upload",
            )
        return None

    def primary_action(
        self,
        *,
        status_value: str,
        detail_url: str,
        review_url: str,
    ) -> tuple[str, str, str, str]:
        if status_value in {
            UploadedDocumentStatus.REQUIRES_REVIEW.value,
            UploadedDocumentStatus.IMPORTED.value,
        }:
            return review_url, "проверка", "clipboard-check", "primary"
        return detail_url, "детали", "file-text", "secondary"


@dataclass(frozen=True)
class ImportIndexPageContext:
    documents: Sequence[object]
    can_import: bool

    def template_values(self, *, app_name: str, workspace: object) -> dict[str, object]:
        page = ImportIndexPresenter().build(
            documents=self.documents,
            workspace=workspace,
            can_import=self.can_import,
        )
        return {
            "app_name": app_name,
            "page": page,
            "workspace": workspace,
        }


@dataclass(frozen=True)
class UploadAccountVM:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class UploadPageVM:
    workspace_name: str
    title: str
    next_step: ImportPageNextStepVM
    accounts: list[UploadAccountVM]
    error: str | None
    has_accounts: bool


class UploadPagePresenter:
    def build(
        self,
        *,
        accounts: Sequence[object],
        workspace: object,
        error: str | None = None,
    ) -> UploadPageVM:
        account_vms = [self.account(account) for account in accounts]
        return UploadPageVM(
            workspace_name=str(getattr(workspace, "name", "")),
            title="Загрузить выписку",
            next_step=self.next_step(has_accounts=bool(account_vms)),
            accounts=account_vms,
            error=error,
            has_accounts=bool(account_vms),
        )

    def account(self, account: Any) -> UploadAccountVM:
        return UploadAccountVM(
            id=account.id,
            name=str(account.name),
            currency=str(account.currency),
        )

    def next_step(self, *, has_accounts: bool) -> ImportPageNextStepVM:
        if has_accounts:
            return ImportPageNextStepVM(
                title="Выберите счет и файл",
                message=(
                    "Загрузите PDF или XLSX выписку. После извлечения строки попадут "
                    "в проверяемый импорт."
                ),
                primary_href="#upload-form",
                primary_label="к загрузке",
                primary_icon="upload",
            )
        return ImportPageNextStepVM(
            title="Создайте счет",
            message="Выписка всегда привязана к счету, чтобы проводки считались корректно.",
            primary_href="/accounts",
            primary_label="создать счет",
            primary_icon="plus",
        )


@dataclass(frozen=True)
class UploadPageContext:
    accounts: Sequence[object]
    error: str | None = None

    def template_values(self, *, app_name: str, workspace: object) -> dict[str, object]:
        page = UploadPagePresenter().build(
            accounts=self.accounts,
            workspace=workspace,
            error=self.error,
        )
        return {
            "app_name": app_name,
            "page": page,
            "workspace": workspace,
        }


@dataclass(frozen=True)
class DocumentDetailPageContext:
    view: ImportDocumentDetailView
    can_manage_imports: bool

    def template_values(self, *, app_name: str, workspace: object) -> dict[str, object]:
        page = DocumentDetailPresenter().build(
            self.view,
            can_manage_imports=self.can_manage_imports,
        )
        return {
            "app_name": app_name,
            "page": page,
            "workspace": workspace,
        }
