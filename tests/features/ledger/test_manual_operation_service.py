from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

import app.features.ledger.application.manual_operation_service as service_module
from app.features.ledger.application.commands import CreateManualIncomeExpenseCommand
from app.features.ledger.application.manual_operation_dtos import ManualOperationReadDto
from app.features.ledger.application.manual_operation_service import ManualOperationService
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.workspaces.service import WorkspaceContext


@pytest.mark.asyncio
async def test_create_returns_reloaded_read_dto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    persisted_operation = SimpleNamespace(id=operation_id, source=OperationSource.MANUAL)
    expected = manual_operation_dto(operation_id)

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(
            self,
            requested_workspace_id: UUID,
            requested_operation_id: UUID,
        ) -> object:
            assert requested_workspace_id == workspace_id
            assert requested_operation_id == operation_id
            return persisted_operation

    class FakeUseCase:
        def __init__(self, _session: object) -> None:
            pass

        async def create_income_expense(self, **_kwargs: object) -> object:
            return persisted_operation

    monkeypatch.setattr(service_module, "LedgerRepository", FakeRepository)
    monkeypatch.setattr(service_module, "ManualOperationUseCase", FakeUseCase)
    monkeypatch.setattr(
        service_module.ManualOperationReadDtoMapper,
        "from_model",
        staticmethod(lambda _operation: expected),
    )
    service = ManualOperationService(cast(Any, object()))

    result = await service.create(
        context=cast(
            WorkspaceContext,
            SimpleNamespace(workspace=SimpleNamespace(id=workspace_id)),
        ),
        command=CreateManualIncomeExpenseCommand(
            operation_type=OperationType.INCOME,
            account_id=uuid4(),
            amount=Decimal("10.00"),
            operation_date=date(2026, 7, 21),
            description="Доход",
            category_id=None,
            property_id=None,
            idempotency_key=uuid4(),
        ),
    )

    assert result is expected


def manual_operation_dto(operation_id: UUID) -> ManualOperationReadDto:
    return ManualOperationReadDto(
        id=operation_id,
        version=1,
        operation_type=OperationType.INCOME,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 7, 21),
        description="Доход",
        money=None,
        account=None,
        source_account=None,
        destination_account=None,
        category=None,
        property=None,
    )
