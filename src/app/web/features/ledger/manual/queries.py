from dataclasses import dataclass, replace
from uuid import UUID

from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.ledger.application.listing import LedgerPage
from app.features.ledger.mapping.dto import ManualOperationView
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.service import WorkspaceContext
from app.web.features.ledger.manual.query_state import ManualLedgerListQuery


@dataclass(frozen=True)
class ManualLedgerNamedReference:
    id: UUID
    name: str


@dataclass(frozen=True)
class ManualLedgerAccountReference:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class ManualLedgerPageData:
    operations: tuple[ManualOperationView, ...]
    page: LedgerPage


@dataclass(frozen=True)
class ManualLedgerFormData:
    accounts: tuple[ManualLedgerAccountReference, ...]
    categories: tuple[ManualLedgerNamedReference, ...]
    properties: tuple[ManualLedgerNamedReference, ...]


@dataclass(frozen=True)
class ManualLedgerEditData:
    operation: ManualOperationView
    form: ManualLedgerFormData


class ManualLedgerPageQuery:
    def __init__(self, ledger: LedgerPostingService) -> None:
        self._ledger = ledger

    async def execute(
        self,
        *,
        workspace_id: UUID,
        query: ManualLedgerListQuery,
    ) -> ManualLedgerPageData:
        operations, page = await self._ledger.list_manual_operations(
            workspace_id,
            filters=query.filters,
            pagination=query.pagination,
        )
        if page.page > page.total_pages:
            normalized_query = replace(
                query,
                pagination=replace(query.pagination, page=page.total_pages),
            )
            operations, page = await self._ledger.list_manual_operations(
                workspace_id,
                filters=normalized_query.filters,
                pagination=normalized_query.pagination,
            )
        return ManualLedgerPageData(
            operations=tuple(operations),
            page=page,
        )


class ManualLedgerFormQuery:
    def __init__(
        self,
        *,
        accounts: AccountService,
        categories: CategoryService,
        properties: PropertyService,
    ) -> None:
        self._accounts = accounts
        self._categories = categories
        self._properties = properties

    async def execute(
        self,
        *,
        context: WorkspaceContext,
    ) -> ManualLedgerFormData:
        workspace_id = context.workspace.id
        accounts = await self._accounts.list_active_accounts(workspace_id)
        categories = await self._categories.list_or_seed_defaults(
            workspace_id,
            context.workspace.type,
        )
        properties = await self._properties.list_active(workspace_id)
        return ManualLedgerFormData(
            accounts=tuple(
                ManualLedgerAccountReference(
                    id=account.id,
                    name=account.name,
                    currency=account.currency,
                )
                for account in accounts
            ),
            categories=tuple(
                ManualLedgerNamedReference(id=category.id, name=category.name)
                for category in categories
            ),
            properties=tuple(
                ManualLedgerNamedReference(id=property_.id, name=property_.name)
                for property_ in properties
            ),
        )


class ManualLedgerEditQuery:
    def __init__(
        self,
        *,
        ledger: LedgerPostingService,
        form: ManualLedgerFormQuery,
    ) -> None:
        self._ledger = ledger
        self._form = form

    async def execute(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> ManualLedgerEditData | None:
        operation = await self._ledger.get_manual_operation(
            workspace_id=context.workspace.id,
            operation_id=operation_id,
        )
        if operation is None:
            return None
        return ManualLedgerEditData(
            operation=operation,
            form=await self._form.execute(context=context),
        )
