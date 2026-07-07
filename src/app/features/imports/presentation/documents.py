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
class ImportIndexNextStepVM:
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
    next_step: ImportIndexNextStepVM | None
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
    ) -> ImportIndexNextStepVM | None:
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
            return ImportIndexNextStepVM(
                title="Проверьте выписку",
                message="Этот документ требует решения перед тем, как строки попадут в учет.",
                primary_href=attention_document.review_url,
                primary_label="открыть проверку",
                primary_icon="clipboard-check",
            )
        if documents:
            return ImportIndexNextStepVM(
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
class UploadPageContext:
    accounts: Sequence[object]
    error: str | None = None

    def template_values(self, *, app_name: str, workspace: object) -> dict[str, object]:
        return {
            "accounts": self.accounts,
            "app_name": app_name,
            "error": self.error,
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
