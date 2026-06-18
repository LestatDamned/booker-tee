from collections.abc import Sequence
from dataclasses import dataclass


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
    view: object

    def template_values(self, *, app_name: str, workspace: object) -> dict[str, object]:
        return {
            "app_name": app_name,
            "view": self.view,
            "workspace": workspace,
        }
