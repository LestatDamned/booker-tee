from collections.abc import Sequence
from dataclasses import dataclass

from app.features.imports.application.documents.detail_view import ImportDocumentDetailView
from app.features.imports.presentation.document_page.presenter import (
    DocumentDetailPresenter,
)


@dataclass(frozen=True)
class ImportIndexPageContext:
    documents: Sequence[object]

    def template_values(self, *, app_name: str, workspace: object) -> dict[str, object]:
        return {
            "app_name": app_name,
            "documents": self.documents,
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
