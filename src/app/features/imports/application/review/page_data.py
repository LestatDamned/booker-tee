from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.imports.service import ImportService
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class ImportReviewReferences:
    accounts: Sequence[object]
    categories: Sequence[object]
    properties: Sequence[object]


@dataclass(frozen=True)
class ImportReviewTransferData:
    suggestions: Mapping[UUID, Sequence[object]]
    existing_suggestions: Mapping[UUID, Sequence[object]]


@dataclass(frozen=True)
class ImportReviewPageData:
    accounts: Sequence[object]
    categories: Sequence[object]
    properties: Sequence[object]
    transfer_suggestions: Mapping[UUID, Sequence[object]]
    existing_transfer_suggestions: Mapping[UUID, Sequence[object]]


@dataclass(frozen=True)
class ImportReviewPageDataLoader:
    session: AsyncSession

    async def load_document(self, *, workspace_id: UUID, document_id: UUID) -> object | None:
        return await ImportService(self.session).get_document(workspace_id, document_id)

    async def load_page_data(
        self,
        *,
        context: WorkspaceContext,
        document: object,
    ) -> ImportReviewPageData:
        references = await self._load_references(context)
        transfer_data = await self._load_transfer_data(
            workspace_id=context.workspace.id,
            document=document,
        )
        return ImportReviewPageData(
            accounts=references.accounts,
            categories=references.categories,
            properties=references.properties,
            transfer_suggestions=transfer_data.suggestions,
            existing_transfer_suggestions=transfer_data.existing_suggestions,
        )

    async def _load_references(self, context: WorkspaceContext) -> ImportReviewReferences:
        return ImportReviewReferences(
            accounts=await AccountService(self.session).list_active_accounts(
                context.workspace.id
            ),
            categories=await CategoryService(self.session).list_or_seed_defaults(
                context.workspace.id,
                context.workspace.type,
            ),
            properties=await PropertyService(self.session).list_active(context.workspace.id),
        )

    async def _load_transfer_data(
        self,
        *,
        workspace_id: UUID,
        document: object,
    ) -> ImportReviewTransferData:
        ledger_service = LedgerPostingService(self.session)
        raw_transactions = getattr(document, "raw_transactions", [])
        return ImportReviewTransferData(
            suggestions=await ledger_service.list_transfer_suggestions_for_document(
                workspace_id=workspace_id,
                raw_transactions=raw_transactions,
            ),
            existing_suggestions=(
                await ledger_service.list_existing_transfer_suggestions_for_document(
                    workspace_id=workspace_id,
                    raw_transactions=raw_transactions,
                )
            ),
        )
