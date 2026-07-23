from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.features.imports.application.documents.detail_view import ImportDocumentDetailView
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
