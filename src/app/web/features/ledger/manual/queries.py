from dataclasses import dataclass, replace
from uuid import UUID

from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.ledger.application.listing import LedgerPage
from app.features.ledger.mapping.dto import ManualOperationView
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.service import WorkspaceContext
from app.web.features.ledger.manual.query_state import ManualLedgerPageParams


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
    pagination: LedgerPage


@dataclass(frozen=True)
class ManualLedgerReferenceData:
    accounts: tuple[ManualLedgerAccountReference, ...]
    categories: tuple[ManualLedgerNamedReference, ...]
    properties: tuple[ManualLedgerNamedReference, ...]


@dataclass(frozen=True)
class ManualLedgerEditData:
    operation: ManualOperationView
    references: ManualLedgerReferenceData


class ManualLedgerPageQuery:
    def __init__(self, ledger: LedgerPostingService) -> None:
        self._ledger = ledger

    async def execute(
        self,
        *,
        workspace_id: UUID,
        params: ManualLedgerPageParams,
    ) -> ManualLedgerPageData:
        operations, pagination = await self._ledger.list_manual_operations(
            workspace_id,
            filters=params.filters,
            pagination=params.pagination,
        )
        if pagination.page > pagination.total_pages:
            normalized_params = replace(
                params,
                pagination=replace(params.pagination, page=pagination.total_pages),
            )
            operations, pagination = await self._ledger.list_manual_operations(
                workspace_id,
                filters=normalized_params.filters,
                pagination=normalized_params.pagination,
            )
        return ManualLedgerPageData(
            operations=tuple(operations),
            pagination=pagination,
        )


class ManualLedgerReferenceQuery:
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
    ) -> ManualLedgerReferenceData:
        workspace_id = context.workspace.id
        accounts = await self._accounts.list_active_accounts(workspace_id)
        categories = await self._categories.list_or_seed_defaults(
            workspace_id,
            context.workspace.type,
        )
        properties = await self._properties.list_active(workspace_id)
        return ManualLedgerReferenceData(
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
        references: ManualLedgerReferenceQuery,
    ) -> None:
        self._ledger = ledger
        self._references = references

    async def execute(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        references: ManualLedgerReferenceData | None = None,
    ) -> ManualLedgerEditData | None:
        operation = await self._ledger.get_manual_operation(
            workspace_id=context.workspace.id,
            operation_id=operation_id,
        )
        if operation is None:
            return None
        return ManualLedgerEditData(
            operation=operation,
            references=references or await self._references.execute(context=context),
        )
