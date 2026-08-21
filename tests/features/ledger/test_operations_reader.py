from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.features.ledger.application.operations import OperationsReader
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.schemas.listing import LedgerPagination, OperationFilters


async def test_list_projects_every_source_with_typed_provenance_and_capabilities() -> None:
    workspace_id = uuid4()
    operations_by_source = {source: operation(source) for source in OperationSource}
    operations = list(operations_by_source.values())
    filters = OperationFilters(search="Аренда")
    pagination = LedgerPagination(page=2, per_page=25)
    repository = SimpleNamespace(
        count_operations_for_workspace=AsyncMock(return_value=60),
        list_operations_page_for_workspace=AsyncMock(return_value=operations),
    )
    reader = OperationsReader(cast(Any, object()))
    reader._ledger = cast(Any, repository)

    items, page = await reader.list(
        workspace_id=workspace_id,
        can_write=True,
        filters=filters,
        pagination=pagination,
    )

    assert [item.source for item in items] == list(OperationSource)
    by_source = {item.source: item for item in items}
    assert by_source[OperationSource.MANUAL].provenance is None
    assert by_source[OperationSource.MANUAL].capabilities.edit_kind == "manual"
    assert by_source[OperationSource.MANUAL].capabilities.can_cancel is True
    import_provenance = by_source[OperationSource.BANK_PDF].provenance
    assert import_provenance is not None
    assert import_provenance.kind == "import"
    imported_operation = operations_by_source[OperationSource.BANK_PDF]
    assert import_provenance.uploaded_document_id == (
        imported_operation.raw_transactions[0].uploaded_document_id
    )
    assert import_provenance.raw_transaction_id == imported_operation.raw_transactions[0].id
    assert by_source[OperationSource.BANK_PDF].capabilities.edit_kind == "imported"
    debt_provenance = by_source[OperationSource.DEBT].provenance
    assert debt_provenance is not None
    assert debt_provenance.kind == "debt"
    assert debt_provenance.debt_account_id == (
        operations_by_source[OperationSource.DEBT].money_entries[0].account_id
    )
    assert by_source[OperationSource.DEBT].capabilities.readonly_reason == (
        "source_workflow_required"
    )
    system_provenance = by_source[OperationSource.SYSTEM].provenance
    assert system_provenance is not None
    assert system_provenance.kind == "system"
    assert by_source[OperationSource.SYSTEM].capabilities.readonly_reason == ("system_operation")
    assert page.page == 2
    assert page.per_page == 25
    assert page.total == 60
    repository.count_operations_for_workspace.assert_awaited_once_with(
        workspace_id=workspace_id,
        filters=filters,
    )
    repository.list_operations_page_for_workspace.assert_awaited_once_with(
        workspace_id=workspace_id,
        filters=filters,
        pagination=pagination,
    )


async def test_get_masks_an_operation_missing_from_the_workspace() -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    lookup = AsyncMock(return_value=None)
    reader = OperationsReader(cast(Any, object()))
    reader._ledger = cast(
        Any,
        SimpleNamespace(get_operation_for_workspace=lookup),
    )

    result = await reader.get(
        workspace_id=workspace_id,
        operation_id=operation_id,
        can_write=True,
    )

    assert result is None
    lookup.assert_awaited_once_with(workspace_id, operation_id)


async def test_readonly_member_receives_no_operation_mutations() -> None:
    item = operation(OperationSource.MANUAL)
    reader = OperationsReader(cast(Any, object()))
    reader._ledger = cast(
        Any,
        SimpleNamespace(get_operation_for_workspace=AsyncMock(return_value=item)),
    )

    result = await reader.get(
        workspace_id=item.workspace_id,
        operation_id=item.id,
        can_write=False,
    )

    assert result is not None
    assert result.capabilities.model_dump() == {
        "can_edit": False,
        "edit_kind": "none",
        "can_cancel": False,
        "can_restore": False,
        "can_delete": False,
        "readonly_reason": "financial_write_forbidden",
    }


def operation(source: OperationSource) -> SimpleNamespace:
    workspace_id = uuid4()
    operation_id = uuid4()
    account = SimpleNamespace(
        id=uuid4(),
        name="Основной счёт",
        currency="RUB",
        type=AccountType.DEBT if source is OperationSource.DEBT else AccountType.CHECKING,
    )
    raw_transaction_id = uuid4()
    uploaded_document_id = uuid4()
    return SimpleNamespace(
        id=operation_id,
        version=1,
        workspace_id=workspace_id,
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        source=source,
        operation_date=date(2026, 8, 11),
        description="Аренда",
        category=None,
        property=None,
        money_entries=[
            SimpleNamespace(
                account_id=account.id,
                account=account,
                amount=Decimal("-100.00"),
                currency="RUB",
            )
        ],
        raw_transactions=(
            [
                SimpleNamespace(
                    id=raw_transaction_id,
                    uploaded_document_id=uploaded_document_id,
                )
            ]
            if source is OperationSource.BANK_PDF
            else []
        ),
    )
